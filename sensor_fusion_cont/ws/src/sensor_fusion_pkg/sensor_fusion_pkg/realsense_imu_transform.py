"""Publish RealSense IMU gyro/accel in the robot base_link frame."""

from __future__ import annotations

import os
from typing import Iterable

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu


def optical_to_base(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Map RealSense optical-frame vectors into ROS base_link axes.

    RealSense optical frame is x-right, y-down, z-forward. ROS base_link is
    x-forward, y-left, z-up, so robot yaw is -optical_y.
    """

    return z, -x, -y


def transform_covariance(covariance: Iterable[float]) -> list[float]:
    cov = list(covariance)
    if len(cov) != 9 or cov[0] < 0.0:
        return cov

    # R maps optical vectors to base_link: [x_b, y_b, z_b] = [z_o, -x_o, -y_o]
    r = (
        (0.0, 0.0, 1.0),
        (-1.0, 0.0, 0.0),
        (0.0, -1.0, 0.0),
    )
    source = [cov[0:3], cov[3:6], cov[6:9]]
    result = []
    for i in range(3):
        for j in range(3):
            value = 0.0
            for a in range(3):
                for b in range(3):
                    value += r[i][a] * source[a][b] * r[j][b]
            result.append(value)
    return result


class RealSenseImuTransform(Node):
    def __init__(self) -> None:
        super().__init__("realsense_imu_transform")
        self.input_topic = os.environ.get("SF_IMU_OUTPUT_TOPIC", "/imu/data")
        self.output_topic = os.environ.get("SF_IMU_BASE_TOPIC", "/imu/base_link")
        self.output_frame = os.environ.get("SF_IMU_BASE_FRAME", "base_link")

        self.publisher = self.create_publisher(Imu, self.output_topic, qos_profile_sensor_data)
        self.subscription = self.create_subscription(
            Imu,
            self.input_topic,
            self.imu_callback,
            qos_profile_sensor_data,
        )
        self.get_logger().info(
            f"Transforming RealSense IMU {self.input_topic} -> {self.output_topic} "
            f"({self.output_frame}; yaw_rate=-optical_y)"
        )

    def imu_callback(self, msg: Imu) -> None:
        out = Imu()
        out.header = msg.header
        out.header.frame_id = self.output_frame

        # Orientation from the optical-frame filter is intentionally not reused
        # after changing frames. EKF uses angular velocity only.
        out.orientation.w = 1.0
        out.orientation_covariance[0] = -1.0

        avx, avy, avz = optical_to_base(
            msg.angular_velocity.x,
            msg.angular_velocity.y,
            msg.angular_velocity.z,
        )
        out.angular_velocity.x = avx
        out.angular_velocity.y = avy
        out.angular_velocity.z = avz
        out.angular_velocity_covariance = transform_covariance(msg.angular_velocity_covariance)

        lax, lay, laz = optical_to_base(
            msg.linear_acceleration.x,
            msg.linear_acceleration.y,
            msg.linear_acceleration.z,
        )
        out.linear_acceleration.x = lax
        out.linear_acceleration.y = lay
        out.linear_acceleration.z = laz
        out.linear_acceleration_covariance = transform_covariance(msg.linear_acceleration_covariance)

        self.publisher.publish(out)


def main(args: list[str] | None = None) -> None:
    rclpy.init(args=args)
    node = RealSenseImuTransform()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
