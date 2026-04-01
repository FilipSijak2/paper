import importlib.util
import math
import struct
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = REPO_ROOT / "bridge_cont" / "robot_serial_bridge.py"


def load_bridge_module():
    previous_modules = {}

    def inject(name: str, module: ModuleType):
        previous_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    rclpy = ModuleType("rclpy")
    rclpy_node = ModuleType("rclpy.node")
    rclpy_qos = ModuleType("rclpy.qos")
    serial_mod = ModuleType("serial")
    geometry_msgs = ModuleType("geometry_msgs")
    geometry_msgs_msg = ModuleType("geometry_msgs.msg")
    sensor_msgs = ModuleType("sensor_msgs")
    sensor_msgs_msg = ModuleType("sensor_msgs.msg")
    nav_msgs = ModuleType("nav_msgs")
    nav_msgs_msg = ModuleType("nav_msgs.msg")
    std_msgs = ModuleType("std_msgs")
    std_msgs_msg = ModuleType("std_msgs.msg")

    class Node:
        pass

    class QoSProfile:
        pass

    class ReliabilityPolicy:
        BEST_EFFORT = 1
        RELIABLE = 2

    class Quaternion:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.w = 0.0

    class Twist:
        pass

    class Imu:
        pass

    class Odometry:
        pass

    class String:
        pass

    class Header:
        pass

    class PoseWithCovariance:
        pass

    class TwistWithCovariance:
        pass

    class Pose:
        pass

    class Vector3:
        pass

    class Point:
        pass

    serial_mod.Serial = object
    serial_mod.EIGHTBITS = 8
    serial_mod.PARITY_NONE = "N"
    serial_mod.STOPBITS_ONE = 1

    rclpy_node.Node = Node
    rclpy_qos.QoSProfile = QoSProfile
    rclpy_qos.ReliabilityPolicy = ReliabilityPolicy
    geometry_msgs_msg.Twist = Twist
    geometry_msgs_msg.PoseWithCovariance = PoseWithCovariance
    geometry_msgs_msg.TwistWithCovariance = TwistWithCovariance
    geometry_msgs_msg.Pose = Pose
    geometry_msgs_msg.Vector3 = Vector3
    geometry_msgs_msg.Quaternion = Quaternion
    geometry_msgs_msg.Point = Point
    sensor_msgs_msg.Imu = Imu
    nav_msgs_msg.Odometry = Odometry
    std_msgs_msg.String = String
    std_msgs_msg.Header = Header

    geometry_msgs.msg = geometry_msgs_msg
    sensor_msgs.msg = sensor_msgs_msg
    nav_msgs.msg = nav_msgs_msg
    std_msgs.msg = std_msgs_msg

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("rclpy.qos", rclpy_qos)
    inject("serial", serial_mod)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("sensor_msgs", sensor_msgs)
    inject("sensor_msgs.msg", sensor_msgs_msg)
    inject("nav_msgs", nav_msgs)
    inject("nav_msgs.msg", nav_msgs_msg)
    inject("std_msgs", std_msgs)
    inject("std_msgs.msg", std_msgs_msg)

    try:
        spec = importlib.util.spec_from_file_location("test_robot_serial_bridge", BRIDGE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def test_crc16_ccitt_matches_standard_vector():
    bridge = load_bridge_module()
    assert bridge.crc16_ccitt(b"123456789") == 0x29B1


def test_resolve_runtime_config_prefers_cli_over_env(monkeypatch):
    bridge = load_bridge_module()
    monkeypatch.setenv("SERIAL_PORT", "/dev/env")
    monkeypatch.setenv("SERIAL_BAUD", "57600")
    monkeypatch.setenv("IMU_TOPIC", "/imu/custom")
    monkeypatch.setenv("COMMAND_TIMEOUT_MS", "2000")
    monkeypatch.setenv("WATCHDOG_TIMEOUT_S", "4.5")
    monkeypatch.setenv("STATUS_PERIOD_S", "7.0")
    monkeypatch.setenv("SERIAL_RETRY_DELAY_S", "2.0")

    config = bridge.resolve_runtime_config(SimpleNamespace(port="/dev/cli", baud=115200))

    assert config == {
        "port": "/dev/cli",
        "baud": 115200,
        "imu_topic": "/imu/custom",
        "command_timeout_ms": 2000,
        "watchdog_timeout_s": 4.5,
        "status_period_s": 7.0,
        "serial_retry_delay_s": 2.0,
    }


def test_resolve_runtime_config_falls_back_on_invalid_env(monkeypatch):
    bridge = load_bridge_module()
    monkeypatch.delenv("IMU_TOPIC", raising=False)
    monkeypatch.setenv("SERIAL_BAUD", "not-a-number")
    monkeypatch.setenv("COMMAND_TIMEOUT_MS", "0")
    monkeypatch.setenv("WATCHDOG_TIMEOUT_S", "-1")
    monkeypatch.setenv("STATUS_PERIOD_S", "bad")
    monkeypatch.setenv("SERIAL_RETRY_DELAY_S", "-2")

    config = bridge.resolve_runtime_config(SimpleNamespace(port=None, baud=None))

    assert config["baud"] == 115200
    assert config["command_timeout_ms"] == 1200
    assert config["watchdog_timeout_s"] == 3.0
    assert config["status_period_s"] == 5.0
    assert config["serial_retry_delay_s"] == 1.0
    assert config["imu_topic"] == "/imu/arduino"


def test_euler_to_quaternion_identity():
    bridge = load_bridge_module()
    q = bridge.euler_to_quaternion(0.0)

    assert q.x == 0.0
    assert q.y == 0.0
    assert q.z == 0.0
    assert q.w == 1.0


def test_euler_to_quaternion_pi_yaw():
    bridge = load_bridge_module()
    q = bridge.euler_to_quaternion(math.pi)

    assert math.isclose(q.x, 0.0, abs_tol=1e-9)
    assert math.isclose(q.y, 0.0, abs_tol=1e-9)
    assert math.isclose(abs(q.z), 1.0, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(q.w, 0.0, abs_tol=1e-9)


class FakeSerialPort:
    def __init__(self, is_open=True):
        self.is_open = is_open
        self.writes = []

    def write(self, payload):
        self.writes.append(payload)

    def close(self):
        self.is_open = False


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class FakeLogger:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.infos = []

    def info(self, message):
        self.infos.append(message)

    def error(self, message):
        self.errors.append(message)

    def warn(self, message):
        self.warnings.append(message)


def make_bridge_instance(bridge):
    instance = bridge.RobotSerialBridge.__new__(bridge.RobotSerialBridge)
    instance.serial_port = FakeSerialPort()
    instance.stats = {
        "packets_received": 0,
        "packets_sent": 0,
        "crc_errors": 0,
        "sync_errors": 0,
        "serial_errors": 0,
    }
    instance.command_sequence = 0
    instance.last_command_time = 0.0
    instance.last_packet_time = 0.0
    instance.packet_buffer = bytearray()
    instance.status_pub = FakePublisher()
    instance._logger = FakeLogger()
    instance.get_logger = lambda: instance._logger
    return instance


def test_cmd_vel_callback_builds_packet_with_crc_and_sequence():
    bridge = load_bridge_module()
    instance = make_bridge_instance(bridge)
    message = SimpleNamespace(
        linear=SimpleNamespace(x=0.5),
        angular=SimpleNamespace(z=-0.25),
    )

    bridge.RobotSerialBridge.cmd_vel_callback(instance, message)

    assert instance.stats["packets_sent"] == 1
    assert instance.command_sequence == 1
    packet = instance.serial_port.writes[-1]
    unpacked = struct.unpack("<LBBHffHL", packet)
    header, version, sequence, timeout_ms, linear_x, angular_z, crc, tail = unpacked
    assert header == bridge.COMMAND_PACKET_HEADER
    assert tail == bridge.COMMAND_PACKET_TAIL
    assert version == bridge.PROTOCOL_VERSION
    assert sequence == 0
    assert timeout_ms == 1200
    assert math.isclose(linear_x, 0.5, rel_tol=1e-9)
    assert math.isclose(angular_z, -0.25, rel_tol=1e-9)
    assert crc == bridge.crc16_ccitt(packet[:-6])


def test_process_packets_skips_garbage_and_tracks_sync_errors():
    bridge = load_bridge_module()
    instance = make_bridge_instance(bridge)
    sensor_packet = struct.pack("<L", bridge.SENSOR_PACKET_HEADER) + bytes(bridge.SENSOR_PACKET_SIZE - 4)
    instance.packet_buffer = bytearray(b"junk" + sensor_packet + b"\x00\x01")
    seen_packets = []
    instance.parse_sensor_packet = lambda payload: seen_packets.append(payload) or True

    bridge.RobotSerialBridge.process_packets(instance)

    assert len(seen_packets) == 1
    assert seen_packets[0] == sensor_packet
    assert instance.stats["sync_errors"] == 1
    assert instance.stats["packets_received"] == 1
    assert instance.packet_buffer == bytearray(b"\x00\x01")


def test_parse_sensor_packet_rejects_bad_crc():
    bridge = load_bridge_module()
    instance = make_bridge_instance(bridge)
    instance.publish_imu = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("publish_imu should not be called"))
    instance.publish_odometry = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("publish_odometry should not be called"))
    values = (
        bridge.SENSOR_PACKET_HEADER,
        bridge.PROTOCOL_VERSION,
        1,
        0,
        123,
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
        0.6,
        1.1,
        1.2,
        2.1,
        2.2,
        2.3,
        12000,
        25,
        0,
        0,
        bridge.SENSOR_PACKET_TAIL,
    )
    packet = struct.pack("<LBBHLfffffffffffHBBHL", *values)
    correct_crc = bridge.crc16_ccitt(packet[:-6])
    bad_packet = packet[:-6] + struct.pack("<H", (correct_crc + 1) & 0xFFFF) + packet[-4:]

    assert bridge.RobotSerialBridge.parse_sensor_packet(instance, bad_packet) is False


