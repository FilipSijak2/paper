import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
RUN_MAPPING_PATH = REPO_ROOT / "slam_cont" / "run_mapping.sh"
STACK_SLAM_ENV_PATH = STACK_ROOT / "config" / "containers" / "slam_cont.env"


def run_mapping_text() -> str:
    return RUN_MAPPING_PATH.read_text(encoding="utf-8")


def default_mapping_topics() -> set[str]:
    match = re.search(r'^\s*TOPICS="([^"]+)"', run_mapping_text(), re.MULTILINE)
    assert match is not None, "Default TOPICS assignment not found"
    return set(match.group(1).split())


def test_mapping_default_topics_include_imu_yaw_correction_chain():
    topics = default_mapping_topics()

    assert "/odom_rf2o" in topics
    assert "/odometry/filtered" in topics
    assert "/imu/data" in topics
    assert "/imu/base_link" in topics
    assert "/imu/base_link_corrected" in topics
    assert "/cmd_vel_collision_in" in topics


def test_mapping_preflight_requires_corrected_imu_and_ekf_when_expected():
    content = run_mapping_text()

    assert "EXPECT_IMU_YAW_CORRECTION" in content
    assert "preflight_mapping_imu_yaw_correction" in content
    assert "IMU_YAW_PREFLIGHT_TOPIC" in content
    assert "MAPPING_EKF_ODOM_TOPIC" in content
    assert "preflight_mapping_odometry\npreflight_mapping_imu_yaw_correction\npreflight_mapping_scan_topic" in content


@pytest.mark.skipif(not STACK_SLAM_ENV_PATH.exists(), reason="Sibling stack slam_cont.env is not available")
def test_stack_slam_env_enables_mapping_imu_yaw_preflight():
    env_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in STACK_SLAM_ENV_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.lstrip().startswith("#") and "=" in line
    }

    assert env_lines["EXPECT_IMU_YAW_CORRECTION"] == "auto"
    assert env_lines["IMU_YAW_PREFLIGHT_TOPIC"] == "/imu/base_link_corrected"
    assert env_lines["MAPPING_EKF_ODOM_TOPIC"] == "/odometry/filtered"
