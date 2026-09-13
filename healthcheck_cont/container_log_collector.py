#!/usr/bin/env python3
"""Collect Docker logs into daily per-container files.

The collector tails logs for all containers in the active docker-compose
project and writes them to /logs/<day>/<container>.log. Resume markers are
checkpointed periodically and on graceful shutdown. An abrupt termination
can replay log lines written since the last checkpoint.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Tuple, TypedDict

import yaml


DOCKER_TIMESTAMP_RE = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<tz>Z|[+-]\d{2}:\d{2})$"
)


class CollectorConfig(TypedDict):
    enabled: bool
    log_dir: str
    state_file: str
    date_folder_format: str
    scan_interval_seconds: int
    reconnect_delay_seconds: int
    state_flush_interval_seconds: int
    include_containers: List[str]
    exclude_containers: List[str]


class ResumeState(TypedDict):
    last_timestamp: str
    lines_at_last_timestamp: int


DEFAULT_CONFIG: CollectorConfig = {
    "enabled": True,
    "log_dir": "/logs",
    "state_file": "/logs/.container-log-state.json",
    "date_folder_format": "%-d-%-m-%Y",
    "scan_interval_seconds": 30,
    "reconnect_delay_seconds": 3,
    "state_flush_interval_seconds": 30,
    "include_containers": [],
    "exclude_containers": [],
}


def collector_log(message: str) -> None:
    print(f"[collector] {message}", flush=True)


def run(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=5)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, "", str(exc)


def normalize_config(raw: Mapping[str, object]) -> CollectorConfig:
    def positive_seconds(name: str, default: int) -> int:
        value = raw.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"{name} must be a positive integer")
        result = int(value)
        if result < 1:
            raise ValueError(f"{name} must be a positive integer")
        return result

    def container_names(name: str) -> List[str]:
        value = raw.get(name, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"{name} must be a list of container names")
        return list(value)

    enabled = raw.get("enabled", DEFAULT_CONFIG["enabled"])
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")

    return {
        "enabled": enabled,
        "log_dir": str(raw.get("log_dir", DEFAULT_CONFIG["log_dir"])),
        "state_file": str(raw.get("state_file", DEFAULT_CONFIG["state_file"])),
        "date_folder_format": str(
            raw.get("date_folder_format", DEFAULT_CONFIG["date_folder_format"])
        ),
        "scan_interval_seconds": positive_seconds(
            "scan_interval_seconds", DEFAULT_CONFIG["scan_interval_seconds"]
        ),
        "reconnect_delay_seconds": positive_seconds(
            "reconnect_delay_seconds", DEFAULT_CONFIG["reconnect_delay_seconds"]
        ),
        "state_flush_interval_seconds": positive_seconds(
            "state_flush_interval_seconds", DEFAULT_CONFIG["state_flush_interval_seconds"]
        ),
        "include_containers": container_names("include_containers"),
        "exclude_containers": container_names("exclude_containers"),
    }


def load_config(config_path: str) -> CollectorConfig:
    config: Dict[str, object] = {}
    source = Path(config_path)

    if source.exists():
        with source.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if raw is None:
            raw = {}
        if not isinstance(raw, dict) or not isinstance(raw.get("container_logging", {}), dict):
            raise ValueError("Logging config and container_logging must be mappings")
        config.update(raw.get("container_logging", {}))

    config["log_dir"] = os.environ.get(
        "LOG_DIR", str(config.get("log_dir", DEFAULT_CONFIG["log_dir"]))
    )
    config["state_file"] = os.environ.get(
        "LOG_STATE_FILE", str(config.get("state_file", DEFAULT_CONFIG["state_file"]))
    )
    return normalize_config(config)


def parse_docker_timestamp(value: str) -> datetime:
    match = DOCKER_TIMESTAMP_RE.match(value.strip())
    if not match:
        raise ValueError(f"Unsupported Docker timestamp: {value}")

    fraction = (match.group("fraction") or "0")[:6].ljust(6, "0")
    tz_part = "+00:00" if match.group("tz") == "Z" else match.group("tz")
    normalized = f"{match.group('base')}.{fraction}{tz_part}"
    return datetime.fromisoformat(normalized)


def format_local_timestamp(value: datetime) -> str:
    return value.astimezone().isoformat(sep=" ", timespec="milliseconds")


class ContainerLogCollector:
    def __init__(self, config: Mapping[str, object]) -> None:
        tzset = getattr(time, "tzset", None)
        if tzset is not None:
            tzset()

        settings = normalize_config(config)
        self.enabled = settings["enabled"]
        self.log_dir = Path(settings["log_dir"])
        self.state_file = Path(settings["state_file"])
        self.date_folder_format = settings["date_folder_format"]
        self.scan_interval_seconds = settings["scan_interval_seconds"]
        self.reconnect_delay_seconds = settings["reconnect_delay_seconds"]
        self.state_flush_interval_seconds = settings["state_flush_interval_seconds"]
        self.state_dirty = False
        self.last_state_flush = time.monotonic()
        self.include_containers = settings["include_containers"]
        self.exclude_containers = set(settings["exclude_containers"])
        self.compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "stack")
        self.state_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.process_lock = threading.Lock()
        self.stream_processes: Dict[str, subprocess.Popen[str]] = {}
        self.stream_threads: Dict[str, threading.Thread] = {}
        self.state = self._load_state()
        self.warned_no_targets = False

    def _load_state(self) -> Dict[str, ResumeState]:
        if not self.state_file.exists():
            return {}

        try:
            with self.state_file.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            collector_log(f"State file unreadable, starting fresh ({exc}).")
            return {}

        containers = raw.get("containers", {}) if isinstance(raw, dict) else {}
        state: Dict[str, ResumeState] = {}
        if not isinstance(containers, dict):
            return state
        for name, entry in containers.items():
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("last_timestamp", "")
            count = entry.get("lines_at_last_timestamp", 0)
            if not isinstance(timestamp, str) or not isinstance(count, int) or count < 0:
                continue
            if timestamp:
                try:
                    parse_docker_timestamp(timestamp)
                except ValueError:
                    continue
            state[name] = {"last_timestamp": timestamp, "lines_at_last_timestamp": count}
        return state

    def _save_state_locked(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        payload = {"containers": self.state}
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
        temp_path.replace(self.state_file)

    def _update_state(self, container_name: str, docker_timestamp: str) -> None:
        with self.state_lock:
            entry = self.state.setdefault(
                container_name,
                {"last_timestamp": "", "lines_at_last_timestamp": 0},
            )
            if entry.get("last_timestamp") == docker_timestamp:
                entry["lines_at_last_timestamp"] += 1
            else:
                entry["last_timestamp"] = docker_timestamp
                entry["lines_at_last_timestamp"] = 1
            self.state_dirty = True

    def _flush_state_if_due(self, force: bool = False) -> None:
        now = time.monotonic()
        with self.state_lock:
            if not self.state_dirty:
                return

            if not force and now - self.last_state_flush < self.state_flush_interval_seconds:
                return

            self._save_state_locked()
            self.state_dirty = False
            self.last_state_flush = now

    def _get_resume_marker(self, container_name: str) -> Tuple[str, int]:
        with self.state_lock:
            entry = self.state.get(container_name)
            last_timestamp = entry["last_timestamp"] if entry else ""
            lines_at_timestamp = entry["lines_at_last_timestamp"] if entry else 0

        if last_timestamp:
            return last_timestamp, lines_at_timestamp

        local_now = datetime.now().astimezone()
        local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start_utc = local_day_start.astimezone(timezone.utc)
        return day_start_utc.isoformat().replace("+00:00", "Z"), 0

    def _list_target_containers(self) -> List[str]:
        if self.include_containers:
            names = self.include_containers
        else:
            code, out, err = run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--format",
                    "{{.Names}}",
                    "--filter",
                    f"label=com.docker.compose.project={self.compose_project}",
                ]
            )
            if code != 0:
                collector_log(
                    f"Unable to list containers for compose project '{self.compose_project}': {err or out}"
                )
                return []
            names = [line.strip() for line in out.splitlines() if line.strip()]

        filtered = [name for name in sorted(set(names)) if name not in self.exclude_containers]
        return filtered

    def _write_log_line(self, container_name: str, docker_timestamp: str, message: str) -> None:
        try:
            event_time = parse_docker_timestamp(docker_timestamp)
        except ValueError:
            event_time = datetime.now(timezone.utc)

        local_time = event_time.astimezone()
        date_dir = local_time.strftime(self.date_folder_format)
        log_dir = self.log_dir / date_dir
        log_path = log_dir / f"{container_name}.log"

        log_dir.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"[{format_local_timestamp(local_time)}] {message}\n")

    def _stream_logs(self, container_name: str) -> None:
        while not self.stop_event.is_set():
            resume_timestamp, skip_count = self._get_resume_marker(container_name)
            cmd = [
                "docker",
                "logs",
                "--timestamps",
                "--follow",
                "--since",
                resume_timestamp,
                container_name,
            ]

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                collector_log(f"Docker CLI not available for {container_name}: {exc}")
                self.stop_event.wait(self.reconnect_delay_seconds)
                continue

            # Register and check the stop flag together so shutdown cannot miss
            # a process that was being started when the stop was requested.
            with self.process_lock:
                self.stream_processes[container_name] = proc
                if self.stop_event.is_set():
                    self._terminate_process(proc)

            try:
                if proc.stdout is None:
                    collector_log(f"Failed to open stdout stream for {container_name}.")
                    return

                for raw_line in proc.stdout:
                    if self.stop_event.is_set():
                        break
                    line = raw_line.rstrip("\r\n")
                    docker_timestamp, separator, message = line.partition(" ")
                    if not separator or not DOCKER_TIMESTAMP_RE.fullmatch(docker_timestamp):
                        # CLI diagnostics have no Docker timestamp. They must
                        # never advance the marker used by --since.
                        collector_log(f"{container_name}: {line}")
                        continue

                    if docker_timestamp == resume_timestamp and skip_count > 0:
                        skip_count -= 1
                        continue

                    self._write_log_line(container_name, docker_timestamp, message)
                    self._update_state(container_name, docker_timestamp)

                return_code = proc.wait(timeout=5)
            finally:
                self._terminate_process(proc)
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._terminate_process(proc, kill=True)
                    proc.wait()
                if proc.stdout is not None:
                    proc.stdout.close()
                with self.process_lock:
                    self.stream_processes.pop(container_name, None)

            if self.stop_event.is_set():
                return
            if return_code == 0:
                # An exited container has no live stream to follow. Let the
                # next discovery scan reconnect instead of polling every 3 s.
                return
            collector_log(f"Log stream for {container_name} exited with code {return_code}.")

            self.stop_event.wait(self.reconnect_delay_seconds)

    @staticmethod
    def _terminate_process(proc: subprocess.Popen[str], kill: bool = False) -> None:
        try:
            if proc.poll() is None:
                if kill:
                    proc.kill()
                else:
                    proc.terminate()
        except ProcessLookupError:
            pass  # The CLI exited between poll() and the signal.

    def request_stop(self) -> None:
        self.stop_event.set()

    def shutdown(self) -> None:
        self.request_stop()
        with self.process_lock:
            for proc in self.stream_processes.values():
                self._terminate_process(proc)

        deadline = time.monotonic() + 3
        for thread in self.stream_threads.values():
            thread.join(timeout=max(0, deadline - time.monotonic()))

        with self.process_lock:
            for proc in self.stream_processes.values():
                self._terminate_process(proc, kill=True)
        for thread in self.stream_threads.values():
            thread.join()

        # All writes and marker updates have finished before the final flush.
        self._flush_state_if_due(force=True)

    def _ensure_streams(self) -> None:
        target_containers = self._list_target_containers()
        if not target_containers:
            if not self.warned_no_targets:
                collector_log("No target containers discovered yet; retrying.")
                self.warned_no_targets = True
            return

        self.warned_no_targets = False
        for container_name in target_containers:
            if self.stop_event.is_set():
                break
            thread = self.stream_threads.get(container_name)
            if thread is not None and thread.is_alive():
                continue

            thread = threading.Thread(
                target=self._stream_logs,
                args=(container_name,),
                daemon=True,
                name=f"log-stream-{container_name}",
            )
            self.stream_threads[container_name] = thread
            thread.start()
            collector_log(f"Started log capture for {container_name}.")

    def run_forever(self) -> int:
        if not self.enabled:
            collector_log("Container log collector is disabled in config.")
            return 0

        self.log_dir.mkdir(parents=True, exist_ok=True)
        collector_log(
            f"Container log collector active for compose project '{self.compose_project}'. "
            f"Logs root: {self.log_dir}"
        )

        try:
            while not self.stop_event.is_set():
                code, _, err = run(["docker", "info"])
                if code == 0:
                    break
                collector_log(f"Docker daemon not ready yet: {err or 'unknown error'}")
                self.stop_event.wait(self.reconnect_delay_seconds)

            next_scan = time.monotonic()
            next_flush = next_scan + self.state_flush_interval_seconds
            while not self.stop_event.is_set():
                if time.monotonic() >= next_scan:
                    self._ensure_streams()
                    next_scan = time.monotonic() + self.scan_interval_seconds
                if time.monotonic() >= next_flush:
                    self._flush_state_if_due()
                    next_flush = time.monotonic() + self.state_flush_interval_seconds
                self.stop_event.wait(max(0, min(next_scan, next_flush) - time.monotonic()))
        finally:
            self.shutdown()
        return 0


def main() -> int:
    config_path = os.environ.get("LOGGING_CONFIG", "/config/logging.yaml")
    config = load_config(config_path)
    collector = ContainerLogCollector(config)

    def handle_stop(_signum: int, _frame: object) -> None:
        collector.request_stop()

    previous_handlers = {
        signum: signal.signal(signum, handle_stop) for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        return collector.run_forever()
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    sys.exit(main())
