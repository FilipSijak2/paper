"""Deprecated path_planner placeholder.

Original DB-backed path planner removed in favor of Nav2 + goal_forwarder.
This file kept to avoid import errors if referenced elsewhere.
"""

import warnings


DEPRECATION_MESSAGE = (
    "[path_planner] Deprecated compatibility shim. "
    "Use goal_forwarder.py and Nav2 NavigateToPose action."
)


def main():
    warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
    print(DEPRECATION_MESSAGE)

if __name__ == '__main__':
    main()
