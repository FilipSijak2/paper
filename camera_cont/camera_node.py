#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
import yaml
import os

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        # Parameters (can be overridden via Docker compose env vars)
        self.declare_parameter('camera_device', '/dev/video0')
        self.declare_parameter('camera_width', 640)
        self.declare_parameter('camera_height', 480)
        self.declare_parameter('camera_fps', 30)
        self.declare_parameter('camera_info_yaml', '/app/camera_info.yaml')

        self.camera_device = self.get_parameter('camera_device').value
        self.width = int(self.get_parameter('camera_width').value)
        self.height = int(self.get_parameter('camera_height').value)
        self.fps = int(self.get_parameter('camera_fps').value)
        self.camera_info_yaml = self.get_parameter('camera_info_yaml').value

        self.get_logger().info(f"Starting camera on {self.camera_device} at {self.width}x{self.height} @ {self.fps} FPS")

        # Load camera info
        self.camera_info_msg = self.load_camera_info(self.camera_info_yaml)

        # OpenCV VideoCapture
        self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not self.cap.isOpened():
            self.get_logger().error(f"Failed to open camera {self.camera_device}")
            raise SystemExit

        # ROS publishers
        self.image_pub = self.create_publisher(Image, '/image_raw', 10)
        self.cam_info_pub = self.create_publisher(CameraInfo, '/camera_info', 10)
        self.bridge = CvBridge()

        # Timer callback at desired FPS
        self.timer = self.create_timer(1.0 / self.fps, self.publish_frame)

    def load_camera_info(self, yaml_file):
        """Load camera calibration from YAML file"""
        cam_info = CameraInfo()
        if not os.path.exists(yaml_file):
            self.get_logger().warn(f"Camera calibration file not found: {yaml_file}, using defaults.")
            cam_info.width = self.width
            cam_info.height = self.height
            cam_info.distortion_model = "plumb_bob"
            return cam_info

        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)

            cam_info.width = data.get('image_width', self.width)
            cam_info.height = data.get('image_height', self.height)
            cam_info.distortion_model = data.get('distortion_model', 'plumb_bob')
            cam_info.d = data.get('distortion_coefficients', {}).get('data', [])
            cam_info.k = data.get('camera_matrix', {}).get('data', [0.0] * 9)
            cam_info.r = data.get('rectification_matrix', {}).get('data', [0.0] * 9)
            cam_info.p = data.get('projection_matrix', {}).get('data', [0.0] * 12)
            self.get_logger().info(f"Loaded camera calibration from {yaml_file}")
        except Exception as e:
            self.get_logger().error(f"Error loading camera info: {str(e)}")

        return cam_info

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warning("Failed to capture frame")
            return

        # Convert frame to ROS2 Image message
        image_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.image_pub.publish(image_msg)

        # Publish camera info
        self.cam_info_pub.publish(self.camera_info_msg)

    def destroy_node(self):
        if self.cap.isOpened():
            self.cap.release()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
