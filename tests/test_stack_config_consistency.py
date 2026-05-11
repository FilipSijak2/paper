import importlib.util
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
RECORDED_TOPICS_PATH = STACK_ROOT / "config" / "containers" / "recorded_topics.yaml"
BRIDGE_PATH = REPO_ROOT / "bridge_cont" / "robot_serial_bridge.py"
HEALTHCHECK_PATH = REPO_ROOT / "healthcheck_cont" / "healthcheck.py"


def load_healthcheck_module():
    spec = importlib.util.spec_from_file_location("test_stack_healthcheck", HEALTHCHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(not STACK_ROOT.exists(), reason="Sibling stack directory is not available")


def parse_recorded_topics(path: Path) -> list[str]:
    topics = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line.startswith("- "):
            topics.append(line[2:].strip())
    return topics


def parse_bridge_published_topics(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8")
    matches = re.findall(r"create_publisher\([^,]+,\s*'([^']+)'", content)
    return {topic if topic.startswith("/") else f"/{topic}" for topic in matches}


def test_stack_topics_are_resolvable_against_known_runtime_publishers():
    healthcheck = load_healthcheck_module()
    recorded_topics = parse_recorded_topics(RECORDED_TOPICS_PATH)
    bridge_topics = parse_bridge_published_topics(BRIDGE_PATH)
    known_runtime_topics = set(bridge_topics)
    known_runtime_topics.update(
        {
            "/scan",
            "/tf",
            "/tf_static",
            "/imu/data",
            "/imu/arduino",
            "/realsense/imu",
            "/realsense/color/image_raw",
            "/realsense/color/image_compressed",
            "/realsense/color/camera_info",
            "/realsense/depth/image_rect_raw",
            "/realsense/depth/camera_info",
            "/realsense/aligned_depth_to_color/image_raw",
            "/realsense/imu/gyro",
            "/realsense/imu/accel",
        }
    )

    for topic in ["/wheel_odom", "/imu/data", "/imu/arduino", "/camera/realsense/color/image_compressed"]:
        assert topic in recorded_topics
        assert healthcheck.resolve_available_topic(topic, known_runtime_topics) is not None

    for topic in healthcheck.DEFAULT_EXPECTED_TOPICS:
        assert healthcheck.resolve_available_topic(topic, known_runtime_topics) is not None

    # /rosout recording is optional in the current stack and may be excluded
    # to reduce bag size. The important runtime topics are asserted above.
