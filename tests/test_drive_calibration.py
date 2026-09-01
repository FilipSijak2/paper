import json
import math
from datetime import datetime

from nav_cont.drive_calibration_core import (
    Pose2D,
    Trial,
    calculate_result,
    repeated_trials,
    summarize,
    write_reports,
    yaw_from_quaternion,
)


def test_yaw_from_quaternion_returns_planar_heading():
    half = math.sqrt(0.5)
    assert math.isclose(yaw_from_quaternion(0.0, 0.0, half, half), math.pi / 2, abs_tol=1e-6)


def test_calculate_result_uses_start_frame_for_forward_and_lateral_motion():
    trial = Trial("forward", 0.08, 0.0, 2.0)
    result = calculate_result(
        "laminate",
        trial,
        Pose2D(1.0, 2.0, math.pi / 2),
        Pose2D(0.99, 2.16, math.pi / 2 + 0.02),
    )
    assert math.isclose(result.forward_m, 0.16, abs_tol=1e-9)
    assert math.isclose(result.lateral_m, 0.01, abs_tol=1e-9)
    assert math.isclose(result.measured_linear_mps, 0.08, abs_tol=1e-9)


def test_repeated_trials_include_both_turn_directions_and_requested_repeats():
    trials = repeated_trials(2.5, include_reverse=False, repeats=3)
    assert len(trials) == 30
    assert any(trial.angular_z > 0.0 for trial in trials)
    assert any(trial.angular_z < 0.0 for trial in trials)
    assert trials[0].name.endswith("_r1")
    assert trials[2].name.endswith("_r3")


def test_report_contains_results_and_summary(tmp_path):
    trial = Trial("forward_080_r1", 0.08, 0.0, 2.0)
    result = calculate_result("carpet", trial, Pose2D(0, 0, 0), Pose2D(0.12, 0.01, 0))
    csv_path, json_path = write_reports(
        tmp_path,
        "carpet",
        [result],
        {"surface": "carpet"},
        now=datetime(2026, 9, 1, 12, 0, 0),
    )
    assert csv_path.name == "drive-calibration-carpet-20260901-120000.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["results"][0]["trial"] == "forward_080_r1"
    assert summarize([result])["smallest_requested_forward_that_moved_mps"] == 0.08


def test_result_summarizes_signed_motor_pwm_samples():
    trial = Trial("turn", 0.0, 0.1, 2.0)
    result = calculate_result(
        "laminate",
        trial,
        Pose2D(0, 0, 0),
        Pose2D(0, 0, 0.2),
        motor_pwm_samples=[(-0.28, 0.28), (-0.30, 0.30)],
    )
    assert math.isclose(result.mean_left_motor_pwm, -0.29)
    assert math.isclose(result.mean_right_motor_pwm, 0.29)
    assert math.isclose(result.peak_abs_motor_pwm, 0.30)
