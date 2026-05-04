#!/usr/bin/env python3
"""
ROS 2 direct hardware bridge for the Devastator robot on Raspberry Pi.

Architecture:
    ROS 2 topics <-> this bridge <-> RPi GPIO + I2C

Published topics:
    /wheel_odom (nav_msgs/Odometry)
    /robot_status (std_msgs/String)

Subscribed topics:
    /cmd_vel (geometry_msgs/Twist)
"""

import argparse
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

import rclpy
from geometry_msgs.msg import Point, Quaternion, Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

try:
    if "RPI_LGPIO_REVISION" not in os.environ:
        revision_paths = (
            Path("/proc/device-tree/system/linux,revision"),
            Path("/sys/firmware/devicetree/base/system/linux,revision"),
        )
        for revision_path in revision_paths:
            try:
                revision_raw = revision_path.read_bytes()
            except OSError:
                continue
            if len(revision_raw) >= 4:
                revision_value = int.from_bytes(revision_raw[:4], byteorder="big", signed=False)
                if revision_value > 0:
                    os.environ["RPI_LGPIO_REVISION"] = f"{revision_value:x}"
                    break
    if "RPI_LGPIO_REVISION" not in os.environ:
        try:
            for cpuinfo_line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
                if not cpuinfo_line.lower().startswith("revision"):
                    continue
                _, revision_text = cpuinfo_line.split(":", 1)
                revision_text = revision_text.strip().lower().lstrip("0x")
                if revision_text:
                    int(revision_text, 16)
                    os.environ["RPI_LGPIO_REVISION"] = revision_text
                    break
        except OSError:
            pass

    import RPi.GPIO as GPIO
except Exception as exc:  # pragma: no cover - handled at runtime on non-RPi hosts
    GPIO = None
    GPIO_IMPORT_ERROR = exc
else:
    GPIO_IMPORT_ERROR = None

try:
    from smbus2 import SMBus
except Exception:  # pragma: no cover - handled at runtime on hosts missing smbus
    SMBus = None


REG_STATUS = 0x0B # Bit 5 (0b00100000) indicates a new angle sample is ready
REG_RAW_ANGLE = 0x0C

SENSOR_FLAG_ENC_LEFT_OK = 1 << 1
SENSOR_FLAG_ENC_RIGHT_OK = 1 << 2
SENSOR_FLAG_CMD_RX_OK = 1 << 4

ERROR_FLAG_ENC_FAIL = 1 << 1
ERROR_FLAG_COMM_TIMEOUT = 1 << 2


@dataclass
class UnwrapState:
    initialized: bool = False
    previous_raw: int = 0
    turns: int = 0


def _env_int(name, default, minimum=None):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw, 0)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _env_float(name, default, minimum=None):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if minimum is not None and value < minimum:
        return default
    return value


def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def clamp(value, low, high):
    return max(low, min(high, value))


def euler_to_quaternion(yaw, pitch=0.0, roll=0.0):
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q


def integrate_pose(x_pose, y_pose, yaw, linear_velocity, angular_velocity, dt_s):
    if dt_s <= 0.0:
        return x_pose, y_pose, yaw
    next_yaw = yaw + (angular_velocity * dt_s)
    next_x = x_pose + (linear_velocity * dt_s * math.cos(next_yaw))
    next_y = y_pose + (linear_velocity * dt_s * math.sin(next_yaw))
    return next_x, next_y, next_yaw


def unwrap_raw(raw, state):
    if not state.initialized:
        state.initialized = True
        state.previous_raw = raw
        return float(raw)

    delta = int(raw) - int(state.previous_raw)
    if delta > 2048:
        state.turns -= 1
    elif delta < -2048:
        state.turns += 1

    state.previous_raw = raw
    return float((state.turns * 4096) + raw)


def raw_counts_to_radians(counts):
    return float(counts) * (2.0 * math.pi / 4096.0)


def compute_wheel_commands(cmd_linear, cmd_angular, wheel_base, left_inverted=False, right_inverted=False):
    left_speed = cmd_linear - (cmd_angular * wheel_base / 2.0)
    right_speed = cmd_linear + (cmd_angular * wheel_base / 2.0)

    if left_inverted:
        left_speed = -left_speed
    if right_inverted:
        right_speed = -right_speed

    return clamp(left_speed, -1.0, 1.0), clamp(right_speed, -1.0, 1.0)


