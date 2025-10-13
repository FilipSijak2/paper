"""Deprecated path_planner placeholder.

Original DB-backed path planner removed in favor of Nav2 + goal_forwarder.
This file kept to avoid import errors if referenced elsewhere.
"""

def main():
    print("[path_planner] Deprecated. Use goal_forwarder.py and Nav2 NavigateToPose action.")

if __name__ == '__main__':
    main()