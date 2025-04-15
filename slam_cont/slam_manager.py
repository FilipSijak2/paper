import os
import signal
import subprocess
import psycopg2
import yaml
import json
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.srv import SaveMap

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

class SlamManager(Node):
    def __init__(self):
        super().__init__('slam_manager')
        self.process = None

    def start_slam_toolbox(self):
        """Pokreće slam_toolbox kao podproces."""
        self.get_logger().info("Pokrećem slam_toolbox...")
        self.process = subprocess.Popen(
            ["ros2", "launch", "slam_toolbox", "online_async_launch.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def stop_slam_toolbox(self):
        """Zaustavlja slam_toolbox i sprema mapu."""
        if self.process:
            self.get_logger().info("Zaustavljam slam_toolbox...")
            self.process.terminate()
            self.process.wait()

    def save_map_to_file(self, map_path="/app/map"):
        """Poziva ROS 2 servis za spremanje mape u datoteku."""
        self.get_logger().info("Spremam mapu u datoteku...")
        client = self.create_client(SaveMap, '/slam_toolbox/save_map')
        client.wait_for_service()

        request = SaveMap.Request()
        request.map_url = map_path
        request.map_format = "pgm"

        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future)

        if future.result() is not None:
            self.get_logger().info("Mapa je spremljena u datoteku.")
        else:
            self.get_logger().error("Greška prilikom spremanja mape u datoteku.")

    def save_map_to_database(self, map_path="/app/map.yaml"):
        """Učitava mapu iz datoteke i sprema je u PostgreSQL bazu podataka."""
        self.get_logger().info("Spremam mapu u bazu podataka...")
        try:
            # Povezivanje s bazom podataka
            connection = psycopg2.connect(
                dbname="maps",
                user="user",
                password="password",
                host="database_cont",
                port="5432"
            )
            cursor = connection.cursor()

            # Učitavanje mape iz YAML datoteke
            with open(map_path, "r") as yaml_file:
                map_data = yaml.safe_load(yaml_file)

            # Pretvaranje mape u JSON format
            map_json = json.dumps(map_data)

            # Spremanje mape u bazu podataka
            cursor.execute("INSERT INTO maps (map_name, map_data) VALUES (%s, %s)", ("my_map", map_json))
            connection.commit()

            self.get_logger().info("Mapa je uspješno spremljena u bazu podataka.")

            # Zatvaranje veze
            cursor.close()
            connection.close()
        except Exception as e:
            self.get_logger().error(f"Greška prilikom spremanja mape u bazu podataka: {e}")

    def handle_shutdown(self, signum, frame):
        """Rukuje prekidom procesa (Ctrl+C)."""
        self.get_logger().info("Prekid procesa detektiran. Spremam mapu...")
        self.stop_slam_toolbox()
        self.save_map_to_file()
        self.save_map_to_database()
        self.get_logger().info("Proces završen.")
        rclpy.shutdown()
        exit(0)

def main():
    rclpy.init()
    slam_manager = SlamManager()

    # Postavljanje signala za prekid (Ctrl+C)
    signal.signal(signal.SIGINT, slam_manager.handle_shutdown)

    # Pokretanje slam_toolbox-a
    slam_manager.start_slam_toolbox()

    # Čekanje dok se proces ne prekine
    rclpy.spin(slam_manager)

if __name__ == "__main__":
    main()