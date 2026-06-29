import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = REPO_ROOT / "realsense_cont" / "realsense_watchdog.py"


def load_watchdog_module():
    spec = importlib.util.spec_from_file_location("realsense_watchdog", WATCHDOG_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stream_waits_within_startup_grace_period():
    module = load_watchdog_module()

    reason = module.stream_failure_reason(
        started_at=100.0,
        last_message_at=None,
        now=159.9,
        startup_timeout_s=60.0,
        stale_timeout_s=15.0,
    )

    assert reason is None


def test_stream_fails_when_first_frame_never_arrives():
    module = load_watchdog_module()

    reason = module.stream_failure_reason(
        started_at=100.0,
        last_message_at=None,
        now=160.0,
        startup_timeout_s=60.0,
        stale_timeout_s=15.0,
    )

    assert reason == "no first frame received after 60.0s"


def test_stream_fails_after_frames_become_stale():
    module = load_watchdog_module()

    reason = module.stream_failure_reason(
        started_at=100.0,
        last_message_at=140.0,
        now=155.1,
        startup_timeout_s=60.0,
        stale_timeout_s=15.0,
    )

    assert reason == "image stream stale for 15.1s"


def test_recent_frame_keeps_stream_healthy():
    module = load_watchdog_module()

    reason = module.stream_failure_reason(
        started_at=100.0,
        last_message_at=150.0,
        now=155.0,
        startup_timeout_s=60.0,
        stale_timeout_s=15.0,
    )

    assert reason is None
