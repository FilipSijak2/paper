#!/usr/bin/env python3
"""Basic healthcheck script for the robot stack.

Checks expected Docker containers, reports their runtime and health status,
and writes a timestamped report into the mounted logs directory.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import List, Tuple


def run(cmd: List[str]) -> Tuple[int, str, str]:
    """Run a command and capture exit code, stdout, stderr."""
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:  # docker missing
        return 127, "", str(exc)


def log(line: str, *, file_handle) -> None:
    print(line)
    file_handle.write(line + "\n")


def run_ros2(args: List[str], timeout_s: int = 6) -> Tuple[int, str, str]:
    """Run a ROS2 CLI command via bash sourcing the ROS environment."""
    cmd = [
        "bash",
        "-lc",
        f"source /opt/ros/{os.environ.get('ROS_DISTRO', 'humble')}/setup.sh && timeout {timeout_s}s ros2 "
        + " ".join(args),
    ]
    return run(cmd)


def wait_for_containers(containers: List[str], fh, deadline: float, poll_s: int = 5) -> bool:
    """Poll until all containers are running or the deadline is reached."""
    while time.time() < deadline:
        all_running = True
        for name in containers:
            code, out, _ = run(["docker", "inspect", "--format", "{{.State.Status}}", name])
            if code != 0 or out != "running":
                all_running = False
                break
        if all_running:
            return True
        time.sleep(poll_s)
    log("WARN: Not all containers reached running state before deadline.", file_handle=fh)
    return False


def check_port(host: str, port: int, label: str, fh, timeout_s: int = 2) -> bool:
    code, _, err = run(["nc", "-z", "-w", str(timeout_s), host, str(port)])
    if code == 0:
        log(f"{label}: port {port} reachable", file_handle=fh)
        return True
    log(f"WARN: {label}: port {port} not reachable ({err})", file_handle=fh)
    return False


def check_device(path: str, label: str, fh) -> bool:
    if os.path.exists(path):
        log(f"{label}: present at {path}", file_handle=fh)
        return True
    log(f"WARN: {label}: device {path} not found", file_handle=fh)
    return False


def check_host_health(fh) -> bool:
    ok = True
    log("-- Host health --", file_handle=fh)

    if os.path.exists("/proc/loadavg"):
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            load = f.read().strip().split()[:3]
        log(f"Load avg (1/5/15): {' '.join(load)}", file_handle=fh)

    if os.path.exists("/proc/meminfo"):
        meminfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, val = line.split(":", maxsplit=1)
                meminfo[key] = int(val.strip().split()[0])  # kB
        mem_total = meminfo.get("MemTotal", 0) // 1024
        mem_avail = meminfo.get("MemAvailable", 0) // 1024
        log(f"Memory: total={mem_total}MB available={mem_avail}MB", file_handle=fh)
        if mem_avail < 300:
            ok = False
            log("WARN: Low available memory (<300MB)", file_handle=fh)

    code, out, _ = run(["df", "-h", "/srv"])
    if code == 0:
        log(out, file_handle=fh)
        # crude parse for available percentage
        parts = out.splitlines()
        if len(parts) >= 2:
            avail = parts[1].split()
            if len(avail) >= 5:
                pct_str = avail[4].rstrip("%")
                try:
                    pct = int(pct_str)
                    if pct > 90:
                        ok = False
                        log("WARN: /srv disk usage above 90%", file_handle=fh)
                except ValueError:
                    pass

    temp_path = "/sys/class/thermal/thermal_zone0/temp"
    if os.path.exists(temp_path):
        try:
            with open(temp_path, "r", encoding="utf-8") as f:
                milli_c = int(f.read().strip())
            temp_c = milli_c / 1000.0
            log(f"CPU temp: {temp_c:.1f}C", file_handle=fh)
            if temp_c > 80.0:
                ok = False
                log("WARN: High CPU temperature (>80C)", file_handle=fh)
        except (ValueError, OSError):
            log("WARN: Unable to read CPU temperature", file_handle=fh)

    return ok


def check_lidar(path: str, fh) -> bool:
    if not check_device(path, "Lidar", fh):
        return False
    code, out, err = run(["timeout", "2s", "head", "-c", "16", path])
    if code == 0 and out:
        log(f"Lidar data sample (hex): {out.encode().hex()[:32]}", file_handle=fh)
        return True
    log(f"WARN: Lidar read failed ({err or 'no data'})", file_handle=fh)
    return False


def check_camera(path: str, fh) -> bool:
    # Presence check only; grabbing frames would require v4l tooling/ROS node.
    return check_device(path, "Camera", fh)


def check_arduino(path: str, fh) -> bool:
    return check_device(path, "Arduino/bridge", fh)


def check_ros_topics(fh, expected_topics: List[str]) -> bool:
    if not os.path.exists(f"/opt/ros/{os.environ.get('ROS_DISTRO', 'humble')}/setup.sh"):
        log("ROS2 not installed in healthcheck image; skipping ROS graph checks.", file_handle=fh)
        return True

    code, out, err = run_ros2(["topic", "list"], timeout_s=8)
    if code != 0:
        log(f"WARN: ros2 topic list failed ({err})", file_handle=fh)
        return False

    topics = set(out.splitlines()) if out else set()
    ok = True
    for topic in expected_topics:
        if topic not in topics:
            ok = False
            log(f"WARN: ROS topic missing: {topic}", file_handle=fh)
            continue
        info_code, info_out, info_err = run_ros2(["topic", "info", topic], timeout_s=6)
        if info_code != 0:
            ok = False
            log(f"WARN: ros2 topic info failed for {topic} ({info_err})", file_handle=fh)
            continue
        # Look for publishers count
        pub_lines = [ln for ln in info_out.splitlines() if "Publisher count" in ln]
        if pub_lines:
            try:
                count = int(pub_lines[0].split(":")[-1].strip())
                if count == 0:
                    ok = False
                    log(f"WARN: {topic} has zero publishers", file_handle=fh)
            except ValueError:
                pass
    return ok


def main() -> int:
    log_dir = os.environ.get("LOG_DIR", "/logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    log_path = os.path.join(log_dir, f"healthcheck-{timestamp}.log")
    start_ts = time.time()
    overall_deadline = start_ts + 150  # 2.5 minutes overall budget

    # Default container list can be overridden via REQUIRED_CONTAINERS env (comma separated)
    default_containers = [
        "nav_cont",
        "database_cont",
        "slam_cont",
        "sensor_fusion_cont",
        "robot_bridge_cont",
        "rosbridge_websocket_cont",
        "foxglove_bridge_cont",
        "camera_cont",
        "laser_driver_cont",
    ]
    env_override = os.environ.get("REQUIRED_CONTAINERS")
    containers = [c.strip() for c in env_override.split(",") if c.strip()] if env_override else default_containers

    lidar_dev = os.environ.get("LIDAR_DEVICE", "/dev/ttyUSB0")
    cam_dev = os.environ.get("CAMERA_DEVICE", "/dev/video0")
    bridge_dev = os.environ.get("BRIDGE_SERIAL_DEVICE", "/dev/ttyACM0")
    stabilization_delay = 30  # seconds after containers become ready
    expected_topics = [
        "/scan",
        "/odom",
        "/tf",
        "/tf_static",
        "/camera/image_raw",
    ]

    with open(log_path, "w", encoding="utf-8") as fh:
        log(f"=== Healthcheck {timestamp} UTC ===", file_handle=fh)
        log(f"Log directory: {log_dir}", file_handle=fh)

        if not os.path.exists("/var/run/docker.sock"):
            log("ERROR: /var/run/docker.sock not found; cannot inspect containers.", file_handle=fh)
            return 1

        code, _, err = run(["docker", "info"])
        if code != 0:
            log("ERROR: docker daemon unreachable.", file_handle=fh)
            if err:
                log(err, file_handle=fh)
            return 1

        ready = wait_for_containers(containers, fh, deadline=overall_deadline - stabilization_delay)
        if ready:
            # Give the stack 30s to fully initialize, but stay within overall deadline
            remaining = overall_deadline - time.time()
            sleep_for = min(stabilization_delay, max(0, remaining))
            if sleep_for > 0:
                log(f"Containers running; waiting additional {sleep_for:.0f}s for stabilization.", file_handle=fh)
                time.sleep(sleep_for)

        overall_ok = True
        log("-- Container status --", file_handle=fh)
        for name in containers:
            fmt = "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}|{{.State.StartedAt}}|{{.RestartCount}}|{{.State.Error}}"
            code, out, err = run(["docker", "inspect", "--format", fmt, name])
            if code != 0:
                overall_ok = False
                log(f"{name}: MISSING ({err or 'inspect failed'})", file_handle=fh)
                continue

            parts = out.split("|", maxsplit=4)
            if len(parts) != 5:
                overall_ok = False
                log(f"{name}: unexpected inspect output: {out}", file_handle=fh)
                continue

            status, health, started_at, restarts, state_err = parts
            healthy = status == "running" and health in {"healthy", "none"}
            if not healthy:
                overall_ok = False
            err_suffix = f" error={state_err}" if state_err else ""
            log(f"{name}: status={status}, health={health}, restarts={restarts}, started_at={started_at}{err_suffix}", file_handle=fh)

        log("-- Connectivity checks --", file_handle=fh)
        overall_ok = check_port("127.0.0.1", 5432, "Postgres", fh) and overall_ok
        overall_ok = check_port("127.0.0.1", 9090, "Rosbridge WS", fh) and overall_ok
        overall_ok = check_port("127.0.0.1", 8765, "Foxglove WS", fh) and overall_ok

        log("-- Hardware checks --", file_handle=fh)
        overall_ok = check_lidar(lidar_dev, fh) and overall_ok
        overall_ok = check_camera(cam_dev, fh) and overall_ok
        overall_ok = check_arduino(bridge_dev, fh) and overall_ok

        log("-- ROS graph checks --", file_handle=fh)
        overall_ok = check_ros_topics(fh, expected_topics) and overall_ok

        overall_ok = check_host_health(fh) and overall_ok

        log("-- Summary --", file_handle=fh)
        if overall_ok:
            log("All monitored containers and checks are healthy.", file_handle=fh)
        else:
            log("One or more checks reported issues.", file_handle=fh)

    duration = time.time() - start_ts
    with open(log_path, "a", encoding="utf-8") as fh:
        log(f"Healthcheck duration: {duration:.1f}s", file_handle=fh)
    print(f"Report written to {log_path}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
