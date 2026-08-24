# Navigation Container

`nav_cont` runs the deployed Nav2 and AMCL navigation path. Runtime values are supplied by `robot-stack/config/containers/nav_cont.env` and the configuration files mounted by `robot-stack/docker-compose.yaml`.

## Active data flow

```text
Nav2 / joystick
    -> /cmd_vel_auto or /cmd_vel_joy
    -> cmd_vel_mux
    -> collision monitor
    -> cmd_vel_safety_filter
    -> /cmd_vel
    -> robot_bridge
```

Obstacle input comes from the filtered laser scan and the RealSense point cloud configured in `nav2_params.yaml`. AMCL publishes localization against the selected occupancy map. `robot_pose_map_publisher.py` publishes `/robot_pose_map` for the Jetson anomaly client.

## Mounted configuration

- `/app/nav2_params.yaml`
- `/app/navigate_to_pose_stable.xml`
- `/app/collision_monitor_params.yaml`
- `/app/map.yaml`
- `/srv` for map and persisted AMCL state

## Enabled runtime functions

The deployed `nav_cont.env` enables:

- command multiplexing
- collision monitoring
- velocity safety filtering
- scan- and map-based emergency stopping
- anomaly close-up inspection
- robot pose publication in the `map` frame
- AMCL pose persistence
- joystick input when `/dev/input/js0` is available

The exact speeds, stop distances, timeouts and topic names are defined only in `robot-stack/config/containers/nav_cont.env` and `robot-stack/config/containers/nav2_params.yaml`.

## Startup

The container entry point is `start_nav.sh`. It starts the launch description in `robot_nav_launch.py` and the enabled helper nodes. Recreate the container after changing mounted runtime configuration:

```bash
docker compose up -d --force-recreate nav_cont
```

Select a saved map from the `robot-stack` checkout before localization:

```bash
scripts/select_map.sh <session-or-map-path>
```

## Verification

```bash
ros2 action list | grep navigate_to_pose
ros2 topic echo /amcl_pose --once
ros2 topic echo /cmd_vel_safety_status --once
ros2 topic echo /robot_pose_map --once
```
