import json
import subprocess
import sys
import threading

import pytest

from tests.test_logging import load_collector_module


FIRST = "2026-03-22T10:00:00.123456789Z"
SECOND = "2026-03-22T10:00:01.123456789Z"


@pytest.fixture
def runtime(tmp_path):
    module = load_collector_module()
    config = dict(
        module.DEFAULT_CONFIG,
        log_dir=str(tmp_path / "logs"),
        state_file=str(tmp_path / "state.json"),
        date_folder_format="%Y-%m-%d",
    )
    collector = module.ContainerLogCollector(config)
    yield module, collector
    collector.shutdown()


def disk_marker(collector):
    return json.loads(collector.state_file.read_text(encoding="utf-8"))["containers"]["nav_cont"]


def use_python_stream(monkeypatch, module, code):
    real_popen = subprocess.Popen
    processes = []

    def start(_cmd, **kwargs):
        proc = real_popen([sys.executable, "-u", "-c", code], **kwargs)
        processes.append(proc)
        return proc

    monkeypatch.setattr(module.subprocess, "Popen", start)
    return processes


def test_state_is_written_only_when_dirty_and_interval_has_elapsed(runtime, monkeypatch):
    module, collector = runtime
    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    collector.last_state_flush = now[0]
    original_save = collector._save_state_locked
    saves = []

    def save():
        saves.append(now[0])
        original_save()

    monkeypatch.setattr(collector, "_save_state_locked", save)
    collector._update_state("nav_cont", FIRST)
    now[0] = 129
    collector._flush_state_if_due()
    assert not collector.state_file.exists()

    now[0] = 130
    collector._flush_state_if_due()
    assert disk_marker(collector)["last_timestamp"] == FIRST
    now[0] = 160
    collector._flush_state_if_due()
    collector._flush_state_if_due(force=True)
    assert saves == [130]

    collector._update_state("nav_cont", SECOND)
    collector._flush_state_if_due()
    assert saves == [130, 160]
    assert disk_marker(collector)["last_timestamp"] == SECOND


def test_failed_save_remains_dirty_and_can_be_retried(runtime, monkeypatch):
    _, collector = runtime
    collector._update_state("nav_cont", FIRST)

    def fail():
        raise OSError("disk temporarily unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(collector, "_save_state_locked", fail)
        with pytest.raises(OSError):
            collector._flush_state_if_due(force=True)
    assert collector.state_dirty
    collector._flush_state_if_due(force=True)
    assert disk_marker(collector)["last_timestamp"] == FIRST
    assert not collector.state_dirty


def test_update_during_flush_is_not_lost(runtime, monkeypatch):
    _, collector = runtime
    collector._update_state("nav_cont", FIRST)
    save_started = threading.Event()
    allow_save = threading.Event()
    update_started = threading.Event()
    update_finished = threading.Event()
    original_save = collector._save_state_locked

    def slow_save():
        save_started.set()
        assert allow_save.wait(5)
        original_save()

    def update():
        update_started.set()
        collector._update_state("nav_cont", SECOND)
        update_finished.set()

    monkeypatch.setattr(collector, "_save_state_locked", slow_save)
    writer = threading.Thread(target=collector._flush_state_if_due, kwargs={"force": True})
    updater = threading.Thread(target=update)
    writer.start()
    try:
        assert save_started.wait(5)
        updater.start()
        assert update_started.wait(5)
        assert not update_finished.wait(0.05)
    finally:
        allow_save.set()
        writer.join(timeout=5)
        if updater.ident is not None:
            updater.join(timeout=5)
    assert not writer.is_alive()
    assert not updater.is_alive()
    assert disk_marker(collector)["last_timestamp"] == FIRST
    assert collector.state_dirty
    collector._flush_state_if_due(force=True)
    assert disk_marker(collector)["last_timestamp"] == SECOND


def test_stream_captures_stdout_and_stderr_without_using_cli_diagnostics_as_markers(
    runtime, monkeypatch, capsys
):
    module, collector = runtime
    code = (
        "import sys\n"
        f"print('{FIRST} normal log', flush=True)\n"
        f"print('{SECOND} error log', file=sys.stderr, flush=True)\n"
        "print('Error response from daemon: diagnostic', file=sys.stderr, flush=True)\n"
    )
    processes = use_python_stream(monkeypatch, module, code)
    collector._stream_logs("nav_cont")
    logs = list(collector.log_dir.rglob("nav_cont.log"))
    lines = logs[0].read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].endswith("normal log")
    assert lines[1].endswith("error log")
    assert collector._get_resume_marker("nav_cont") == (SECOND, 1)
    assert "diagnostic" in capsys.readouterr().out
    assert len(processes) == 1  # A cleanly ended stream waits for the next scan.
    assert processes[0].poll() == 0
    assert collector.stream_processes == {}


