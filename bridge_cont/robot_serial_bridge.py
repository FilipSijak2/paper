#!/usr/bin/env python3
"""
ROS 2 Serial Bridge for Devastator Robot
Bridges custom serial protocol ↔ standard ROS 2 topics

Architecture:
	ROS 2 Topics ↔ This Bridge ↔ Custom Protocol ↔ Nano ESP32

Published Topics:
	/imu/arduino (sensor_msgs/Imu, configurable via IMU_TOPIC)
	/wheel_odom (nav_msgs/Odometry) 
	/robot_status (std_msgs/String)
    
Subscribed Topics:
	/cmd_vel (geometry_msgs/Twist)

Usage:
	python3 robot_serial_bridge.py --port /dev/ttyUSB0 --baud 115200
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

import serial
import struct
import threading
import time

# ROS message types
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Imu
from nav_msgs.msg import Odometry
from std_msgs.msg import String, Header
from geometry_msgs.msg import PoseWithCovariance, TwistWithCovariance
from geometry_msgs.msg import Pose, Vector3, Quaternion, Point

import argparse
import sys
import os

# Protocol constants (must match Arduino firmware)
PROTOCOL_VERSION = 1

SENSOR_PACKET_HEADER = 0xDEADBEEF
SENSOR_PACKET_TAIL   = 0xCAFEBABE
SENSOR_PACKET_SIZE   = 66  # sizeof(SensorPacket) with __attribute__((packed))

COMMAND_PACKET_HEADER = 0xFEEDFACE  
COMMAND_PACKET_TAIL   = 0xDEADC0DE
COMMAND_PACKET_SIZE   = 22  # sizeof(CommandPacket) with __attribute__((packed))

STATUS_PACKET_HEADER  = 0xABCDEF01
STATUS_PACKET_TAIL    = 0x12345678
STATUS_PACKET_SIZE    = 32

def crc16_ccitt(data, crc=0xFFFF):
	"""CRC-16/CCITT implementation matching Arduino"""
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
	"""Convert Euler angles to quaternion"""
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
	def __init__(self, port='/dev/ttyUSB0', baud=115200):
		super().__init__('robot_serial_bridge')
        
		self.get_logger().info(f'Starting Robot Serial Bridge on {port}@{baud}')
		self.imu_topic = os.environ.get('IMU_TOPIC', '/imu/arduino')
        
		# Serial connection
		self.serial_port = None
		self.port = port
		self.baud = baud
		self.connect_serial()
        
		# ROS publishers
		self.imu_pub = self.create_publisher(Imu, self.imu_topic, 10)
		self.odom_pub = self.create_publisher(Odometry, 'wheel_odom', 10)
		self.status_pub = self.create_publisher(String, 'robot_status', 10)
        
		# ROS subscriber
		self.cmd_sub = self.create_subscription(
			Twist, 'cmd_vel', self.cmd_vel_callback, 10)
        
		# Internal state
		self.last_command_time = time.time()
		self.command_sequence = 0
		self.packet_buffer = bytearray()
		self.stats = {
			'packets_received': 0,
			'packets_sent': 0, 
			'crc_errors': 0,
			'sync_errors': 0,
			'serial_errors': 0
		}
        
		# Threading for serial I/O
		self.running = True
		self.serial_thread = threading.Thread(target=self.serial_loop, daemon=True)
		self.serial_thread.start()
        
		# Watchdog timer
		self.watchdog_timer = self.create_timer(1.0, self.watchdog_callback)
		self.last_packet_time = time.time()
        
		# Status reporting
		self.status_timer = self.create_timer(5.0, self.status_callback)
        
		self.get_logger().info(f'Robot Serial Bridge initialized (IMU topic: {self.imu_topic})')

	def connect_serial(self):
		"""Connect to serial port with retry logic"""
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
				write_timeout=0.1
			)
			self.get_logger().info(f'Serial connected: {self.port}@{self.baud}')
			return True
            
		except Exception as e:
			self.get_logger().error(f'Serial connection failed: {e}')
			self.stats['serial_errors'] += 1
			return False

	def cmd_vel_callback(self, msg):
		"""Handle incoming cmd_vel commands"""
		try:
			# Build command packet
			packet = struct.pack('<LBBHffHL',
				COMMAND_PACKET_HEADER,  # header
				PROTOCOL_VERSION,       # version  
				self.command_sequence & 0xFF,  # sequence
				1200,                   # timeout_ms
				msg.linear.x,           # linear_x
				msg.angular.z,          # angular_z
				0,                      # crc16 placeholder
				COMMAND_PACKET_TAIL     # tail
			)
            
			# Calculate and insert CRC
			crc = crc16_ccitt(packet[:-6])  # Exclude crc and tail
			packet = packet[:-6] + struct.pack('<H', crc) + packet[-4:]
            
			# Send to robot
			if self.serial_port and self.serial_port.is_open:
				self.serial_port.write(packet)
				self.stats['packets_sent'] += 1
				self.command_sequence += 1
				self.last_command_time = time.time()
                
		except Exception as e:
			self.get_logger().error(f'Failed to send command: {e}')
			self.stats['serial_errors'] += 1

	def serial_loop(self):
		"""Background thread for reading serial data"""
		while self.running:
			try:
				if not self.serial_port or not self.serial_port.is_open:
					if not self.connect_serial():
						time.sleep(1.0)
						continue
                
				# Read available data
				data = self.serial_port.read(1024)
				if data:
					self.packet_buffer.extend(data)
					self.process_packets()
                    
			except Exception as e:
				self.get_logger().error(f'Serial read error: {e}')
				self.stats['serial_errors'] += 1
				time.sleep(0.1)

	def process_packets(self):
		"""Process received packet buffer"""
		while len(self.packet_buffer) >= SENSOR_PACKET_SIZE:
			# Look for sensor packet header
			header_pos = self.find_packet_header(SENSOR_PACKET_HEADER)
            
			if header_pos == -1:
				# No header found, keep only last few bytes for potential partial header
				if len(self.packet_buffer) > 8:
					self.packet_buffer = self.packet_buffer[-8:]
				break
                
			if header_pos > 0:
				# Skip bytes before header
				self.packet_buffer = self.packet_buffer[header_pos:]
				self.stats['sync_errors'] += 1
                
			if len(self.packet_buffer) < SENSOR_PACKET_SIZE:
				break  # Need more data
                
			# Extract packet
			packet_data = self.packet_buffer[:SENSOR_PACKET_SIZE]
			self.packet_buffer = self.packet_buffer[SENSOR_PACKET_SIZE:]
            
			# Parse packet
			if self.parse_sensor_packet(packet_data):
				self.stats['packets_received'] += 1
				self.last_packet_time = time.time()
			else:
				self.stats['crc_errors'] += 1

	def find_packet_header(self, header):
		"""Find packet header in buffer"""
		header_bytes = struct.pack('<L', header)
		return self.packet_buffer.find(header_bytes)

	def parse_sensor_packet(self, data):
		"""Parse sensor packet and publish ROS messages"""
		try:
			# Unpack sensor packet
			# Format: header(L) version(B) sequence(B) flags(H) timestamp_ms(L)
			#         accel×3(fff) gyro×3(fff) encoders×2(ff) odom×3(fff)
			#         battery_mv(H) temperature(B) error_flags(B) crc16(H) tail(L)
			# Total: 66 bytes = sizeof(SensorPacket) with __attribute__((packed))
			unpacked = struct.unpack('<LBBHL ffffff ff fff HBB HL', data)
            
			(header, version, sequence, flags, timestamp_ms,
			 accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z,
			 left_angle, right_angle,
			 odom_x, odom_y, odom_yaw,
			 battery_mv, temperature, error_flags, crc16, tail) = unpacked
            
			# Validate packet structure
			if header != SENSOR_PACKET_HEADER or tail != SENSOR_PACKET_TAIL:
				return False
			if version != PROTOCOL_VERSION:
				return False
                
			# Validate CRC
			expected_crc = crc16_ccitt(data[:-6])
			if crc16 != expected_crc:
				return False
            
			# Create ROS timestamp
			now = self.get_clock().now()
            
			# Publish IMU data
			self.publish_imu(now, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
            
			# Publish odometry
			self.publish_odometry(now, odom_x, odom_y, odom_yaw, left_angle, right_angle)
            
			return True
            
		except Exception as e:
			self.get_logger().error(f'Packet parsing error: {e}')
			return False

	def publish_imu(self, timestamp, ax, ay, az, gx, gy, gz):
		"""Publish IMU message"""
		msg = Imu()
		msg.header.stamp = timestamp.to_msg()
		msg.header.frame_id = 'imu_link'
        
		msg.linear_acceleration.x = ax
		msg.linear_acceleration.y = ay  
		msg.linear_acceleration.z = az
        
		msg.angular_velocity.x = gx
		msg.angular_velocity.y = gy
		msg.angular_velocity.z = gz
        
		# Set covariance (unknown)
		msg.linear_acceleration_covariance[0] = -1.0
		msg.angular_velocity_covariance[0] = -1.0
		msg.orientation_covariance[0] = -1.0
        
		self.imu_pub.publish(msg)

	def publish_odometry(self, timestamp, x, y, yaw, left_angle, right_angle):
		"""Publish odometry message"""
		msg = Odometry()
		msg.header.stamp = timestamp.to_msg()
		msg.header.frame_id = 'odom'
		msg.child_frame_id = 'base_link'
        
		# Position
		msg.pose.pose.position = Point(x=x, y=y, z=0.0)
		msg.pose.pose.orientation = euler_to_quaternion(yaw)
        
		# Velocity (computed from encoder rates would be better, but simplified for now)
		msg.twist.twist.linear.x = 0.0  # Could compute from delta encoders
		msg.twist.twist.angular.z = 0.0
        
		# Set covariance (simplified)
		msg.pose.covariance[0] = 0.1   # x
		msg.pose.covariance[7] = 0.1   # y  
		msg.pose.covariance[35] = 0.1  # yaw
		msg.twist.covariance[0] = 0.1  # vx
		msg.twist.covariance[35] = 0.1 # vyaw
        
		self.odom_pub.publish(msg)

	def watchdog_callback(self):
		"""Monitor connection health"""
		now = time.time()
		if now - self.last_packet_time > 3.0:
			self.get_logger().warn('No packets received for 3 seconds - checking connection')
			if self.serial_port and not self.serial_port.is_open:
				self.connect_serial()
                
	def status_callback(self):
		"""Publish periodic status"""
		msg = String()
		msg.data = f"Serial Bridge: RX={self.stats['packets_received']} TX={self.stats['packets_sent']} " \
				  f"CRC_ERR={self.stats['crc_errors']} SYNC_ERR={self.stats['sync_errors']}"
		self.status_pub.publish(msg)
        
	def destroy_node(self):
		"""Cleanup on shutdown"""
		self.running = False
		if self.serial_port and self.serial_port.is_open:
			self.serial_port.close()
		super().destroy_node()

def main():
	parser = argparse.ArgumentParser(description='Robot Serial Bridge')
	parser.add_argument('--port', default=None, help='Serial port (overrides SERIAL_PORT env)')
	parser.add_argument('--baud', type=int, default=None, help='Baud rate (overrides SERIAL_BAUD env)')
	args = parser.parse_args()

	# Resolve configuration precedence: CLI args > env vars > defaults
	port = args.port or os.environ.get('SERIAL_PORT', '/dev/ttyUSB0')
	try:
		baud_env = os.environ.get('SERIAL_BAUD')
		baud = args.baud or (int(baud_env) if baud_env else 115200)
	except ValueError:
		print(f"Invalid SERIAL_BAUD env value '{os.environ.get('SERIAL_BAUD')}', falling back to 115200")
		baud = 115200

	rclpy.init()

	try:
		node = RobotSerialBridge(port=port, baud=baud)
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		if 'node' in locals():
			node.destroy_node()
		rclpy.shutdown()

if __name__ == '__main__':
	import math  # Add missing import for quaternion conversion
	main()
