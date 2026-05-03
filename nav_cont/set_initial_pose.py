#!/usr/bin/env python3
import math
import sys

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped

def usage():
    print("Usage: set_initial_pose.py x y yaw_deg [frame_id=map]", file=sys.stderr)

class InitialPosePublisher(Node):
    def __init__(self, x, y, yaw_deg, frame_id):
        super().__init__('initial_pose_setter')
        self.pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        yaw = math.radians(yaw_deg)
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = frame_id
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw/2.0)
        msg.pose.pose.orientation.w = math.cos(yaw/2.0)
        cov = [0.0]*36
        cov[0] = 0.05  # x
        cov[7] = 0.05  # y
        cov[35] = 0.2  # yaw variance (~sqrt=0.447 rad ~ 25 deg)
        msg.pose.covariance = cov
        self.msg = msg
        self.count = 0
        self.timer = self.create_timer(0.2, self.timer_cb)

    def timer_cb(self):
        if self.count < 5:
            self.msg.header.stamp = self.get_clock().now().to_msg()
            self.pub.publish(self.msg)
            self.get_logger().info(f"Published initial pose ({self.msg.pose.pose.position.x:.2f}, {self.msg.pose.pose.position.y:.2f}, count={self.count+1}/5)")
            self.count += 1
        else:
            self.get_logger().info('Done publishing initial pose.')
            rclpy.shutdown()


def main():
    if len(sys.argv) < 4:
        usage()
        return 1
    try:
        x = float(sys.argv[1])
        y = float(sys.argv[2])
        yaw_deg = float(sys.argv[3])
    except ValueError:
        usage()
        return 1
    frame_id = sys.argv[4] if len(sys.argv) > 4 else 'map'
    rclpy.init()
    node = InitialPosePublisher(x, y, yaw_deg, frame_id)
    rclpy.spin(node)
    return 0

if __name__ == '__main__':
    sys.exit(main())
