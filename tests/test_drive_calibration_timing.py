"""Exercise the real node methods with a deterministic clock, without ROS/GPIO."""
import ast
import math
import threading
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from nav_cont.drive_calibration_core import (
    Pose2D, Trial, calculate_result, stamp_is_fresh, summarize, yaw_from_quaternion,
)


class Clock:
    t = 100.0

    def monotonic(self):
        return self.t

    def sleep(self, delay):
        self.t += delay


def load_node(clock):
    source = Path(__file__).resolve().parents[1] / 'nav_cont/drive_calibration.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    selected = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    ns = dict(Node=object, time=clock, math=math, Pose2D=Pose2D,
              Trial=Trial, calculate_result=calculate_result,
              stamp_is_fresh=stamp_is_fresh, yaw_from_quaternion=yaw_from_quaternion,
              Twist=lambda: SimpleNamespace(linear=SimpleNamespace(x=0), angular=SimpleNamespace(z=0)))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[future] + selected, type_ignores=[])), str(source), 'exec'), ns)
    return ns['DriveCalibrationNode'], ns['CalibrationError']


def test_stamps_reject_old_duplicate_future_and_nonfinite_values():
    assert stamp_is_fresh(100.0, 100.1, 99.9)
    for stamp in (0, 99, 100.2, float('nan'), float('inf')):
        assert not stamp_is_fresh(stamp, 100.0)
    assert not stamp_is_fresh(100.0, 100.1, 100.0)


def test_old_queued_odom_cannot_become_fresh_on_receipt():
    clock = Clock()
    cls, _ = load_node(clock)
    node = cls.__new__(cls)
    node.data_lock = threading.Lock()
    node.latest_pose_stamp = 0.0
    node.latest_pose = None
    node.latest_pose_received_at = 0
    node.get_clock = lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=int(clock.t * 1e9)))
    msg = SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=90, nanosec=0)),
                          pose=SimpleNamespace(pose=SimpleNamespace(
                              position=SimpleNamespace(x=1, y=2),
                              orientation=SimpleNamespace(x=0, y=0, z=0, w=1))))
    node._odom_cb(msg)
    assert node.latest_pose is None
    msg.header.stamp.sec = 100
    node._odom_cb(msg)
    assert node.latest_pose == Pose2D(1, 2, 0)


def test_phases_exclude_old_pwm_and_use_pose_timestamp_interval():
    clock = Clock()
    cls, _ = load_node(clock)
    node = cls.__new__(cls)
    node.data_lock = threading.Lock()
    node.manual_speed_scale = node.manual_angular_scale = 1
    node.motor_pwm_samples = deque([(99.0, 0.0, 0.0)])
    node.pose_sample = lambda: (Pose2D(0, 0, (clock.t - 100) * 0.1), clock.t)
    node.command_pub = SimpleNamespace(publish=lambda msg: node.motor_pwm_samples.append((clock.t, -0.4, 0.4)))
    trial = Trial('turn', 0, .1, 1)
    ramp = node.measure_phase('carpet', trial, 'ramp', 1)
    hold = node.measure_phase('carpet', trial, 'hold', 1)
    assert hold.start_stamp_s == pytest.approx(ramp.end_stamp_s)
    assert hold.duration_s == pytest.approx(1)
    assert hold.measured_angular_rps == pytest.approx(.1)
    assert hold.mean_left_motor_pwm == pytest.approx(-.4)
    assert summarize([ramp])['mean_left_rotation_response_ratio'] is None


def test_failed_phase_and_interrupt_always_send_stop():
    clock = Clock()
    cls, error = load_node(clock)
    for exc in (error('stale'), KeyboardInterrupt()):
        node = cls.__new__(cls)
        stops = []
        node.wait_for_fresh_pose = lambda: None
        node.stop = lambda: stops.append(True)
        def fail(*args):
            raise exc
        node.measure_phase = fail
        with pytest.raises(type(exc)):
            node.run_trial('carpet', Trial('test', 0, .1, 1), 1)
        assert stops == [True]
