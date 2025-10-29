import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import socket
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('camera_stream_node')
        self.publisher_ = self.create_publisher(Image, '/camera/image_raw', 10)
        self.bridge = CvBridge()

        # GStreamer pipeline for receiving H264 over UDP
        pipeline = (
            "udpsrc port=5000 ! "
            "application/x-rtp, encoding-name=H264 ! "
            "rtph264depay ! avdec_h264 ! videoconvert ! appsink"
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
            self.publisher_.publish(msg)
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

