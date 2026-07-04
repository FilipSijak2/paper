import ast
from pathlib import Path
from xml.etree import ElementTree

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
DEFAULT_PARAMS = REPO_ROOT / "nav_cont" / "nav2_params.yaml"
DEFAULT_TREE = REPO_ROOT / "nav_cont" / "navigate_to_pose_stable.xml"
DEFAULT_COLLISION = REPO_ROOT / "nav_cont" / "collision_monitor_params.yaml"
DEFAULT_SAFETY_FILTER = REPO_ROOT / "nav_cont" / "cmd_vel_safety_filter.py"
STACK_PARAMS = STACK_ROOT / "config" / "containers" / "nav2_params.yaml"
STACK_TREE = STACK_ROOT / "config" / "containers" / "navigate_to_pose_stable.xml"
STACK_COLLISION = STACK_ROOT / "config" / "containers" / "collision_monitor_params.yaml"
STACK_NAV_ENV = STACK_ROOT / "config" / "containers" / "nav_cont.env"
START_NAV = REPO_ROOT / "nav_cont" / "start_nav.sh"


def indented_block(text: str, heading: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != heading:
            continue
        heading_indent = len(line) - len(line.lstrip())
        block = []
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                block.append(candidate)
                continue
            indent = len(candidate) - len(candidate.lstrip())
            if indent <= heading_indent:
                break
            block.append(candidate)
        return "\n".join(block)
    raise AssertionError(f"Missing YAML heading: {heading}")


def scalar(block: str, key: str):
    for line in block.splitlines():
        content = line.strip()
        if content.startswith(f"{key}:"):
            raw_value = content.split(":", maxsplit=1)[1].split("#", maxsplit=1)[0].strip()
            return ast.literal_eval(raw_value)
    raise AssertionError(f"Missing YAML key: {key}")


def test_navigation_detects_blocked_translation_without_penalizing_rotation():
    text = DEFAULT_PARAMS.read_text(encoding="utf-8")
    progress = indented_block(text, "progress_checker:")

    assert scalar(progress, "plugin") == "nav2_controller::PoseProgressChecker"
    assert scalar(progress, "required_movement_radius") <= 0.04
    assert scalar(progress, "required_movement_angle") <= 0.10
    assert scalar(progress, "movement_time_allowance") <= 8.0


def test_follow_path_context_recovery_makes_room_before_retry():
    root = ElementTree.parse(DEFAULT_TREE).getroot()
    follow_recovery = root.find(".//RecoveryNode[@name='FollowPath']")

    assert follow_recovery is not None
    backup = follow_recovery.find(".//BackUp")
    assert backup is not None
    assert float(backup.attrib["backup_dist"]) >= 0.18
    assert float(backup.attrib["backup_speed"]) <= 0.025


def test_reverse_recovery_uses_directional_hard_stops():
    collision = DEFAULT_COLLISION.read_text(encoding="utf-8")
    active_polygons = scalar(collision, "polygons")

    assert "front_stop" not in active_polygons
    assert "rear_stop" not in active_polygons
    assert "footprint_approach" in active_polygons

    if STACK_NAV_ENV.exists():
        nav_env = STACK_NAV_ENV.read_text(encoding="utf-8")
        assert "CMD_VEL_SCAN_STOP_ENABLED=true" in nav_env
        assert "CMD_VEL_MAP_STOP_ENABLED=true" in nav_env


def test_goal_tolerance_does_not_accept_large_visible_offset():
    text = DEFAULT_PARAMS.read_text(encoding="utf-8")
    goal_checker = indented_block(text, "general_goal_checker:")
    follow_path = indented_block(text, "FollowPath:")

    assert scalar(goal_checker, "xy_goal_tolerance") <= 0.12
    assert scalar(goal_checker, "yaw_goal_tolerance") <= 0.30
    assert scalar(follow_path, "xy_goal_tolerance") <= 0.12


def test_narrow_corridor_profile_retains_hard_stops():
    text = DEFAULT_PARAMS.read_text(encoding="utf-8")
    follow_path = indented_block(text, "FollowPath:")
    local_costmap = indented_block(text, "local_costmap:")
    global_costmap = indented_block(text, "global_costmap:")
    collision = DEFAULT_COLLISION.read_text(encoding="utf-8")
    footprint_approach = indented_block(collision, "footprint_approach:")

    vtheta_samples = scalar(follow_path, "vtheta_samples")
    assert vtheta_samples == 15
    assert vtheta_samples % 2 == 1
    assert scalar(local_costmap, "footprint_padding") == 0.01
    assert scalar(local_costmap, "inflation_radius") == 0.25
    assert scalar(local_costmap, "cost_scaling_factor") == 6.0
    assert scalar(global_costmap, "footprint_padding") == 0.01
    assert scalar(global_costmap, "inflation_radius") == 0.33
    assert scalar(global_costmap, "cost_scaling_factor") == 5.0
    assert scalar(footprint_approach, "time_before_collision") == 0.8

    safety_filter = DEFAULT_SAFETY_FILTER.read_text(encoding="utf-8")
    assert 'declare_parameter("front_stop_distance", 0.24)' in safety_filter
    assert 'declare_parameter("rear_stop_distance", 0.20)' in safety_filter

    if STACK_NAV_ENV.exists():
        nav_env = STACK_NAV_ENV.read_text(encoding="utf-8")
        assert "CMD_VEL_FRONT_STOP_DISTANCE=0.24" in nav_env
        assert "CMD_VEL_REAR_STOP_DISTANCE=0.20" in nav_env
        assert "CMD_VEL_SCAN_MIN_POINTS=7" in nav_env
        assert "CMD_VEL_MAP_LOOKAHEAD_M=0.20" in nav_env
        assert "CMD_VEL_MAP_HALF_WIDTH_M=0.08" in nav_env


def test_anomaly_inspection_is_configurable_and_safe_by_default():
    start_nav = START_NAV.read_text(encoding="utf-8")
    assert "ENABLE_ANOMALY_INSPECTION:=0" in start_nav
    assert "anomaly_inspection_coordinator.py" in start_nav
    assert "INSPECTION_ONLY_WHEN_IDLE" in start_nav
    assert "INSPECTION_MIN_STANDOFF_M" in start_nav

    if STACK_NAV_ENV.exists():
        nav_env = STACK_NAV_ENV.read_text(encoding="utf-8")
        assert "ENABLE_ANOMALY_INSPECTION=0" in nav_env
        assert "INSPECTION_ONLY_WHEN_IDLE=true" in nav_env
        assert "INSPECTION_DEFAULT_STANDOFF_M=0.70" in nav_env
        assert "INSPECTION_REQUIRE_METRIC_DISTANCE=true" in nav_env


@pytest.mark.skipif(not STACK_ROOT.exists(), reason="Sibling stack directory is unavailable")
def test_stack_navigation_overrides_match_image_defaults():
    assert STACK_PARAMS.read_bytes() == DEFAULT_PARAMS.read_bytes()
    assert STACK_TREE.read_bytes() == DEFAULT_TREE.read_bytes()
    assert STACK_COLLISION.read_bytes() == DEFAULT_COLLISION.read_bytes()
