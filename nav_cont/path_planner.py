import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseStamped
import psycopg2
import json

class PathPlanner(Node):
    def __init__(self):
        super().__init__('path_planner')
        self.goal_publisher = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.db_connection = self.connect_to_database()
        self.map_data = self.load_map_from_database()
        self.get_logger().info("Path Planner Node has been started.")

    def connect_to_database(self):
        """Connect to the PostgreSQL database."""
        try:
            connection = psycopg2.connect(
                dbname="maps",
                user="user",
                password="password",
                host="localhost",
                port="5432"
            )
            self.get_logger().info("Connected to the database.")
            return connection
        except Exception as e:
            self.get_logger().error(f"Failed to connect to database: {e}")
            return None

    def load_map_from_database(self):
        """Load the map from the database."""
        if self.db_connection is None:
            self.get_logger().error("Database connection not available.")
            return None

        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT map_data FROM maps WHERE map_name = %s", ("latest_map",))
            result = cursor.fetchone()
            cursor.close()
            if result:
                self.get_logger().info("Map loaded from the database.")
                return json.loads(result[0])
            else:
                self.get_logger().error("No map found in the database.")
                return None
        except Exception as e:
            self.get_logger().error(f"Failed to load map: {e}")
            return None

    def set_goal(self, x, y, theta):
        """Set a goal position for the robot."""
        if self.map_data is None:
            self.get_logger().error("Map not available. Cannot set goal.")
            return

        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = x
        goal.pose.position.y = y
        goal.pose.orientation.z = theta  # Simplified for 2D
        self.goal_publisher.publish(goal)
        self.get_logger().info(f"Goal set to x: {x}, y: {y}, theta: {theta}")

def main(args=None):
    rclpy.init(args=args)
    planner = PathPlanner()

    try:
        rclpy.spin(planner)
    except KeyboardInterrupt:
        planner.get_logger().info("Keyboard interrupt, shutting down.")
    finally:
        if planner.db_connection:
            planner.db_connection.close()
        planner.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()