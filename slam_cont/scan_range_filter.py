#!/usr/bin/env python3
"""Republishes /scan as /scan_filtered with invalid readings replaced by inf.

RPLIDAR A1 returns 0.0 m for objects that are too close or for no-return readings.
slam_toolbox's minimum_laser_range is NOT a functional ROS2 parameter in Humble and
cannot be set via --params-file.  Unfiltered 0.0 m points map to the sensor's exact
position in the global frame, which falls outside the CorrelationGrid used during scan
matching, causing the hard crash:
    "Mapper FATAL ERROR - unable to get pointer in probability search!"

This node must be running before slam_toolbox subscribes to /scan_filtered.
It is started by slam_manager.py at container startup.
"""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

MIN_RANGE_DEFAULT = 0.2  # metres — RPLIDAR A1 hardware minimum


class ScanRangeFilter(Node):
    def __init__(self) -> None:
        super().__init__("scan_range_filter")
        self.declare_parameter("min_range", MIN_RANGE_DEFAULT)
        self._min_range: float = (
            self.get_parameter("min_range").get_parameter_value().double_value
        )
        self._pub = self.create_publisher(LaserScan, "/scan_filtered", 10)
        self.create_subscription(LaserScan, "/scan", self._cb, 10)
        self.get_logger().info(
            f"ScanRangeFilter started: /scan → /scan_filtered  (min={self._min_range} m)"
        )

    def _cb(self, msg: LaserScan) -> None:
        min_r = self._min_range
        max_r = msg.range_max
        inf = float("inf")
        msg.ranges = tuple(
            r if (not math.isnan(r)) and (not math.isinf(r)) and min_r <= r <= max_r
            else inf
            for r in msg.ranges
        )
        msg.range_min = min_r
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
