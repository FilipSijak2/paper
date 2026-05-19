#!/usr/bin/env python3
"""Safety filter for velocity commands before they reach the robot bridge.

Purpose:
    - Preserve normal forward and in-place/forward-arc motion.
    - Allow reverse motion only as straight reverse.
    - Limit maximum reverse speed.
    - Publish debug information when a command is modified.

Suggested command chain:
    Nav2 /cmd_vel_auto
      -> cmd_vel_mux
      -> cmd_vel_safety_filter
      -> robot_bridge /cmd_vel
"""

import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def filter_cmd_vel(
    msg: Twist,
    *,
    reverse_max_speed: float = 0.08,
    forbid_reverse_turning: bool = True,
    angular_deadband: float = 1e-4,
) -> tuple[Twist, bool, str]:
    """Return a filtered Twist and metadata.

    Reverse motion is allowed, but if linear.x is negative and reverse turning is
    forbidden, angular.z is forced to zero. Reverse speed is clamped to
    -reverse_max_speed.
    """

    out = Twist()
    out.linear.x = float(msg.linear.x)
    out.linear.y = float(msg.linear.y)
    out.linear.z = float(msg.linear.z)
    out.angular.x = float(msg.angular.x)
    out.angular.y = float(msg.angular.y)
    out.angular.z = float(msg.angular.z)

    modified = False
    reasons: list[str] = []

    reverse_max_speed = abs(float(reverse_max_speed))
    if out.linear.x < 0.0:
        limited = clamp(out.linear.x, -reverse_max_speed, 0.0)
        if not math.isclose(limited, out.linear.x, rel_tol=0.0, abs_tol=1e-9):
            out.linear.x = limited
            modified = True
            reasons.append("reverse_speed_limited")

        if forbid_reverse_turning and abs(out.angular.z) > angular_deadband:
            out.angular.z = 0.0
            modified = True
            reasons.append("reverse_turn_blocked")

    return out, modified, ",".join(reasons) if reasons else "unchanged"


class CmdVelSafetyFilter(Node):
    def __init__(self):
        super().__init__("cmd_vel_safety_filter")

        self.input_topic = self.declare_parameter("input_topic", "/cmd_vel_muxed").get_parameter_value().string_value
        self.output_topic = self.declare_parameter("output_topic", "/cmd_vel").get_parameter_value().string_value
        self.status_topic = self.declare_parameter("status_topic", "/cmd_vel_safety_status").get_parameter_value().string_value
        self.reverse_max_speed = self.declare_parameter("reverse_max_speed", 0.08).get_parameter_value().double_value
        self.forbid_reverse_turning = self.declare_parameter("forbid_reverse_turning", True).get_parameter_value().bool_value
        self.angular_deadband = self.declare_parameter("angular_deadband", 1e-4).get_parameter_value().double_value
        self.publish_unchanged_status = self.declare_parameter("publish_unchanged_status", False).get_parameter_value().bool_value

        self.pub = self.create_publisher(Twist, self.output_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.create_subscription(Twist, self.input_topic, self._cmd_cb, 10)

        self.get_logger().info(
            "CmdVelSafetyFilter started "
            f"input={self.input_topic} output={self.output_topic} reverse_max_speed={self.reverse_max_speed:.3f} "
            f"forbid_reverse_turning={self.forbid_reverse_turning} angular_deadband={self.angular_deadband:.6f}"
        )

    def _cmd_cb(self, msg: Twist):
        out, modified, reason = filter_cmd_vel(
            msg,
            reverse_max_speed=self.reverse_max_speed,
            forbid_reverse_turning=self.forbid_reverse_turning,
            angular_deadband=self.angular_deadband,
        )
        self.pub.publish(out)

        if modified or self.publish_unchanged_status:
            status = String()
            status.data = (
                f"CMD_VEL_SAFETY modified={1 if modified else 0} reason={reason} "
                f"in_linear_x={msg.linear.x:.3f} in_angular_z={msg.angular.z:.3f} "
                f"out_linear_x={out.linear.x:.3f} out_angular_z={out.angular.z:.3f}"
            )
            self.status_pub.publish(status)


def main():
    rclpy.init()
    node = CmdVelSafetyFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
