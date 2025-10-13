import os
import signal
import subprocess
import rclpy
from rclpy.node import Node
import yaml
import math


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
        # Optionally spawn static transform publisher if requested (e.g. base_link -> laser)
        if os.environ.get("PUBLISH_LASER_STATIC_TF", "0") == "1":
            laser_parent = os.environ.get("LASER_PARENT_FRAME", "base_link")
            laser_frame = os.environ.get("LASER_FRAME", "laser")
            xyz = [os.environ.get(k, d) for k, d in (
                ("LASER_X", "0.0"), ("LASER_Y", "0.0"), ("LASER_Z", "0.0")
            )]
            rpy = [os.environ.get(k, d) for k, d in (
                ("LASER_ROLL", "0.0"), ("LASER_PITCH", "0.0"), ("LASER_YAW", "0.0")
            )]
            tf_cmd = [
                "ros2", "run", "tf2_ros", "static_transform_publisher",
                xyz[0], xyz[1], xyz[2], rpy[0], rpy[1], rpy[2],
                laser_parent, laser_frame
            ]
            try:
                self.get_logger().info(f"Pokrećem static TF publisher: {' '.join(tf_cmd)}")
                subprocess.Popen(tf_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                self.get_logger().warn(f"Ne mogu pokrenuti static TF publisher: {e}")
        # YAML-defined static transforms
        static_tf_file = os.environ.get("STATIC_TF_FILE", "/app/static_tf.yaml")
        if os.path.exists(static_tf_file):
            try:
                with open(static_tf_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                for entry in data.get('static_transforms', []):
                    parent = entry.get('parent')
                    child = entry.get('child')
                    trans = entry.get('translation', [0,0,0])
                    rot = entry.get('rotation_rpy', [0,0,0])
                    if not parent or not child:
                        continue
                    if len(trans) != 3 or len(rot) != 3:
                        self.get_logger().warn(f"Preskačem static TF (neispravna duljina) {entry}")
                        continue
                    tf_cmd = ["ros2","run","tf2_ros","static_transform_publisher",
                              str(trans[0]), str(trans[1]), str(trans[2]),
                              str(rot[0]), str(rot[1]), str(rot[2]), parent, child]
                    try:
                        self.get_logger().info(f"Static TF iz YAML: {' '.join(tf_cmd)}")
                        subprocess.Popen(tf_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        self.get_logger().warn(f"Ne mogu pokrenuti static TF iz YAML za {child}: {e}")
            except Exception as e:
                self.get_logger().warn(f"Ne mogu pročitati static TF YAML {static_tf_file}: {e}")
        # Best-effort param dump for debugging (async)
        if os.environ.get("DUMP_SLAM_PARAMS", "1") == "1":
            subprocess.Popen([
                "bash", "-lc",
                "sleep 4; source /opt/ros/humble/setup.bash; ros2 param dump /slam_toolbox > /srv/slam_toolbox_params_dump.yaml 2>/dev/null || true"
            ])

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