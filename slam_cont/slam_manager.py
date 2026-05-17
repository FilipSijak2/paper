import os
import signal
import subprocess

import rclpy
from rclpy.node import Node
import yaml


class SlamManager(Node):
    """Minimal manager that keeps slam_toolbox running for live SLAM/localization."""

    def __init__(self):
        super().__init__("slam_manager")
        self.process = None
        self.rf2o_process = None
        self.scan_filter_process = None
        self.static_tf_processes = []
        self.create_timer(2.0, self.monitor_processes)
        self.get_logger().info("SlamManager started (bez automatskog spremanja mape).")

    def start_slam_toolbox(self):
        """Start slam_toolbox as a child process with normalized RMW/params."""
        if not hasattr(self, "static_tf_processes"):
            self.static_tf_processes = []

        # Start scan range filter first so /scan_filtered is available before
        # slam_toolbox subscribes to it.  The filter strips 0.0 m RPLIDAR invalid
        # returns that otherwise crash CorrelationGrid::GetDataPointer.
        self.start_scan_filter()

        rmw = os.environ.get("RMW_IMPLEMENTATION", "")
        if "cyclonedx" in rmw:
            self.get_logger().warn(f"RMW tipfeler '{rmw}' -> koristim rmw_cyclonedds_cpp")
            os.environ["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
        elif not rmw:
            os.environ["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"

        start_slam_toolbox = os.environ.get("START_SLAM_TOOLBOX", "1").strip().lower()
        if start_slam_toolbox not in ("0", "false", "no", "off"):
            slam_params = "/app/slam_params.yaml"
            # Use localization_slam_toolbox_node for navigation: no pose graph,
            # no map building, no loop closures -> significantly lower CPU on RPi 5.
            # Mapping sessions use their own slam_toolbox instance (run_mapping.sh).
            cmd = (
                [
                    "ros2",
                    "run",
                    "slam_toolbox",
                    "localization_slam_toolbox_node",
                    "--ros-args",
                    "--params-file",
                    slam_params,
                ]
                if os.path.exists(slam_params)
                else ["ros2", "launch", "slam_toolbox", "localization_launch.py"]
            )

            self.get_logger().info(f"Pokrecem slam_toolbox (cmd={' '.join(cmd)})")
            # Inherit stdout/stderr so slam_toolbox logs stay visible in `docker logs`.
            self.process = subprocess.Popen(cmd)
        else:
            self.get_logger().info(
                "START_SLAM_TOOLBOX=0 -> slam_toolbox preskocen; "
                "slam_cont i dalje objavljuje static TF/rf2o pomocne procese."
            )

        if os.environ.get("PUBLISH_LASER_STATIC_TF", "0") == "1":
            laser_parent = os.environ.get("LASER_PARENT_FRAME", "base_link")
            laser_frame = os.environ.get("LASER_FRAME", "laser")
            xyz = [os.environ.get(key, default) for key, default in (
                ("LASER_X", "0.0"),
                ("LASER_Y", "0.0"),
                ("LASER_Z", "0.0"),
            )]
            rpy = [os.environ.get(key, default) for key, default in (
                ("LASER_ROLL", "0.0"),
                ("LASER_PITCH", "0.0"),
                ("LASER_YAW", "0.0"),
            )]
            tf_cmd = [
                "ros2",
                "run",
                "tf2_ros",
                "static_transform_publisher",
                "--frame-id", laser_parent,
                "--child-frame-id", laser_frame,
                "--x", xyz[0],
                "--y", xyz[1],
                "--z", xyz[2],
                "--roll", rpy[0],
                "--pitch", rpy[1],
                "--yaw", rpy[2],
            ]
            try:
                self.get_logger().info(f"Pokrecem static TF publisher: {' '.join(tf_cmd)}")
                tf_proc = subprocess.Popen(tf_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.static_tf_processes.append((laser_frame, tf_proc))
            except Exception as exc:
                self.get_logger().warn(f"Ne mogu pokrenuti static TF publisher: {exc}")

        static_tf_file = os.environ.get("STATIC_TF_FILE", "/app/static_tf.yaml")
        if os.path.exists(static_tf_file):
            try:
                with open(static_tf_file, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}

                for entry in data.get("static_transforms", []):
                    parent = entry.get("parent")
                    child = entry.get("child")
                    trans = entry.get("translation", [0, 0, 0])
                    rot = entry.get("rotation_rpy", [0, 0, 0])
                    if not parent or not child:
                        continue
                    if len(trans) != 3 or len(rot) != 3:
                        self.get_logger().warn(f"Preskacem static TF (neispravna duljina) {entry}")
                        continue

                    tf_cmd = [
                        "ros2",
                        "run",
                        "tf2_ros",
                        "static_transform_publisher",
                        "--frame-id", parent,
                        "--child-frame-id", child,
                        "--x", str(trans[0]),
                        "--y", str(trans[1]),
                        "--z", str(trans[2]),
                        "--roll", str(rot[0]),
                        "--pitch", str(rot[1]),
                        "--yaw", str(rot[2]),
                    ]
                    try:
                        self.get_logger().info(f"Static TF iz YAML: {' '.join(tf_cmd)}")
                        tf_proc = subprocess.Popen(tf_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.static_tf_processes.append((child, tf_proc))
                    except Exception as exc:
                        self.get_logger().warn(f"Ne mogu pokrenuti static TF iz YAML za {child}: {exc}")
            except Exception as exc:
                self.get_logger().warn(f"Ne mogu procitati static TF YAML {static_tf_file}: {exc}")

        if self.process is not None and os.environ.get("DUMP_SLAM_PARAMS", "1") == "1":
            subprocess.Popen(
                [
                    "bash",
                    "-lc",
                    "sleep 4; source /opt/ros/humble/setup.bash; ros2 param dump /slam_toolbox > /srv/slam_toolbox_params_dump.yaml 2>/dev/null || true",
                ]
            )

        if self._should_start_rf2o():
            self.start_rf2o()
        else:
            self.get_logger().info(
                "rf2o_laser_odometry preskočen (START_RF2O=auto + ENCODERS_ENABLED=1). "
                "Koristi se wheel odometry + EKF. Postavi START_RF2O=1 za ručno pokretanje."
            )

    def _should_start_rf2o(self) -> bool:
        """Decide whether to start rf2o based on START_RF2O and ENCODERS_ENABLED env vars.

        START_RF2O=0    -> never start (encoders working, save ~15% CPU on one core)
        START_RF2O=1    -> always start
        START_RF2O=auto -> start only if ENCODERS_ENABLED=0 (default: off when encoders present)
        """
        mode = os.environ.get("START_RF2O", "auto").strip().lower()
        if mode == "0":
            return False
        if mode == "1":
            return True
        # auto: only start if encoders are disabled
        encoders = os.environ.get("ENCODERS_ENABLED", "1").strip()
        return encoders == "0"

    def start_rf2o(self):
        rf2o_cmd = [
            "ros2",
            "launch",
            "/app/rf2o_odom.launch.py",
        ]
        self.get_logger().info("Pokrecem rf2o_laser_odometry kao zamjenu za wheel_odom...")
        try:
            self.rf2o_process = subprocess.Popen(rf2o_cmd)
        except FileNotFoundError:
            self.get_logger().error("rf2o_laser_odometry_node nije pronadjen - provjeri Dockerfile!")

    def start_scan_filter(self) -> None:
        """Start scan_range_filter.py: filters 0.0 m RPLIDAR invalid returns.

        Republishes /scan as /scan_filtered with readings outside [0.2, range_max]
        replaced by inf.  slam_toolbox uses /scan_filtered (set in slam_params.yaml)
        so it never receives the 0.0 m readings that cause a CorrelationGrid crash.
        """
        cmd = ["python3", "/app/scan_range_filter.py"]
        self.get_logger().info("Pokrecem scan_range_filter (/scan → /scan_filtered, min=0.2 m)...")
        try:
            self.scan_filter_process = subprocess.Popen(cmd)
        except Exception as exc:
            self.get_logger().error(f"Ne mogu pokrenuti scan_range_filter: {exc}")

    def monitor_processes(self):
        """Best-effort health logging for slam_toolbox and helper TF publishers."""
        if self.process is not None:
            return_code = self.process.poll()
            if return_code is not None:
                self.get_logger().error(f"slam_toolbox exited unexpectedly with code {return_code}")
                self.process = None

        if self.rf2o_process is not None:
            rc = self.rf2o_process.poll()
            if rc is not None:
                self.get_logger().error(f"rf2o_laser_odometry izasao neocekivano s kodom {rc}, restartujem...")
                self.rf2o_process = None
                self.start_rf2o()

        if self.scan_filter_process is not None:
            rc = self.scan_filter_process.poll()
            if rc is not None:
                self.get_logger().error(f"scan_range_filter izasao s kodom {rc}, restartujem...")
                self.scan_filter_process = None
                self.start_scan_filter()

        alive_static_tf = []
        for child, proc in getattr(self, "static_tf_processes", []):
            return_code = proc.poll()
            if return_code is None:
                alive_static_tf.append((child, proc))
                continue
            if return_code != 0:
                self.get_logger().warn(f"Static TF publisher za {child} zavrsio s kodom {return_code}")
        self.static_tf_processes = alive_static_tf

    def stop_slam_toolbox(self):
        """Stop slam_toolbox, rf2o, scan_range_filter and helper TF publishers."""
        if self.scan_filter_process:
            if self.scan_filter_process.poll() is None:
                self.get_logger().info("Zaustavljam scan_range_filter...")
                self.scan_filter_process.terminate()
                try:
                    self.scan_filter_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.scan_filter_process.kill()
                    self.scan_filter_process.wait(timeout=3)
            self.scan_filter_process = None

        if self.rf2o_process:
            if self.rf2o_process.poll() is None:
                self.get_logger().info("Zaustavljam rf2o_laser_odometry...")
                self.rf2o_process.terminate()
                try:
                    self.rf2o_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.rf2o_process.kill()
                    self.rf2o_process.wait(timeout=3)
            self.rf2o_process = None

        if self.process:
            if self.process.poll() is None:
                self.get_logger().info("Zaustavljam slam_toolbox...")
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.get_logger().warn("slam_toolbox nije zavrsio na SIGTERM, saljem SIGKILL.")
                    self.process.kill()
                    self.process.wait(timeout=5)
            self.process = None

        for child, proc in getattr(self, "static_tf_processes", []):
            if proc.poll() is not None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.get_logger().warn(
                    f"Static TF publisher za {child} nije zavrsio na SIGTERM, saljem SIGKILL."
                )
                proc.kill()
                proc.wait(timeout=5)
        self.static_tf_processes = []

    def handle_shutdown(self, signum, frame):
        """Handle SIGINT/SIGTERM without automatic map saving."""
        self.get_logger().info(
            "Signal zavrsetka primljen - gasenje bez automatskog spremanja "
            "(koristi save_current_map service za rucno spremanje)."
        )
        self.stop_slam_toolbox()
        rclpy.shutdown()
        os._exit(0)


def main():
    rclpy.init()
    slam_manager = SlamManager()
    signal.signal(signal.SIGINT, slam_manager.handle_shutdown)
    try:
        signal.signal(signal.SIGTERM, slam_manager.handle_shutdown)
    except Exception:
        pass

    slam_manager.start_slam_toolbox()
    rclpy.spin(slam_manager)


if __name__ == "__main__":
    main()
