import importlib.util
import math
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "nav_cont"
    / "inspection_geometry.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("inspection_geometry", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_payload():
    return {
        "request_id": "inspect_1",
        "cluster_id": "cluster_1",
        "label": "bottle",
        "object_pose_map": {"x": 2.0, "y": 0.0},
        "robot_pose_map": {"x": 0.0, "y": 0.0},
        "localization": {
            "distance_source": "depth",
            "distance_uncertainty_m": 0.08,
        },
        "standoff_m": 0.70,
    }


def test_approach_goal_stays_before_object_and_faces_it():
    module = load_module()
    request = module.parse_inspection_request(valid_payload())
    approach = module.compute_approach_pose(request)

    assert approach.x == pytest.approx(1.30)
    assert approach.y == pytest.approx(0.0)
    assert approach.yaw == pytest.approx(0.0)
    assert math.hypot(2.0 - approach.x, approach.y) == pytest.approx(0.70)


def test_approach_uses_current_robot_side_of_object():
    module = load_module()
    request = module.parse_inspection_request(valid_payload())
    approach = module.compute_approach_pose(
        request, module.Point2D(x=3.0, y=0.0)
    )

    assert approach.x == pytest.approx(2.70)
    assert abs(abs(approach.yaw) - math.pi) < 1e-6


def test_request_rejects_non_metric_or_uncertain_localization():
    module = load_module()
    payload = valid_payload()
    payload["localization"]["distance_source"] = "default"
    with pytest.raises(ValueError, match="depth or laser"):
        module.parse_inspection_request(payload)

    payload["localization"]["distance_source"] = "depth"
    payload["localization"]["distance_uncertainty_m"] = 0.8
    with pytest.raises(ValueError, match="exceeds limit"):
        module.parse_inspection_request(payload)
