#!/usr/bin/env python3
"""Coordinate safe Nav2 approach and Jetson privacy capture handshakes."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import rclpy
from action_msgs.msg import GoalStatus, GoalStatusArray
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool

from inspection_geometry import (
    InspectionRequest,
    Point2D,
    compute_approach_pose,
    parse_inspection_request,
)


@dataclass
class ActiveInspection:
    request: InspectionRequest
    state: str
    deadline: float
    goal_handle: Any = None
    settle_until: float = 0.0
    fallback_reason: str = ""


class AnomalyInspectionCoordinator(Node):
    def __init__(self) -> None:
        super().__init__("anomaly_inspection_coordinator")
        self.enabled = self.declare_parameter(
            "enabled", True
        ).get_parameter_value().bool_value
        self.request_topic = self.declare_parameter(
            "request_topic", "/anomaly/inspection/request"
        ).get_parameter_value().string_value
        self.status_topic = self.declare_parameter(
            "status_topic", "/anomaly/inspection/status"
        ).get_parameter_value().string_value
        self.result_topic = self.declare_parameter(
            "result_topic", "/anomaly/inspection/result"
        ).get_parameter_value().string_value
        self.robot_pose_topic = self.declare_parameter(
            "robot_pose_topic", "/robot_pose_map"
        ).get_parameter_value().string_value
        self.manual_mode_topic = self.declare_parameter(
            "manual_mode_topic", "/manual_mode"
        ).get_parameter_value().string_value
        self.map_frame = self.declare_parameter(
            "map_frame", "map"
        ).get_parameter_value().string_value
        self.only_when_idle = self.declare_parameter(
            "only_when_idle", True
        ).get_parameter_value().bool_value
        self.navigation_timeout_s = max(
            5.0,
            self.declare_parameter(
                "navigation_timeout_s", 45.0
            ).get_parameter_value().double_value,
        )
        self.settle_time_s = max(
            0.0,
            self.declare_parameter(
                "settle_time_s", 1.0
            ).get_parameter_value().double_value,
        )
        self.capture_timeout_s = max(
            2.0,
            self.declare_parameter(
                "capture_timeout_s", 12.0
            ).get_parameter_value().double_value,
        )
        self.default_standoff_m = self.declare_parameter(
            "default_standoff_m", 0.70
        ).get_parameter_value().double_value
        self.min_standoff_m = self.declare_parameter(
            "min_standoff_m", 0.40
        ).get_parameter_value().double_value
        self.max_standoff_m = self.declare_parameter(
            "max_standoff_m", 1.20
        ).get_parameter_value().double_value
        self.max_uncertainty_m = self.declare_parameter(
            "max_uncertainty_m", 0.30
        ).get_parameter_value().double_value
        self.require_metric_distance = self.declare_parameter(
            "require_metric_distance", True
        ).get_parameter_value().bool_value
        self.capture_on_navigation_failure = self.declare_parameter(
            "capture_on_navigation_failure", True
        ).get_parameter_value().bool_value

        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.create_subscription(String, self.request_topic, self._request_cb, 10)
        self.create_subscription(String, self.result_topic, self._result_cb, 10)
        self.create_subscription(
            PoseStamped, self.robot_pose_topic, self._pose_cb, 10
        )
        self.create_subscription(
            Bool, self.manual_mode_topic, self._manual_mode_cb, 10
        )
        self.create_subscription(
            GoalStatusArray,
            "/navigate_to_pose/_action/status",
            self._nav_status_cb,
            10,
        )
        self.action_client = ActionClient(
            self, NavigateToPose, "navigate_to_pose"
        )
        self.set_manual_mode_client = self.create_client(
            SetBool, "/set_manual_mode"
        )
        self.timer = self.create_timer(0.1, self._timer_cb)

        self.latest_robot_position: Optional[Point2D] = None
        self.manual_mode = False
        self.manual_mode_known = False
        self.navigation_active = False
        self.active: Optional[ActiveInspection] = None
        self.get_logger().info(
            f"Inspection coordinator enabled={self.enabled} "
            f"request={self.request_topic} status={self.status_topic} "
            f"only_when_idle={self.only_when_idle}"
        )

    def _request_cb(self, msg: String) -> None:
        request_id = ""
        try:
            payload = json.loads(msg.data)
            request_id = str(payload.get("request_id") or "")
            request = parse_inspection_request(
                payload,
                default_standoff_m=self.default_standoff_m,
                min_standoff_m=self.min_standoff_m,
                max_standoff_m=self.max_standoff_m,
                require_metric_distance=self.require_metric_distance,
                max_uncertainty_m=self.max_uncertainty_m,
            )
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            self._publish_status(request_id, "rejected", f"invalid_request: {exc}")
            return

        if not self.enabled:
            self._publish_status(request.request_id, "rejected", "disabled")
            return
        if self.active is not None:
            self._publish_status(request.request_id, "rejected", "inspection_busy")
            return
        if not self.manual_mode_known:
            self._publish_status(
                request.request_id, "rejected", "manual_mode_unknown"
            )
            return
        if self.manual_mode:
            self._publish_status(request.request_id, "rejected", "manual_mode")
            return
        if self.only_when_idle and self.navigation_active:
            self._publish_status(
                request.request_id, "rejected", "navigation_busy"
            )
            return

        try:
            approach = compute_approach_pose(
                request, self.latest_robot_position
            )
        except ValueError as exc:
            if self.capture_on_navigation_failure:
                self._begin_fallback_capture(request, f"goal_geometry: {exc}")
            else:
                self._publish_status(request.request_id, "rejected", str(exc))
            return
        if not self.action_client.wait_for_server(timeout_sec=0.8):
            if self.capture_on_navigation_failure:
                self._begin_fallback_capture(
                    request, "navigate_to_pose_unavailable"
                )
            else:
                self._publish_status(
                    request.request_id,
                    "rejected",
                    "navigate_to_pose_unavailable",
                )
            return

        self.active = ActiveInspection(
            request=request,
            state="sending_goal",
            deadline=time.monotonic() + self.navigation_timeout_s,
        )
        self._request_auto_mode()
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = self.map_frame
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = approach.x
        goal.pose.pose.position.y = approach.y
        goal.pose.pose.orientation.z = math.sin(approach.yaw * 0.5)
        goal.pose.pose.orientation.w = math.cos(approach.yaw * 0.5)
        future = self.action_client.send_goal_async(
            goal, feedback_callback=self._feedback_cb
        )
        future.add_done_callback(self._goal_response_cb)
        self._publish_status(
            request.request_id,
            "accepted",
            "goal_sent",
            goal={
                "x": approach.x,
                "y": approach.y,
                "yaw": approach.yaw,
                "standoff_m": approach.distance_to_object_m,
            },
        )

    def _goal_response_cb(self, future: Any) -> None:
        active = self.active
        if active is None:
            return
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._navigation_failed_or_fallback(f"goal_send_failed: {exc}")
            return
        if active.state != "sending_goal":
            if goal_handle.accepted:
                goal_handle.cancel_goal_async()
            return
        if not goal_handle.accepted:
            self._navigation_failed_or_fallback("goal_rejected")
            return
        active.goal_handle = goal_handle
        active.state = "navigating"
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._goal_result_cb)
        self._publish_status(active.request.request_id, "navigating")

    def _goal_result_cb(self, future: Any) -> None:
        active = self.active
        if active is None or active.state != "navigating":
            return
        try:
            status = int(future.result().status)
        except Exception as exc:
            self._navigation_failed_or_fallback(f"goal_result_error: {exc}")
            return
        if status == GoalStatus.STATUS_SUCCEEDED:
            active.state = "settling"
            active.settle_until = time.monotonic() + self.settle_time_s
            active.deadline = active.settle_until + self.capture_timeout_s
            self._publish_status(active.request.request_id, "arrived")
        elif status == GoalStatus.STATUS_CANCELED:
            self._navigation_failed_or_fallback("navigation_canceled")
        else:
            self._navigation_failed_or_fallback(f"navigation_status_{status}")

    def _feedback_cb(self, _feedback_msg: Any) -> None:
        # Nav2 feedback keeps the action connection active; timeout is enforced
        # independently so a stalled approach cannot wait forever.
        return

    def _timer_cb(self) -> None:
        active = self.active
        if active is None:
            return
        now = time.monotonic()
        if active.state == "settling" and now >= active.settle_until:
            active.state = "waiting_capture"
            active.deadline = now + self.capture_timeout_s
            self._publish_status(
                active.request.request_id,
                "capture_requested",
                active.fallback_reason,
                fallback=bool(active.fallback_reason),
            )
            return
        if now < active.deadline:
            return
        if active.state in {"sending_goal", "navigating"}:
            self._cancel_active_goal()
            self._navigation_failed_or_fallback("navigation_timeout")
        elif active.state in {"settling", "waiting_capture"}:
            self._finish("capture_failed", "capture_result_timeout")

    def _result_cb(self, msg: String) -> None:
        active = self.active
        if active is None or active.state != "waiting_capture":
            return
        try:
            result = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return
        if str(result.get("request_id") or "") != active.request.request_id:
            return
        if bool(result.get("success")):
            self._finish(
                "completed",
                (
                    "fallback_privacy_capture_saved"
                    if active.fallback_reason
                    else "privacy_capture_saved"
                ),
                privacy_image=result.get("privacy_image"),
                sharpness_score=result.get("sharpness_score"),
                fallback=bool(active.fallback_reason),
                fallback_reason=active.fallback_reason,
            )
        else:
            self._finish(
                "capture_failed", str(result.get("reason") or "capture_failed")
            )

    def _pose_cb(self, msg: PoseStamped) -> None:
        self.latest_robot_position = Point2D(
            float(msg.pose.position.x), float(msg.pose.position.y)
        )

    def _manual_mode_cb(self, msg: Bool) -> None:
        self.manual_mode = bool(msg.data)
        self.manual_mode_known = True
        if self.manual_mode and self.active is not None:
            self._cancel_active_goal()
            self._finish("canceled", "manual_override")

    def _nav_status_cb(self, msg: GoalStatusArray) -> None:
        if self.active is not None:
            return
        active_statuses = {
            GoalStatus.STATUS_ACCEPTED,
            GoalStatus.STATUS_EXECUTING,
            GoalStatus.STATUS_CANCELING,
        }
        self.navigation_active = any(
            int(item.status) in active_statuses for item in msg.status_list
        )

    def _request_auto_mode(self) -> None:
        if not self.set_manual_mode_client.service_is_ready():
            if not self.set_manual_mode_client.wait_for_service(timeout_sec=0.2):
                return
        request = SetBool.Request()
        request.data = False
        self.set_manual_mode_client.call_async(request)

    def _cancel_active_goal(self) -> None:
        if self.active is not None and self.active.goal_handle is not None:
            self.active.goal_handle.cancel_goal_async()

    def _navigation_failed_or_fallback(self, reason: str) -> None:
        active = self.active
        if active is None:
            return
        if self.capture_on_navigation_failure and not self.manual_mode:
            self._begin_fallback_capture(active.request, reason)
        else:
            self._finish("failed", reason)

    def _begin_fallback_capture(
        self,
        request: InspectionRequest,
        reason: str,
    ) -> None:
        now = time.monotonic()
        if self.active is None:
            self.active = ActiveInspection(
                request=request,
                state="settling",
                deadline=now + self.settle_time_s + self.capture_timeout_s,
            )
        active = self.active
        active.state = "settling"
        active.goal_handle = None
        active.fallback_reason = reason
        active.settle_until = now + self.settle_time_s
        active.deadline = active.settle_until + self.capture_timeout_s
        self._publish_status(
            request.request_id,
            "fallback_capture",
            reason,
            fallback=True,
        )

    def _finish(self, state: str, reason: str, **extra: Any) -> None:
        active = self.active
        if active is None:
            return
        request_id = active.request.request_id
        self.active = None
        self._publish_status(request_id, state, reason, **extra)

    def _publish_status(
        self,
        request_id: str,
        state: str,
        reason: str = "",
        **extra: Any,
    ) -> None:
        payload: Dict[str, Any] = {
            "request_id": request_id,
            "state": state,
            "reason": reason,
            "timestamp": time.time(),
        }
        payload.update(extra)
        message = String()
        message.data = json.dumps(payload, separators=(",", ":"))
        self.status_pub.publish(message)
        self.get_logger().info(
            f"Inspection {request_id or '-'} state={state} "
            f"reason={reason or '-'}"
        )


def main() -> None:
    rclpy.init()
    node = AnomalyInspectionCoordinator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
