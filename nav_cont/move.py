import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class MobileRobotController(Node):
    def __init__(self):
        super().__init__('mobile_robot_controller')
        topic = self.declare_parameter('topic', '/cmd_vel_joy').get_parameter_value().string_value
        self.publisher_ = self.create_publisher(Twist, topic, 10)
        self.get_logger().info(
            f"Mobile Robot Controller test node started. Publishing on {topic} "
            "(use /set_manual_mode=true to take control through mux)."
        )

    def move(self, linear_speed, angular_speed):
        """
        Publish movement commands to the robot.
        :param linear_speed: Forward/backward speed (m/s)
        :param angular_speed: Rotational speed (rad/s)
        """
        msg = Twist()
        msg.linear.x = linear_speed
        msg.angular.z = angular_speed
        self.publisher_.publish(msg)
        self.get_logger().info(f"Published linear: {linear_speed}, angular: {angular_speed}")

    def stop(self):
        """Stop the robot."""
        self.move(0.0, 0.0)

def main(args=None):
    rclpy.init(args=args)
    controller = MobileRobotController()

    try:
        # Simple smoke test: command for 2 seconds, then explicit stop.
        controller.move(0.2, 0.0)
        controller.get_logger().info("Publishing forward command for 2 seconds...")
        end_time = controller.get_clock().now().nanoseconds + int(2.0 * 1e9)
        while controller.get_clock().now().nanoseconds < end_time:
            controller.move(0.2, 0.0)
            rclpy.spin_once(controller, timeout_sec=0.1)
        controller.stop()
        controller.get_logger().info("Robot stopped.")
    except KeyboardInterrupt:
        controller.get_logger().info("Keyboard interrupt, stopping robot.")
        controller.stop()
    finally:
        controller.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
