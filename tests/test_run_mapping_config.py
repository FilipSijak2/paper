import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
RUN_MAPPING_PATH = REPO_ROOT / "slam_cont" / "run_mapping.sh"
STACK_SLAM_ENV_PATH = STACK_ROOT / "config" / "containers" / "slam_cont.env"
STACK_SLAM_PARAMS_PATH = STACK_ROOT / "config" / "containers" / "slam_params.yaml"
STACK_NAV_ENV_PATH = STACK_ROOT / "config" / "containers" / "nav_cont.env"
START_NAV_PATH = REPO_ROOT / "nav_cont" / "start_nav.sh"
RF2O_LAUNCH_PATH = REPO_ROOT / "slam_cont" / "rf2o_odom.launch.py"


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


def test_mapping_profile_limits_speed_only_in_mapping_mode():
    start_nav = START_NAV_PATH.read_text(encoding="utf-8")
    nav_env = STACK_NAV_ENV_PATH.read_text(encoding="utf-8")

    assert 'if [ "${MAPPING_MODE}" = "1" ]; then' in start_nav
    assert 'CMD_VEL_FORWARD_MAX_SPEED="${MAPPING_FORWARD_MAX_SPEED}"' in start_nav
    assert 'CMD_VEL_ANGULAR_MAX_SPEED="${MAPPING_ANGULAR_MAX_SPEED}"' in start_nav
    assert "MAPPING_FORWARD_MAX_SPEED=0.05" in nav_env
    assert "MAPPING_ANGULAR_MAX_SPEED=0.12" in nav_env


def test_mapping_enables_conservative_loop_closure_and_larger_search():
    runtime_override = run_mapping_text()
    slam_params = STACK_SLAM_PARAMS_PATH.read_text(encoding="utf-8")

    for content in (runtime_override, slam_params):
        assert "do_loop_closing: true" in content
        assert "loop_match_minimum_response_coarse: 0.75" in content
        assert "loop_match_maximum_variance_coarse: 0.5" in content
        assert "loop_search_maximum_distance: 2.5" in content
        assert "correlation_search_space_dimension: 1.5" in content


def test_rf2o_and_slam_use_same_filtered_scan_topic():
    rf2o_launch = RF2O_LAUNCH_PATH.read_text(encoding="utf-8")
    slam_params = STACK_SLAM_PARAMS_PATH.read_text(encoding="utf-8")
    slam_env = STACK_SLAM_ENV_PATH.read_text(encoding="utf-8")

    assert '"RF2O_SCAN_TOPIC", "/scan_filtered"' in rf2o_launch
    assert "scan_topic: /scan_filtered" in slam_params
    assert "RF2O_SCAN_TOPIC=/scan_filtered" in slam_env


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
