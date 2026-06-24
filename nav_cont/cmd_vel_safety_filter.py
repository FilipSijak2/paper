#!/usr/bin/env python3
"""Safety filter for velocity commands before they reach the robot bridge.

Purpose:
    - Preserve normal forward and in-place/forward-arc motion.
    - Allow reverse motion, including reverse arcs.
    - Optionally limit maximum forward speed.
    - Optionally limit maximum reverse speed.
    - Optionally limit maximum angular speed.
    - Publish debug information when a command is modified.

Suggested command chain:
    Nav2 /cmd_vel_auto
      -> cmd_vel_mux
      -> cmd_vel_safety_filter
      -> robot_bridge /cmd_vel
"""

import math
import time

import rclpy
from geometry_msgs.msg import Twist
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_quaternion(q) -> float:
    return math.atan2(
        2.0 * (q.w * q.z + q.x * q.y),
        1.0 - 2.0 * (q.y * q.y + q.z * q.z),
    )


def copy_twist(msg: Twist) -> Twist:
    out = Twist()
    out.linear.x = float(msg.linear.x)
    out.linear.y = float(msg.linear.y)
    out.linear.z = float(msg.linear.z)
    out.angular.x = float(msg.angular.x)
    out.angular.y = float(msg.angular.y)
    out.angular.z = float(msg.angular.z)
    return out


def filter_cmd_vel(
    msg: Twist,
    *,
    forward_max_speed: float = 0.0,
    reverse_max_speed: float = 0.22,
    angular_max_speed: float = 0.0,
    forbid_reverse_turning: bool = False,
    angular_deadband: float = 1e-4,
) -> tuple[Twist, bool, str]:
    """Return a filtered Twist and metadata.

    If ``forward_max_speed`` is positive, forward speed is clamped to that
    value. Reverse motion is allowed. If ``reverse_max_speed`` is positive,
    reverse speed is clamped to ``-reverse_max_speed``. If
    ``angular_max_speed`` is positive, angular speed is clamped symmetrically.
    A legacy
    straight-reverse-only mode remains available through
    ``forbid_reverse_turning``.
    """

    out = copy_twist(msg)

    modified = False
    reasons: list[str] = []

    forward_max_speed = abs(float(forward_max_speed))
    if forward_max_speed > 0.0 and out.linear.x > forward_max_speed:
        out.linear.x = forward_max_speed
        modified = True
        reasons.append("forward_speed_limited")

    reverse_max_speed = abs(float(reverse_max_speed))
    if out.linear.x < 0.0:
        if reverse_max_speed > 0.0:
            limited = clamp(out.linear.x, -reverse_max_speed, 0.0)
            if not math.isclose(limited, out.linear.x, rel_tol=0.0, abs_tol=1e-9):
                out.linear.x = limited
                modified = True
                reasons.append("reverse_speed_limited")

        if forbid_reverse_turning and abs(out.angular.z) > angular_deadband:
            out.angular.z = 0.0
            modified = True
            reasons.append("reverse_turn_blocked")

    angular_max_speed = abs(float(angular_max_speed))
    if angular_max_speed > 0.0:
        limited = clamp(out.angular.z, -angular_max_speed, angular_max_speed)
        if not math.isclose(limited, out.angular.z, rel_tol=0.0, abs_tol=1e-9):
            out.angular.z = limited
            modified = True
            reasons.append("angular_speed_limited")

    return out, modified, ",".join(reasons) if reasons else "unchanged"


def scan_sector_blocked(
    scan: LaserScan,
    *,
    distance_m: float,
    half_angle_rad: float,
    front: bool,
    min_points: int = 1,
) -> bool:
    if scan is None or distance_m <= 0.0 or half_angle_rad <= 0.0:
        return False

    hits = 0
    for idx, rng in enumerate(scan.ranges):
        if not math.isfinite(float(rng)):
            continue
        rng = float(rng)
        if rng <= 0.0 or rng > distance_m:
            continue
        if scan.range_min > 0.0 and rng < scan.range_min:
            continue
        if scan.range_max > 0.0 and rng > scan.range_max:
            continue

        angle = normalize_angle(float(scan.angle_min) + idx * float(scan.angle_increment))
        in_sector = abs(angle) <= half_angle_rad if front else abs(abs(angle) - math.pi) <= half_angle_rad
        if in_sector:
            hits += 1
            if hits >= min_points:
                return True
    return False