def test_resume_skips_only_the_saved_number_of_identical_timestamps(runtime, monkeypatch):
    module, collector = runtime
    for message in ("first", "second"):
        collector._write_log_line("nav_cont", FIRST, message)
        collector._update_state("nav_cont", FIRST)
    collector._flush_state_if_due(force=True)
    resumed = module.ContainerLogCollector(
        dict(
            module.DEFAULT_CONFIG,
            log_dir=str(collector.log_dir),
            state_file=str(collector.state_file),
            date_folder_format="%Y-%m-%d",
        )
    )
    code = "\n".join(f"print('{FIRST} {message}')" for message in ("first", "second", "third"))
    use_python_stream(monkeypatch, module, code)
    try:
        resumed._stream_logs("nav_cont")
    finally:
        resumed.shutdown()
    lines = next(collector.log_dir.rglob("nav_cont.log")).read_text(encoding="utf-8").splitlines()
    assert [line.rsplit(" ", 1)[-1] for line in lines] == ["first", "second", "third"]
    assert disk_marker(resumed)["lines_at_last_timestamp"] == 3


def test_shutdown_stops_a_blocked_stream_and_saves_its_marker(runtime, monkeypatch):
    module, collector = runtime
    written = threading.Event()
    original_update = collector._update_state

    def update(*args):
        original_update(*args)
        written.set()

    monkeypatch.setattr(collector, "_update_state", update)
    monkeypatch.setattr(collector, "_list_target_containers", lambda: ["nav_cont"])
    processes = use_python_stream(
        monkeypatch, module, f"import time\nprint('{FIRST} ready', flush=True)\ntime.sleep(60)"
    )
    collector._ensure_streams()
    assert written.wait(5)
    collector.shutdown()
    assert processes[0].poll() is not None
    assert all(not thread.is_alive() for thread in collector.stream_threads.values())
    assert collector.stream_processes == {}
    assert disk_marker(collector)["last_timestamp"] == FIRST


def test_shutdown_waits_for_an_inflight_log_write_before_saving(runtime, monkeypatch):
    module, collector = runtime
    write_started = threading.Event()
    finish_write = threading.Event()
    shutdown_finished = threading.Event()
    original_write = collector._write_log_line

    def write(*args):
        original_write(*args)
        write_started.set()
        assert finish_write.wait(5)

    def shutdown():
        collector.shutdown()
        shutdown_finished.set()

    monkeypatch.setattr(collector, "_write_log_line", write)
    monkeypatch.setattr(collector, "_list_target_containers", lambda: ["nav_cont"])
    use_python_stream(
        monkeypatch, module, f"import time\nprint('{FIRST} ready', flush=True)\ntime.sleep(60)"
    )
    collector._ensure_streams()
    stopper = threading.Thread(target=shutdown)
    try:
        assert write_started.wait(5)
        stopper.start()
        assert collector.stop_event.wait(5)
        assert not shutdown_finished.wait(0.05)
    finally:
        finish_write.set()
        if stopper.ident is not None:
            stopper.join(timeout=5)
    assert shutdown_finished.is_set()
    assert disk_marker(collector)["last_timestamp"] == FIRST


def test_shutdown_catches_a_process_still_being_started(runtime, monkeypatch):
    module, collector = runtime
    started = threading.Event()
    finish_start = threading.Event()
    real_popen = subprocess.Popen
    processes = []

    def delayed_start(_cmd, **kwargs):
        proc = real_popen([sys.executable, "-u", "-c", "import time; time.sleep(60)"], **kwargs)
        processes.append(proc)
        started.set()
        assert finish_start.wait(5)
        return proc

    monkeypatch.setattr(module.subprocess, "Popen", delayed_start)
    monkeypatch.setattr(collector, "_list_target_containers", lambda: ["nav_cont"])
    collector._ensure_streams()
    stopper = threading.Thread(target=collector.shutdown)
    try:
        assert started.wait(5)
        assert collector.stream_processes == {}
        stopper.start()
        assert collector.stop_event.wait(5)
    finally:
        finish_start.set()
        if stopper.ident is not None:
            stopper.join(timeout=5)
    assert not stopper.is_alive()
    assert processes[0].poll() is not None
    assert all(not thread.is_alive() for thread in collector.stream_threads.values())
    assert collector.stream_processes == {}


