#!/usr/bin/env python3
"""Publish validated ground-truth experiment labels for rosbag recording."""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence


SCENARIOS = (
    "normal_idle",
    "normal_straight",
    "normal_turn",
    "blocked",
    "collision",
    "too_close",
    "unstable",
)
PHASES = ("start", "end")
VALID_EVENTS = tuple(f"{scenario}_{phase}" for scenario in SCENARIOS for phase in PHASES)


def resolve_event(label: str, phase: str | None) -> str | None:
    """Return a one-shot event or None when an interactive scenario was requested."""
    if label in VALID_EVENTS:
        if phase is not None:
            raise ValueError("Do not add a phase to an already complete event label")
        return label
    if label not in SCENARIOS:
        raise ValueError(f"Unknown scenario or event: {label}")
    if phase is None:
        return None
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    return f"{label}_{phase}"


def publish_event(event: str, topic: str, wait_timeout: float, settle_time: float) -> None:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String

    rclpy.init(args=None)
    node = Node(f"experiment_event_publisher_{os.getpid()}")
    qos = QoSProfile(
        depth=10,
        reliability=ReliabilityPolicy.RELIABLE,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
    )
    publisher = node.create_publisher(String, topic, qos)
    deadline = time.monotonic() + wait_timeout

    try:
        while publisher.get_subscription_count() == 0:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"No subscriber appeared on {topic} within {wait_timeout:.1f}s; "
                    "the bag recorder may not be running"
                )
            rclpy.spin_once(node, timeout_sec=0.1)

        publisher.publish(String(data=event))
        settle_deadline = time.monotonic() + settle_time
        while time.monotonic() < settle_deadline:
            rclpy.spin_once(node, timeout_sec=min(0.1, settle_deadline - time.monotonic()))
    finally:
        node.destroy_node()
        rclpy.shutdown()

    print(f"Published {event} on {topic}", flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Publish one event as '<scenario> <start|end>' or '<scenario>_start/end'. "
            "With only a scenario, publish start, wait for Enter, then publish end."
        )
    )
    parser.add_argument("label", nargs="?", help="Scenario name or complete event label")
    parser.add_argument("phase", nargs="?", help="start or end")
    parser.add_argument("--topic", default="/experiment_event")
    parser.add_argument("--wait-timeout", type=float, default=10.0)
    parser.add_argument("--settle-time", type=float, default=0.5)
    parser.add_argument("--list", action="store_true", help="List valid event labels and exit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(VALID_EVENTS))
        return 0
    if args.label is None:
        parser.error("a scenario or event label is required")
    if args.wait_timeout <= 0:
        parser.error("--wait-timeout must be greater than zero")
    if args.settle_time < 0:
        parser.error("--settle-time cannot be negative")

    try:
        event = resolve_event(args.label, args.phase)
    except ValueError as exc:
        parser.error(str(exc))

    if event is not None:
        publish_event(event, args.topic, args.wait_timeout, args.settle_time)
        return 0

    start_event = f"{args.label}_start"
    end_event = f"{args.label}_end"
    publish_event(start_event, args.topic, args.wait_timeout, args.settle_time)
    try:
        input(f"{start_event} recorded. Press Enter to publish {end_event}: ")
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
    publish_event(end_event, args.topic, args.wait_timeout, args.settle_time)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
