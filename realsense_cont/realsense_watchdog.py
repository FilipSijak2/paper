#!/usr/bin/env python3
"""Exit when a RealSense ROS camera stream stops producing fresh frames."""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence


STARTUP_TIMEOUT_EXIT = 20
STALE_STREAM_EXIT = 21


def stream_failure_reason(
    *,
    started_at: float,
    last_message_at: float | None,
    now: float,
    startup_timeout_s: float,
    stale_timeout_s: float,
) -> str | None:
    if last_message_at is None:
        elapsed = now - started_at
        if elapsed >= startup_timeout_s:
            return f"no first frame received after {elapsed:.1f}s"
        return None

    stale_for = now - last_message_at
    if stale_for >= stale_timeout_s:
        return f"image stream stale for {stale_for:.1f}s"
    return None


def run_watchdog(
    *,
    topic: str,
    startup_timeout_s: float,
    stale_timeout_s: float,
    poll_interval_s: float,
) -> int:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo

    rclpy.init(args=None)
    node = Node("realsense_stream_watchdog")
    started_at = time.monotonic()
    last_message_at: float | None = None
    first_frame_reported = False

    def frame_callback(_message: CameraInfo) -> None:
        nonlocal first_frame_reported, last_message_at
        last_message_at = time.monotonic()
        if not first_frame_reported:
            node.get_logger().info(f"Monitoring fresh frames on {topic}")
            first_frame_reported = True

    # CameraInfo is emitted with each frame and avoids moving full images
    # through a Python watchdog process.
    node.create_subscription(CameraInfo, topic, frame_callback, qos_profile_sensor_data)

    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=poll_interval_s)
            reason = stream_failure_reason(
                started_at=started_at,
                last_message_at=last_message_at,
                now=time.monotonic(),
                startup_timeout_s=startup_timeout_s,
                stale_timeout_s=stale_timeout_s,
            )
            if reason is not None:
                node.get_logger().error(f"{reason}; requesting RealSense container restart")
                return STARTUP_TIMEOUT_EXIT if last_message_at is None else STALE_STREAM_EXIT
    except KeyboardInterrupt:
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--startup-timeout", type=float, default=60.0)
    parser.add_argument("--stale-timeout", type=float, default=15.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.startup_timeout <= 0:
        parser.error("--startup-timeout must be greater than zero")
    if args.stale_timeout <= 0:
        parser.error("--stale-timeout must be greater than zero")
    if args.poll_interval <= 0:
        parser.error("--poll-interval must be greater than zero")
    return run_watchdog(
        topic=args.topic,
        startup_timeout_s=args.startup_timeout,
        stale_timeout_s=args.stale_timeout,
        poll_interval_s=args.poll_interval,
    )


if __name__ == "__main__":
    raise SystemExit(main())
