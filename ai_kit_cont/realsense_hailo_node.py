#!/usr/bin/env python3
"""
ROS2 node that ingests RealSense images and forwards frames to an optional
Hailo GStreamer pipeline.

If HAILO_GST_PIPELINE is unset, the node works in passthrough mode and only
republishes input images to AI overlay topics.

Pipeline requirements:
- include appsrc named `ros_src`
- include appsink named `ros_sink`
- output image-compatible buffers on appsink (BGR/RGB/GRAY8)

Template placeholders supported in HAILO_GST_PIPELINE:
- {WIDTH}
- {HEIGHT}
- {FPS}
"""

import os
import queue
import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import rclpy # type: ignore
from cv_bridge import CvBridge # type: ignore
from rclpy.executors import ExternalShutdownException # type: ignore
from rclpy.node import Node # type: ignore
from rclpy.qos import qos_profile_sensor_data # type: ignore
from sensor_msgs.msg import CompressedImage, Image # type: ignore

try:
    import gi # type: ignore

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst   # type: ignore

    GST_AVAILABLE = True
    GST_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - runtime environment specific
    GST_AVAILABLE = False
    GST_IMPORT_ERROR = str(exc)
    Gst = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class HailoGstProcessor:
    def __init__(
        self,
        pipeline_template: str,
        width: int,
        height: int,
        fps: int,
        logger,
    ) -> None:
        if not GST_AVAILABLE:
            raise RuntimeError(f"GStreamer python bindings unavailable: {GST_IMPORT_ERROR}")

        Gst.init(None) # type: ignore
        self._logger = logger
        self._fps = max(1, fps)
        self._frame_duration_ns = int(1e9 / self._fps)
        self._frame_counter = 0

        pipeline_desc = (
            pipeline_template.replace("{WIDTH}", str(width))
            .replace("{HEIGHT}", str(height))
            .replace("{FPS}", str(self._fps))
        )
        self._logger.info(f"Using Hailo GST pipeline: {pipeline_desc}")

        self._pipeline = Gst.parse_launch(pipeline_desc) # type: ignore
        self._appsrc = self._pipeline.get_by_name("ros_src")
        self._appsink = self._pipeline.get_by_name("ros_sink")
        if self._appsrc is None or self._appsink is None:
            raise RuntimeError("Pipeline must contain appsrc name=ros_src and appsink name=ros_sink.")

        caps = Gst.Caps.from_string( # type: ignore
            f"video/x-raw,format=BGR,width={width},height={height},framerate={self._fps}/1"
        )
        self._appsrc.set_property("caps", caps)
        self._appsrc.set_property("is-live", True)
        self._appsrc.set_property("block", True)
        self._appsrc.set_property("format", Gst.Format.TIME) # type: ignore
        self._appsink.set_property("emit-signals", False)
        self._appsink.set_property("sync", False)
        self._appsink.set_property("drop", True)
        self._appsink.set_property("max-buffers", 1)

        state_ret = self._pipeline.set_state(Gst.State.PLAYING) # type: ignore
        if state_ret not in (Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.ASYNC): # type: ignore
            raise RuntimeError(f"Failed to set pipeline to PLAYING. Return={state_ret}")

    def process(self, frame_bgr: np.ndarray, timeout_ms: int = 50) -> Optional[np.ndarray]:
        if frame_bgr.dtype != np.uint8:
            frame_bgr = frame_bgr.astype(np.uint8, copy=False)
        if not frame_bgr.flags["C_CONTIGUOUS"]:
            frame_bgr = np.ascontiguousarray(frame_bgr)

        data = frame_bgr.tobytes()
        gst_buffer = Gst.Buffer.new_allocate(None, len(data), None) # type: ignore
        gst_buffer.fill(0, data)
        gst_buffer.pts = self._frame_counter * self._frame_duration_ns
        gst_buffer.dts = gst_buffer.pts
        gst_buffer.duration = self._frame_duration_ns
        self._frame_counter += 1

        push_ret = self._appsrc.emit("push-buffer", gst_buffer)
        if push_ret != Gst.FlowReturn.OK: # type: ignore
            self._logger.warning(f"Hailo pipeline push-buffer failed: {push_ret}")
            return None

        sample = self._appsink.emit("try-pull-sample", timeout_ms * 1_000_000)
        if sample is None:
            return None

        return self._sample_to_bgr(sample)

    def _sample_to_bgr(self, sample) -> Optional[np.ndarray]:
        caps = sample.get_caps()
        if caps is None or caps.get_size() == 0:
            return None

        structure = caps.get_structure(0)
        width = structure.get_value("width")
        height = structure.get_value("height")
        pixel_format = structure.get_value("format")
        if not width or not height or not pixel_format:
            return None

        buffer = sample.get_buffer()
        if buffer is None:
            return None

        ok, map_info = buffer.map(Gst.MapFlags.READ) # type: ignore
        if not ok:
            return None

        try:
            raw = np.frombuffer(map_info.data, dtype=np.uint8)
            if pixel_format == "BGR":
                frame = raw.reshape((height, width, 3))
                return frame.copy()
            if pixel_format == "RGB":
                frame = raw.reshape((height, width, 3))
                return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            if pixel_format == "GRAY8":
                frame = raw.reshape((height, width))
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            self._logger.warning(f"Unsupported appsink pixel format '{pixel_format}', using input frame.")
            return None
        finally:
            buffer.unmap(map_info)

    def close(self) -> None:
        try:
            self._appsrc.emit("end-of-stream")
        except Exception:
            pass
        self._pipeline.set_state(Gst.State.NULL) # type: ignore