@pytest.mark.skipif(sys.platform == "win32", reason="Requires POSIX signal handling")
def test_shutdown_kills_a_cli_that_ignores_sigterm(runtime, monkeypatch):
    module, collector = runtime
    written = threading.Event()
    original_update = collector._update_state

    def update(*args):
        original_update(*args)
        written.set()

    monkeypatch.setattr(collector, "_update_state", update)
    monkeypatch.setattr(collector, "_list_target_containers", lambda: ["nav_cont"])
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"print('{FIRST} ready', flush=True)\n"
        "time.sleep(60)"
    )
    processes = use_python_stream(monkeypatch, module, code)
    collector._ensure_streams()
    assert written.wait(5)
    collector.shutdown()
    assert processes[0].poll() == -module.signal.SIGKILL
    assert disk_marker(collector)["last_timestamp"] == FIRST


@pytest.mark.parametrize("scan_interval,flush_interval", [(30, 7), (5, 30)])
def test_scan_and_flush_use_independent_intervals(
    runtime, monkeypatch, scan_interval, flush_interval
):
    module, collector = runtime
    now = [0.0]
    scans = []
    flushes = []

    class ClockEvent:
        stopped = False

        def is_set(self):
            return self.stopped

        def set(self):
            self.stopped = True

        def wait(self, timeout):
            assert timeout > 0
            now[0] = min(65, now[0] + timeout)
            self.stopped = now[0] >= 65
            return self.stopped

    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(module, "run", lambda cmd: (0, "", ""))
    monkeypatch.setattr(collector, "stop_event", ClockEvent())
    monkeypatch.setattr(collector, "_ensure_streams", lambda: scans.append(now[0]))
    monkeypatch.setattr(
        collector, "_flush_state_if_due", lambda force=False: flushes.append((now[0], force))
    )
    collector.scan_interval_seconds = scan_interval
    collector.state_flush_interval_seconds = flush_interval
    assert collector.run_forever() == 0
    assert scans == list(range(0, 65, scan_interval))
    assert [when for when, force in flushes if not force] == list(
        range(flush_interval, 65, flush_interval)
    )
    assert flushes[-1] == (65, True)


@pytest.mark.parametrize(
    "override",
    [
        {"scan_interval_seconds": 0},
        {"reconnect_delay_seconds": -1},
        {"state_flush_interval_seconds": False},
        {"state_flush_interval_seconds": "invalid"},
        {"include_containers": "nav_cont"},
        {"exclude_containers": None},
        {"enabled": "false"},
    ],
)
def test_invalid_config_is_rejected_instead_of_causing_bad_loops(override):
    module = load_collector_module()
    with pytest.raises(ValueError):
        module.normalize_config(override)


@pytest.mark.parametrize("raw", [[], {"container_logging": None}, {"container_logging": []}])
def test_invalid_yaml_structure_is_rejected(tmp_path, raw):
    module = load_collector_module()
    path = tmp_path / "logging.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="mappings"):
        module.load_config(str(path))


def test_state_loader_keeps_valid_entries_and_ignores_invalid_ones(runtime):
    _, collector = runtime
    collector.state_file.write_text(
        json.dumps(
            {
                "containers": {
                    "nav_cont": {"last_timestamp": FIRST, "lines_at_last_timestamp": 2},
                    "invalid_count": {"last_timestamp": FIRST, "lines_at_last_timestamp": "bad"},
                    "invalid_timestamp": {
                        "last_timestamp": "Error response",
                        "lines_at_last_timestamp": 1,
                    },
                    "invalid_entry": [],
                }
            }
        ),
        encoding="utf-8",
    )
    assert collector._load_state() == {
        "nav_cont": {"last_timestamp": FIRST, "lines_at_last_timestamp": 2}
    }
    collector.state_file.write_text("[]", encoding="utf-8")
    assert collector._load_state() == {}


def test_main_registers_and_restores_shutdown_signal_handlers(runtime, monkeypatch):
    module, collector = runtime
    previous = {module.signal.SIGINT: object(), module.signal.SIGTERM: object()}
    handlers = dict(previous)

    def register(signum, handler):
        old = handlers[signum]
        handlers[signum] = handler
        return old

    def run_forever():
        handlers[module.signal.SIGTERM](module.signal.SIGTERM, None)
        assert collector.stop_event.is_set()
        return 0

    monkeypatch.setattr(module.signal, "signal", register)
    monkeypatch.setattr(module, "load_config", lambda path: {})
    monkeypatch.setattr(module, "ContainerLogCollector", lambda config: collector)
    monkeypatch.setattr(collector, "run_forever", run_forever)
    assert module.main() == 0
    assert handlers == previous


def test_docker_control_command_has_a_timeout(monkeypatch):
    module = load_collector_module()

    def stalled(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(module.subprocess, "run", stalled)
    code, out, error = module.run(["docker", "info"])
    assert code == 124
    assert out == ""
    assert "5 seconds" in error
