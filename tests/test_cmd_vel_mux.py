import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
MUX_PATH = REPO_ROOT / "nav_cont" / "cmd_vel_mux.py"


def load_cmd_vel_mux_module():
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
    std_srvs = ModuleType("std_srvs")
    std_srvs_srv = ModuleType("std_srvs.srv")

    class Node:
        pass

    class Twist:
        def __init__(self):
            self.linear = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            self.angular = SimpleNamespace(x=0.0, y=0.0, z=0.0)

    class Bool:
        def __init__(self):
            self.data = False

    class SetBool:
        class Request:
            def __init__(self):
                self.data = False

        class Response:
            def __init__(self):
                self.success = False
                self.message = ""

    rclpy_node.Node = Node
    geometry_msgs_msg.Twist = Twist
    std_msgs_msg.Bool = Bool
    std_srvs_srv.SetBool = SetBool
    geometry_msgs.msg = geometry_msgs_msg
    std_msgs.msg = std_msgs_msg
    std_srvs.srv = std_srvs_srv

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("geometry_msgs", geometry_msgs)
    inject("geometry_msgs.msg", geometry_msgs_msg)
    inject("std_msgs", std_msgs)
    inject("std_msgs.msg", std_msgs_msg)
    inject("std_srvs", std_srvs)
    inject("std_srvs.srv", std_srvs_srv)

    try:
        spec = importlib.util.spec_from_file_location("test_cmd_vel_mux", MUX_PATH)
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


class FakeTime:
    def __init__(self, nanoseconds: int):
        self.nanoseconds = nanoseconds

    def __sub__(self, other):
        return SimpleNamespace(nanoseconds=self.nanoseconds - other.nanoseconds)


class FakeClock:
    def __init__(self, now_ns: int):
        self._now_ns = now_ns

    def now(self):
        return FakeTime(self._now_ns)


class FakePublisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)


class FakeLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warn(self, message):
        self.warnings.append(message)

    def info(self, message):
        self.infos.append(message)


def make_twist(module, linear_x: float = 0.0, angular_z: float = 0.0):
    twist = module.Twist()
    twist.linear.x = linear_x
    twist.angular.z = angular_z
    return twist


def make_mux(module, *, now_ns: int = 0):
    mux = module.CmdVelMux.__new__(module.CmdVelMux)
    mux.manual_mode = False
    mux.manual_timeout_s = 0.5
    mux.auto_timeout_s = 0.7
    mux.last_auto = None
    mux.last_auto_time = None
    mux.last_joy = None
    mux.last_joy_time = None
    mux._auto_stale_warned = False
    mux._joy_stale_warned = False
    mux.pub = FakePublisher()
    mux.mode_pub = FakePublisher()
    mux._logger = FakeLogger()
    mux.get_logger = lambda: mux._logger
    mux.get_clock = lambda: FakeClock(now_ns)
    return mux


def test_publish_cb_uses_fresh_joy_in_manual_mode():
    module = load_cmd_vel_mux_module()
    mux = make_mux(module, now_ns=100_000_000)
    mux.manual_mode = True
    mux.last_joy = make_twist(module, linear_x=1.2, angular_z=0.4)
    mux.last_joy_time = FakeTime(0)

    module.CmdVelMux._publish_cb(mux)

    published = mux.pub.messages[-1]
    assert published.linear.x == 1.2
    assert published.angular.z == 0.4


def test_publish_cb_uses_fresh_auto_in_auto_mode():
    module = load_cmd_vel_mux_module()
    mux = make_mux(module, now_ns=200_000_000)
    mux.manual_mode = False
    mux.last_auto = make_twist(module, linear_x=0.7, angular_z=-0.2)
    mux.last_auto_time = FakeTime(0)

    module.CmdVelMux._publish_cb(mux)

    published = mux.pub.messages[-1]
    assert published.linear.x == 0.7
    assert published.angular.z == -0.2


def test_publish_cb_stale_manual_command_publishes_stop_and_warns():
    module = load_cmd_vel_mux_module()
    mux = make_mux(module, now_ns=2_000_000_000)
    mux.manual_mode = True
    mux.last_joy = make_twist(module, linear_x=1.0, angular_z=1.0)
    mux.last_joy_time = FakeTime(0)

    module.CmdVelMux._publish_cb(mux)

    published = mux.pub.messages[-1]
    assert published.linear.x == 0.0
    assert published.angular.z == 0.0
    assert mux._joy_stale_warned is True
    assert len(mux._logger.warnings) == 1


def test_set_mode_cb_updates_mode_and_publishes_mode_flag():
    module = load_cmd_vel_mux_module()
    mux = make_mux(module)
    req = module.SetBool.Request()
    res = module.SetBool.Response()
    req.data = True

    returned = module.CmdVelMux._set_mode_cb(mux, req, res)

    assert returned.success is True
    assert returned.message == "manual"
    assert mux.manual_mode is True
    assert mux.mode_pub.messages[-1].data is True