def resolve_runtime_config(args):
    return {
        "i2c_bus": args.i2c_bus if args.i2c_bus is not None else _env_int("I2C_BUS", 1, minimum=0),
        "mux_addr": _env_int("I2C_MUX_ADDR", 0x70, minimum=0),
        "as5600_addr": _env_int("AS5600_ADDR", 0x36, minimum=0),
        "left_mux_channel": _env_int("LEFT_MUX_CHANNEL", 0, minimum=-1),
        "right_mux_channel": _env_int("RIGHT_MUX_CHANNEL", 4, minimum=-1),
        "wheel_radius": _env_float("WHEEL_RADIUS_M", 0.033, minimum=0.0001),
        "wheel_base": _env_float("WHEEL_BASE_M", 0.20, minimum=0.0001),
        "control_period_s": _env_float("CONTROL_PERIOD_S", 0.02, minimum=0.001),
        "status_period_s": _env_float("STATUS_PERIOD_S", 2.0, minimum=0.1),
        "command_timeout_ms": _env_int("COMMAND_TIMEOUT_MS", 1200, minimum=1),
        "pwm_frequency_hz": _env_int("PWM_FREQUENCY_HZ", 1000, minimum=1),
        "pin_ain1": _env_int("DRV_AIN1_PIN", 18, minimum=0),
        "pin_ain2": _env_int("DRV_AIN2_PIN", 23, minimum=0),
        "pin_bin1": _env_int("DRV_BIN1_PIN", 19, minimum=0),
        "pin_bin2": _env_int("DRV_BIN2_PIN", 24, minimum=0),
        "pin_sleep": _env_int("DRV_SLEEP_PIN", -1),
        "left_motor_inverted": _env_bool("LEFT_MOTOR_INVERTED", False),
        "right_motor_inverted": _env_bool("RIGHT_MOTOR_INVERTED", False),
        "left_encoder_inverted": _env_bool("LEFT_ENCODER_INVERTED", False),
        "right_encoder_inverted": _env_bool("RIGHT_ENCODER_INVERTED", False),
        "encoders_enabled": _env_bool("ENCODERS_ENABLED", True),
        "open_loop_odom_from_cmd": _env_bool("OPEN_LOOP_ODOM_FROM_CMD", False),
    }


