import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
DIRECT_BRIDGE_PATH = REPO_ROOT / "bridge_cont" / "robot_rpi_direct_bridge.py"


def load_direct_bridge_module():
    previous_modules = {}

    def inject(name: str, module: ModuleType):
        previous_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    rclpy = ModuleType("rclpy")
    rclpy_node = ModuleType("rclpy.node")

    geometry_msgs = ModuleType("geometry_msgs")
    geometry_msgs_msg = ModuleType("geometry_msgs.msg")
    nav_msgs = ModuleType("nav_msgs")
    nav_msgs_msg = ModuleType("nav_msgs.msg")
    std_msgs = ModuleType("std_msgs")
    std_msgs_msg = ModuleType("std_msgs.msg")

    rpi_mod = ModuleType("RPi")
    rpi_gpio_mod = ModuleType("RPi.GPIO")
    smbus2_mod = ModuleType("smbus2")

    class Node:
        pass

    class Twist:
        pass

    class Point:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = x
            self.y = y
            self.z = z

    class Quaternion:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.z = 0.0
            self.w = 0.0

    class Odometry:
        pass

    class String:
        pass

    class SMBus:
        def __init__(self, *args, **kwargs):
            pass

    setattr(rclpy_node, "Node", Node)

    setattr(geometry_msgs_msg, "Twist", Twist)
    setattr(geometry_msgs_msg, "Point", Point)
    setattr(geometry_msgs_msg, "Quaternion", Quaternion)
    setattr(nav_msgs_msg, "Odometry", Odometry)
    setattr(std_msgs_msg, "String", String)

    setattr(geometry_msgs, "msg", geometry_msgs_msg)
    setattr(nav_msgs, "msg", nav_msgs_msg)
    setattr(std_msgs, "msg", std_msgs_msg)

    setattr(rpi_mod, "GPIO", rpi_gpio_mod)
    setattr(smbus2_mod, "SMBus", SMBus)

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("nav_msgs", nav_msgs)
    inject("nav_msgs.msg", nav_msgs_msg)
    inject("std_msgs", std_msgs)
    inject("std_msgs.msg", std_msgs_msg)
    inject("RPi", rpi_mod)
    inject("RPi.GPIO", rpi_gpio_mod)
    inject("smbus2", smbus2_mod)

    try:
        spec = importlib.util.spec_from_file_location("test_robot_rpi_direct_bridge", DIRECT_BRIDGE_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous_modules.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def test_resolve_runtime_config_uses_env(monkeypatch):
    module = load_direct_bridge_module()
    monkeypatch.setenv("I2C_MUX_ADDR", "0x71")
    monkeypatch.setenv("AS5600_ADDR", "0x37")
    monkeypatch.setenv("LEFT_MUX_CHANNEL", "2")
    monkeypatch.setenv("RIGHT_MUX_CHANNEL", "6")
    monkeypatch.setenv("WHEEL_RADIUS_M", "0.05")
    monkeypatch.setenv("WHEEL_BASE_M", "0.25")
    monkeypatch.setenv("ENCODERS_ENABLED", "0")
    monkeypatch.setenv("OPEN_LOOP_ODOM_FROM_CMD", "1")

    config = module.resolve_runtime_config(SimpleNamespace(i2c_bus=None))

    assert config["i2c_bus"] == 1
    assert config["mux_addr"] == 0x71
    assert config["as5600_addr"] == 0x37
    assert config["left_mux_channel"] == 2
    assert config["right_mux_channel"] == 6
    assert config["wheel_radius"] == 0.05
    assert config["wheel_base"] == 0.25
    assert config["encoders_enabled"] is False
    assert config["open_loop_odom_from_cmd"] is True


def test_unwrap_raw_handles_wraparound():
    module = load_direct_bridge_module()
    state = module.UnwrapState()

    first = module.unwrap_raw(4090, state)
    wrapped_forward = module.unwrap_raw(10, state)
    wrapped_back = module.unwrap_raw(4080, state)

    assert first == 4090.0
    assert wrapped_forward == 4106.0
    assert wrapped_back == 4080.0


def test_compute_wheel_commands_matches_expected_mapping():
    module = load_direct_bridge_module()

    # max_linear_vel=1.0, max_angular_vel=1.0: lin=0.5, ang=1.0 -> left=-0.5, right=1.0 (clamped)
    left, right = module.compute_wheel_commands(0.5, 1.0, 1.0, 1.0)
    assert left == -0.5
    assert right == 1.0

    # pure linear, no angular: left == right == normalised linear
    left2, right2 = module.compute_wheel_commands(0.5, 0.0, 1.0, 1.0)
    assert left2 == 0.5
    assert right2 == 0.5

    # inversion flags flip signs
    left_i, right_i = module.compute_wheel_commands(0.5, 0.0, 1.0, 1.0, left_inverted=True, right_inverted=True)
    assert left_i == -0.5
    assert right_i == -0.5


def test_integrate_pose_updates_position_and_heading():
    module = load_direct_bridge_module()
    x, y, yaw = module.integrate_pose(0.0, 0.0, 0.0, linear_velocity=1.0, angular_velocity=0.0, dt_s=0.5)
    assert x == 0.5
    assert y == 0.0
    assert yaw == 0.0