def occupancy_value_at(grid: OccupancyGrid, world_x: float, world_y: float) -> int | None:
    info = grid.info
    resolution = float(info.resolution)
    if resolution <= 0.0 or info.width <= 0 or info.height <= 0:
        return None

    origin = info.origin
    origin_x = float(origin.position.x)
    origin_y = float(origin.position.y)
    origin_yaw = yaw_from_quaternion(origin.orientation)

    dx = float(world_x) - origin_x
    dy = float(world_y) - origin_y
    cos_yaw = math.cos(-origin_yaw)
    sin_yaw = math.sin(-origin_yaw)
    map_x_m = dx * cos_yaw - dy * sin_yaw
    map_y_m = dx * sin_yaw + dy * cos_yaw

    mx = int(math.floor(map_x_m / resolution))
    my = int(math.floor(map_y_m / resolution))
    if mx < 0 or my < 0 or mx >= int(info.width) or my >= int(info.height):
        return None
    return int(grid.data[my * int(info.width) + mx])


def map_motion_blocked(
    grid: OccupancyGrid,
    pose_msg: PoseWithCovarianceStamped,
    *,
    linear_x: float,
    lookahead_m: float,
    half_width_m: float,
    occupied_threshold: int = 65,
    unknown_is_obstacle: bool = False,
    linear_deadband: float = 1e-3,
) -> bool:
    if grid is None or pose_msg is None or abs(linear_x) <= linear_deadband:
        return False

    pose = pose_msg.pose.pose
    heading = yaw_from_quaternion(pose.orientation)
    direction = 1.0 if linear_x > 0.0 else -1.0
    lookahead_m = max(0.05, float(lookahead_m))
    half_width_m = max(0.0, float(half_width_m))

    distances = [min(0.12, lookahead_m), lookahead_m]
    if lookahead_m > 0.20:
        distances.insert(1, 0.5 * (0.12 + lookahead_m))
    offsets = [-half_width_m, 0.0, half_width_m] if half_width_m > 0.0 else [0.0]

    cos_h = math.cos(heading)
    sin_h = math.sin(heading)
    for dist in distances:
        for offset in offsets:
            sample_x = float(pose.position.x) + direction * dist * cos_h - offset * sin_h
            sample_y = float(pose.position.y) + direction * dist * sin_h + offset * cos_h
            value = occupancy_value_at(grid, sample_x, sample_y)
            if value is None:
                return True
            if value < 0:
                if unknown_is_obstacle:
                    return True
            elif value >= occupied_threshold:
                return True
    return False


