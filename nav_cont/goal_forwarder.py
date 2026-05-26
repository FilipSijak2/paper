#!/usr/bin/env python3
import rclpy
from action_msgs.msg import GoalStatus
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.duration import Duration
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Bool, String
from std_srvs.srv import SetBool
from tf2_ros import Buffer, TransformException, TransformListener

# Required for PoseStamped transform support registration.
import tf2_geometry_msgs  # noqa: F401

class GoalForwarder(Node):
    """Listens for simple PoseStamped goals (on a configurable topic) and forwards them to Nav2 NavigateToPose action.

    Expected use: user clicks a pose in a UI (Foxglove/RViz) publishing PoseStamped to /move_base_simple/goal (default),
    robot navigates there via Nav2 stack.
    """
    def __init__(self):
        super().__init__('goal_forwarder')
        goal_topic = self.declare_parameter('goal_topic', '/move_base_simple/goal').get_parameter_value().string_value
        self._target_frame = self.declare_parameter('target_frame', 'map').get_parameter_value().string_value
        self._transform_timeout_s = self.declare_parameter('transform_timeout_s', 0.3).get_parameter_value().double_value
        self._cancel_previous_goal = self.declare_parameter('cancel_previous_goal', True).get_parameter_value().bool_value
        self._stuck_recovery_threshold = self.declare_parameter('stuck_recovery_threshold', 2).get_parameter_value().integer_value
        self._stall_timeout_s = self.declare_parameter('stall_timeout_s', 4.0).get_parameter_value().double_value
        self._distance_stall_eps = self.declare_parameter('distance_stall_eps', 0.05).get_parameter_value().double_value
        anomaly_topic = self.declare_parameter(
            'anomaly_topic', '/navigation/anomaly_on_path'
        ).get_parameter_value().string_value
        anomaly_detail_topic = self.declare_parameter(
            'anomaly_detail_topic', '/navigation/anomaly_detail'
        ).get_parameter_value().string_value

        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._sub = self.create_subscription(PoseStamped, goal_topic, self.goal_cb, 10)
        self._anomaly_pub = self.create_publisher(Bool, anomaly_topic, 10)
        self._anomaly_detail_pub = self.create_publisher(String, anomaly_detail_topic, 10)
        self._set_manual_mode_client = self.create_client(SetBool, '/set_manual_mode')
        self._tf_buffer = Buffer(cache_time=Duration(seconds=10.0))
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._active_goal_handle = None
        self._anomaly_active = False
        self._anomaly_reason = ''
        self._last_distance_remaining = None
        self._last_distance_update_time = None
        self._last_recoveries = 0

        self.get_logger().info(
            f"GoalForwarder started. Subscribing {goal_topic} -> navigate_to_pose, "
            f"target_frame={self._target_frame}, anomaly_topic={anomaly_topic}"
        )
        self._set_anomaly(False, 'idle')

    def goal_cb(self, pose: PoseStamped):
        transformed_pose = self._to_target_frame(pose)
        if transformed_pose is None:
            self._set_anomaly(True, 'goal_transform_failed')
            return

        if not self._action_client.wait_for_server(timeout_sec=0.8):
            self.get_logger().warn('NavigateToPose action server not available yet')
            self._set_anomaly(True, 'navigate_to_pose_unavailable')
            return

        self._request_auto_mode()

        if self._cancel_previous_goal and self._active_goal_handle is not None:
            self.get_logger().warn('Canceling previous active goal before sending a new one.')
            self._active_goal_handle.cancel_goal_async()
            self._active_goal_handle = None

        goal = NavigateToPose.Goal()
        goal.pose = transformed_pose

        self._last_distance_remaining = None
        self._last_distance_update_time = self.get_clock().now()
        self._last_recoveries = 0
        self._set_anomaly(False, 'goal_sent')

        send_future = self._action_client.send_goal_async(goal, feedback_callback=self._feedback_cb)
        send_future.add_done_callback(self._goal_response)
        self.get_logger().info(
            f"Forwarded goal x={transformed_pose.pose.position.x:.2f} "
            f"y={transformed_pose.pose.position.y:.2f} frame={transformed_pose.header.frame_id}"
        )

    def _goal_response(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.get_logger().error(f'Failed to send goal: {exc}')
            self._set_anomaly(True, 'goal_send_failed')
            return

        if not goal_handle.accepted:
            self.get_logger().warn('Goal rejected by NavigateToPose server')
            self._set_anomaly(True, 'goal_rejected')
            return

        self._active_goal_handle = goal_handle
        self.get_logger().info('Goal accepted; waiting for result')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _feedback_cb(self, feedback_msg):
        fb = feedback_msg.feedback
        now = self.get_clock().now()

        distance_remaining = float(fb.distance_remaining)
        if (
            self._last_distance_remaining is None
            or abs(distance_remaining - self._last_distance_remaining) > self._distance_stall_eps
        ):
            self._last_distance_remaining = distance_remaining
            self._last_distance_update_time = now

        recoveries = int(fb.number_of_recoveries)
        if recoveries > self._last_recoveries:
            self._last_recoveries = recoveries
            self._set_anomaly(True, f'recovery_behavior_triggered count={recoveries}')

        if self._last_distance_update_time is not None:
            stalled_for = (now - self._last_distance_update_time).nanoseconds / 1e9
            if stalled_for > self._stall_timeout_s and recoveries >= self._stuck_recovery_threshold:
                self._set_anomaly(
                    True,
                    f'path_stalled stalled_for={stalled_for:.1f}s recoveries={recoveries} '
                    f'distance_remaining={distance_remaining:.2f}',
                )

    def _result_cb(self, future):
        self._active_goal_handle = None
        try:
            result = future.result()
            status = result.status
        except Exception as exc:
            self.get_logger().error(f'NavigateToPose result handling failed: {exc}')
            self._set_anomaly(True, 'goal_result_error')
            return

        if status == GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().info('Goal succeeded')
            self._set_anomaly(False, 'goal_succeeded')
        elif status == GoalStatus.STATUS_ABORTED:
            self.get_logger().warn('Goal aborted (likely obstacle/path blocked)')
            self._set_anomaly(True, 'goal_aborted')
        elif status == GoalStatus.STATUS_CANCELED:
            self.get_logger().warn('Goal canceled')
            self._set_anomaly(True, 'goal_canceled')
        else:
            self.get_logger().warn(f'Goal finished with status={status}')
            self._set_anomaly(True, f'goal_finished_status={status}')

    def _to_target_frame(self, pose: PoseStamped):
        if pose.header.frame_id == '':
            pose.header.frame_id = self._target_frame
            return pose

        if pose.header.frame_id == self._target_frame:
            return pose

        try:
            return self._tf_buffer.transform(
                pose, self._target_frame, timeout=Duration(seconds=self._transform_timeout_s)
            )
        except TransformException as exc:
            self.get_logger().warn(
                f"Could not transform goal from {pose.header.frame_id} to {self._target_frame}: {exc}"
            )
            return None

    def _request_auto_mode(self):
        if not self._set_manual_mode_client.service_is_ready():
            if not self._set_manual_mode_client.wait_for_service(timeout_sec=0.2):
                self.get_logger().warn('/set_manual_mode service not available; goal sent without mux auto switch')
                return

        req = SetBool.Request()
        req.data = False
        future = self._set_manual_mode_client.call_async(req)
        future.add_done_callback(self._auto_mode_response)

    def _auto_mode_response(self, future):
        try:
            res = future.result()
        except Exception as exc:
            self.get_logger().warn(f'Could not switch mux to auto mode: {exc}')
            return

        if res.success:
            self.get_logger().info('Mux switched to auto mode for navigation goal')
        else:
            self.get_logger().warn(f'Mux auto mode request failed: {res.message}')

    def _set_anomaly(self, active: bool, reason: str):
        if self._anomaly_active == active and self._anomaly_reason == reason:
            return

        self._anomaly_active = active
        self._anomaly_reason = reason

        bool_msg = Bool()
        bool_msg.data = active
        self._anomaly_pub.publish(bool_msg)

        detail_msg = String()
        detail_msg.data = reason
        self._anomaly_detail_pub.publish(detail_msg)


def main():
    rclpy.init()
    node = GoalForwarder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
