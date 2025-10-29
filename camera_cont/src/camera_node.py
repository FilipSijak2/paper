#!/usr/bin/env python3
import os
import time
import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
from camera_info_manager import CameraInfoManager

class UdpH264CameraNode(Node):
    def __init__(self):
        super().__init__('udp_h264_camera_node')

        # Params/env
        self.port = int(os.environ.get('CAMERA_PORT', '5000'))
        self.width = int(os.environ.get('WIDTH', '1280'))
        self.height = int(os.environ.get('HEIGHT', '720'))
        self.fps = int(os.environ.get('FPS', '30'))
        self.frame_id = os.environ.get('FRAME_ID', 'camera_optical_frame')
        self.cam_info_path = os.environ.get('CAMERA_INFO_PATH', '/app/config/camera_info.yaml')

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )

        self.pub_img = self.create_publisher(Image, 'image_raw', qos)
        self.pub_info = self.create_publisher(CameraInfo, 'camera_info', qos)
        self.bridge = CvBridge()

        # CameraInfo
        cam_name = 'rpicam'
        self.ci_manager = CameraInfoManager(self, cam_name, self.cam_info_path)
        if not self.ci_manager.isCalibrated():
            self.get_logger().warn(f'Camera not calibrated, using file: {self.cam_info_path}')
        self.ci_manager.loadCameraInfo()

        # GStreamer pipeline for UDP H.264 -> raw BGR
        # Ensure Zero sends with --inline so SPS/PPS are present.
        gst = (
            f"udpsrc port={self.port} caps=application/x-rtp,media=video,encoding-name=H264,payload=96 ! "
            f"rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! "
            f"video/x-raw,format=BGR,width={self.width},height={self.height},framerate={self.fps}/1 ! appsink"
        )

        self.get_logger().info(f"GStreamer pipeline:\n{gst}")
        self.cap = cv2.VideoCapture(gst, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            self.get_logger().error("Failed to open GStreamer pipeline. Check UDP port/firewall & --inline.")
            raise RuntimeError("Cannot open video pipeline")

        # Timer loop
        self.timer = self.create_timer(1.0 / max(self.fps, 1), self.loop)

    def loop(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.get_logger().warn("Empty frame; waiting for stream...")
            time.sleep(0.05)
            return

        # CameraInfo
        cam_info = self.ci_manager.getCameraInfo()
        now = self.get_clock().now().to_msg()
        cam_info.header.stamp = now
        cam_info.header.frame_id = self.frame_id

        # Image message
        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = now
        msg.header.frame_id = self.frame_id

        self.pub_img.publish(msg)
        self.pub_info.publish(cam_info)

def main():
    rclpy.init()
    try:
        node = UdpH264CameraNode()
        rclpy.spin(node)
    except Exception as e:
        print(f"[FATAL] {e}")
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()
