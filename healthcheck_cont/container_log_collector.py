#!/usr/bin/env python3
"""Collect Docker logs into daily per-container files.

The collector tails logs for all containers in the active docker-compose
project, writes them to /logs/<day>/<container>.log, and persists resume state
to avoid duplicating log lines across stack restarts on the same day.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


DOCKER_TIMESTAMP_RE = re.compile(
    r"^(?P<base>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<tz>Z|[+-]\d{2}:\d{2})$"
)

DEFAULT_CONFIG = {
    "enabled": True,
    "log_dir": "/logs",
    "state_file": "/logs/.container-log-state.json",
    "date_folder_format": "%-d-%-m-%Y",
    "scan_interval_seconds": 5,
    "reconnect_delay_seconds": 3,
    "include_containers": [],
    "exclude_containers": [],
}


def collector_log(message: str) -> None:
    print(f"[collector] {message}", flush=True)


def run(cmd: List[str]) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", str(exc)


def load_config(config_path: str) -> Dict[str, object]:
    config = dict(DEFAULT_CONFIG)
    source = Path(config_path)

    if source.exists():
        with source.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        config.update(raw.get("container_logging", {}))

    config["log_dir"] = os.environ.get("LOG_DIR", str(config["log_dir"]))
    config["state_file"] = os.environ.get("LOG_STATE_FILE", str(config["state_file"]))
    return config


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
    def __init__(self, config: Dict[str, object]) -> None:
        if hasattr(time, "tzset"):
            time.tzset()

        self.enabled = bool(config.get("enabled", True))
        self.log_dir = Path(str(config["log_dir"]))
        self.state_file = Path(str(config["state_file"]))
        self.date_folder_format = str(config["date_folder_format"])
        self.scan_interval_seconds = int(config["scan_interval_seconds"])
        self.reconnect_delay_seconds = int(config["reconnect_delay_seconds"])
        self.include_containers = [str(name) for name in config.get("include_containers", [])]
        self.exclude_containers = {str(name) for name in config.get("exclude_containers", [])}
        self.compose_project = os.environ.get("COMPOSE_PROJECT_NAME", "stack")
        self.state_lock = threading.Lock()
        self.stream_threads: Dict[str, threading.Thread] = {}
        self.state = self._load_state()
        self.warned_no_targets = False

    def _load_state(self) -> Dict[str, Dict[str, object]]:
        if not self.state_file.exists():
            return {}

        try:
            with self.state_file.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            collector_log(f"State file unreadable, starting fresh ({exc}).")
            return {}

        containers = raw.get("containers", {})
        if isinstance(containers, dict):
            return containers
        return {}

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
                entry["lines_at_last_timestamp"] = int(entry.get("lines_at_last_timestamp", 0)) + 1
            else:
                entry["last_timestamp"] = docker_timestamp
                entry["lines_at_last_timestamp"] = 1
            self._save_state_locked()

    def _get_resume_marker(self, container_name: str) -> Tuple[str, int]:
        with self.state_lock:
            entry = self.state.get(container_name, {})
            last_timestamp = str(entry.get("last_timestamp", "") or "")
            lines_at_timestamp = int(entry.get("lines_at_last_timestamp", 0) or 0)

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
                collector_log(f"Unable to list containers for compose project '{self.compose_project}': {err or out}")
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
        while True:
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
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except FileNotFoundError as exc:
                collector_log(f"Docker CLI not available for {container_name}: {exc}")
                time.sleep(self.reconnect_delay_seconds)
                continue

            if proc.stdout is None:
                collector_log(f"Failed to open stdout stream for {container_name}.")
                proc.kill()
                time.sleep(self.reconnect_delay_seconds)
                continue

            for raw_line in proc.stdout:
                line = raw_line.rstrip("\r\n")
                docker_timestamp, separator, message = line.partition(" ")
                if not separator:
                    docker_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    message = line

                if docker_timestamp == resume_timestamp and skip_count > 0:
                    skip_count -= 1
                    continue

                self._write_log_line(container_name, docker_timestamp, message)
                self._update_state(container_name, docker_timestamp)

            stderr_output = ""
            if proc.stderr is not None:
                stderr_output = proc.stderr.read().strip()

            return_code = proc.wait()
            if return_code != 0:
                collector_log(
                    f"Log stream for {container_name} exited with code {return_code}: {stderr_output or 'no details'}"
                )

            time.sleep(self.reconnect_delay_seconds)

    def _ensure_streams(self) -> None:
        target_containers = self._list_target_containers()
        if not target_containers:
            if not self.warned_no_targets:
                collector_log("No target containers discovered yet; retrying.")
                self.warned_no_targets = True
            return

        self.warned_no_targets = False
        for container_name in target_containers:
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

        while True:
            code, _, err = run(["docker", "info"])
            if code == 0:
                break
            collector_log(f"Docker daemon not ready yet: {err or 'unknown error'}")
            time.sleep(self.reconnect_delay_seconds)

        while True:
            self._ensure_streams()
            time.sleep(self.scan_interval_seconds)


def main() -> int:
    config_path = os.environ.get("LOGGING_CONFIG", "/config/logging.yaml")
    config = load_config(config_path)
    collector = ContainerLogCollector(config)
    return collector.run_forever()


if __name__ == "__main__":
    sys.exit(main())
