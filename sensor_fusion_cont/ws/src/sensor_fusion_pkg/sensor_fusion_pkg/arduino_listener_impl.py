#!/usr/bin/env python3
"""Relay Arduino/Nano IMU messages from the bridge into sensor_fusion topics."""

import time
import yaml

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String


class ArduinoImuNode(Node):
    def __init__(self):
        super().__init__('arduino_imu_listener')

        cfg_path = self._config_path()
        self.get_logger().info(f'Loading config: {cfg_path}')
        self.cfg = self._load_config(cfg_path)

        source_cfg = self.cfg.get('source', {})
        imu_cfg = self.cfg.get('imu', {})

        self.source_topic = source_cfg.get('topic', '/imu/arduino')
        self.frame_id = imu_cfg.get('frame_id', 'imu_link')
        self.rate = float(imu_cfg.get('publish_rate_hz', 30.0))
        self.orientation_cov = imu_cfg.get('covariance_orientation', [-1.0] * 9)
        self.angular_cov = imu_cfg.get('covariance_angular_velocity', [-1.0] * 9)
        self.linear_cov = imu_cfg.get('covariance_linear_acceleration', [-1.0] * 9)

        self.imu_pub = self.create_publisher(Imu, 'imu/data_raw', 10)
        self.raw_line_pub = self.create_publisher(String, 'imu/raw_line', 10)
        self.diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)
        self.imu_sub = self.create_subscription(Imu, self.source_topic, self.imu_callback, 10)

        self.last_msg_time = 0.0
        self.last_summary = ''
        self.source_ok = False

        self.create_timer(1.0, self.publish_diag)
        self.get_logger().info(f'Relaying IMU from {self.source_topic} to imu/data_raw')

    def _config_path(self) -> str:
        return self.declare_parameter(
            'config_file',
            self._env('SF_CONFIG', '/app/sensor_fusion.yaml'),
        ).value

    def _env(self, key: str, default: str) -> str:
        import os

        return os.getenv(key, default)

    def _load_config(self, cfg_path: str):
        try:
            with open(cfg_path, 'r', encoding='utf-8') as fh:
                return yaml.safe_load(fh) or {}
        except Exception as exc:
            self.get_logger().warn(f'Could not load config {cfg_path}: {exc}; using defaults')
            return {}

    def imu_callback(self, msg: Imu) -> None:
        relay = Imu()
        relay.header = msg.header
        relay.header.frame_id = self.frame_id or msg.header.frame_id
        relay.orientation = msg.orientation
        relay.angular_velocity = msg.angular_velocity
        relay.linear_acceleration = msg.linear_acceleration
        relay.orientation_covariance = list(self.orientation_cov)
        relay.angular_velocity_covariance = list(self.angular_cov)
        relay.linear_acceleration_covariance = list(self.linear_cov)

        self.imu_pub.publish(relay)
        self.last_msg_time = time.time()
        self.source_ok = True

        self.last_summary = (
            f"IMU,{relay.orientation.w:.4f},{relay.orientation.x:.4f},"
            f"{relay.orientation.y:.4f},{relay.orientation.z:.4f},"
            f"{relay.linear_acceleration.x:.4f},{relay.linear_acceleration.y:.4f},"
            f"{relay.linear_acceleration.z:.4f},{relay.angular_velocity.x:.4f},"
            f"{relay.angular_velocity.y:.4f},{relay.angular_velocity.z:.4f}"
        )
        self.raw_line_pub.publish(String(data=self.last_summary))

    def publish_diag(self) -> None:
        now = time.time()
        timeout = 5.0 if self.rate <= 0 else 3.0 / max(1.0, self.rate)
        ok = self.last_msg_time > 0 and (now - self.last_msg_time) < timeout

        da = DiagnosticArray()
        da.header.stamp = self.get_clock().now().to_msg()

        st = DiagnosticStatus()
        st.name = 'arduino_imu_listener'
        st.level = DiagnosticStatus.OK if ok else DiagnosticStatus.WARN
        st.message = 'OK' if ok else 'No recent IMU messages from bridge'
        st.values = [
            KeyValue(key='source_topic', value=self.source_topic),
            KeyValue(key='source_ok', value=str(self.source_ok)),
            KeyValue(key='last_summary', value=self.last_summary[:120]),
        ]
        da.status.append(st)
        self.diag_pub.publish(da)


def main():
    rclpy.init()
    node = ArduinoImuNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

