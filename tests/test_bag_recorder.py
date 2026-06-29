import importlib.util
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "bag_recorder_cont" / "bag_recorder.sh"
EVENT_SCRIPT_PATH = REPO_ROOT / "bag_recorder_cont" / "experiment_event.py"
STACK_RECORDED_TOPICS_PATH = REPO_ROOT.parent / "stack" / "config" / "containers" / "recorded_topics.yaml"


def bash_available() -> bool:
    bash = shutil.which("bash")
    if not bash:
        return False
    try:
        proc = subprocess.run([bash, "--version"], capture_output=True, text=True, check=False)
    except OSError:
        return False
    return proc.returncode == 0


pytestmark = pytest.mark.skipif(not bash_available(), reason="bash is not available in this environment")


def run_bash(snippet: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-lc", snippet],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def source_script_snippet() -> str:
    return f"source {shlex.quote(SCRIPT_PATH.as_posix())}"


def test_load_topics_file_parses_yaml_array(tmp_path):
    topics_file = tmp_path / "topics.yaml"
    topics_file.write_text(
        "\n".join(
            [
                "# comment",
                "- /scan",
                "- /odom   # inline comment",
                "",
                "  - /camera/realsense/color/image_raw",
            ]
        ),
        encoding="utf-8",
    )

    proc = run_bash(
        f"""
        {source_script_snippet()}
        TOPICS_FILE={shlex.quote(topics_file.as_posix())}
        load_topics_file
        printf '%s\\n' "${{TOPICS[@]}}"
        """
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines() == [
        "/scan",
        "/odom",
        "/camera/realsense/color/image_raw",
    ]


def test_stack_recorded_topics_include_corrected_imu_streams():
    if not STACK_RECORDED_TOPICS_PATH.exists():
        pytest.skip("Sibling stack recorded topics file is not available")

    content = STACK_RECORDED_TOPICS_PATH.read_text(encoding="utf-8")
    topics = {
        line.split("#", 1)[0].strip()[2:].strip()
        for line in content.splitlines()
        if line.split("#", 1)[0].strip().startswith("- ")
    }

    assert "/imu/base_link" in topics
    assert "/imu/base_link_corrected" in topics


def test_stack_recorded_topics_include_ml_anomaly_dataset_streams():
    if not STACK_RECORDED_TOPICS_PATH.exists():
        pytest.skip("Sibling stack recorded topics file is not available")

    content = STACK_RECORDED_TOPICS_PATH.read_text(encoding="utf-8")
    topics = {
        line.split("#", 1)[0].strip()[2:].strip()
        for line in content.splitlines()
        if line.split("#", 1)[0].strip().startswith("- ")
    }
    required_topics = {
        "/cmd_vel",
        "/cmd_vel_auto",
        "/cmd_vel_collision_in",
        "/cmd_vel_safety_in",
        "/scan",
        "/scan_filtered",
        "/imu/data",
        "/wheel_odom",
        "/odometry/filtered",
        "/robot_status",
        "/cmd_vel_safety_status",
        "/tf",
        "/tf_static",
        "/experiment_event",
    }

    assert required_topics <= topics


def test_experiment_event_labels_are_validated_without_ros_runtime():
    spec = importlib.util.spec_from_file_location("experiment_event", EVENT_SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.resolve_event("normal_straight", "start") == "normal_straight_start"
    assert module.resolve_event("collision_end", None) == "collision_end"
    assert module.resolve_event("unstable", None) is None

    with pytest.raises(ValueError):
        module.resolve_event("normal_strait", "start")


def test_refresh_topic_resolution_resolves_aliases_to_active_topics():
    proc = run_bash(
        f"""
        {source_script_snippet()}
        TOPICS=(/odom /camera/realsense/color/image_raw)
        topic_exists() {{
          [[ "$1" == "/wheel_odom" || "$1" == "/realsense/color/image_raw" ]]
        }}
        topic_has_publishers() {{
          topic_exists "$1"
        }}
        refresh_topic_resolution
        printf 'RESOLVED:%s\\n' "${{RESOLVED_TOPICS[@]}}"
        printf 'ACTIVE:%s\\n' "${{ACTIVE_TOPICS[@]}}"
        """
    )

    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.strip().splitlines()
    assert "RESOLVED:/wheel_odom" in lines
    assert "RESOLVED:/realsense/color/image_raw" in lines
    assert "ACTIVE:/wheel_odom" in lines
    assert "ACTIVE:/realsense/color/image_raw" in lines


def test_wait_for_active_topics_succeeds_when_publisher_appears():
    proc = run_bash(
        f"""
        {source_script_snippet()}
        TOPICS=(/odom)
        TOPIC_WAIT_TIMEOUT_S=1
        TOPIC_RECHECK_INTERVAL_S=0
        MIN_ACTIVE_TOPICS=1
        calls=0
        topic_exists() {{
          [[ "$1" == "/wheel_odom" ]]
        }}
        topic_has_publishers() {{
          if [[ "$1" == "/wheel_odom" ]]; then
            calls=$((calls + 1))
            [[ "$calls" -ge 2 ]]
            return
          fi
          return 1
        }}
        wait_for_active_topics
        echo "STATUS:$?"
        printf '%s\\n' "${{ACTIVE_TOPICS[@]}}"
        """
    )

    assert proc.returncode == 0, proc.stderr
    assert "STATUS:0" in proc.stdout
    assert "/wheel_odom" in proc.stdout


def test_wait_for_active_topics_times_out_without_publishers():
    proc = run_bash(
        f"""
        {source_script_snippet()}
        TOPICS=(/odom)
        TOPIC_WAIT_TIMEOUT_S=0
        TOPIC_RECHECK_INTERVAL_S=0
        MIN_ACTIVE_TOPICS=1
        topic_exists() {{
          return 1
        }}
        topic_has_publishers() {{
          return 1
        }}
        set +e
        wait_for_active_topics
        status=$?
        set -e
        echo "STATUS:$status"
        """
    )

    assert proc.returncode == 0, proc.stderr
    assert "STATUS:1" in proc.stdout
    assert "No active publishers found" in proc.stderr
