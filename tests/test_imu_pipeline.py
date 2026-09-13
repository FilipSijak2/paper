"""Regression for direct RealSense input after removing its Madgwick node."""
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

PATH = (Path(__file__).resolve().parents[1] / 'sensor_fusion_cont/ws/src/'
        'sensor_fusion_pkg/sensor_fusion_pkg/realsense_imu_transform.py')


def load_transform(monkeypatch):
    class Imu:
        def __init__(self):
            self.header = SimpleNamespace(frame_id='camera_imu_optical_frame', stamp=123)
            self.orientation = SimpleNamespace(w=0)
            self.orientation_covariance = [0.] * 9
            self.angular_velocity = SimpleNamespace(x=0., y=0., z=0.)
            self.angular_velocity_covariance = [1., 0., 0., 0., 2., 0., 0., 0., 3.]
            self.linear_acceleration = SimpleNamespace(x=0., y=0., z=0.)
            self.linear_acceleration_covariance = [0.] * 9

    class Node:
        def __init__(self, name):
            self.messages = []

        def create_publisher(self, kind, topic, qos):
            self.published_topic = topic
            return SimpleNamespace(publish=self.messages.append)

        def create_subscription(self, kind, topic, callback, qos):
            self.subscribed_topic = topic
            return SimpleNamespace(callback=callback)

        def get_logger(self):
            return SimpleNamespace(info=lambda message: None)

    for name, attrs in {
        'rclpy': {}, 'rclpy.node': {'Node': Node},
        'rclpy.qos': {'qos_profile_sensor_data': object()},
        'sensor_msgs': {}, 'sensor_msgs.msg': {'Imu': Imu},
    }.items():
        stub = ModuleType(name)
        stub.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, stub)
    spec = importlib.util.spec_from_file_location('imu_transform_test', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('input_topic', [None, '/custom/camera/imu'])
def test_direct_camera_input_ignores_old_madgwick_output(monkeypatch, input_topic):
    module = load_transform(monkeypatch)
    monkeypatch.setenv('SF_IMU_OUTPUT_TOPIC', '/imu/data')
    monkeypatch.setenv('SF_IMU_BASE_TOPIC', '/imu/base_link')
    monkeypatch.setenv('SF_IMU_BASE_FRAME', 'base_link')
    if input_topic:
        monkeypatch.setenv('SF_IMU_INPUT_TOPIC', input_topic)
    else:
        monkeypatch.delenv('SF_IMU_INPUT_TOPIC', raising=False)
    node = module.RealSenseImuTransform()
    assert node.subscribed_topic == (input_topic or '/camera/realsense/imu')
    assert node.published_topic == '/imu/base_link'
    msg = module.Imu()
    msg.angular_velocity.y = -0.3
    node.subscription.callback(msg)
    output, = node.messages
    assert output.angular_velocity.z == pytest.approx(0.3)
    assert output.header.frame_id == 'base_link'
    assert output.header.stamp == 123
    assert output.angular_velocity_covariance[8] == 2.
    assert output.orientation_covariance[0] == -1.
