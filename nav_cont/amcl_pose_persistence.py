#!/usr/bin/env python3
"""Persist the last AMCL pose and restore it on the next Nav2 boot."""

from __future__ import annotations

import json
import math
import os
import signal
import sys
import time
from pathlib import Path

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node


def yaw_from_quaternion(q) -> float:
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


class AmclPosePersistence(Node):
    def __init__(self) -> None:
        super().__init__("amcl_pose_persistence")

        self.pose_topic = self.declare_parameter("pose_topic", "/amcl_pose").get_parameter_value().string_value
        self.initialpose_topic = self.declare_parameter("initialpose_topic", "/initialpose").get_parameter_value().string_value
        self.pose_file = Path(
            self.declare_parameter("pose_file", "/srv/nav/last_amcl_pose.json").get_parameter_value().string_value
        )
        self.map_file = self.declare_parameter("map_file", "").get_parameter_value().string_value
        self.allow_map_mismatch = self.declare_parameter("allow_map_mismatch", False).get_parameter_value().bool_value
        self.restore_on_start = self.declare_parameter("restore_on_start", True).get_parameter_value().bool_value
        self.restore_delay_s = self.declare_parameter("restore_delay_s", 12.0).get_parameter_value().double_value
        self.restore_republish_count = (
            self.declare_parameter("restore_republish_count", 12).get_parameter_value().integer_value
        )
        self.restore_republish_period_s = (
            self.declare_parameter("restore_republish_period_s", 0.75).get_parameter_value().double_value
        )
        self.save_period_s = self.declare_parameter("save_period_s", 2.0).get_parameter_value().double_value
        self.max_pose_age_s = self.declare_parameter("max_pose_age_s", 7.0 * 24.0 * 3600.0).get_parameter_value().double_value

        self.last_pose: PoseWithCovarianceStamped | None = None
        self.last_saved_pose_id: tuple[float, float, float] | None = None
        self.restore_msg: PoseWithCovarianceStamped | None = None
        self.restore_remaining = 0

        self.initialpose_pub = self.create_publisher(PoseWithCovarianceStamped, self.initialpose_topic, 10)
        self.create_subscription(PoseWithCovarianceStamped, self.pose_topic, self._pose_cb, 10)
        self.create_subscription(PoseWithCovarianceStamped, self.initialpose_topic, self._initialpose_cb, 10)

        self.create_timer(max(0.5, float(self.save_period_s)), self._save_timer_cb)
        if self.restore_on_start:
            self.create_timer(max(0.0, float(self.restore_delay_s)), self._restore_start_cb)

        self.get_logger().info(
            "AMCL pose persistence started "
            f"pose_topic={self.pose_topic} initialpose_topic={self.initialpose_topic} "
            f"pose_file={self.pose_file} restore_on_start={self.restore_on_start}"
        )

    def _pose_cb(self, msg: PoseWithCovarianceStamped) -> None:
        self.last_pose = msg

    def _initialpose_cb(self, msg: PoseWithCovarianceStamped) -> None:
        if self.restore_msg is not None and self.restore_remaining > 0:
            if self._pose_id(msg) == self._pose_id(self.restore_msg):
                return

            self.restore_msg = None
            self.restore_remaining = 0
            self.get_logger().info("Manual /initialpose received; cancelling saved-pose restore")

    def _pose_id(self, msg: PoseWithCovarianceStamped) -> tuple[float, float, float]:
        pose = msg.pose.pose
        return (
            round(float(pose.position.x), 4),
            round(float(pose.position.y), 4),
            round(yaw_from_quaternion(pose.orientation), 4),
        )

    def _payload_from_msg(self, msg: PoseWithCovarianceStamped) -> dict:
        pose = msg.pose.pose
        q = pose.orientation
        return {
            "saved_unix_s": time.time(),
            "map_file": self.map_file,
            "frame_id": msg.header.frame_id or "map",
            "position": {
                "x": float(pose.position.x),
                "y": float(pose.position.y),
                "z": float(pose.position.z),
            },
            "orientation": {
                "x": float(q.x),
                "y": float(q.y),
                "z": float(q.z),
                "w": float(q.w),
            },
            "covariance": [float(v) for v in msg.pose.covariance],
        }

    def _save_timer_cb(self) -> None:
        self.save_now(reason="periodic")

    def save_now(self, *, reason: str) -> None:
        if self.last_pose is None:
            return

        pose_id = self._pose_id(self.last_pose)
        if reason == "periodic" and pose_id == self.last_saved_pose_id:
            return

        payload = self._payload_from_msg(self.last_pose)
        try:
            self.pose_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.pose_file.with_suffix(self.pose_file.suffix + ".tmp")
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            os.replace(tmp_path, self.pose_file)
            self.last_saved_pose_id = pose_id
        except OSError as exc:
            self.get_logger().warn(f"Failed to save AMCL pose to {self.pose_file}: {exc}")
            return

        if reason != "periodic":
            x = payload["position"]["x"]
            y = payload["position"]["y"]
            yaw = yaw_from_quaternion(self.last_pose.pose.pose.orientation)
            self.get_logger().info(f"Saved AMCL pose on {reason}: x={x:.3f} y={y:.3f} yaw={yaw:.3f}")

    def _load_saved_pose(self) -> PoseWithCovarianceStamped | None:
        try:
            payload = json.loads(self.pose_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.get_logger().info(f"No saved AMCL pose found at {self.pose_file}")
            return None
        except (OSError, json.JSONDecodeError) as exc:
            self.get_logger().warn(f"Could not read saved AMCL pose from {self.pose_file}: {exc}")
            return None

        saved_map_file = str(payload.get("map_file") or "")
        if (
            self.map_file
            and saved_map_file
            and saved_map_file != self.map_file
            and not self.allow_map_mismatch
        ):
            self.get_logger().warn(
                "Saved AMCL pose belongs to a different map; skipping restore "
                f"saved_map={saved_map_file} current_map={self.map_file}"
            )
            return None

        saved_unix_s = float(payload.get("saved_unix_s") or 0.0)
        age_s = time.time() - saved_unix_s if saved_unix_s > 0.0 else 0.0
        if self.max_pose_age_s > 0.0 and age_s > self.max_pose_age_s:
            self.get_logger().warn(
                f"Saved AMCL pose is too old ({age_s:.0f}s > {self.max_pose_age_s:.0f}s); skipping restore"
            )
            return None

        try:
            position = payload["position"]
            orientation = payload["orientation"]
            covariance = payload.get("covariance") or []
            msg = PoseWithCovarianceStamped()
            msg.header.frame_id = str(payload.get("frame_id") or "map")
            msg.pose.pose.position.x = float(position["x"])
            msg.pose.pose.position.y = float(position["y"])
            msg.pose.pose.position.z = float(position.get("z", 0.0))
            msg.pose.pose.orientation.x = float(orientation.get("x", 0.0))
            msg.pose.pose.orientation.y = float(orientation.get("y", 0.0))
            msg.pose.pose.orientation.z = float(orientation["z"])
            msg.pose.pose.orientation.w = float(orientation["w"])
            if len(covariance) == 36:
                msg.pose.covariance = [float(v) for v in covariance]
            else:
                msg.pose.covariance[0] = 0.05
                msg.pose.covariance[7] = 0.05
                msg.pose.covariance[35] = 0.20
        except (KeyError, TypeError, ValueError) as exc:
            self.get_logger().warn(f"Saved AMCL pose has invalid format: {exc}")
            return None

        return msg

    def _restore_start_cb(self) -> None:
        if self.restore_remaining != 0 or self.restore_msg is not None:
            return

        msg = self._load_saved_pose()
        if msg is None:
            self.restore_msg = None
            self.restore_remaining = -1
            return

        self.restore_msg = msg
        self.restore_remaining = max(1, int(self.restore_republish_count))
        self.create_timer(max(0.1, float(self.restore_republish_period_s)), self._restore_publish_cb)
        self._restore_publish_cb()

    def _restore_publish_cb(self) -> None:
        if self.restore_msg is None or self.restore_remaining <= 0:
            return

        self.restore_msg.header.stamp = self.get_clock().now().to_msg()
        self.initialpose_pub.publish(self.restore_msg)
        self.restore_remaining -= 1

        pose = self.restore_msg.pose.pose
        yaw = yaw_from_quaternion(pose.orientation)
        self.get_logger().info(
            "Published saved initial pose "
            f"x={pose.position.x:.3f} y={pose.position.y:.3f} yaw={yaw:.3f} "
            f"remaining={self.restore_remaining}"
        )


def main() -> int:
    rclpy.init()
    node = AmclPosePersistence()

    def _shutdown_handler(signum, _frame):
        node.save_now(reason=f"signal_{signum}")
        rclpy.shutdown()

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    try:
        rclpy.spin(node)
    finally:
        node.save_now(reason="shutdown")
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
