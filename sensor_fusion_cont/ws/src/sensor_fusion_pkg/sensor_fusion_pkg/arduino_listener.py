# Reuse existing implementation by importing from original path if needed
from pathlib import Path
import sys

# If running inside built package, original script may have been copied already.
# For now duplicate minimal wrapper (can refactor to move logic here directly).

from sensor_fusion_pkg.arduino_listener_impl import main  # type: ignore

if __name__ == '__main__':
    main()
