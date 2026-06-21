"""Bias-correct base_link IMU yaw rate before feeding robot_localization."""

from __future__ import annotations

from copy import deepcopy
from statistics import fmean

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu


class ImuYawRateCorrector(Node):
    def __init__(self) -> None:
        super().__init__("imu_yaw_rate_corrector")

        self.input_topic = self.declare_parameter("input_topic", "/imu/base_link").value
        self.output_topic = self.declare_parameter("output_topic", "/imu/base_link_corrected").value
        self.cmd_vel_topic = self.declare_parameter("cmd_vel_topic", "/cmd_vel_collision_in").value

        self.min_calibration_samples = int(
            self.declare_parameter("min_calibration_samples", 150).value
        )
        self.startup_timeout_s = float(
            self.declare_parameter("startup_timeout_s", 5.0).value
        )
        self.cmd_timeout_s = float(self.declare_parameter("cmd_timeout_s", 0.75).value)
        self.cmd_linear_threshold = float(
            self.declare_parameter("cmd_linear_threshold", 0.015).value
        )
        self.cmd_angular_threshold = float(
            self.declare_parameter("cmd_angular_threshold", 0.03).value
        )
        self.stationary_gyro_threshold = float(
            self.declare_parameter("stationary_gyro_threshold", 0.08).value
        )
        self.zero_clamp_threshold = float(
            self.declare_parameter("zero_clamp_threshold", 0.018).value
        )
        self.bias_alpha = float(self.declare_parameter("bias_alpha", 0.002).value)
        self.bias_limit = float(self.declare_parameter("bias_limit", 0.15).value)
        self.yaw_rate_variance = float(
            self.declare_parameter("yaw_rate_variance", 0.02).value
        )
        self.publish_uncalibrated = bool(
            self.declare_parameter("publish_uncalibrated", False).value
        )

        self.start_time = self._now_s()
        self.bias_z = 0.0
        self.calibration_samples: list[float] = []
        self.calibrated = self.min_calibration_samples <= 0
        self.last_cmd_time: float | None = None
        self.last_cmd_linear = 0.0
        self.last_cmd_angular = 0.0

        self.publisher = self.create_publisher(Imu, self.output_topic, qos_profile_sensor_data)
        self.imu_subscription = self.create_subscription(
            Imu,
            self.input_topic,
            self.imu_callback,
            qos_profile_sensor_data,
        )
        self.cmd_subscription = self.create_subscription(
            Twist,
            self.cmd_vel_topic,
            self.cmd_callback,
            10,
        )

        self.get_logger().info(
            "Correcting IMU yaw rate "
            f"{self.input_topic} -> {self.output_topic}; cmd={self.cmd_vel_topic}, "
            f"min_samples={self.min_calibration_samples}, variance={self.yaw_rate_variance}"
        )

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def cmd_callback(self, msg: Twist) -> None:
        self.last_cmd_linear = max(abs(msg.linear.x), abs(msg.linear.y))
        self.last_cmd_angular = abs(msg.angular.z)
        self.last_cmd_time = self._now_s()

    def _cmd_is_stationary(self, now_s: float) -> bool:
        if self.last_cmd_time is None:
            return not self.calibrated and (now_s - self.start_time) <= self.startup_timeout_s
        if (now_s - self.last_cmd_time) > self.cmd_timeout_s:
            return False
        return (
            self.last_cmd_linear <= self.cmd_linear_threshold
            and self.last_cmd_angular <= self.cmd_angular_threshold
        )

    def _stationary_calibration_candidate(self, raw_z: float, now_s: float) -> bool:
        return self._cmd_is_stationary(now_s) and abs(raw_z) <= self.stationary_gyro_threshold

    def _finish_calibration(self) -> None:
        if self.calibration_samples:
            self.bias_z = max(
                -self.bias_limit,
                min(self.bias_limit, fmean(self.calibration_samples)),
            )
        self.calibrated = True
        self.get_logger().info(
            f"IMU yaw-rate bias calibrated: bias_z={self.bias_z:.5f} rad/s "
            f"from {len(self.calibration_samples)} samples"
        )

    def _update_running_bias(self, raw_z: float) -> None:
        if self.bias_alpha <= 0.0 or abs(raw_z) > self.bias_limit:
            return
        self.bias_z = (1.0 - self.bias_alpha) * self.bias_z + self.bias_alpha * raw_z
        self.bias_z = max(-self.bias_limit, min(self.bias_limit, self.bias_z))

    def imu_callback(self, msg: Imu) -> None:
        now_s = self._now_s()
        raw_z = float(msg.angular_velocity.z)
        stationary_candidate = self._stationary_calibration_candidate(raw_z, now_s)

        if not self.calibrated:
            if stationary_candidate:
                self.calibration_samples.append(raw_z)
                if len(self.calibration_samples) >= self.min_calibration_samples:
                    self._finish_calibration()
            elif (now_s - self.start_time) >= self.startup_timeout_s:
                self.get_logger().warning(
                    "IMU yaw-rate startup calibration timed out; using collected "
                    f"{len(self.calibration_samples)} samples"
                )
                self._finish_calibration()

            if not self.calibrated and not self.publish_uncalibrated:
                return

        if self.calibrated and stationary_candidate:
            self._update_running_bias(raw_z)

        corrected_z = raw_z - self.bias_z
        if self._cmd_is_stationary(now_s) and abs(corrected_z) <= self.zero_clamp_threshold:
            corrected_z = 0.0

        out = deepcopy(msg)
        out.angular_velocity.z = corrected_z

        covariance = list(out.angular_velocity_covariance)
        if len(covariance) != 9:
            covariance = [0.0] * 9
        if covariance[8] <= 0.0 or covariance[8] < self.yaw_rate_variance:
            covariance[8] = self.yaw_rate_variance
        out.angular_velocity_covariance = covariance

        self.publisher.publish(out)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = ImuYawRateCorrector()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
