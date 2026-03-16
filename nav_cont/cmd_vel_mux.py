#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from std_srvs.srv import SetBool


class CmdVelMux(Node):
    def __init__(self):
        super().__init__('cmd_vel_mux')

        self.auto_topic = self.declare_parameter('auto_topic', '/cmd_vel_auto').get_parameter_value().string_value
        self.joy_topic = self.declare_parameter('joy_topic', '/cmd_vel_joy').get_parameter_value().string_value
        self.out_topic = self.declare_parameter('out_topic', '/cmd_vel').get_parameter_value().string_value
        self.manual_default = self.declare_parameter('manual_default', False).get_parameter_value().bool_value
        self.manual_timeout_s = self.declare_parameter('manual_timeout_s', 0.5).get_parameter_value().double_value
        self.auto_timeout_s = self.declare_parameter('auto_timeout_s', 0.7).get_parameter_value().double_value
        self.publish_rate_hz = self.declare_parameter('publish_rate_hz', 20.0).get_parameter_value().double_value

        self.manual_mode = self.manual_default
        self.last_auto = None
        self.last_auto_time = None
        self.last_joy = None
        self.last_joy_time = None
        self._auto_stale_warned = False
        self._joy_stale_warned = False

        self.pub = self.create_publisher(Twist, self.out_topic, 10)
        self.mode_pub = self.create_publisher(Bool, '/manual_mode', 10)

        self.create_subscription(Twist, self.auto_topic, self._auto_cb, 10)
        self.create_subscription(Twist, self.joy_topic, self._joy_cb, 10)

        self.create_service(SetBool, '/set_manual_mode', self._set_mode_cb)

        period = 1.0 / max(self.publish_rate_hz, 1e-3)
        self.timer = self.create_timer(period, self._publish_cb)

        self.get_logger().info(
            f"CmdVelMux started auto={self.auto_topic} joy={self.joy_topic} out={self.out_topic} "
            f"manual_default={self.manual_default} auto_timeout_s={self.auto_timeout_s} "
            f"manual_timeout_s={self.manual_timeout_s}"
        )
        self._publish_mode()

    def _auto_cb(self, msg: Twist):
        self.last_auto = msg
        self.last_auto_time = self.get_clock().now()
        self._auto_stale_warned = False

    def _joy_cb(self, msg: Twist):
        self.last_joy = msg
        self.last_joy_time = self.get_clock().now()
        self._joy_stale_warned = False

    def _set_mode_cb(self, req: SetBool.Request, res: SetBool.Response):
        self.manual_mode = bool(req.data)
        res.success = True
        res.message = 'manual' if self.manual_mode else 'auto'
        self.get_logger().info(f"Mode switched to {res.message}")
        self._publish_mode()
        return res

    def _publish_mode(self):
        msg = Bool()
        msg.data = self.manual_mode
        self.mode_pub.publish(msg)

    def _publish_cb(self):
        now = self.get_clock().now()
        out = Twist()

        if self.manual_mode:
            if self.last_joy is not None and self.last_joy_time is not None:
                age = (now - self.last_joy_time).nanoseconds / 1e9
                if age <= self.manual_timeout_s:
                    out = self.last_joy
                else:
                    if not self._joy_stale_warned:
                        self.get_logger().warn(
                            f"Manual cmd stale for {age:.2f}s (> {self.manual_timeout_s:.2f}s). Publishing stop."
                        )
                        self._joy_stale_warned = True
        else:
            if self.last_auto is not None and self.last_auto_time is not None:
                age = (now - self.last_auto_time).nanoseconds / 1e9
                if age <= self.auto_timeout_s:
                    out = self.last_auto
                else:
                    if not self._auto_stale_warned:
                        self.get_logger().warn(
                            f"Auto cmd stale for {age:.2f}s (> {self.auto_timeout_s:.2f}s). Publishing stop."
                        )
                        self._auto_stale_warned = True

        self.pub.publish(out)


def main():
    rclpy.init()
    node = CmdVelMux()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
