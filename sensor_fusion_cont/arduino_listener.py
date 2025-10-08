#!/usr/bin/env python3
import os
import sys
import time
import math
import threading
import serial
import yaml

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from std_msgs.msg import String
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue


def clamp(v, mn, mx):
    return mn if v < mn else mx if v > mx else v

class ArduinoImuNode(Node):
    def __init__(self):
        super().__init__('arduino_imu_listener')
        cfg_path = os.getenv('SF_CONFIG', '/app/sensor_fusion.yaml')
        self.get_logger().info(f'Loading config: {cfg_path}')
        try:
            with open(cfg_path, 'r') as f:
                self.cfg = yaml.safe_load(f) or {}
        except Exception as e:
            self.get_logger().warn(f'Could not load config {cfg_path}: {e}; using defaults')
            self.cfg = {}

        serial_cfg = self.cfg.get('serial', {})
        self.port = serial_cfg.get('port', '/dev/ttyACM0')
        self.baud = int(serial_cfg.get('baudrate', 115200))
        self.timeout = serial_cfg.get('timeout_ms', 200) / 1000.0
        imu_cfg = self.cfg.get('imu', {})
        self.frame_id = imu_cfg.get('frame_id', 'imu_link')
        self.rate = float(imu_cfg.get('publish_rate_hz', 30.0))

        self.imu_pub = self.create_publisher(Imu, 'imu/data_raw', 10)
        self.raw_line_pub = self.create_publisher(String, 'imu/raw_line', 10)
        self.diag_pub = self.create_publisher(DiagnosticArray, '/diagnostics', 10)

        self.last_msg_time = time.time()
        self.last_line = ''
        self.port_ok = False
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.reader_loop, daemon=True)
        self.thread.start()

        self.create_timer(1.0, self.publish_diag)
        self.get_logger().info(f'Initialized. Serial: {self.port} @ {self.baud}')

    def open_serial(self):
        try:
            ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            self.port_ok = True
            self.get_logger().info(f'Opened serial {self.port}')
            return ser
        except Exception as e:
            self.port_ok = False
            self.get_logger().error(f'Failed to open {self.port}: {e}')
            return None

    def reader_loop(self):
        ser = None
        retry_delay = 2.0
        while not self.stop_event.is_set():
            if ser is None or not ser.is_open:
                ser = self.open_serial()
                if ser is None:
                    time.sleep(retry_delay)
                    continue
            try:
                line = ser.readline().decode(errors='ignore').strip()
                if not line:
                    continue
                self.last_line = line
                self.raw_line_pub.publish(String(data=line))
                msg = self.parse_line(line)
                if msg:
                    self.imu_pub.publish(msg)
                    self.last_msg_time = time.time()
            except Exception as e:
                self.get_logger().warn(f'Read/parse error: {e}')
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                time.sleep(retry_delay)

    def quaternion_from_euler(self, roll, pitch, yaw):
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        qw = cy * cr * cp + sy * sr * sp
        qx = cy * sr * cp - sy * cr * sp
        qy = cy * cr * sp + sy * sr * cp
        qz = sy * cr * cp - cy * sr * sp
        return qw, qx, qy, qz

    def parse_line(self, line: str):
        # Supported formats:
        # IMU,qw,qx,qy,qz,ax,ay,az,gx,gy,gz
        # RAW,ax,ay,az,gx,gy,gz,mx,my,mz,yaw_deg,roll_deg,pitch_deg
        parts = line.split(',')
        if len(parts) < 2:
            return None
        tag = parts[0].upper()
        imu_msg = Imu()
        imu_msg.header.stamp = self.get_clock().now().to_msg()
        imu_msg.header.frame_id = self.frame_id
        try:
            if tag == 'IMU' and len(parts) >= 11:
                qw,qx,qy,qz = map(float, parts[1:5])
                ax,ay,az = map(float, parts[5:8])
                gx,gy,gz = map(float, parts[8:11])
            elif tag == 'RAW' and len(parts) >= 13:
                ax,ay,az = map(float, parts[1:4])
                gx,gy,gz = map(float, parts[4:7])
                # mag components currently unused
                yawd, rolld, pitchd = map(float, parts[10:13])
                # convert degrees to radians
                yaw = math.radians(yawd)
                roll = math.radians(rolld)
                pitch = math.radians(pitchd)
                qw,qx,qy,qz = self.quaternion_from_euler(roll, pitch, yaw)
            else:
                return None
        except ValueError:
            return None

        imu_msg.orientation.w = qw
        imu_msg.orientation.x = qx
        imu_msg.orientation.y = qy
        imu_msg.orientation.z = qz
        imu_msg.linear_acceleration.x = ax
        imu_msg.linear_acceleration.y = ay
        imu_msg.linear_acceleration.z = az
        imu_msg.angular_velocity.x = gx
        imu_msg.angular_velocity.y = gy
        imu_msg.angular_velocity.z = gz
        # Simple covariance defaults
        imu_msg.orientation_covariance = self.cfg.get('imu', {}).get('covariance_orientation', [-1.0]*9)
        imu_msg.angular_velocity_covariance = self.cfg.get('imu', {}).get('covariance_angular_velocity', [-1.0]*9)
        imu_msg.linear_acceleration_covariance = self.cfg.get('imu', {}).get('covariance_linear_acceleration', [-1.0]*9)
        return imu_msg

    def publish_diag(self):
        da = DiagnosticArray()
        da.header.stamp = self.get_clock().now().to_msg()
        st = DiagnosticStatus()
        st.name = 'arduino_imu_listener'
        ok = (time.time() - self.last_msg_time) < (5.0 if self.rate <= 0 else 3.0 / max(1.0, self.rate))
        st.level = DiagnosticStatus.OK if ok else DiagnosticStatus.WARN
        st.message = 'OK' if ok else 'No recent IMU data'
        st.values = [
            KeyValue(key='port', value=self.port),
            KeyValue(key='baud', value=str(self.baud)),
            KeyValue(key='last_line', value=self.last_line[:80]),
            KeyValue(key='port_ok', value=str(self.port_ok)),
        ]
        da.status.append(st)
        self.diag_pub.publish(da)

    def destroy_node(self):
        self.stop_event.set()
        super().destroy_node()


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

if __name__ == '__main__':
    main()
