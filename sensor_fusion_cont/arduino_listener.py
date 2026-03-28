#!/usr/bin/env python3
"""Compatibility wrapper for the packaged Arduino IMU listener."""

from pathlib import Path
import sys


PKG_ROOT = Path(__file__).resolve().parent / "ws" / "src" / "sensor_fusion_pkg"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))

from sensor_fusion_pkg.arduino_listener_impl import main  # noqa: E402


if __name__ == '__main__':
    main()
