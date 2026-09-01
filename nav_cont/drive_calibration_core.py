"""Pure calculation and reporting helpers for drive calibration."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class Trial:
    name: str
    linear_x: float
    angular_z: float
    duration_s: float


@dataclass
class Result:
    surface: str
    trial: str
    requested_linear_mps: float
    requested_angular_rps: float
    duration_s: float
    forward_m: float
    lateral_m: float
    path_m: float
    yaw_rad: float
    yaw_deg: float
    measured_linear_mps: float
    measured_angular_rps: float
    linear_response_ratio: float | None
    angular_response_ratio: float | None
    passed_motion_threshold: bool
    mean_left_motor_pwm: float | None
    mean_right_motor_pwm: float | None
    peak_abs_motor_pwm: float | None


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def calculate_result(
    surface: str,
    trial: Trial,
    start: Pose2D,
    end: Pose2D,
    motor_pwm_samples: list[tuple[float, float]] | None = None,
) -> Result:
    dx = end.x - start.x
    dy = end.y - start.y
    cos_yaw = math.cos(start.yaw)
    sin_yaw = math.sin(start.yaw)
    forward = dx * cos_yaw + dy * sin_yaw
    lateral = -dx * sin_yaw + dy * cos_yaw
    yaw_delta = normalize_angle(end.yaw - start.yaw)
    path = math.hypot(dx, dy)
    measured_linear = forward / trial.duration_s
    measured_angular = yaw_delta / trial.duration_s
    linear_ratio = measured_linear / trial.linear_x if abs(trial.linear_x) > 1e-6 else None
    angular_ratio = measured_angular / trial.angular_z if abs(trial.angular_z) > 1e-6 else None
    moved = path >= 0.015 or abs(yaw_delta) >= math.radians(3.0)
    samples = motor_pwm_samples or []
    mean_left_pwm = sum(sample[0] for sample in samples) / len(samples) if samples else None
    mean_right_pwm = sum(sample[1] for sample in samples) / len(samples) if samples else None
    peak_pwm = (
        max(max(abs(sample[0]), abs(sample[1])) for sample in samples)
        if samples
        else None
    )
    return Result(
        surface=surface,
        trial=trial.name,
        requested_linear_mps=trial.linear_x,
        requested_angular_rps=trial.angular_z,
        duration_s=trial.duration_s,
        forward_m=forward,
        lateral_m=lateral,
        path_m=path,
        yaw_rad=yaw_delta,
        yaw_deg=math.degrees(yaw_delta),
        measured_linear_mps=measured_linear,
        measured_angular_rps=measured_angular,
        linear_response_ratio=linear_ratio,
        angular_response_ratio=angular_ratio,
        passed_motion_threshold=moved,
        mean_left_motor_pwm=mean_left_pwm,
        mean_right_motor_pwm=mean_right_pwm,
        peak_abs_motor_pwm=peak_pwm,
    )


def default_trials(duration_s: float, include_reverse: bool) -> list[Trial]:
    trials = [
        Trial("forward_020", 0.02, 0.0, duration_s),
        Trial("forward_040", 0.04, 0.0, duration_s),
        Trial("forward_060", 0.06, 0.0, duration_s),
        Trial("forward_080", 0.08, 0.0, duration_s),
        Trial("rotate_left_040", 0.0, 0.04, duration_s),
        Trial("rotate_left_070", 0.0, 0.07, duration_s),
        Trial("rotate_left_100", 0.0, 0.10, duration_s),
        Trial("rotate_right_040", 0.0, -0.04, duration_s),
        Trial("rotate_right_070", 0.0, -0.07, duration_s),
        Trial("rotate_right_100", 0.0, -0.10, duration_s),
    ]
    if include_reverse:
        trials.extend(
            [
                Trial("reverse_030", -0.03, 0.0, duration_s),
                Trial("reverse_060", -0.06, 0.0, duration_s),
            ]
        )
    return trials


def repeated_trials(duration_s: float, include_reverse: bool, repeats: int) -> list[Trial]:
    return [
        Trial(f"{trial.name}_r{repeat}", trial.linear_x, trial.angular_z, trial.duration_s)
        for trial in default_trials(duration_s, include_reverse)
        for repeat in range(1, repeats + 1)
    ]


def mean_ratio(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None and math.isfinite(value)]
    return sum(valid) / len(valid) if valid else None


def summarize(results: list[Result]) -> dict:
    linear = [r for r in results if abs(r.requested_linear_mps) > 1e-6]
    forward = [r for r in linear if r.requested_linear_mps > 0.0]
    left = [r for r in results if r.requested_angular_rps > 0.0]
    right = [r for r in results if r.requested_angular_rps < 0.0]

    def first_motion(items: list[Result], field: str) -> float | None:
        moving = [item for item in items if item.passed_motion_threshold]
        return min((abs(getattr(item, field)) for item in moving), default=None)

    return {
        "smallest_requested_forward_that_moved_mps": first_motion(forward, "requested_linear_mps"),
        "smallest_requested_left_rotation_that_moved_rps": first_motion(left, "requested_angular_rps"),
        "smallest_requested_right_rotation_that_moved_rps": first_motion(right, "requested_angular_rps"),
        "max_abs_lateral_error_m": max((abs(r.lateral_m) for r in forward), default=0.0),
        "mean_forward_response_ratio": mean_ratio([r.linear_response_ratio for r in forward]),
        "mean_left_rotation_response_ratio": mean_ratio([r.angular_response_ratio for r in left]),
        "mean_right_rotation_response_ratio": mean_ratio([r.angular_response_ratio for r in right]),
    }


def write_reports(
    output_dir: Path,
    surface: str,
    results: list[Result],
    metadata: dict,
    now: datetime | None = None,
) -> tuple[Path, Path]:
    if not results:
        raise ValueError("at least one calibration result is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    base = output_dir / f"drive-calibration-{surface}-{stamp}"
    csv_path = base.with_suffix(".csv")
    json_path = base.with_suffix(".json")
    rows = [asdict(result) for result in results]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    json_path.write_text(
        json.dumps({"metadata": metadata, "results": rows, "summary": summarize(results)}, indent=2),
        encoding="utf-8",
    )
    return csv_path, json_path
