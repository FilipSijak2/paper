import os
import signal
import subprocess
import rclpy
from rclpy.node import Node


class SlamManager(Node):
    """Minimal manager: samo pokreće slam_toolbox za kontinuiranu lokalizaciju/SLAM.
    Ne sprema mapu automatski niti nudi servis. Mapiranje se pokreće ručno skriptom run_mapping.sh.
    """

    def __init__(self):
        super().__init__('slam_manager')
        self.process = None
        self.get_logger().info("SlamManager started (bez automatskog spremanja mape).")

    def start_slam_toolbox(self):
        """Pokreće slam_toolbox kao podproces uz normalizaciju RMW i params."""
        rmw = os.environ.get("RMW_IMPLEMENTATION", "")
        if "cyclonedx" in rmw:
            self.get_logger().warn(f"RMW tipfeler '{rmw}' -> koristim rmw_cyclonedds_cpp")
            os.environ["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
        elif not rmw:
            os.environ["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
        slam_params = "/app/slam_params.yaml"
        cmd = [
            "ros2", "run", "slam_toolbox", "async_slam_toolbox_node",
            "--ros-args", "--params-file", slam_params
        ] if os.path.exists(slam_params) else [
            "ros2", "launch", "slam_toolbox", "online_async_launch.py"
        ]
        self.get_logger().info(f"Pokrećem slam_toolbox (cmd={' '.join(cmd)})")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def stop_slam_toolbox(self):
        """Zaustavlja slam_toolbox i sprema mapu."""
        if self.process:
            self.get_logger().info("Zaustavljam slam_toolbox...")
            self.process.terminate()
            self.process.wait()

    def handle_shutdown(self, signum, frame):
        """Rukuje prekidom procesa bez automatskog spremanja mape."""
        self.get_logger().info("Signal završetka primljen – gašenje bez automatskog spremanja (koristi save_current_map service za ručno spremanje).")
        self.stop_slam_toolbox()
        rclpy.shutdown()
        os._exit(0)

def main():
    rclpy.init()
    slam_manager = SlamManager()
    # Hvatanje SIGINT (Ctrl+C) i SIGTERM (docker stop)
    signal.signal(signal.SIGINT, slam_manager.handle_shutdown)
    try:
        signal.signal(signal.SIGTERM, slam_manager.handle_shutdown)
    except Exception:
        pass

    # Pokretanje slam_toolbox-a
    slam_manager.start_slam_toolbox()

    # Čekanje dok se proces ne prekine
    rclpy.spin(slam_manager)

if __name__ == "__main__":
    main()