class CmdVelSafetyFilter(Node):
    def __init__(self):
        super().__init__("cmd_vel_safety_filter")

        self.input_topic = self.declare_parameter("input_topic", "/cmd_vel_muxed").get_parameter_value().string_value
        self.output_topic = self.declare_parameter("output_topic", "/cmd_vel").get_parameter_value().string_value
        self.status_topic = self.declare_parameter("status_topic", "/cmd_vel_safety_status").get_parameter_value().string_value
        self.forward_max_speed = self.declare_parameter("forward_max_speed", 0.08).get_parameter_value().double_value
        self.reverse_max_speed = self.declare_parameter("reverse_max_speed", 0.06).get_parameter_value().double_value
        self.angular_max_speed = self.declare_parameter("angular_max_speed", 0.25).get_parameter_value().double_value
        self.forbid_reverse_turning = self.declare_parameter("forbid_reverse_turning", False).get_parameter_value().bool_value
        self.angular_deadband = self.declare_parameter("angular_deadband", 1e-4).get_parameter_value().double_value
        self.publish_unchanged_status = self.declare_parameter("publish_unchanged_status", False).get_parameter_value().bool_value
        self.linear_deadband = self.declare_parameter("linear_deadband", 0.01).get_parameter_value().double_value

        self.scan_stop_enabled = self.declare_parameter("scan_stop_enabled", False).get_parameter_value().bool_value
        self.scan_topic = self.declare_parameter("scan_topic", "/scan_filtered").get_parameter_value().string_value
        self.front_stop_distance = self.declare_parameter("front_stop_distance", 0.24).get_parameter_value().double_value
        self.rear_stop_distance = self.declare_parameter("rear_stop_distance", 0.20).get_parameter_value().double_value
        self.scan_half_angle_deg = self.declare_parameter("scan_half_angle_deg", 14.0).get_parameter_value().double_value
        self.scan_min_points = self.declare_parameter("scan_min_points", 5).get_parameter_value().integer_value
        self.scan_stale_timeout_s = self.declare_parameter("scan_stale_timeout_s", 0.6).get_parameter_value().double_value

        self.map_stop_enabled = self.declare_parameter("map_stop_enabled", False).get_parameter_value().bool_value
        self.map_topic = self.declare_parameter("map_topic", "/map").get_parameter_value().string_value
        self.pose_topic = self.declare_parameter("pose_topic", "/amcl_pose").get_parameter_value().string_value
        self.map_lookahead_m = self.declare_parameter("map_lookahead_m", 0.22).get_parameter_value().double_value
        self.map_half_width_m = self.declare_parameter("map_half_width_m", 0.10).get_parameter_value().double_value
        self.map_occupied_threshold = self.declare_parameter("map_occupied_threshold", 65).get_parameter_value().integer_value
        self.map_unknown_is_obstacle = self.declare_parameter("map_unknown_is_obstacle", False).get_parameter_value().bool_value
        self.map_pose_stale_timeout_s = self.declare_parameter("map_pose_stale_timeout_s", 2.0).get_parameter_value().double_value

        self.last_scan = None
        self.last_scan_time = 0.0
        self.last_map = None
        self.last_pose = None
        self.last_pose_time = 0.0

        self.pub = self.create_publisher(Twist, self.output_topic, 10)
        self.status_pub = self.create_publisher(String, self.status_topic, 10)
        self.create_subscription(Twist, self.input_topic, self._cmd_cb, 10)
        if self.scan_stop_enabled:
            self.create_subscription(LaserScan, self.scan_topic, self._scan_cb, 10)
        if self.map_stop_enabled:
            self.create_subscription(OccupancyGrid, self.map_topic, self._map_cb, 1)
            self.create_subscription(PoseWithCovarianceStamped, self.pose_topic, self._pose_cb, 10)

        self.get_logger().info(
            "CmdVelSafetyFilter started "
            f"input={self.input_topic} output={self.output_topic} forward_max_speed={self.forward_max_speed:.3f} "
            f"reverse_max_speed={self.reverse_max_speed:.3f} "
            f"angular_max_speed={self.angular_max_speed:.3f} "
            f"forbid_reverse_turning={self.forbid_reverse_turning} angular_deadband={self.angular_deadband:.6f} "
            f"scan_stop_enabled={self.scan_stop_enabled} map_stop_enabled={self.map_stop_enabled}"
        )

    def _scan_cb(self, msg: LaserScan):
        self.last_scan = msg
        self.last_scan_time = time.monotonic()

    def _map_cb(self, msg: OccupancyGrid):
        self.last_map = msg

    def _pose_cb(self, msg: PoseWithCovarianceStamped):
        self.last_pose = msg
        self.last_pose_time = time.monotonic()

    def _obstacle_reasons(self, out: Twist) -> list[str]:
        reasons: list[str] = []
        now = time.monotonic()

        if self.scan_stop_enabled and self.last_scan is not None and now - self.last_scan_time <= self.scan_stale_timeout_s:
            half_angle = math.radians(self.scan_half_angle_deg)
            if out.linear.x > self.linear_deadband and scan_sector_blocked(
                self.last_scan,
                distance_m=self.front_stop_distance,
                half_angle_rad=half_angle,
                front=True,
                min_points=max(1, int(self.scan_min_points)),
            ):
                reasons.append("front_scan_blocked")
            if out.linear.x < -self.linear_deadband and scan_sector_blocked(
                self.last_scan,
                distance_m=self.rear_stop_distance,
                half_angle_rad=half_angle,
                front=False,
                min_points=max(1, int(self.scan_min_points)),
            ):
                reasons.append("rear_scan_blocked")

        if (
            self.map_stop_enabled
            and self.last_map is not None
            and self.last_pose is not None
            and now - self.last_pose_time <= self.map_pose_stale_timeout_s
        ):
            if map_motion_blocked(
                self.last_map,
                self.last_pose,
                linear_x=out.linear.x,
                lookahead_m=self.map_lookahead_m,
                half_width_m=self.map_half_width_m,
                occupied_threshold=int(self.map_occupied_threshold),
                unknown_is_obstacle=bool(self.map_unknown_is_obstacle),
                linear_deadband=self.linear_deadband,
            ):
                reasons.append("map_blocked")

        return reasons

    def _cmd_cb(self, msg: Twist):
        out, modified, reason = filter_cmd_vel(
            msg,
            forward_max_speed=self.forward_max_speed,
            reverse_max_speed=self.reverse_max_speed,
            angular_max_speed=self.angular_max_speed,
            forbid_reverse_turning=self.forbid_reverse_turning,
            angular_deadband=self.angular_deadband,
        )

        reasons = [] if reason == "unchanged" else reason.split(",")
        obstacle_reasons = self._obstacle_reasons(out)
        if obstacle_reasons:
            out.linear.x = 0.0
            modified = True
            reasons.extend(obstacle_reasons)
        reason = ",".join(reasons) if reasons else "unchanged"
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
