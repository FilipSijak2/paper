#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
import yaml

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')

        # --- Parameters ---
        self.declare_parameter('camera_device', '/dev/video0')
        self.declare_parameter('camera_info_yaml', '/app/camera_info.yaml')
        self.declare_parameter('camera_width', 640)
        self.declare_parameter('camera_height', 480)
        self.declare_parameter('camera_fps', 30)

        self.camera_device = self.get_parameter('camera_device').value
        self.camera_info_yaml = self.get_parameter('camera_info_yaml').value
        self.width = self.get_parameter('camera_width').value
        self.height = self.get_parameter('camera_height').value
        self.fps = self.get_parameter('camera_fps').value

        # --- ROS2 Publishers ---
        self.image_pub = self.create_publisher(Image, '/image_raw', 10)
        self.cam_info_pub = self.create_publisher(CameraInfo, '/camera_info', 10)

        self.bridge = CvBridge()
        self.cam_info_msg = self.load_camera_info(self.camera_info_yaml)

        # --- Open camera ---
        self.cap = cv2.VideoCapture(self.camera_device, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        if not self.cap.isOpened():
            self.get_logger().error(f"Cannot open camera {self.camera_device}")
            exit(1)

        # --- Timer for publishing ---
        self.timer = self.create_timer(1.0 / self.fps, self.publish_frame)

        self.get_logger().info(f"Camera node started on {self.camera_device} ({self.width}x{self.height} @ {self.fps} FPS)")

    def load_camera_info(self, yaml_file):
        """Load CameraInfo from a YAML calibration file"""
        cam_info_msg = CameraInfo()
        try:
            with open(yaml_file, "r") as file:
                data = yaml.safe_load(file)
                cam_info_msg.width = data.get('image_width', self.width)
                cam_info_msg.height = data.get('image_height', self.height)
                cam_info_msg.k = data.get('camera_matrix', {}).get('data', [0]*9)
                cam_info_msg.d = data.get('distortion_coefficients', {}).get('data', [])
                cam_info_msg.r = data.get('rectification_matrix', {}).get('data', [0]*9)
                cam_info_msg.p = data.get('projection_matrix', {}).get('data', [0]*12)
                cam_info_msg.distortion_model = data.get('distortion_model', 'plumb_bob')
        except Exception as e:
            self.get_logger().warning(f"Failed to load camera info YAML: {e}")
        return cam_info_msg

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warning("Failed to read frame from camera")
            return

        # Convert OpenCV image to ROS2 Image message (RAW)
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.image_pub.publish(msg)

        # Publish CameraInfo
        self.cam_info_pub.publish(self.cam_info_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.cap.release()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
