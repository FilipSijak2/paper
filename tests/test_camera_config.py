import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMERA_PATH = REPO_ROOT / "camera_cont" / "camera_node.py"


def load_camera_module():
    previous_modules = {}

    def inject(name: str, module: ModuleType):
        previous_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    rclpy = ModuleType("rclpy")
    rclpy_node = ModuleType("rclpy.node")
    rclpy_qos = ModuleType("rclpy.qos")
    sensor_msgs = ModuleType("sensor_msgs")
    sensor_msgs_msg = ModuleType("sensor_msgs.msg")
    cv2 = ModuleType("cv2")
    yaml = ModuleType("yaml")

    class Node:
        pass

    class QoSProfile:
        def __init__(self, *args, **kwargs):
            pass

    class ReliabilityPolicy:
        BEST_EFFORT = 1

    class HistoryPolicy:
        KEEP_LAST = 1

    class CameraInfo:
        pass

    class CompressedImage:
        pass

    rclpy_node.Node = Node  # type: ignore
    rclpy_qos.QoSProfile = QoSProfile # type: ignore
    rclpy_qos.ReliabilityPolicy = ReliabilityPolicy # type: ignore
    rclpy_qos.HistoryPolicy = HistoryPolicy # type: ignore
    sensor_msgs_msg.CameraInfo = CameraInfo # type: ignore
    sensor_msgs_msg.CompressedImage = CompressedImage # type: ignore
    sensor_msgs.msg = sensor_msgs_msg # type: ignore
    cv2.CAP_GSTREAMER = 0 # type: ignore
    cv2.IMWRITE_JPEG_QUALITY = 1    # type: ignore
    yaml.safe_load = lambda value: {} # type: ignore

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("rclpy.qos", rclpy_qos)
    inject("sensor_msgs", sensor_msgs)
    inject("sensor_msgs.msg", sensor_msgs_msg)
    inject("cv2", cv2)
    inject("yaml", yaml)

    try:
        spec = importlib.util.spec_from_file_location("test_camera_node", CAMERA_PATH)
        module = importlib.util.module_from_spec(spec) # type: ignore
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def test_resolve_camera_info_path_prefers_explicit_env(tmp_path, monkeypatch):
    module = load_camera_module()
    target = tmp_path / "explicit_camera_info.yaml"
    target.write_text("image_width: 640\n", encoding="utf-8")

    monkeypatch.setenv("CAMERA_INFO_PATH", str(target))

    assert module.resolve_camera_info_path() == str(target)


def test_resolve_camera_info_path_uses_first_existing_candidate(tmp_path, monkeypatch):
    module = load_camera_module()
    first = tmp_path / "missing.yaml"
    second = tmp_path / "camera_info.yaml"
    second.write_text("image_width: 640\n", encoding="utf-8")

    monkeypatch.delenv("CAMERA_INFO_PATH", raising=False)
    monkeypatch.setenv("CAMERA_INFO_PATHS", os.pathsep.join([str(first), str(second)]))

    assert module.resolve_camera_info_path() == str(second)


def test_build_gstreamer_pipeline_uses_udp_port_or_full_override(monkeypatch):
    module = load_camera_module()

    monkeypatch.delenv("CAMERA_GSTREAMER_PIPELINE", raising=False)
    monkeypatch.setenv("CAMERA_UDP_PORT", "6001")
    assert "port=6001" in module.build_gstreamer_pipeline()

    monkeypatch.setenv("CAMERA_GSTREAMER_PIPELINE", "custom pipeline")
    assert module.build_gstreamer_pipeline() == "custom pipeline"
