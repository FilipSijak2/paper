#!/usr/bin/env python3
import os
import time
import yaml
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from builtin_interfaces.msg import Time as TimeMsg
import cv2
import numpy as np

def load_camera_info(path, width, height):
    info = CameraInfo()
    if os.path.isfile(path):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        info.width = data.get('image_width', width)
        info.height = data.get('image_height', height)
        info.distortion_model = data.get('distortion_model', 'plumb_bob')
        info.d = data.get('D', [0.0]*5)
        info.k = data.get('K', [0.0]*9)
        info.r = data.get('R', [0.0]*9)
        info.p = data.get('P', [0.0]*12)
        roi = data.get('roi', {})
        info.roi.x_offset = roi.get('x_offset', 0)
        info.roi.y_offset = roi.get('y_offset', 0)
        info.roi.height = roi.get('height', 0)
        info.roi.width  = roi.get('width', 0)
        info.roi.do_rectify = roi.get('do_rectify', False)
        info.binning_x = data.get('binning_x', 1)
        info.binning_y = data.get('binning_y', 1)
    else:
        info.width = width
        info.height = height
        info.distortion_model = 'plumb_bob'
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        fx = fy = float(min(width, height))
        cx = width / 2.0
        cy = height / 2.0
        info.k = [fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0]
        info.r = [1.0,0.0,0.0, 0.0,1.0,0.0, 0.0,0.0,1.0]
        info.p = [fx,0.0,cx,0.0, 0.0,fy,cy,0.0, 0.0,0.0,1.0,0.0]
    return info

class GStreamerCameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.declare_parameter('width', int(os.getenv('WIDTH', '1280')))
        self.declare_parameter('height', int(os.getenv('HEIGHT', '720')))
        self.declare_parameter('fps', int(os.getenv('FPS', '30')))
        self.declare_parameter('camera_info_file', os.getenv('CAMERA_INFO_FILE', '/app/camera_info.yaml'))

        self.width = self.get_parameter('width').get_parameter_value().integer_value
        self.height = self.get_parameter('height').get_parameter_value().integer_value
        self.fps = self.get_parameter('fps').get_parameter_value().integer_value
        self.camera_info_file = self.get_parameter('camera_info_file').get_parameter_value().string_value

        # Publishers
        self.image_pub = self.create_publisher(Image, '/camera/image_raw', 10)
        self.info_pub  = self.create_publisher(CameraInfo, '/camera/camera_info', 10)

        # CameraInfo
        self.cam_info = load_camera_info(self.camera_info_file, self.width, self.height)

        # GStreamer pipeline for RAW frames (BGR via appsink)
        # libcamerasrc daje RAW; videoconvert -> BGR za OpenCV; appsink za Python
        gst = (
            f"libcamerasrc camera-name=rpi_cam ! "
            f"video/x-raw,width={self.width},height={self.height},framerate={self.fps}/1,format=RGB ! "
            f"videoconvert ! video/x-raw,format=BGR ! "
            f"appsink drop=true max-buffers=2 sync=false"
        )
        self.get_logger().info(f"Opening GStreamer pipeline:\n{gst}")
        self.cap = cv2.VideoCapture(gst, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            self.get_logger().error("Failed to open GStreamer pipeline for capture.")
            raise RuntimeError("CV VideoCapture open failed")

        self.timer = self.create_timer(1.0 / float(self.fps), self._tick)

    def _tick(self):
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.get_logger().warn("Failed to read frame")
            return
        # Build Image msg
        msg = Image()
        now = self.get_clock().now().to_msg()
        msg.header.stamp = now
        msg.header.frame_id = 'camera_frame'
        msg.height, msg.width = frame.shape[0], frame.shape[1]
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = frame.shape[1] * 3
        msg.data = frame.tobytes()
        self.image_pub.publish(msg)

        # CameraInfo with same timestamp
        info = self.cam_info
        info.header.stamp = now
        info.header.frame_id = 'camera_frame'
        self.info_pub.publish(info)

    def destroy_node(self):
        try:
            if hasattr(self, 'cap') and self.cap:
                self.cap.release()
        except Exception:
            pass
        super().destroy_node()

def main():
    rclpy.init()
    node = None
    try:
        node = GStreamerCameraNode()
        rclpy.spin(node)
    except Exception as e:
        print(f"[FATAL] {e}")
    finally:
        if node:
            node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
