import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class MobileRobotController(Node):
    def __init__(self):
        super().__init__('mobile_robot_controller')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.get_logger().info("Mobile Robot Controller Node has been started.")

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
        # Example: Move forward for 2 seconds, then stop
        controller.move(0.5, 0.0)  # Move forward at 0.5 m/s
        controller.get_logger().info("Moving forward for 2 seconds...")
        rclpy.spin_once(controller, timeout_sec=2.0)
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