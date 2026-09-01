import importlib.util
import math
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
    rclpy_qos = ModuleType("rclpy.qos")

    geometry_msgs = ModuleType("geometry_msgs")
    geometry_msgs_msg = ModuleType("geometry_msgs.msg")
    nav_msgs = ModuleType("nav_msgs")
    nav_msgs_msg = ModuleType("nav_msgs.msg")
    sensor_msgs = ModuleType("sensor_msgs")
    sensor_msgs_msg = ModuleType("sensor_msgs.msg")
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

    class Imu:
        pass

    class String:
        pass

    class Float32MultiArray:
        def __init__(self):
            self.data = []

    class SMBus:
        def __init__(self, *args, **kwargs):
            pass

    setattr(rclpy_node, "Node", Node)
    setattr(rclpy_qos, "qos_profile_sensor_data", object())

    setattr(geometry_msgs_msg, "Twist", Twist)
    setattr(geometry_msgs_msg, "Point", Point)
    setattr(geometry_msgs_msg, "Quaternion", Quaternion)
    setattr(nav_msgs_msg, "Odometry", Odometry)
    setattr(sensor_msgs_msg, "Imu", Imu)
    setattr(std_msgs_msg, "String", String)
    setattr(std_msgs_msg, "Float32MultiArray", Float32MultiArray)

    setattr(geometry_msgs, "msg", geometry_msgs_msg)
    setattr(nav_msgs, "msg", nav_msgs_msg)
    setattr(sensor_msgs, "msg", sensor_msgs_msg)
    setattr(std_msgs, "msg", std_msgs_msg)

    setattr(rpi_mod, "GPIO", rpi_gpio_mod)
    setattr(smbus2_mod, "SMBus", SMBus)

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("rclpy.qos", rclpy_qos)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("nav_msgs", nav_msgs)
    inject("nav_msgs.msg", nav_msgs_msg)
    inject("sensor_msgs", sensor_msgs)
    inject("sensor_msgs.msg", sensor_msgs_msg)
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
    assert config["max_angular_vel"] == 1.0
    assert config["min_motor_cmd"] == 0.35
    assert config["drive_profile_name"] == "unprofiled"
    assert config["motor_slew_enabled"] is False
    assert config["motor_slew_rate_up"] == 0.8
    assert config["motor_slew_rate_down"] == 1.6
    assert config["motor_reversal_neutral_s"] == 0.15
    assert config["motor_immediate_stop"] is True
    assert config["power_adapt_enabled"] is False
    assert config["power_adapt_imu_topic"] == "/imu/data"
    assert config["linear_traction_assist_enabled"] is False
    assert config["linear_traction_max_motor_cmd"] == 0.42
    assert config["forward_arc_turn_enabled"] is False


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


def test_compute_wheel_commands_applies_min_motor_cmd_deadband_compensation():
    module = load_direct_bridge_module()

    left, right = module.compute_wheel_commands(
        0.0,
        0.1,
        max_linear_vel=1.0,
        max_angular_vel=1.0,
        min_motor_cmd=0.25,
    )

    assert left == -0.25
    assert right == 0.25


def test_motor_ramp_limits_acceleration_but_stops_immediately():
    module = load_direct_bridge_module()
    state = module.MotorRampState()

    first = module.update_motor_ramp(state, 0.5, 0.02, rate_up=0.8)
    second = module.update_motor_ramp(state, 0.5, 0.02, rate_up=0.8)
    stopped = module.update_motor_ramp(state, 0.0, 0.02, immediate_stop=True)

    assert math.isclose(first, 0.016)
    assert math.isclose(second, 0.032)
    assert stopped == 0.0


def test_motor_slew_disabled_bypasses_ramp_and_reversal_interlock():
    module = load_direct_bridge_module()
    state = module.MotorRampState(output=0.35, last_nonzero_sign=1)

    output = module.update_motor_ramp(
        state,
        -0.40,
        0.02,
        enabled=False,
        rate_up=0.01,
        rate_down=0.01,
        reversal_neutral_s=10.0,
    )

    assert output == -0.40
    assert state.output == -0.40
    assert state.reversal_neutral_remaining_s == 0.0


def test_motor_ramp_requires_neutral_interval_before_reversal():
    module = load_direct_bridge_module()
    state = module.MotorRampState(output=0.10)

    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_down=1.0, reversal_neutral_s=0.10
    ) == 0.05
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_down=1.0, reversal_neutral_s=0.10
    ) == 0.0
    assert state.reversal_neutral_remaining_s == 0.10
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_up=1.0, reversal_neutral_s=0.10
    ) == 0.0
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_up=1.0, reversal_neutral_s=0.10
    ) == 0.0
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_up=1.0, reversal_neutral_s=0.10
    ) == -0.05


