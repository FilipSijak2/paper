#!/usr/bin/env python3
"""
ROS 2 serial bridge for the Devastator robot.

Architecture:
    ROS 2 topics <-> this bridge <-> custom protocol <-> Nano ESP32

Published topics:
    /imu/arduino (sensor_msgs/Imu, configurable via IMU_TOPIC)
    /wheel_odom (nav_msgs/Odometry)
    /robot_status (std_msgs/String)

Subscribed topics:
    /cmd_vel (geometry_msgs/Twist)

Usage:
    python3 robot_serial_bridge.py --port /dev/ttyUSB0 --baud 115200
"""

import argparse
import math
import os
import struct
import threading
import time

import rclpy
import serial
from geometry_msgs.msg import Point, Quaternion, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String

# Protocol constants (must match Arduino firmware)
PROTOCOL_VERSION = 1

SENSOR_PACKET_HEADER = 0xDEADBEEF
SENSOR_PACKET_TAIL = 0xCAFEBABE
SENSOR_PACKET_FORMAT = "<LBBHLfffffffffffHBBHL"
SENSOR_PACKET_SIZE = struct.calcsize(SENSOR_PACKET_FORMAT)

COMMAND_PACKET_HEADER = 0xFEEDFACE
COMMAND_PACKET_TAIL = 0xDEADC0DE
COMMAND_PACKET_FORMAT = "<LBBHffHL"
COMMAND_PACKET_SIZE = struct.calcsize(COMMAND_PACKET_FORMAT)

STATUS_PACKET_HEADER = 0xABCDEF01
STATUS_PACKET_TAIL = 0x12345678
STATUS_PACKET_FORMAT = "<LBBHLLHH12sHL"
STATUS_PACKET_SIZE = struct.calcsize(STATUS_PACKET_FORMAT)
PACKET_HEADER_SIZE = struct.calcsize("<L")


def _default_stats():
    return {
        "packets_received": 0,
        "status_packets_received": 0,
        "packets_sent": 0,
        "crc_errors": 0,
        "sync_errors": 0,
        "serial_errors": 0,
    }


def _env_int(name, default, minimum=None):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _env_float(name, default, minimum=None):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def resolve_runtime_config(args):
    """Resolve runtime configuration from CLI arguments and environment."""
    port = args.port or os.environ.get("SERIAL_PORT", "/dev/ttyUSB0")
    baud = args.baud if args.baud is not None else _env_int("SERIAL_BAUD", 115200, minimum=1)

    return {
        "port": port,
        "baud": baud,
        "imu_topic": os.environ.get("IMU_TOPIC", "/imu/arduino"),
        "command_timeout_ms": _env_int("COMMAND_TIMEOUT_MS", 1200, minimum=1),
        "watchdog_timeout_s": _env_float("WATCHDOG_TIMEOUT_S", 3.0, minimum=0.1),
        "status_period_s": _env_float("STATUS_PERIOD_S", 5.0, minimum=0.1),
        "serial_retry_delay_s": _env_float("SERIAL_RETRY_DELAY_S", 1.0, minimum=0.1),
    }


