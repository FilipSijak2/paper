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
    nav_msgs = ModuleType("nav_msgs")
    nav_msgs_msg = ModuleType("nav_msgs.msg")
    sensor_msgs = ModuleType("sensor_msgs")
    sensor_msgs_msg = ModuleType("sensor_msgs.msg")
    std_msgs = ModuleType("std_msgs")
    std_msgs_msg = ModuleType("std_msgs.msg")

    class Node:
        pass

    class Twist:
        def __init__(self):
            self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

    class PoseWithCovarianceStamped:
        def __init__(self):
            orientation = SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)
            position = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            self.pose = SimpleNamespace(pose=SimpleNamespace(position=position, orientation=orientation))

    class OccupancyGrid:
        def __init__(self):
            orientation = SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)
            position = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            origin = SimpleNamespace(position=position, orientation=orientation)
            self.info = SimpleNamespace(resolution=0.1, width=10, height=10, origin=origin)
            self.data = [0] * 100

    class LaserScan:
        def __init__(self):
            self.angle_min = 0.0
            self.angle_increment = 0.0
            self.range_min = 0.0
            self.range_max = 10.0
            self.ranges = []

    class String:
        def __init__(self):
            self.data = ""

    rclpy_node.Node = Node
    geometry_msgs_msg.Twist = Twist
    geometry_msgs_msg.PoseWithCovarianceStamped = PoseWithCovarianceStamped
    nav_msgs_msg.OccupancyGrid = OccupancyGrid
    sensor_msgs_msg.LaserScan = LaserScan
    std_msgs_msg.String = String
    geometry_msgs.msg = geometry_msgs_msg
    nav_msgs.msg = nav_msgs_msg
    sensor_msgs.msg = sensor_msgs_msg
    std_msgs.msg = std_msgs_msg

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("nav_msgs", nav_msgs)
    inject("nav_msgs.msg", nav_msgs_msg)
    inject("sensor_msgs", sensor_msgs)
    inject("sensor_msgs.msg", sensor_msgs_msg)
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


def test_filter_caps_forward_speed_when_enabled():
    module = load_safety_filter_module()
    msg = make_twist(module, linear_x=0.32, angular_z=0.10)

    out, modified, reason = module.filter_cmd_vel(msg, forward_max_speed=0.22)

    assert out.linear.x == 0.22
    assert out.angular.z == 0.10
    assert modified is True
    assert reason == "forward_speed_limited"


def test_filter_caps_positive_and_negative_angular_speed():
    module = load_safety_filter_module()
    positive = make_twist(module, linear_x=0.10, angular_z=1.20)
    negative = make_twist(module, linear_x=0.10, angular_z=-1.20)

    out_positive, modified_positive, reason_positive = module.filter_cmd_vel(
        positive,
        angular_max_speed=0.45,
    )
    out_negative, modified_negative, reason_negative = module.filter_cmd_vel(
        negative,
        angular_max_speed=0.45,
    )

    assert out_positive.angular.z == 0.45
    assert modified_positive is True
    assert reason_positive == "angular_speed_limited"
    assert out_negative.angular.z == -0.45
    assert modified_negative is True
    assert reason_negative == "angular_speed_limited"


def test_filter_can_still_run_legacy_straight_reverse_mode():
    module = load_safety_filter_module()
    msg = make_twist(module, linear_x=-0.10, angular_z=0.35)

    out, modified, reason = module.filter_cmd_vel(msg, forbid_reverse_turning=True)

    assert out.linear.x == -0.10
    assert out.angular.z == 0.0
    assert modified is True
    assert reason == "reverse_turn_blocked"


def test_scan_sector_detects_front_obstacle():
    module = load_safety_filter_module()
    scan = module.LaserScan()
    scan.angle_min = -0.2
    scan.angle_increment = 0.1
    scan.range_min = 0.02
    scan.range_max = 12.0
    scan.ranges = [1.0, 0.20, 0.21, 1.0]

    assert module.scan_sector_blocked(
        scan,
        distance_m=0.28,
        half_angle_rad=0.25,
        front=True,
        min_points=2,
    )


def test_map_motion_blocks_occupied_cell_ahead():
    module = load_safety_filter_module()
    grid = module.OccupancyGrid()
    grid.info.resolution = 0.1
    grid.info.width = 10
    grid.info.height = 10
    grid.data = [0] * 100
    grid.data[5 * 10 + 7] = 100

    pose = module.PoseWithCovarianceStamped()
    pose.pose.pose.position.x = 0.5
    pose.pose.pose.position.y = 0.5

    assert module.map_motion_blocked(
        grid,
        pose,
        linear_x=0.1,
        lookahead_m=0.25,
        half_width_m=0.0,
    )
