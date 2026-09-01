#!/usr/bin/env python3
"""Interactive ROS 2 drivetrain characterization executed inside nav_cont."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from std_srvs.srv import SetBool

from drive_calibration_core import (
    Pose2D,
    Result,
    Trial,
    calculate_result,
    repeated_trials,
    summarize,
    write_reports,
    yaw_from_quaternion,
)


class CalibrationError(RuntimeError):
    pass


class DriveCalibrationNode(Node):
    def __init__(
        self,
        command_topic: str,
        odom_topic: str,
        manual_speed_scale: float,
        manual_angular_scale: float,
    ):
        super().__init__("drive_calibration")
        self.latest_pose: Pose2D | None = None
        self.latest_pose_received_at = 0.0
        self.motor_pwm_samples: list[tuple[float, float]] = []
        self.collect_motor_pwm = False
        self.manual_speed_scale = manual_speed_scale
        self.manual_angular_scale = manual_angular_scale
        self.command_pub = self.create_publisher(Twist, command_topic, 10)
        self.create_subscription(Odometry, odom_topic, self._odom_cb, 10)
        self.create_subscription(Float32MultiArray, "/motor_pwm", self._motor_pwm_cb, 20)
        self.manual_client = self.create_client(SetBool, "/set_manual_mode")

    def _motor_pwm_cb(self, msg: Float32MultiArray) -> None:
        if self.collect_motor_pwm and len(msg.data) >= 2:
            self.motor_pwm_samples.append((float(msg.data[0]), float(msg.data[1])))

    def _odom_cb(self, msg: Odometry) -> None:
        pose = msg.pose.pose
        q = pose.orientation
        self.latest_pose = Pose2D(
            x=float(pose.position.x),
            y=float(pose.position.y),
            yaw=yaw_from_quaternion(float(q.x), float(q.y), float(q.z), float(q.w)),
        )
        self.latest_pose_received_at = time.monotonic()

    def wait_for_fresh_pose(self, timeout_s: float = 8.0) -> Pose2D:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.latest_pose is not None and time.monotonic() - self.latest_pose_received_at <= 0.5:
                return self.latest_pose
        raise CalibrationError("No fresh odometry received within timeout")

    def set_manual_mode(self, enabled: bool, timeout_s: float = 8.0) -> None:
        if not self.manual_client.wait_for_service(timeout_sec=timeout_s):
            raise CalibrationError("/set_manual_mode service is unavailable")
        request = SetBool.Request()
        request.data = enabled
        future = self.manual_client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout_s)
        if not future.done() or future.result() is None or not future.result().success:
            raise CalibrationError(f"Could not set manual mode to {enabled}")

    def publish_for(self, linear_x: float, angular_z: float, duration_s: float) -> None:
        msg = Twist()
        # cmd_vel_mux scales joystick input. Compensate here so trial values
        # describe the command after the mux and can be compared with Nav2.
        msg.linear.x = float(linear_x) / self.manual_speed_scale
        msg.angular.z = float(angular_z) / self.manual_angular_scale
        deadline = time.monotonic() + duration_s
        self.motor_pwm_samples = []
        self.collect_motor_pwm = True
        try:
            while time.monotonic() < deadline:
                self.command_pub.publish(msg)
                rclpy.spin_once(self, timeout_sec=0.05)
        finally:
            self.collect_motor_pwm = False
            self.stop()

    def stop(self, duration_s: float = 0.6) -> None:
        stop = Twist()
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            self.command_pub.publish(stop)
            rclpy.spin_once(self, timeout_sec=0.05)

    def settle(self, duration_s: float) -> None:
        deadline = time.monotonic() + duration_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Characterize drivetrain response through the normal ROS safety chain."
    )
    parser.add_argument("--surface", required=True, choices=("laminate", "carpet", "safe-demo"))
    parser.add_argument("--odom-topic", default="/odometry/filtered")
    parser.add_argument("--command-topic", default="/cmd_vel_joy")
    parser.add_argument(
        "--manual-speed-scale",
        type=float,
        default=float(os.environ.get("MANUAL_SPEED_SCALE", "1.0")),
    )
    parser.add_argument(
        "--manual-angular-scale",
        type=float,
        default=float(os.environ.get("MANUAL_ANGULAR_SCALE", "1.0")),
    )
    parser.add_argument("--duration", type=float, default=2.5)
    parser.add_argument("--settle", type=float, default=1.0)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--include-reverse", action="store_true")
    parser.add_argument("--continuous", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("/srv/calibration_results"))
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 1.0 <= args.duration <= 5.0:
        raise CalibrationError("--duration must be between 1.0 and 5.0 seconds")
    if not 0.3 <= args.settle <= 5.0:
        raise CalibrationError("--settle must be between 0.3 and 5.0 seconds")
    if not 1 <= args.repeats <= 10:
        raise CalibrationError("--repeats must be between 1 and 10")
    if not 0.01 <= args.manual_speed_scale <= 1.0:
        raise CalibrationError("--manual-speed-scale must be between 0.01 and 1.0")
    if not 0.01 <= args.manual_angular_scale <= 10.0:
        raise CalibrationError("--manual-angular-scale must be between 0.01 and 10.0")


def print_result(result: Result) -> None:
    print(
        f"  measured: forward={result.forward_m:+.3f} m, "
        f"lateral={result.lateral_m:+.3f} m, yaw={result.yaw_deg:+.1f} deg, "
        f"v={result.measured_linear_mps:+.3f} m/s, "
        f"w={result.measured_angular_rps:+.3f} rad/s",
        flush=True,
    )


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except CalibrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("DRIVE CALIBRATION SAFETY CHECK")
    print("- Put the robot on the selected surface with at least 1 m clear space.")
    print("- Keep a hand on the physical motor power switch / emergency stop.")
    print("- Keep people, cables and table edges outside the test area.")
    print("- The script pauses before every movement unless --continuous is used.")
    if not args.yes and input("Type CALIBRATE to continue: ").strip() != "CALIBRATE":
        print("Calibration cancelled.")
        return 1

    rclpy.init()
    node = DriveCalibrationNode(
        args.command_topic,
        args.odom_topic,
        args.manual_speed_scale,
        args.manual_angular_scale,
    )
    results: list[Result] = []
    manual_enabled = False
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        initial = node.wait_for_fresh_pose()
        print(
            f"Pose source ready: x={initial.x:.3f}, y={initial.y:.3f}, "
            f"yaw={math.degrees(initial.yaw):.1f} deg"
        )
        node.set_manual_mode(True)
        manual_enabled = True
        print(
            "Manual mode enabled; Nav2 commands are ignored. "
            f"Mux compensation: linear={args.manual_speed_scale:.3f}, "
            f"angular={args.manual_angular_scale:.3f}."
        )
        trials = repeated_trials(args.duration, args.include_reverse, args.repeats)
        for index, trial in enumerate(trials, start=1):
            print(
                f"\n[{index}/{len(trials)}] {trial.name}: "
                f"linear={trial.linear_x:+.3f} m/s angular={trial.angular_z:+.3f} rad/s "
                f"for {trial.duration_s:.1f} s"
            )
            if not args.continuous:
                answer = input("Clear and position robot; Enter=start, q=quit: ").strip().lower()
                if answer == "q":
                    break
            start = node.wait_for_fresh_pose()
            node.publish_for(trial.linear_x, trial.angular_z, trial.duration_s)
            node.settle(args.settle)
            end = node.wait_for_fresh_pose()
            result = calculate_result(
                args.surface,
                trial,
                start,
                end,
                motor_pwm_samples=list(node.motor_pwm_samples),
            )
            results.append(result)
            print_result(result)
    except (CalibrationError, KeyboardInterrupt, EOFError) as exc:
        print(f"\nCalibration interrupted: {exc}", file=sys.stderr)
    finally:
        try:
            node.stop()
            if manual_enabled:
                node.set_manual_mode(False)
            print("Robot stopped and automatic mode restored.")
        except Exception as exc:  # noqa: BLE001 - emergency cleanup must continue
            print(
                f"CRITICAL: cleanup failed: {exc}\n"
                "Turn off motor power and restore /set_manual_mode manually.",
                file=sys.stderr,
            )
        node.destroy_node()
        rclpy.shutdown()

    if not results:
        print("No completed trials; no report written.", file=sys.stderr)
        return 1
    metadata = {
        "surface": args.surface,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "odom_topic": args.odom_topic,
        "command_topic": args.command_topic,
        "manual_speed_scale": args.manual_speed_scale,
        "manual_angular_scale": args.manual_angular_scale,
        "note": "Whole-robot RF2O/IMU response; no independent wheel encoders.",
    }
    csv_path, json_path = write_reports(args.output_dir, args.surface, results, metadata)
    print(f"\nCSV report:  {csv_path}")
    print(f"JSON report: {json_path}")
    print(json.dumps(summarize(results), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
