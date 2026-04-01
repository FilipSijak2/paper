#!/usr/bin/env python3

import os
import time

import cv2
import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, CompressedImage


DEFAULT_CAMERA_INFO_PATHS = (
    "/config/camera_info.yaml",
    "/stack/config/camera_info.yaml",
    "/app/camera_info.yaml",
)


def env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default, minimum=None, maximum=None):
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


def env_float(name, default, minimum=None):
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def resolve_camera_info_path():
    explicit = os.getenv("CAMERA_INFO_PATH", "").strip()
    if explicit:
        return explicit

    raw_candidates = os.getenv("CAMERA_INFO_PATHS", "")
    if raw_candidates:
        candidates = tuple(path.strip() for path in raw_candidates.split(os.pathsep) if path.strip())
    else:
        candidates = DEFAULT_CAMERA_INFO_PATHS

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


def build_gstreamer_pipeline():
    explicit = os.getenv("CAMERA_GSTREAMER_PIPELINE", "").strip()
    if explicit:
        return explicit

    udp_port = env_int("CAMERA_UDP_PORT", 5000, minimum=1, maximum=65535)
    return f"udpsrc port={udp_port} ! queue ! h264parse ! avdec_h264 ! videoconvert ! appsink"


class CameraStreamNode(Node):
    def __init__(self):
        super().__init__("camera_stream_node")

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.compressed_topic = os.getenv("CAMERA_COMPRESSED_TOPIC", "/camera/image_raw/compressed")
        self.info_topic = os.getenv("CAMERA_INFO_TOPIC", "/camera/camera_info")
        self.frame_id = os.getenv("CAMERA_FRAME_ID", "camera_frame")
        self.jpeg_quality = env_int("CAMERA_JPEG_QUALITY", 90, minimum=1, maximum=100)
        self.capture_fps = env_float("CAMERA_FPS", 30.0, minimum=0.1)
        self.warn_interval_s = env_float("CAMERA_WARN_INTERVAL_S", 5.0, minimum=0.5)
        self.max_read_failures = env_int("CAMERA_MAX_READ_FAILURES", 30, minimum=1)
        self.camera_info_required = env_bool("CAMERA_INFO_REQUIRED", False)
        self.exit_on_stream_failure = env_bool("CAMERA_EXIT_ON_STREAM_FAILURE", False)
        self.camera_info_path = resolve_camera_info_path()
        self.gstreamer_pipeline = build_gstreamer_pipeline()

        self.compressed_pub = self.create_publisher(CompressedImage, self.compressed_topic, qos_profile)
        self.info_pub = self.create_publisher(CameraInfo, self.info_topic, qos_profile)

        self.camera_info_loaded = False
        self.camera_info = CameraInfo()
        self._last_stream_warn_ts = 0.0
        self._last_encode_warn_ts = 0.0
        self._consecutive_read_failures = 0

        self._load_camera_info()
        if self.camera_info_required and not self.camera_info_loaded:
            raise RuntimeError(
                "camera_info.yaml is required but could not be loaded from "
                f"{self.camera_info_path}"
            )

        self.cap = cv2.VideoCapture(self.gstreamer_pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            self.get_logger().error(
                f"Failed to open video stream with pipeline: {self.gstreamer_pipeline}"
            )
            raise RuntimeError("Could not open video stream")

        timer_period_s = 1.0 / self.capture_fps
        self.timer = self.create_timer(timer_period_s, self.timer_callback)
        self.get_logger().info(
            "Camera stream started "
            f"(compressed_topic={self.compressed_topic}, info_topic={self.info_topic}, "
            f"frame_id={self.frame_id}, fps={self.capture_fps:.2f})"
        )

    def _load_camera_info(self):
        if not os.path.exists(self.camera_info_path):
            self.get_logger().error(
                f"camera_info.yaml not found at {self.camera_info_path}. "
                "CameraInfo publishing will stay disabled."
            )
            return

        self.get_logger().info(f"Loading camera_info.yaml from {self.camera_info_path}")
        try:
            with open(self.camera_info_path, "r", encoding="utf-8") as handle:
                info = yaml.safe_load(handle) or {}
            self.camera_info.width = info.get("image_width", 0)
            self.camera_info.height = info.get("image_height", 0)
            self.camera_info.distortion_model = info.get("distortion_model", "plumb_bob")
            self.camera_info.d = info.get("distortion_coefficients", {}).get("data", [0.0] * 5)
            self.camera_info.k = info.get(
                "camera_matrix", {}
            ).get("data", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
            self.camera_info.r = info.get(
                "rectification_matrix", {}
            ).get("data", [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0])
            self.camera_info.p = info.get("projection_matrix", {}).get(
                "data", [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
            )
            self.camera_info_loaded = True
            self.get_logger().info("camera_info.yaml loaded successfully.")
        except Exception as exc:
            self.get_logger().error(f"Failed to load camera_info.yaml: {exc}")

    def _should_log(self, last_timestamp):
        now = time.monotonic()
        return now - last_timestamp >= self.warn_interval_s

    def timer_callback(self):
        ret, frame = self.cap.read()
        if not ret:
            self._consecutive_read_failures += 1
            if self._should_log(self._last_stream_warn_ts):
                self._last_stream_warn_ts = time.monotonic()
                self.get_logger().warn(
                    "Failed to read frame from stream "
                    f"(consecutive_failures={self._consecutive_read_failures})"
                )
            if (
                self.exit_on_stream_failure
                and self._consecutive_read_failures >= self.max_read_failures
            ):
                message = (
                    "Video stream has failed repeatedly "
                    f"({self._consecutive_read_failures} consecutive failures)."
                )
                self.get_logger().error(message)
                raise RuntimeError(message)
            return

        self._consecutive_read_failures = 0
        now = self.get_clock().now().to_msg()

        try:
            encoded, jpeg = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if not encoded:
                if self._should_log(self._last_encode_warn_ts):
                    self._last_encode_warn_ts = time.monotonic()
                    self.get_logger().warn("Failed to encode frame as JPEG.")
                return
        except Exception as exc:
            if self._should_log(self._last_encode_warn_ts):
                self._last_encode_warn_ts = time.monotonic()
                self.get_logger().warn(f"Exception during JPEG encoding: {exc}")
            return

        comp_msg = CompressedImage()
        comp_msg.header.stamp = now
        comp_msg.header.frame_id = self.frame_id
        comp_msg.format = "jpeg"
        comp_msg.data = jpeg.tobytes()
        self.compressed_pub.publish(comp_msg)

        if self.camera_info_loaded:
            self.camera_info.header.stamp = now
            self.camera_info.header.frame_id = self.frame_id
            self.info_pub.publish(self.camera_info)

    def destroy_node(self):
        if hasattr(self, "cap") and self.cap is not None:
            self.cap.release()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraStreamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
