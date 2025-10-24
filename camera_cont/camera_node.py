#!/usr/bin/env python3
import os
import yaml
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge

def getenv_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        # Params via ENV (fallback to defaults)
        self.device = os.environ.get('CAMERA_DEVICE', '/dev/video0')
        self.width = getenv_int('CAMERA_WIDTH', 1280)
        self.height = getenv_int('CAMERA_HEIGHT', 720)
        self.fps = getenv_int('CAMERA_FPS', 30)
        self.info_yaml = os.environ.get('CAMERA_INFO_YAML', '/app/camera_info.yaml')

        self.get_logger().info(f"Opening {self.device} {self.width}x{self.height}@{self.fps}")

        # Publishers
        self.pub_color = self.create_publisher(Image, '/camera/image_raw', 10)
        self.pub_mono  = self.create_publisher(Image, '/camera/image_mono', 10)
        self.pub_info  = self.create_publisher(CameraInfo, '/camera/camera_info', 10)
        self.bridge = CvBridge()
        self.cam_info = self.load_camera_info(self.info_yaml)

        # OpenCV capture
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS,          float(self.fps))

        if not self.cap.isOpened():
            self.get_logger().error(f"Cannot open camera device {self.device}")
            raise SystemExit(1)

        self.timer = self.create_timer(1.0 / max(1, self.fps), self.tick)

    def load_camera_info(self, path):
        msg = CameraInfo()
        msg.width = self.width
        msg.height = self.height
        msg.distortion_model = 'plumb_bob'
        if not os.path.exists(path):
            self.get_logger().warn(f"CameraInfo YAML not found: {path} (using defaults)")
            return msg
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            msg.width  = data.get('image_width',  self.width)
            msg.height = data.get('image_height', self.height)
            msg.distortion_model = data.get('distortion_model', 'plumb_bob')
            msg.d = data.get('distortion_coefficients', {}).get('data', [])
            msg.k = data.get('camera_matrix', {}).get('data', [0.0]*9)
            msg.r = data.get('rectification_matrix', {}).get('data', [0.0]*9)
            msg.p = data.get('projection_matrix', {}).get('data', [0.0]*12)
            self.get_logger().info(f"Loaded CameraInfo from {path}")
        except Exception as e:
            self.get_logger().error(f"Failed to parse CameraInfo: {e}")
        return msg

    def tick(self):
        ok, frame = self.cap.read()
        if not ok:
            self.get_logger().warn("Failed to read frame")
            return

        # Color (BGR8)
        img_color = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.pub_color.publish(img_color)

        # Mono (mono8)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        img_mono = self.bridge.cv2_to_imgmsg(gray, encoding='mono8')
        self.pub_mono.publish(img_mono)

        # CameraInfo
        self.pub_info.publish(self.cam_info)

    def destroy_node(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        super().destroy_node()

def main():
    rclpy.init()
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
