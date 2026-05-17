import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
SLAM_MANAGER_PATH = REPO_ROOT / "slam_cont" / "slam_manager.py"


def load_slam_manager_module():
    previous_modules = {}

    def inject(name: str, module: ModuleType):
        previous_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    rclpy = ModuleType("rclpy")
    rclpy_node = ModuleType("rclpy.node")
    yaml_mod = ModuleType("yaml")

    class Node:
        pass

    def safe_load(value):
        if hasattr(value, "read"):
            value = value.read()
        return json.loads(value)

    rclpy_node.Node = Node
    yaml_mod.safe_load = safe_load

    inject("rclpy", rclpy)
    inject("rclpy.node", rclpy_node)
    inject("yaml", yaml_mod)

    try:
        spec = importlib.util.spec_from_file_location("test_slam_manager", SLAM_MANAGER_PATH)
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


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warn(self, message):
        self.warnings.append(message)


class DummyProcess:
    def terminate(self):
        pass

    def wait(self):
        pass


def make_manager(module):
    manager = module.SlamManager.__new__(module.SlamManager)
    manager.process = None
    manager._logger = FakeLogger()
    manager.get_logger = lambda: manager._logger
    return manager


def test_start_slam_toolbox_uses_params_file_and_normalizes_rmw(monkeypatch):
    module = load_slam_manager_module()
    manager = make_manager(module)
    commands = []

    def fake_popen(cmd, *args, **kwargs):
        commands.append(cmd)
        return DummyProcess()

    monkeypatch.setenv("RMW_IMPLEMENTATION", "cyclonedx")
    monkeypatch.setenv("PUBLISH_LASER_STATIC_TF", "0")
    monkeypatch.setenv("DUMP_SLAM_PARAMS", "0")
    monkeypatch.delenv("STATIC_TF_FILE", raising=False)
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        module.os.path,
        "exists",
        lambda path: path == "/app/slam_params.yaml",
    )

    module.SlamManager.start_slam_toolbox(manager)

    assert os.environ["RMW_IMPLEMENTATION"] == "rmw_cyclonedds_cpp"
    assert commands[0] == [
        "ros2",
        "run",
        "slam_toolbox",
        "localization_slam_toolbox_node",
        "--ros-args",
        "--params-file",
        "/app/slam_params.yaml",
    ]


def test_start_slam_toolbox_falls_back_to_launch_when_params_missing(monkeypatch):
    module = load_slam_manager_module()
    manager = make_manager(module)
    commands = []

    def fake_popen(cmd, *args, **kwargs):
        commands.append(cmd)
        return DummyProcess()

    monkeypatch.delenv("RMW_IMPLEMENTATION", raising=False)
    monkeypatch.setenv("PUBLISH_LASER_STATIC_TF", "0")
    monkeypatch.setenv("DUMP_SLAM_PARAMS", "0")
    monkeypatch.delenv("STATIC_TF_FILE", raising=False)
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module.os.path, "exists", lambda path: False)

    module.SlamManager.start_slam_toolbox(manager)

    assert os.environ["RMW_IMPLEMENTATION"] == "rmw_cyclonedds_cpp"
    assert commands[0] == ["ros2", "launch", "slam_toolbox", "localization_launch.py"]


def test_start_rf2o_matches_working_launch_parameters(monkeypatch):
    module = load_slam_manager_module()
    manager = make_manager(module)
    commands = []

    def fake_popen(cmd, *args, **kwargs):
        commands.append(cmd)
        return DummyProcess()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    module.SlamManager.start_rf2o(manager)

    assert commands
    assert commands[0] == [
        "ros2",
        "run",
        "rf2o_laser_odometry",
        "rf2o_laser_odometry_node",
        "--ros-args",
        "-r",
        "__node:=rf2o_laser_odometry",
        "-p",
        "laser_scan_topic:=/scan",
        "-p",
        "odom_topic:=/odom_rf2o",
        "-p",
        "publish_tf:=false",
        "-p",
        "base_frame_id:=base_link",
        "-p",
        "odom_frame_id:=odom",
        "-p",
        "freq:=20.0",
    ]


def test_start_slam_toolbox_loads_valid_static_tf_and_skips_invalid_entry(tmp_path, monkeypatch):
    module = load_slam_manager_module()
    manager = make_manager(module)
    commands = []

    static_tf_path = tmp_path / "static_tf.json"
    static_tf_path.write_text(
        json.dumps(
            {
                "static_transforms": [
                    {
                        "parent": "base_link",
                        "child": "laser",
                        "translation": [0, 0, 0],
                        "rotation_rpy": [0, 0, 0],
                    },
                    {
                        "parent": "base_link",
                        "child": "bad_tf",
                        "translation": [0, 0],
                        "rotation_rpy": [0, 0, 0],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_popen(cmd, *args, **kwargs):
        commands.append(cmd)
        return DummyProcess()

    def fake_exists(path):
        if path == "/app/slam_params.yaml":
            return False
        if path == str(static_tf_path):
            return True
        return False

    monkeypatch.setenv("PUBLISH_LASER_STATIC_TF", "0")
    monkeypatch.setenv("DUMP_SLAM_PARAMS", "0")
    monkeypatch.setenv("STATIC_TF_FILE", str(static_tf_path))
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module.os.path, "exists", fake_exists)

    module.SlamManager.start_slam_toolbox(manager)

    assert commands[0] == ["ros2", "launch", "slam_toolbox", "localization_launch.py"]
    assert [
        "ros2",
        "run",
        "tf2_ros",
        "static_transform_publisher",
        "--frame-id", "base_link",
        "--child-frame-id", "laser",
        "--x", "0",
        "--y", "0",
        "--z", "0",
        "--roll", "0",
        "--pitch", "0",
        "--yaw", "0",
    ] in commands
    assert not any(cmd[-1] == "bad_tf" for cmd in commands if isinstance(cmd, list))
    assert any("neispravna duljina" in warning for warning in manager._logger.warnings)