def test_motor_ramp_can_cancel_pending_reversal():
    module = load_direct_bridge_module()
    state = module.MotorRampState(
        output=0.0,
        reversal_neutral_remaining_s=0.10,
        reversal_target_sign=-1,
        last_nonzero_sign=1,
    )

    output = module.update_motor_ramp(state, 0.20, 0.05, rate_up=1.0)

    assert output == 0.05
    assert state.reversal_neutral_remaining_s == 0.0


def test_motor_ramp_counts_zero_time_toward_reversal_interlock():
    module = load_direct_bridge_module()
    state = module.MotorRampState(output=0.20, last_nonzero_sign=1)

    assert module.update_motor_ramp(state, 0.0, 0.05, reversal_neutral_s=0.10) == 0.0
    # The first reverse cycle completes the remaining 50 ms neutral time.
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_up=1.0, reversal_neutral_s=0.10
    ) == 0.0
    assert module.update_motor_ramp(
        state, -0.20, 0.05, rate_up=1.0, reversal_neutral_s=0.10
    ) == -0.05


def test_compute_forward_arc_turn_commands_keeps_both_wheels_forward():
    module = load_direct_bridge_module()

    left, right = module.compute_forward_arc_turn_commands(
        0.4,
        max_angular_vel=1.0,
        min_motor_cmd=0.35,
        inner_motor_cmd=0.16,
    )

    assert left == 0.16
    assert right == 0.4


def test_compute_forward_arc_turn_commands_right_turn_keeps_both_wheels_forward():
    module = load_direct_bridge_module()

    left, right = module.compute_forward_arc_turn_commands(
        -0.4,
        max_angular_vel=1.0,
        min_motor_cmd=0.35,
        inner_motor_cmd=0.16,
    )

    assert left == 0.4
    assert right == 0.16


def test_enforce_forward_turn_no_reverse_clamps_inner_wheel_forward():
    module = load_direct_bridge_module()

    left, right = module.enforce_forward_turn_no_reverse(
        -0.2,
        0.7,
        cmd_angular=0.4,
        inner_motor_cmd=0.18,
    )

    assert left == 0.18
    assert right == 0.7


def test_update_power_adapt_boost_increases_when_measured_rotation_is_too_low():
    module = load_direct_bridge_module()

    boost = module.update_power_adapt_boost(
        0.10,
        cmd_angular=0.6,
        measured_angular=0.1,
        feedback_age_s=0.02,
        enabled=True,
        step_up=0.02,
        max_boost=0.5,
    )

    assert math.isclose(boost, 0.12, rel_tol=1e-9)


def test_update_power_adapt_boost_decays_when_measured_rotation_is_high():
    module = load_direct_bridge_module()

    boost = module.update_power_adapt_boost(
        0.10,
        cmd_angular=0.3,
        measured_angular=0.5,
        feedback_age_s=0.02,
        enabled=True,
        step_down=0.02,
    )

    assert math.isclose(boost, 0.08, rel_tol=1e-9)


def test_linear_traction_assist_ramps_after_sustained_drive_command():
    module = load_direct_bridge_module()

    assist = module.update_linear_traction_assist(
        0.04,
        cmd_linear=0.08,
        cmd_angular=0.04,
        active_duration_s=0.5,
        enabled=True,
        delay_s=0.35,
        step_up=0.01,
        max_assist=0.14,
    )

    assert math.isclose(assist, 0.05, rel_tol=1e-9)


def test_linear_traction_assist_does_not_raise_pwm_before_delay():
    module = load_direct_bridge_module()

    assist = module.update_linear_traction_assist(
        0.04,
        cmd_linear=0.08,
        cmd_angular=0.04,
        active_duration_s=0.1,
        enabled=True,
        delay_s=0.35,
        step_down=0.02,
    )

    assert math.isclose(assist, 0.02, rel_tol=1e-9)


def test_linear_traction_assist_decays_when_robot_stops():
    module = load_direct_bridge_module()

    assist = module.update_linear_traction_assist(
        0.08,
        cmd_linear=0.0,
        cmd_angular=0.0,
        active_duration_s=None,
        enabled=True,
        step_down=0.03,
    )

    assert math.isclose(assist, 0.05, rel_tol=1e-9)


def test_integrate_pose_updates_position_and_heading():
    module = load_direct_bridge_module()
    x, y, yaw = module.integrate_pose(0.0, 0.0, 0.0, linear_velocity=1.0, angular_velocity=0.0, dt_s=0.5)
    assert x == 0.5
    assert y == 0.0
    assert yaw == 0.0
