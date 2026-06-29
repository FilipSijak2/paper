from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
DEFAULT_PARAMS = REPO_ROOT / "nav_cont" / "nav2_params.yaml"
DEFAULT_TREE = REPO_ROOT / "nav_cont" / "navigate_to_pose_stable.xml"
STACK_PARAMS = STACK_ROOT / "config" / "containers" / "nav2_params.yaml"
STACK_TREE = STACK_ROOT / "config" / "containers" / "navigate_to_pose_stable.xml"


def test_navigation_detects_blocked_translation_without_penalizing_rotation():
    params = yaml.safe_load(DEFAULT_PARAMS.read_text(encoding="utf-8"))
    controller = params["controller_server"]["ros__parameters"]
    progress = controller["progress_checker"]

    assert progress["plugin"] == "nav2_controller::PoseProgressChecker"
    assert progress["required_movement_radius"] <= 0.04
    assert progress["required_movement_angle"] <= 0.10
    assert progress["movement_time_allowance"] <= 10.0


def test_follow_path_context_recovery_makes_room_before_retry():
    root = ElementTree.parse(DEFAULT_TREE).getroot()
    follow_recovery = root.find(".//RecoveryNode[@name='FollowPath']")

    assert follow_recovery is not None
    backup = follow_recovery.find(".//BackUp")
    assert backup is not None
    assert float(backup.attrib["backup_dist"]) >= 0.12
    assert float(backup.attrib["backup_speed"]) <= 0.025


def test_goal_tolerance_does_not_accept_large_visible_offset():
    params = yaml.safe_load(DEFAULT_PARAMS.read_text(encoding="utf-8"))
    controller = params["controller_server"]["ros__parameters"]

    assert controller["general_goal_checker"]["xy_goal_tolerance"] <= 0.12
    assert controller["general_goal_checker"]["yaw_goal_tolerance"] <= 0.30
    assert controller["FollowPath"]["xy_goal_tolerance"] <= 0.12


@pytest.mark.skipif(not STACK_ROOT.exists(), reason="Sibling stack directory is unavailable")
def test_stack_navigation_overrides_match_image_defaults():
    assert STACK_PARAMS.read_bytes() == DEFAULT_PARAMS.read_bytes()
    assert STACK_TREE.read_bytes() == DEFAULT_TREE.read_bytes()