class RealSenseHailoNode(Node):
    def __init__(self) -> None:
        super().__init__("realsense_hailo_node")
        self._bridge = CvBridge()

        self._image_topic = os.getenv("RS_IMAGE_TOPIC", "/realsense/color/image_raw")
        self._overlay_topic = os.getenv("AI_OVERLAY_TOPIC", "/ai_kit/image_overlay")
        self._overlay_compressed_topic = os.getenv(
            "AI_OVERLAY_COMPRESSED_TOPIC", "/ai_kit/image_overlay/compressed"
        )
        self._jpeg_quality = max(1, min(100, _env_int("AI_JPEG_QUALITY", 85)))
        self._inference_fps = max(1, _env_int("AI_INFERENCE_FPS", 10))
        self._queue_size = max(1, _env_int("AI_FRAME_QUEUE_SIZE", 2))
        self._inference_timeout_ms = max(1, _env_int("AI_INFERENCE_TIMEOUT_MS", 60))
        self._publish_raw_overlay = _env_bool("AI_PUBLISH_RAW_OVERLAY", True)
        self._pipeline_template = os.getenv("HAILO_GST_PIPELINE", "").strip()

        self._overlay_pub = None
        if self._publish_raw_overlay:
            self._overlay_pub = self.create_publisher(Image, self._overlay_topic, 10)
        self._overlay_compressed_pub = self.create_publisher(
            CompressedImage, self._overlay_compressed_topic, 10
        )

        self._frame_queue: "queue.Queue[Tuple[np.ndarray, object, str]]" = queue.Queue(
            maxsize=self._queue_size
        )
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        self._processor: Optional[HailoGstProcessor] = None
        self._processor_lock = threading.Lock()
        self._last_infer_ts = 0.0

        self._sub = self.create_subscription(
            Image, self._image_topic, self._image_callback, qos_profile_sensor_data
        )

        if self._pipeline_template:
            if GST_AVAILABLE:
                self.get_logger().info("Hailo inference mode enabled (HAILO_GST_PIPELINE is set).")
            else:
                self.get_logger().warning(
                    "HAILO_GST_PIPELINE is set but GStreamer Python bindings are unavailable. "
                    f"Running passthrough mode. Import error: {GST_IMPORT_ERROR}"
                )
        else:
            self.get_logger().warning(
                "HAILO_GST_PIPELINE is not set. Running passthrough mode "
                "(RealSense input republished without inference)."
            )

        self.get_logger().info(
            f"Subscribed to {self._image_topic}, publishing overlay to "
            f"{self._overlay_topic} and {self._overlay_compressed_topic}."
        )

    def _image_callback(self, msg: Image) -> None:
        now = time.monotonic()
        min_period = 1.0 / self._inference_fps
        if now - self._last_infer_ts < min_period:
            return
        self._last_infer_ts = now

        try:
            frame_bgr = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().warning(f"Failed to convert ROS image to cv2: {exc}")
            return

        item = (frame_bgr, msg.header.stamp, msg.header.frame_id)
        if self._frame_queue.full():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self._frame_queue.put_nowait(item)
        except queue.Full:
            pass

    def _init_processor_if_needed(self, width: int, height: int) -> None:
        if not self._pipeline_template or not GST_AVAILABLE:
            return
        with self._processor_lock:
            if self._processor is not None:
                return
            try:
                self._processor = HailoGstProcessor(
                    pipeline_template=self._pipeline_template,
                    width=width,
                    height=height,
                    fps=self._inference_fps,
                    logger=self.get_logger(),
                )
            except Exception as exc:
                self.get_logger().error(
                    f"Failed to initialize Hailo GStreamer processor. "
                    f"Falling back to passthrough mode. Error: {exc}"
                )
                self._processor = None

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                frame_bgr, stamp, frame_id = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if frame_bgr is None:
                continue

            self._init_processor_if_needed(frame_bgr.shape[1], frame_bgr.shape[0])

            output_bgr = frame_bgr
            with self._processor_lock:
                if self._processor is not None:
                    processed = self._processor.process(
                        frame_bgr, timeout_ms=self._inference_timeout_ms
                    )
                    if processed is not None:
                        output_bgr = processed

            self._publish_overlay(output_bgr, stamp, frame_id)

    def _publish_overlay(self, frame_bgr: np.ndarray, stamp, frame_id: str) -> None:
        if self._overlay_pub is not None:
            try:
                msg = self._bridge.cv2_to_imgmsg(frame_bgr, encoding="bgr8")
                msg.header.stamp = stamp
                msg.header.frame_id = frame_id
                self._overlay_pub.publish(msg)
            except Exception as exc:
                self.get_logger().warning(f"Failed to publish raw overlay image: {exc}")

        ok, jpg = cv2.imencode(
            ".jpg", frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
        )
        if not ok:
            self.get_logger().warning("Failed to JPEG-encode overlay frame.")
            return

        compressed = CompressedImage()
        compressed.header.stamp = stamp
        compressed.header.frame_id = frame_id
        compressed.format = "jpeg"
        compressed.data = jpg.tobytes()
        self._overlay_compressed_pub.publish(compressed)

    def destroy_node(self):
        self._stop_event.set()
        if self._worker.is_alive():
            self._worker.join(timeout=1.5)
        with self._processor_lock:
            if self._processor is not None:
                self._processor.close()
                self._processor = None
        return super().destroy_node()


def main() -> None:
    rclpy.init()
    node = RealSenseHailoNode()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
