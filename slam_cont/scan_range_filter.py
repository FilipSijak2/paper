#!/usr/bin/env python3
"""Republish /scan as /scan_filtered with invalid readings replaced by inf.

The RPLIDAR can report 0.0 m for invalid or too-close returns. slam_toolbox on
Humble can still ingest those values even when laser range parameters are set,
and that can crash the mapper with:
    "Mapper FATAL ERROR - unable to get pointer in probability search!"

This node gives slam_toolbox a clean LaserScan stream on /scan_filtered.
"""

import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan

MIN_RANGE_DEFAULT = 0.2
MAX_RANGE_DEFAULT = 10.0


class ScanRangeFilter(Node):
    def __init__(self) -> None:
        super().__init__("scan_range_filter")
        self.declare_parameter("min_range", MIN_RANGE_DEFAULT)
        self.declare_parameter("max_range", MAX_RANGE_DEFAULT)
        self._min_range = (
            self.get_parameter("min_range").get_parameter_value().double_value
        )
        self._max_range = (
            self.get_parameter("max_range").get_parameter_value().double_value
        )

        self._pub = self.create_publisher(
            LaserScan, "/scan_filtered", qos_profile_sensor_data
        )
        self.create_subscription(LaserScan, "/scan", self._cb, qos_profile_sensor_data)
        self.get_logger().info(
            "ScanRangeFilter started: /scan -> /scan_filtered "
            f"(valid range={self._min_range}..{self._max_range} m)"
        )

    def _cb(self, msg: LaserScan) -> None:
        min_r = self._min_range
        max_r = min(self._max_range, msg.range_max)
        inf = float("inf")

        msg.ranges = tuple(
            r if (not math.isnan(r)) and (not math.isinf(r)) and min_r <= r <= max_r
            else inf
            for r in msg.ranges
        )
        msg.range_min = min_r
        msg.range_max = max_r
        self._pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = ScanRangeFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
