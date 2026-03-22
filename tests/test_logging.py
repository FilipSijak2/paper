import importlib.util
import json
import sys
from datetime import datetime as real_datetime
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
HEALTHCHECK_PATH = REPO_ROOT / "healthcheck_cont" / "healthcheck.py"
COLLECTOR_PATH = REPO_ROOT / "healthcheck_cont" / "container_log_collector.py"


def load_module(module_name: str, file_path: Path, injected_modules=None):
    injected_modules = injected_modules or {}
    previous = {}

    for name, module in injected_modules.items():
        previous[name] = sys.modules.get(name)
        sys.modules[name] = module

    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, module in injected_modules.items():
            if previous[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous[name]


def load_collector_module():
    yaml_stub = ModuleType("yaml")

    def safe_load(value):
        if hasattr(value, "read"):
            value = value.read()
        return json.loads(value)

    yaml_stub.safe_load = safe_load
    return load_module("test_container_log_collector", COLLECTOR_PATH, {"yaml": yaml_stub})


def load_healthcheck_module():
    return load_module("test_healthcheck", HEALTHCHECK_PATH)


def test_daily_log_path_uses_date_folder_and_container_name(tmp_path, monkeypatch):
    healthcheck = load_healthcheck_module()

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            base = real_datetime(2026, 3, 22, 11, 20, 19)
            return base if tz is None else base.astimezone(tz)

    monkeypatch.setenv("LOG_DATE_FORMAT", "%Y-%m-%d")
    monkeypatch.setattr(healthcheck, "datetime", FrozenDateTime)

    path = healthcheck.daily_log_path(str(tmp_path), "healthcheck_cont")

    assert Path(path) == tmp_path / "2026-03-22" / "healthcheck_cont.log"
    assert (tmp_path / "2026-03-22").is_dir()


def test_log_writes_timestamped_line_to_file_handle(monkeypatch):
    healthcheck = load_healthcheck_module()

    class FrozenDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            base = real_datetime(2026, 3, 22, 11, 20, 19, 456000)
            return base if tz is None else base.astimezone(tz)

    monkeypatch.setattr(healthcheck, "datetime", FrozenDateTime)

    from io import StringIO

    buffer = StringIO()
    healthcheck.log("hello world", file_handle=buffer)

    contents = buffer.getvalue().strip()
    assert contents.startswith("[2026-03-22 11:20:19.456")
    assert contents.endswith("hello world")


def test_load_config_merges_yaml_and_env_overrides(tmp_path, monkeypatch):
    collector_module = load_collector_module()
    config_path = tmp_path / "logging.json"
    config_path.write_text(
        json.dumps(
            {
                "container_logging": {
                    "enabled": True,
                    "log_dir": "/from-config/logs",
                    "state_file": "/from-config/state.json",
                    "include_containers": ["nav_cont"],
                    "exclude_containers": ["healthcheck_cont"],
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("LOG_DIR", str(tmp_path / "override-logs"))
    monkeypatch.setenv("LOG_STATE_FILE", str(tmp_path / "override-state.json"))

    config = collector_module.load_config(str(config_path))

    assert config["log_dir"] == str(tmp_path / "override-logs")
    assert config["state_file"] == str(tmp_path / "override-state.json")
    assert config["include_containers"] == ["nav_cont"]
    assert config["exclude_containers"] == ["healthcheck_cont"]


def test_update_state_counts_duplicate_timestamps_and_persists(tmp_path):
    collector_module = load_collector_module()
    collector = collector_module.ContainerLogCollector(
        {
            "enabled": True,
            "log_dir": str(tmp_path / "logs"),
            "state_file": str(tmp_path / "state.json"),
            "date_folder_format": "%Y-%m-%d",
            "scan_interval_seconds": 1,
            "reconnect_delay_seconds": 1,
            "include_containers": [],
            "exclude_containers": [],
        }
    )

    collector._update_state("nav_cont", "2026-03-22T10:00:00.000000000Z")
    collector._update_state("nav_cont", "2026-03-22T10:00:00.000000000Z")
    collector._update_state("nav_cont", "2026-03-22T10:01:00.000000000Z")

    assert collector.state["nav_cont"]["last_timestamp"] == "2026-03-22T10:01:00.000000000Z"
    assert collector.state["nav_cont"]["lines_at_last_timestamp"] == 1

    state_on_disk = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state_on_disk["containers"]["nav_cont"]["last_timestamp"] == "2026-03-22T10:01:00.000000000Z"
    assert state_on_disk["containers"]["nav_cont"]["lines_at_last_timestamp"] == 1


def test_write_log_line_creates_daily_container_file(tmp_path):
    collector_module = load_collector_module()
    collector = collector_module.ContainerLogCollector(
        {
            "enabled": True,
            "log_dir": str(tmp_path / "logs"),
            "state_file": str(tmp_path / "state.json"),
            "date_folder_format": "%Y-%m-%d",
            "scan_interval_seconds": 1,
            "reconnect_delay_seconds": 1,
            "include_containers": [],
            "exclude_containers": [],
        }
    )

    collector._write_log_line(
        "nav_cont",
        "2026-03-22T10:00:00.123456789Z",
        "navigation started",
    )

    log_path = tmp_path / "logs" / "2026-03-22" / "nav_cont.log"
    contents = log_path.read_text(encoding="utf-8").strip()
    assert log_path.exists()
    assert contents.startswith("[2026-03-22")
    assert contents.endswith("navigation started")


def test_list_target_containers_honors_exclude_filter(tmp_path, monkeypatch):
    collector_module = load_collector_module()

    def fake_run(cmd):
        assert "com.docker.compose.project=stack" in cmd[-1]
        return 0, "nav_cont\nhealthcheck_cont\nslam_cont\n", ""

    monkeypatch.setattr(collector_module, "run", fake_run)

    collector = collector_module.ContainerLogCollector(
        {
            "enabled": True,
            "log_dir": str(tmp_path / "logs"),
            "state_file": str(tmp_path / "state.json"),
            "date_folder_format": "%Y-%m-%d",
            "scan_interval_seconds": 1,
            "reconnect_delay_seconds": 1,
            "include_containers": [],
            "exclude_containers": ["healthcheck_cont"],
        }
    )

    assert collector._list_target_containers() == ["nav_cont", "slam_cont"]
