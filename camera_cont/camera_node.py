import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import socket
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from cv_bridge import CvBridge
import cv2
from rclpy.time import Time
import yaml
import os

class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('camera_stream_node')
        self.publisher_ = self.create_publisher(Image, '/camera/image_raw', 10)
        self.info_pub = self.create_publisher(CameraInfo, '/camera/camera_info', 10)
        self.bridge = CvBridge()

        # Load camera_info.yaml
        camera_info_path = '/stack/config/camera_info.yaml' if os.path.exists('/stack/config/camera_info.yaml') else '/app/camera_info.yaml'
        self.camera_info = CameraInfo()
        try:
            with open(camera_info_path, 'r') as f:
                info = yaml.safe_load(f)
            self.camera_info.width = info.get('image_width', 0)
            self.camera_info.height = info.get('image_height', 0)
            self.camera_info.distortion_model = info.get('distortion_model', 'plumb_bob')
            self.camera_info.d = info.get('distortion_coefficients', {}).get('data', [0.0]*5)
            self.camera_info.k = info.get('camera_matrix', {}).get('data', [1.0,0,0,0,1.0,0,0,0,1.0])
            self.camera_info.r = info.get('rectification_matrix', {}).get('data', [1.0,0,0,0,1.0,0,0,0,1.0])
            self.camera_info.p = info.get('projection_matrix', {}).get('data', [1.0,0,0,0,0,1.0,0,0,0,0,1.0,0])
        except Exception as e:
            self.get_logger().warn(f"Could not load camera_info.yaml: {e}")

        # GStreamer pipeline for receiving H264 over UDP
        pipeline = (
            "udpsrc port=5000 ! queue ! h264parse ! avdec_h264 ! videoconvert ! appsink"
        )

        self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            self.get_logger().error("Failed to open UDP stream via GStreamer")
            raise RuntimeError("Could not open video stream")

        self.timer = self.create_timer(0.03, self.timer_callback)  # ~30 FPS

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            now = self.get_clock().now().to_msg()
            msg.header.stamp = now
            msg.header.frame_id = "camera_frame"
            self.publisher_.publish(msg)

            # Publish camera_info with matching header
            self.camera_info.header.stamp = now
            self.camera_info.header.frame_id = "camera_frame"
            self.info_pub.publish(self.camera_info)
        else:
            self.get_logger().warn("Failed to read frame from stream")

def main(args=None):
    rclpy.init(args=args)
    node = CameraStreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.cap.release()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

