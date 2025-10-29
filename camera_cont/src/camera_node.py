import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import socket

class CameraStreamNode(Node):
    def __init__(self):
        super().__init__('camera_stream_node')
        self.publisher = self.create_publisher(CompressedImage, 'camera/image/compressed', 10)
        self.declare_parameter('udp_port', 5000)

        port = self.get_parameter('udp_port').get_parameter_value().integer_value
        self.get_logger().info(f"Listening for H264 stream on UDP port {port}")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", port))

        self.timer = self.create_timer(0.01, self.receive_frame)

    def receive_frame(self):
        data, _ = self.sock.recvfrom(65535)
        msg = CompressedImage()
        msg.format = "h264"
        msg.data = data
        self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = CameraStreamNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