def test_watchdog_callback_reconnects_when_serial_is_closed(monkeypatch):
    bridge = load_bridge_module()
    instance = make_bridge_instance(bridge)
    instance.serial_port = FakeSerialPort(is_open=False)
    reconnect_attempts = []
    instance.connect_serial = lambda: reconnect_attempts.append(True) or True
    monkeypatch.setattr(time, "time", lambda: 10.0)
    instance.last_packet_time = 0.0

    bridge.RobotSerialBridge.watchdog_callback(instance)

    assert reconnect_attempts == [True]
    assert len(instance._logger.warnings) == 1


def test_status_callback_publishes_bridge_summary():
    bridge = load_bridge_module()
    instance = make_bridge_instance(bridge)
    instance.stats.update(
        {
            "packets_received": 12,
            "packets_sent": 7,
            "crc_errors": 2,
            "sync_errors": 3,
        }
    )

    bridge.RobotSerialBridge.status_callback(instance)

    status = instance.status_pub.messages[-1].data
    assert "RX=12" in status
    assert "TX=7" in status
    assert "CRC_ERR=2" in status
    assert "SYNC_ERR=3" in status


def test_connect_serial_failure_initializes_stats(monkeypatch):
    bridge = load_bridge_module()

    class ExplodingSerial:
        def __init__(self, *args, **kwargs):
            raise OSError("serial unavailable")

    monkeypatch.setattr(bridge.serial, "Serial", ExplodingSerial)

    instance = bridge.RobotSerialBridge.__new__(bridge.RobotSerialBridge)
    instance.port = "/dev/ttyFAIL"
    instance.baud = 115200
    instance.serial_port = None
    instance._logger = FakeLogger()
    instance.get_logger = lambda: instance._logger

    assert bridge.RobotSerialBridge.connect_serial(instance) is False
    assert instance.stats["serial_errors"] == 1
    assert "serial unavailable" in instance._logger.errors[-1]
