#!/usr/bin/env python3
"""Pure geometry and validation helpers for autonomous anomaly inspection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class InspectionRequest:
    request_id: str
    cluster_id: str
    label: str
    object_position: Point2D
    observed_robot_position: Point2D
    standoff_m: float
    distance_source: str
    uncertainty_m: Optional[float]


@dataclass(frozen=True)
class ApproachPose:
    x: float
    y: float
    yaw: float
    distance_to_object_m: float


def parse_inspection_request(
    payload: Dict[str, Any],
    *,
    default_standoff_m: float = 0.70,
    min_standoff_m: float = 0.40,
    max_standoff_m: float = 1.20,
    require_metric_distance: bool = True,
    max_uncertainty_m: float = 0.30,
) -> InspectionRequest:
    request_id = str(payload.get("request_id") or "").strip()
    cluster_id = str(payload.get("cluster_id") or "").strip()
    label = str(payload.get("label") or "").strip()
    if not request_id or not cluster_id or not label:
        raise ValueError("request_id, cluster_id and label are required")

    object_pose = payload.get("object_pose_map") or {}
    robot_pose = payload.get("robot_pose_map") or {}
    localization = payload.get("localization") or {}
    object_position = Point2D(float(object_pose["x"]), float(object_pose["y"]))
    robot_position = Point2D(float(robot_pose["x"]), float(robot_pose["y"]))
    if not all(
        math.isfinite(value)
        for value in (
            object_position.x,
            object_position.y,
            robot_position.x,
            robot_position.y,
        )
    ):
        raise ValueError("inspection coordinates must be finite")

    source = str(localization.get("distance_source") or "")
    uncertainty_raw = localization.get("distance_uncertainty_m")
    uncertainty = (
        float(uncertainty_raw) if uncertainty_raw is not None else None
    )
    if require_metric_distance and source not in {"depth", "laser"}:
        raise ValueError("inspection requires depth or laser distance")
    if uncertainty is None or not math.isfinite(uncertainty):
        raise ValueError("inspection requires a finite distance uncertainty")
    if uncertainty > max(0.0, float(max_uncertainty_m)):
        raise ValueError(
            f"distance uncertainty {uncertainty:.3f} m exceeds limit"
        )

    standoff = float(payload.get("standoff_m", default_standoff_m))
    standoff = max(float(min_standoff_m), min(float(max_standoff_m), standoff))
    return InspectionRequest(
        request_id=request_id,
        cluster_id=cluster_id,
        label=label,
        object_position=object_position,
        observed_robot_position=robot_position,
        standoff_m=standoff,
        distance_source=source,
        uncertainty_m=uncertainty,
    )


def compute_approach_pose(
    request: InspectionRequest,
    current_robot_position: Optional[Point2D] = None,
) -> ApproachPose:
    """Place the robot on the observation ray and orient it toward the object."""
    robot = current_robot_position or request.observed_robot_position
    dx = request.object_position.x - robot.x
    dy = request.object_position.y - robot.y
    distance = math.hypot(dx, dy)
    if distance < 1e-4:
        raise ValueError("robot and object positions are indistinguishable")

    if distance <= request.standoff_m:
        return ApproachPose(
            x=robot.x,
            y=robot.y,
            yaw=math.atan2(dy, dx),
            distance_to_object_m=distance,
        )

    unit_x = dx / distance
    unit_y = dy / distance
    goal_x = request.object_position.x - request.standoff_m * unit_x
    goal_y = request.object_position.y - request.standoff_m * unit_y
    yaw = math.atan2(
        request.object_position.y - goal_y,
        request.object_position.x - goal_x,
    )
    return ApproachPose(
        x=goal_x,
        y=goal_y,
        yaw=yaw,
        distance_to_object_m=request.standoff_m,
    )
