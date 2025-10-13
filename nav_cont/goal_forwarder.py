#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose


def yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.z = math.sin(yaw / 2.0)
    q.w = math.cos(yaw / 2.0)
    return q

class GoalForwarder(Node):
    """Listens for simple PoseStamped goals (on a configurable topic) and forwards them to Nav2 NavigateToPose action.

    Expected use: user clicks a pose in a UI (Foxglove/RViz) publishing PoseStamped to /simple_goal (default),
    robot navigates there via Nav2 stack.
    """
    def __init__(self):
        super().__init__('goal_forwarder')
        goal_topic = self.declare_parameter('goal_topic', '/simple_goal').get_parameter_value().string_value
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._sub = self.create_subscription(PoseStamped, goal_topic, self.goal_cb, 10)
        self.get_logger().info(f"GoalForwarder started. Subscribing on {goal_topic} -> navigate_to_pose action")

    def goal_cb(self, pose: PoseStamped):
        if not self._action_client.wait_for_server(timeout_sec=0.5):
            self.get_logger().warn('NavigateToPose action server not available yet')
            return
        goal = NavigateToPose.Goal()
        # Ensure frame is map; if not, just warn (TF transform could be added later)
        if pose.header.frame_id != 'map':
            self.get_logger().warn(f"Incoming goal frame_id={pose.header.frame_id} (expected 'map'); sending as-is")
        goal.pose = pose
        send_future = self._action_client.send_goal_async(goal)
        send_future.add_done_callback(self._goal_response)
        self.get_logger().info(f"Forwarded goal x={pose.pose.position.x:.2f} y={pose.pose.position.y:.2f}")

    def _goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Goal rejected by NavigateToPose server')
            return
        self.get_logger().info('Goal accepted; waiting for result')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._result_cb)

    def _result_cb(self, future):
        status = future.result().status
        if status == 4:  # SUCCEEDED
            self.get_logger().info('Goal succeeded')
        else:
            self.get_logger().warn(f'Goal finished with status={status}')


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