def crc16_ccitt(data, crc=0xFFFF):
    """CRC-16/CCITT implementation matching Arduino."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def euler_to_quaternion(yaw, pitch=0.0, roll=0.0):
    """Convert Euler angles to quaternion."""
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


class RobotSerialBridge(Node):
    def __init__(
        self,
        port="/dev/ttyUSB0",
        baud=115200,
        imu_topic="/imu/arduino",
        command_timeout_ms=1200,
        watchdog_timeout_s=3.0,
        status_period_s=5.0,
        serial_retry_delay_s=1.0,
    ):
        super().__init__("robot_serial_bridge")

        self.port = port
        self.baud = baud
        self.imu_topic = imu_topic
        self.command_timeout_ms = command_timeout_ms
        self.watchdog_timeout_s = watchdog_timeout_s
        self.status_period_s = status_period_s
        self.serial_retry_delay_s = serial_retry_delay_s

        self.serial_port = None
        self.last_command_time = time.time()
        self.last_packet_time = time.time()
        self.command_sequence = 0
        self.packet_buffer = bytearray()
        self.stats = _default_stats()
        self.last_mcu_status = None
        self.running = True

        self.get_logger().info(
            "Starting Robot Serial Bridge on "
            f"{self.port}@{self.baud} "
            f"(IMU topic: {self.imu_topic}, command_timeout_ms: {self.command_timeout_ms})"
        )

        self.connect_serial()

        self.imu_pub = self.create_publisher(Imu, self.imu_topic, 10)
        self.odom_pub = self.create_publisher(Odometry, 'wheel_odom', 10)
        self.status_pub = self.create_publisher(String, 'robot_status', 10)
        self.cmd_sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_vel_callback, 10)

        self.serial_thread = threading.Thread(target=self.serial_loop, daemon=True)
        self.serial_thread.start()

        self.watchdog_timer = self.create_timer(1.0, self.watchdog_callback)
        self.status_timer = self.create_timer(self.status_period_s, self.status_callback)

        self.get_logger().info("Robot Serial Bridge initialized.")

    def _bump_stat(self, key):
        if not hasattr(self, "stats") or not isinstance(self.stats, dict):
            self.stats = _default_stats()
        self.stats[key] = self.stats.get(key, 0) + 1

    def connect_serial(self):
        """Connect to the serial port with retry-friendly behavior."""
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()

            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=0.1,
            )
            self.get_logger().info(f"Serial connected: {self.port}@{self.baud}")
            return True

        except Exception as exc:
            self.get_logger().error(f"Serial connection failed: {exc}")
            self._bump_stat("serial_errors")
            return False

    def cmd_vel_callback(self, msg):
        """Handle incoming cmd_vel commands."""
        try:
            command_timeout_ms = getattr(self, "command_timeout_ms", 1200)
            packet = struct.pack(
                COMMAND_PACKET_FORMAT,
                COMMAND_PACKET_HEADER,
                PROTOCOL_VERSION,
                self.command_sequence & 0xFF,
                command_timeout_ms,
                msg.linear.x,
                msg.angular.z,
                0,
                COMMAND_PACKET_TAIL,
            )

            crc = crc16_ccitt(packet[:-6])
            packet = packet[:-6] + struct.pack("<H", crc) + packet[-4:]

            if self.serial_port and self.serial_port.is_open:
                self.serial_port.write(packet)
                self._bump_stat("packets_sent")
                self.command_sequence += 1
                self.last_command_time = time.time()

        except Exception as exc:
            self.get_logger().error(f"Failed to send command: {exc}")
            self._bump_stat("serial_errors")

    def serial_loop(self):
        """Background thread for reading serial data."""
        retry_delay_s = getattr(self, "serial_retry_delay_s", 1.0)
        while self.running:
            try:
                if not self.serial_port or not self.serial_port.is_open:
                    if not self.connect_serial():
                        time.sleep(retry_delay_s)
                        continue

                data = self.serial_port.read(1024)
                if data:
                    self.packet_buffer.extend(data)
                    self.process_packets()

            except Exception as exc:
                self.get_logger().error(f"Serial read error: {exc}")
                self._bump_stat("serial_errors")
                time.sleep(0.1)

    def process_packets(self):
        """Process a mixed stream of sensor and status packets."""
        while len(self.packet_buffer) >= PACKET_HEADER_SIZE:
            header_pos, packet_kind = self.find_next_packet_header()

            if header_pos == -1:
                if len(self.packet_buffer) > PACKET_HEADER_SIZE - 1:
                    self.packet_buffer = self.packet_buffer[-(PACKET_HEADER_SIZE - 1):]
                break

            if header_pos > 0:
                self.packet_buffer = self.packet_buffer[header_pos:]
                self._bump_stat("sync_errors")

            packet_size = SENSOR_PACKET_SIZE if packet_kind == "sensor" else STATUS_PACKET_SIZE
            if len(self.packet_buffer) < packet_size:
                break

            packet_data = bytes(self.packet_buffer[:packet_size])
            if packet_kind == "sensor":
                parsed_ok = self.parse_sensor_packet(packet_data)
            else:
                parsed_ok = self.parse_status_packet(packet_data)

            if parsed_ok:
                self.packet_buffer = self.packet_buffer[packet_size:]
                if packet_kind == "sensor":
                    self._bump_stat("packets_received")
                    self.last_packet_time = time.time()
                else:
                    self._bump_stat("status_packets_received")
            else:
                self._bump_stat("crc_errors")
                self.packet_buffer = self.packet_buffer[1:]

    def find_next_packet_header(self):
        """Find the earliest known packet header in the receive buffer."""
        matches = []
        for header, packet_kind in (
            (SENSOR_PACKET_HEADER, "sensor"),
            (STATUS_PACKET_HEADER, "status"),
        ):
            position = self.find_packet_header(header)
            if position != -1:
                matches.append((position, packet_kind))

        if not matches:
            return -1, None

        return min(matches, key=lambda item: item[0])

    def find_packet_header(self, header):
        """Find a packet header in the receive buffer."""
        header_bytes = struct.pack("<L", header)
        return self.packet_buffer.find(header_bytes)

    def parse_sensor_packet(self, data):
        """Parse a sensor packet and publish ROS messages."""
        try:
            # Format:
            # header(L) version(B) sequence(B) flags(H) timestamp_ms(L)
            # accel x/y/z (fff) gyro x/y/z (fff) encoders x2 (ff) odom x/y/yaw (fff)
            # battery_mv(H) temperature(B) error_flags(B) crc16(H) tail(L)
            unpacked = struct.unpack(SENSOR_PACKET_FORMAT, data)

            (
                header,
                version,
                sequence,
                flags,
                timestamp_ms,
                accel_x,
                accel_y,
                accel_z,
                gyro_x,
                gyro_y,
                gyro_z,
                left_angle,
                right_angle,
                odom_x,
                odom_y,
                odom_yaw,
                battery_mv,
                temperature,
                error_flags,
                crc16,
                tail,
            ) = unpacked

            if header != SENSOR_PACKET_HEADER or tail != SENSOR_PACKET_TAIL:
                return False
            if version != PROTOCOL_VERSION:
                return False

            expected_crc = crc16_ccitt(data[:-6])
            if crc16 != expected_crc:
                return False

            now = self.get_clock().now()
            self.publish_imu(now, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
            self.publish_odometry(now, odom_x, odom_y, odom_yaw, left_angle, right_angle)
            return True

        except Exception as exc:
            self.get_logger().error(f"Packet parsing error: {exc}")
            return False

    def parse_status_packet(self, data):
        """Parse an MCU status packet and cache it for /robot_status publishing."""
        try:
            (
                header,
                version,
                sequence,
                flags,
                uptime_ms,
                loop_count,
                loop_rate_hz,
                free_heap_kb,
                status_msg_raw,
                crc16,
                tail,
            ) = struct.unpack(STATUS_PACKET_FORMAT, data)

            if header != STATUS_PACKET_HEADER or tail != STATUS_PACKET_TAIL:
                return False
            if version != PROTOCOL_VERSION:
                return False

            expected_crc = crc16_ccitt(data[:-6])
            if crc16 != expected_crc:
                return False

            status_msg = status_msg_raw.split(b"\0", 1)[0].decode("ascii", errors="ignore") or "unknown"
            self.last_mcu_status = {
                "sequence": sequence,
                "flags": flags,
                "uptime_ms": uptime_ms,
                "loop_count": loop_count,
                "loop_rate_hz": loop_rate_hz,
                "free_heap_kb": free_heap_kb,
                "status_msg": status_msg,
            }
            return True

        except Exception as exc:
            self.get_logger().error(f"Status packet parsing error: {exc}")
            return False

    def publish_imu(self, timestamp, ax, ay, az, gx, gy, gz):
        """Publish an IMU message."""
        msg = Imu()
        msg.header.stamp = timestamp.to_msg()
        msg.header.frame_id = "imu_link"

        msg.linear_acceleration.x = ax
        msg.linear_acceleration.y = ay
        msg.linear_acceleration.z = az

        msg.angular_velocity.x = gx
        msg.angular_velocity.y = gy
        msg.angular_velocity.z = gz

        msg.linear_acceleration_covariance[0] = -1.0
        msg.angular_velocity_covariance[0] = -1.0
        msg.orientation_covariance[0] = -1.0

        self.imu_pub.publish(msg)

    def publish_odometry(self, timestamp, x, y, yaw, left_angle, right_angle):
        """Publish an odometry message."""
        msg = Odometry()
        msg.header.stamp = timestamp.to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"

        msg.pose.pose.position = Point(x=x, y=y, z=0.0)
        msg.pose.pose.orientation = euler_to_quaternion(yaw)

        # Velocity is kept simple here; encoder delta-based velocity can be added later.
        msg.twist.twist.linear.x = 0.0
        msg.twist.twist.angular.z = 0.0

        msg.pose.covariance[0] = 0.1
        msg.pose.covariance[7] = 0.1
        msg.pose.covariance[35] = 0.1
        msg.twist.covariance[0] = 0.1
        msg.twist.covariance[35] = 0.1

        self.odom_pub.publish(msg)

    def watchdog_callback(self):
        """Monitor connection health."""
        watchdog_timeout_s = getattr(self, "watchdog_timeout_s", 3.0)
        now = time.time()
        if now - self.last_packet_time > watchdog_timeout_s:
            self.get_logger().warn(
                f"No packets received for {watchdog_timeout_s:.1f} seconds - checking connection"
            )
            if self.serial_port and not self.serial_port.is_open:
                self.connect_serial()

    def status_callback(self):
        """Publish periodic bridge status."""
        msg = String()
        msg.data = (
            f"Serial Bridge: RX={self.stats['packets_received']} "
            f"STATUS_RX={self.stats.get('status_packets_received', 0)} "
            f"TX={self.stats['packets_sent']} "
            f"CRC_ERR={self.stats['crc_errors']} "
            f"SYNC_ERR={self.stats['sync_errors']}"
        )
        if self.last_mcu_status:
            msg.data += (
                f" MCU={self.last_mcu_status['status_msg']}"
                f" FLAGS=0x{self.last_mcu_status['flags']:04X}"
                f" LOOP_HZ={self.last_mcu_status['loop_rate_hz']}"
                f" HEAP_KB={self.last_mcu_status['free_heap_kb']}"
            )
        self.status_pub.publish(msg)

    def destroy_node(self):
        """Cleanup on shutdown."""
        self.running = False
        if hasattr(self, "serial_thread") and self.serial_thread.is_alive():
            self.serial_thread.join(timeout=1.0)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description="Robot Serial Bridge")
    parser.add_argument("--port", default=None, help="Serial port (overrides SERIAL_PORT env)")
    parser.add_argument("--baud", type=int, default=None, help="Baud rate (overrides SERIAL_BAUD env)")
    args = parser.parse_args()

    config = resolve_runtime_config(args)
    rclpy.init()

    try:
        node = RobotSerialBridge(**config)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if "node" in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
