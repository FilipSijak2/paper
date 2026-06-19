#!/usr/bin/env python3
"""Publish the robot pose in the map frame as a lightweight PoseStamped topic."""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformException, TransformListener


class RobotPoseMapPublisher(Node):
    def __init__(self) -> None:
        super().__init__("robot_pose_map_publisher")
        self.map_frame = self.declare_parameter("map_frame", "map").get_parameter_value().string_value
        self.base_frame = self.declare_parameter("base_frame", "base_link").get_parameter_value().string_value
        self.pose_topic = self.declare_parameter("pose_topic", "/robot_pose_map").get_parameter_value().string_value
        self.publish_rate_hz = (
            self.declare_parameter("publish_rate_hz", 1.0).get_parameter_value().double_value
        )
        self.lookup_timeout_s = (
            self.declare_parameter("lookup_timeout_s", 0.2).get_parameter_value().double_value
        )

        self.tf_buffer = Buffer(cache_time=Duration(seconds=10.0))
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.publisher = self.create_publisher(PoseStamped, self.pose_topic, 10)
        timer_period = 1.0 / max(0.1, self.publish_rate_hz)
        self.timer = self.create_timer(timer_period, self.publish_pose)
        self._warned_once = False

        self.get_logger().info(
            f"Publishing {self.map_frame} -> {self.base_frame} pose "
            f"on {self.pose_topic} at {self.publish_rate_hz:.2f} Hz"
        )

    def publish_pose(self) -> None:
        try:
            transform = self.tf_buffer.lookup_transform(
                self.map_frame,
                self.base_frame,
                Time(),
                timeout=Duration(seconds=max(0.01, self.lookup_timeout_s)),
            )
        except TransformException as exc:
            if not self._warned_once:
                self._warned_once = True
                self.get_logger().warn(
                    f"Waiting for TF {self.map_frame} -> {self.base_frame}: {exc}"
                )
            return

        msg = PoseStamped()
        msg.header = transform.header
        msg.pose.position.x = transform.transform.translation.x
        msg.pose.position.y = transform.transform.translation.y
        msg.pose.position.z = transform.transform.translation.z
        msg.pose.orientation = transform.transform.rotation
        self.publisher.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RobotPoseMapPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
