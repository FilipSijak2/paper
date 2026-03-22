import importlib.util
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_PATH = REPO_ROOT / "healthcheck_cont" / "healthcheck.py"


def load_healthcheck_module():
    spec = importlib.util.spec_from_file_location("test_healthcheck_runtime", HEALTHCHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wait_for_containers_returns_true_when_all_are_running(monkeypatch):
    module = load_healthcheck_module()

    def fake_run(cmd):
        return 0, "running", ""

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module.time, "time", lambda: 0)

    assert module.wait_for_containers(["nav_cont", "slam_cont"], StringIO(), deadline=999999, poll_s=0) is True


def test_wait_for_containers_logs_warning_on_timeout(monkeypatch):
    module = load_healthcheck_module()
    log_buffer = StringIO()
    tick = {"count": 0}

    def fake_run(cmd):
        return 1, "", "missing"

    def fake_time():
        tick["count"] += 1
        return tick["count"]

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module.time, "time", fake_time)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    assert module.wait_for_containers(["nav_cont"], log_buffer, deadline=1, poll_s=0) is False
    assert "Not all containers reached running state before deadline" in log_buffer.getvalue()


def test_check_ros_topics_resolves_aliases_and_detects_zero_publishers(monkeypatch):
    module = load_healthcheck_module()
    log_buffer = StringIO()

    def fake_exists(path):
        return path == "/opt/ros/humble/setup.sh"

    def fake_run_ros2(args, timeout_s=6):
        if args == ["topic", "list"]:
            return 0, "/scan\n/wheel_odom\n/realsense/color/image_raw\n", ""
        if args == ["topic", "info", "/scan"]:
            return 0, "Publisher count: 1\n", ""
        if args == ["topic", "info", "/wheel_odom"]:
            return 0, "Publisher count: 1\n", ""
        if args == ["topic", "info", "/realsense/color/image_raw"]:
            return 0, "Publisher count: 0\n", ""
        raise AssertionError(f"Unexpected ros2 args: {args}")

    monkeypatch.setattr(module.os.path, "exists", fake_exists)
    monkeypatch.setattr(module, "run_ros2", fake_run_ros2)

    ok = module.check_ros_topics(
        log_buffer,
        ["/scan", "/odom", "/camera/realsense/color/image_raw"],
    )

    assert ok is False
    logs = log_buffer.getvalue()
    assert "ROS topic missing: /odom" not in logs
    assert "/realsense/color/image_raw has zero publishers" in logs


def test_main_returns_error_when_docker_socket_is_missing(tmp_path, monkeypatch):
    module = load_healthcheck_module()

    def fake_exists(path):
        return path != "/var/run/docker.sock"

    monkeypatch.setenv("HEALTHCHECK_LOG_TO_FILE", "0")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setattr(module.os.path, "exists", fake_exists)

    assert module.main() == 1


def test_main_returns_error_when_docker_daemon_is_unreachable(tmp_path, monkeypatch):
    module = load_healthcheck_module()

    def fake_exists(path):
        return True

    monkeypatch.setenv("HEALTHCHECK_LOG_TO_FILE", "0")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setattr(module.os.path, "exists", fake_exists)
    monkeypatch.setattr(module, "run", lambda cmd: (1, "", "docker down"))

    assert module.main() == 1
