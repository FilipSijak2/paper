import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
import psycopg2
import json

class MapSaver(Node):
    def __init__(self):
        super().__init__('map_saver')
        self.map_subscriber = self.create_subscription(
            OccupancyGrid,
            '/map',
            self.map_callback,
            10
        )
        self.db_connection = self.connect_to_database()
        self.get_logger().info("Map Saver Node has been started.")

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

    def map_callback(self, msg):
        """Callback to save the map to the database."""
        if self.db_connection is None:
            self.get_logger().error("Database connection not available.")
            return

        try:
            cursor = self.db_connection.cursor()
            map_data = {
                "info": {
                    "width": msg.info.width,
                    "height": msg.info.height,
                    "resolution": msg.info.resolution,
                    "origin": {
                        "position": {
                            "x": msg.info.origin.position.x,
                            "y": msg.info.origin.position.y,
                            "z": msg.info.origin.position.z
                        },
                        "orientation": {
                            "x": msg.info.origin.orientation.x,
                            "y": msg.info.origin.orientation.y,
                            "z": msg.info.origin.orientation.z,
                            "w": msg.info.origin.orientation.w
                        }
                    }
                },
                "data": list(msg.data)
            }
            cursor.execute(
                "INSERT INTO maps (map_name, map_data) VALUES (%s, %s)",
                ("latest_map", json.dumps(map_data))
            )
            self.db_connection.commit()
            cursor.close()
            self.get_logger().info("Map saved to the database.")
        except Exception as e:
            self.get_logger().error(f"Failed to save map: {e}")

def main(args=None):
    rclpy.init(args=args)
    map_saver = MapSaver()

    try:
        rclpy.spin(map_saver)
    except KeyboardInterrupt:
        map_saver.get_logger().info("Keyboard interrupt, shutting down.")
    finally:
        if map_saver.db_connection:
            map_saver.db_connection.close()
        map_saver.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()