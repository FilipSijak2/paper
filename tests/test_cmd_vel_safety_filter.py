import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
FILTER_PATH = REPO_ROOT / "nav_cont" / "cmd_vel_safety_filter.py"


def load_safety_filter_module():
    previous_modules = {}

    def inject(name: str, module: ModuleType):
        previous_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    rclpy = ModuleType("rclpy")
    rclpy_node = ModuleType("rclpy.node")
    geometry_msgs = ModuleType("geometry_msgs")
    geometry_msgs_msg = ModuleType("geometry_msgs.msg")
    std_msgs = ModuleType("std_msgs")
    std_msgs_msg = ModuleType("std_msgs.msg")

    class Node:
        pass

    class Twist:
        def __init__(self):
            self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

    class String:
        def __init__(self):
            self.data = ""

    rclpy_node.Node = Node
    geometry_msgs_msg.Twist = Twist
    std_msgs_msg.String = String
    geometry_msgs.msg = geometry_msgs_msg
    std_msgs.msg = std_msgs_msg

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("std_msgs", std_msgs)
    inject("std_msgs.msg", std_msgs_msg)

    try:
        spec = importlib.util.spec_from_file_location("test_cmd_vel_safety_filter", FILTER_PATH)
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


def make_twist(module, linear_x: float, angular_z: float):
    msg = module.Twist()
    msg.linear.x = linear_x
    msg.angular.z = angular_z
    return msg


def test_filter_allows_reverse_turning_by_default():
    module = load_safety_filter_module()
    msg = make_twist(module, linear_x=-0.10, angular_z=0.35)

    out, modified, reason = module.filter_cmd_vel(msg)

    assert out.linear.x == -0.10
    assert out.angular.z == 0.35
    assert modified is False
    assert reason == "unchanged"


def test_filter_caps_reverse_speed_without_removing_steering():
    module = load_safety_filter_module()
    msg = make_twist(module, linear_x=-0.50, angular_z=-0.20)

    out, modified, reason = module.filter_cmd_vel(msg, reverse_max_speed=0.22)

    assert out.linear.x == -0.22
    assert out.angular.z == -0.20
    assert modified is True
    assert reason == "reverse_speed_limited"


def test_filter_can_still_run_legacy_straight_reverse_mode():
    module = load_safety_filter_module()
    msg = make_twist(module, linear_x=-0.10, angular_z=0.35)

    out, modified, reason = module.filter_cmd_vel(msg, forbid_reverse_turning=True)

    assert out.linear.x == -0.10
    assert out.angular.z == 0.0
    assert modified is True
    assert reason == "reverse_turn_blocked"