class RobotRpiDirectBridge(Node):
    def __init__(
        self,
        i2c_bus=1,
        mux_addr=0x70,
        as5600_addr=0x36,
        left_mux_channel=0,
        right_mux_channel=4,
        wheel_radius=0.033,
        wheel_base=0.20,
        control_period_s=0.02,
        status_period_s=2.0,
        command_timeout_ms=1200,
        pwm_frequency_hz=1000,
        pin_ain1=18,
        pin_ain2=23,
        pin_bin1=19,
        pin_bin2=24,
        pin_sleep=-1,
        left_motor_inverted=False,
        right_motor_inverted=False,
        left_encoder_inverted=False,
        right_encoder_inverted=False,
        encoders_enabled=True,
        open_loop_odom_from_cmd=False,
    ):
        super().__init__("robot_rpi_direct_bridge")

        if GPIO is None:
            detail = f" Import error: {GPIO_IMPORT_ERROR}" if GPIO_IMPORT_ERROR else ""
            raise RuntimeError(
                "RPi.GPIO is not available. Install rpi-lgpio (preferred on Pi 5) or python3-rpi.gpio."
                " If using Pi 5 set RPI_LGPIO_CHIP=4." + detail
            )
        self.encoders_enabled = bool(encoders_enabled and left_mux_channel >= 0 and right_mux_channel >= 0)
        self.open_loop_odom_from_cmd = bool(open_loop_odom_from_cmd or not self.encoders_enabled)
        if self.encoders_enabled and SMBus is None:
            raise RuntimeError("smbus2 is not available. Install python3-smbus2.")

        self.i2c_bus_id = i2c_bus
        self.mux_addr = mux_addr
        self.as5600_addr = as5600_addr
        self.left_mux_channel = left_mux_channel
        self.right_mux_channel = right_mux_channel

        self.wheel_radius = wheel_radius
        self.wheel_base = wheel_base
        self.control_period_s = control_period_s
        self.status_period_s = status_period_s
        self.command_timeout_s = float(command_timeout_ms) / 1000.0
        self.pwm_frequency_hz = pwm_frequency_hz

        self.pin_ain1 = pin_ain1
        self.pin_ain2 = pin_ain2
        self.pin_bin1 = pin_bin1
        self.pin_bin2 = pin_bin2
        self.pin_sleep = pin_sleep

        self.left_motor_inverted = left_motor_inverted
        self.right_motor_inverted = right_motor_inverted
        self.left_encoder_inverted = left_encoder_inverted
        self.right_encoder_inverted = right_encoder_inverted

        self.bus = SMBus(self.i2c_bus_id) if self.encoders_enabled else None

        self.left_unwrap = UnwrapState()
        self.right_unwrap = UnwrapState()
        self.left_angle = 0.0
        self.right_angle = 0.0
        self.prev_left_angle = 0.0
        self.prev_right_angle = 0.0
        self.left_encoder_sample_ok = False
        self.right_encoder_sample_ok = False

        self.x_pose = 0.0
        self.y_pose = 0.0
        self.yaw = 0.0

        self.cmd_linear = 0.0
        self.cmd_angular = 0.0
        self.last_cmd_time = time.time()
        self.command_timeout_active = False

        self.sensor_flags = 0
        self.error_flags = 0

        self.stats = {
            "loops": 0,
            "encoder_reads": 0,
            "encoder_failures": 0,
            "i2c_errors": 0,
            "cmd_timeouts": 0,
            "motor_updates": 0,
            "open_loop_updates": 0,
        }

        self.odom_pub = self.create_publisher(Odometry, "wheel_odom", 10)
        self.status_pub = self.create_publisher(String, "robot_status", 10)
        self.cmd_sub = self.create_subscription(Twist, "cmd_vel", self.cmd_vel_callback, 10)

        self._init_gpio()

        self.control_timer = self.create_timer(self.control_period_s, self.control_loop)
        self.status_timer = self.create_timer(self.status_period_s, self.status_callback)

        self.get_logger().info(
            "Starting RPi direct bridge "
            f"(I2C bus={self.i2c_bus_id}, mux=0x{self.mux_addr:02X}, "
            f"AS5600=0x{self.as5600_addr:02X}, control_period={self.control_period_s:.3f}s, "
            f"encoders_enabled={self.encoders_enabled}, "
            f"odom_source={'open_loop_cmd_vel' if self.open_loop_odom_from_cmd else 'encoders'})"
        )

    def _init_gpio(self):
        GPIO.setmode(GPIO.BCM)

        for pin in (self.pin_ain1, self.pin_ain2, self.pin_bin1, self.pin_bin2):
            GPIO.setup(pin, GPIO.OUT)

        if self.pin_sleep >= 0:
            GPIO.setup(self.pin_sleep, GPIO.OUT)
            GPIO.output(self.pin_sleep, GPIO.HIGH)

        self.pwm_ain1 = GPIO.PWM(self.pin_ain1, self.pwm_frequency_hz)
        self.pwm_ain2 = GPIO.PWM(self.pin_ain2, self.pwm_frequency_hz)
        self.pwm_bin1 = GPIO.PWM(self.pin_bin1, self.pwm_frequency_hz)
        self.pwm_bin2 = GPIO.PWM(self.pin_bin2, self.pwm_frequency_hz)

        self.pwm_ain1.start(0.0)
        self.pwm_ain2.start(0.0)
        self.pwm_bin1.start(0.0)
        self.pwm_bin2.start(0.0)

    def _set_motor_output(self, left_cmd, right_cmd):
        left_duty = abs(left_cmd) * 100.0
        right_duty = abs(right_cmd) * 100.0

        if left_cmd >= 0.0:
            self.pwm_ain1.ChangeDutyCycle(left_duty)
            self.pwm_ain2.ChangeDutyCycle(0.0)
        else:
            self.pwm_ain1.ChangeDutyCycle(0.0)
            self.pwm_ain2.ChangeDutyCycle(left_duty)

        if right_cmd >= 0.0:
            self.pwm_bin1.ChangeDutyCycle(right_duty)
            self.pwm_bin2.ChangeDutyCycle(0.0)
        else:
            self.pwm_bin1.ChangeDutyCycle(0.0)
            self.pwm_bin2.ChangeDutyCycle(right_duty)

        self.stats["motor_updates"] += 1

    def _stop_motors(self):
        self._set_motor_output(0.0, 0.0)

    def _select_mux_channel(self, channel):
        if channel < 0 or channel > 7:
            return False
        self.bus.write_byte(self.mux_addr, 1 << channel)
        return True

    def _read_register8(self, reg):
        return self.bus.read_byte_data(self.as5600_addr, reg)

    def _read_register12(self, reg):
        values = self.bus.read_i2c_block_data(self.as5600_addr, reg, 2)
        return (((values[0] << 8) | values[1]) & 0x0FFF)

    def _read_encoder(self, channel, unwrap_state, invert=False):
        if not self._select_mux_channel(channel):
            return False, None

        status = self._read_register8(REG_STATUS)
        raw = self._read_register12(REG_RAW_ANGLE)
        if (status & 0b00100000) == 0:
            return False, None

        continuous_counts = unwrap_raw(raw, unwrap_state)
        angle = raw_counts_to_radians(continuous_counts)
        if invert:
            angle = -angle

        return True, angle

    def read_encoders(self):
        if not self.encoders_enabled:
            self.left_encoder_sample_ok = False
            self.right_encoder_sample_ok = False
            self.sensor_flags &= ~SENSOR_FLAG_ENC_LEFT_OK
            self.sensor_flags &= ~SENSOR_FLAG_ENC_RIGHT_OK
            self.error_flags &= ~ERROR_FLAG_ENC_FAIL
            return

        self.prev_left_angle = self.left_angle
        self.prev_right_angle = self.right_angle

        self.left_encoder_sample_ok = False
        self.right_encoder_sample_ok = False

        try:
            left_ok, left_angle = self._read_encoder(
                self.left_mux_channel,
                self.left_unwrap,
                invert=self.left_encoder_inverted,
            )
            right_ok, right_angle = self._read_encoder(
                self.right_mux_channel,
                self.right_unwrap,
                invert=self.right_encoder_inverted,
            )

            if left_ok and left_angle is not None:
                self.left_angle = left_angle
                self.left_encoder_sample_ok = True
                self.sensor_flags |= SENSOR_FLAG_ENC_LEFT_OK
            else:
                self.sensor_flags &= ~SENSOR_FLAG_ENC_LEFT_OK

            if right_ok and right_angle is not None:
                self.right_angle = right_angle
                self.right_encoder_sample_ok = True
                self.sensor_flags |= SENSOR_FLAG_ENC_RIGHT_OK
            else:
                self.sensor_flags &= ~SENSOR_FLAG_ENC_RIGHT_OK

            if self.left_encoder_sample_ok and self.right_encoder_sample_ok:
                self.error_flags &= ~ERROR_FLAG_ENC_FAIL
                self.stats["encoder_reads"] += 1
            else:
                self.error_flags |= ERROR_FLAG_ENC_FAIL
                self.stats["encoder_failures"] += 1

        except Exception as exc:
            self.stats["i2c_errors"] += 1
            self.error_flags |= ERROR_FLAG_ENC_FAIL
            self.sensor_flags &= ~SENSOR_FLAG_ENC_LEFT_OK
            self.sensor_flags &= ~SENSOR_FLAG_ENC_RIGHT_OK
            self.left_encoder_sample_ok = False
            self.right_encoder_sample_ok = False
            self.get_logger().warn(f"Encoder read failed: {exc}")

    def update_odometry_from_encoders(self):
        if not (self.left_encoder_sample_ok and self.right_encoder_sample_ok):
            return

        d_left = (self.left_angle - self.prev_left_angle) * self.wheel_radius
        d_right = (self.right_angle - self.prev_right_angle) * self.wheel_radius
        d_center = 0.5 * (d_left + d_right)
        d_theta = (d_right - d_left) / self.wheel_base

        self.yaw += d_theta
        self.x_pose += d_center * math.cos(self.yaw)
        self.y_pose += d_center * math.sin(self.yaw)

        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"

        msg.pose.pose.position = Point(x=self.x_pose, y=self.y_pose, z=0.0)
        msg.pose.pose.orientation = euler_to_quaternion(self.yaw)

        if self.control_period_s > 0.0:
            msg.twist.twist.linear.x = d_center / self.control_period_s
            msg.twist.twist.angular.z = d_theta / self.control_period_s

        msg.pose.covariance[0] = 0.1
        msg.pose.covariance[7] = 0.1
        msg.pose.covariance[35] = 0.1
        msg.twist.covariance[0] = 0.1
        msg.twist.covariance[35] = 0.1

        self.odom_pub.publish(msg)

    def update_odometry_open_loop(self):
        self.x_pose, self.y_pose, self.yaw = integrate_pose(
            self.x_pose,
            self.y_pose,
            self.yaw,
            self.cmd_linear,
            self.cmd_angular,
            self.control_period_s,
        )

        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"
        msg.pose.pose.position = Point(x=self.x_pose, y=self.y_pose, z=0.0)
        msg.pose.pose.orientation = euler_to_quaternion(self.yaw)
        msg.twist.twist.linear.x = self.cmd_linear
        msg.twist.twist.angular.z = self.cmd_angular

        # Open-loop odometry is intentionally less trusted than encoder odometry.
        msg.pose.covariance[0] = 0.5
        msg.pose.covariance[7] = 0.5
        msg.pose.covariance[35] = 0.5
        msg.twist.covariance[0] = 0.5
        msg.twist.covariance[35] = 0.5

        self.odom_pub.publish(msg)
        self.stats["open_loop_updates"] += 1

    def cmd_vel_callback(self, msg):
        self.cmd_linear = msg.linear.x
        self.cmd_angular = msg.angular.z
        self.last_cmd_time = time.time()
        self.sensor_flags |= SENSOR_FLAG_CMD_RX_OK
        self.error_flags &= ~ERROR_FLAG_COMM_TIMEOUT
        self.command_timeout_active = False

    def control_loop(self):
        self.stats["loops"] += 1

        now = time.time()
        command_stale = now - self.last_cmd_time > self.command_timeout_s
        if command_stale:
            self.cmd_linear = 0.0
            self.cmd_angular = 0.0
            self.sensor_flags &= ~SENSOR_FLAG_CMD_RX_OK
            self.error_flags |= ERROR_FLAG_COMM_TIMEOUT
            if not self.command_timeout_active:
                self.stats["cmd_timeouts"] += 1
            self.command_timeout_active = True
        else:
            self.error_flags &= ~ERROR_FLAG_COMM_TIMEOUT
            self.command_timeout_active = False

        left_cmd, right_cmd = compute_wheel_commands(
            self.cmd_linear,
            self.cmd_angular,
            self.wheel_base,
            left_inverted=self.left_motor_inverted,
            right_inverted=self.right_motor_inverted,
        )
        self._set_motor_output(left_cmd, right_cmd)

        if self.open_loop_odom_from_cmd:
            self.left_encoder_sample_ok = False
            self.right_encoder_sample_ok = False
            self.sensor_flags &= ~SENSOR_FLAG_ENC_LEFT_OK
            self.sensor_flags &= ~SENSOR_FLAG_ENC_RIGHT_OK
            self.error_flags &= ~ERROR_FLAG_ENC_FAIL
            self.update_odometry_open_loop()
        else:
            self.read_encoders()
            self.update_odometry_from_encoders()

    def status_callback(self):
        msg = String()
        msg.data = (
            f"RPi Direct Bridge: LOOPS={self.stats['loops']} "
            f"ENC_OK_L={1 if self.left_encoder_sample_ok else 0} "
            f"ENC_OK_R={1 if self.right_encoder_sample_ok else 0} "
            f"ENC_READS={self.stats['encoder_reads']} "
            f"ENC_FAIL={self.stats['encoder_failures']} "
            f"I2C_ERR={self.stats['i2c_errors']} "
            f"CMD_TO={self.stats['cmd_timeouts']} "
            f"OPEN_LOOP_UPD={self.stats['open_loop_updates']} "
            f"ENC_EN={1 if self.encoders_enabled else 0} "
            f"ODOM_SRC={'OPEN_LOOP' if self.open_loop_odom_from_cmd else 'ENC'} "
            f"FLAGS=0x{self.sensor_flags:04X} "
            f"ERR=0x{self.error_flags:02X}"
        )
        self.status_pub.publish(msg)

    def destroy_node(self):
        try:
            self._stop_motors()
        except Exception:
            pass

        for pwm in (
            getattr(self, "pwm_ain1", None),
            getattr(self, "pwm_ain2", None),
            getattr(self, "pwm_bin1", None),
            getattr(self, "pwm_bin2", None),
        ):
            if pwm is not None:
                try:
                    pwm.stop()
                except Exception:
                    pass

        if GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass

        bus = getattr(self, "bus", None)
        if bus is not None:
            try:
                bus.close()
            except Exception:
                pass

        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description="Robot RPi Direct Bridge")
    parser.add_argument("--i2c-bus", type=int, default=None, help="I2C bus id (overrides I2C_BUS env)")
    args = parser.parse_args()

    config = resolve_runtime_config(args)
    rclpy.init()

    try:
        node = RobotRpiDirectBridge(**config)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if "node" in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
