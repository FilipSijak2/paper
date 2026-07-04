# YOLO Anomaly Pipeline Over Rosbridge

This document describes the split Raspberry Pi + Jetson Orin anomaly pipeline.
The Raspberry Pi remains the main ROS 2 robot computer. Jetson runs YOLO and
connects through rosbridge WebSocket, not DDS.

## Architecture

Raspberry Pi:

- runs navigation, SLAM, odometry, LiDAR, TF, camera publishing, rosbridge, and
  foxglove_bridge
- publishes `/map`, `/tf`, `/tf_static`, `/odom`, `/scan`, and compressed camera
  images
- optionally publishes `/robot_pose_map`
- does not run YOLO
- does not save anomaly images or map snapshots

Jetson:

- runs `jetson_yolo_rosbridge_client` from the sibling `jetson-stack` repo
- subscribes to Raspberry Pi topics through `ws://raspberry.local:9090`
- runs real YOLO inference and treats `bottle` as the default anomaly class
- saves original images, annotated images, map snapshots, and JSONL events
  locally under `/home/jetson/anomaly_logs`
- publishes only visualization topics back to the Raspberry Pi through
  rosbridge

Foxglove:

- connects to the Raspberry Pi foxglove_bridge endpoint, usually
  `ws://raspberry.local:8765`
- visualizes normal robot topics and Jetson anomaly topics

## Raspberry Pi Topics

Required inputs for Jetson:

- `/camera/color/image/compressed` (`sensor_msgs/CompressedImage`)
- `/camera/realsense/color/camera_info` (`sensor_msgs/CameraInfo`)
- `/camera/realsense/aligned_depth_to_color/image_raw` (`sensor_msgs/Image`)
- `/map` (`nav_msgs/OccupancyGrid`)
- `/robot_pose_map` (`geometry_msgs/PoseStamped`) or `/amcl_pose`
  (`geometry_msgs/PoseWithCovarianceStamped`)

If the active camera uses the RealSense namespace, configure Jetson with the
actual compressed topic, for example:

```bash
CAMERA_TOPIC=/camera/realsense/color/image_raw/compressed
```

or:

```bash
CAMERA_TOPIC=/camera/realsense/color/image_compressed
```

Jetson publishes back:

- `/anomaly/events` (`std_msgs/String`, JSON)
- `/anomaly/markers` (`visualization_msgs/MarkerArray`)
- `/anomaly/detections_3d` (`visualization_msgs/MarkerArray`)
- `/anomaly/debug_image/compressed` (`sensor_msgs/CompressedImage`)
- `/anomaly/privacy_image/compressed` (`sensor_msgs/CompressedImage`)
- `/anomaly/map_snapshot/compressed` (`sensor_msgs/CompressedImage`)

## Start Rosbridge

The runtime stack already has `rosbridge_websocket` in `../stack/docker-compose.yaml`.
Manual command:

```bash
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Default port is `9090`.

## Start Foxglove Bridge

The runtime stack already has `foxglove_bridge` in `../stack/docker-compose.yaml`.
Manual command:

```bash
ros2 run foxglove_bridge foxglove_bridge --ros-args \
  -p port:=8765 \
  -p address:=0.0.0.0
```

Foxglove should connect to:

```text
ws://raspberry.local:8765
```

## Optional `/robot_pose_map` Publisher

If `/amcl_pose` is reliable, configure Jetson:

```bash
ROBOT_POSE_TOPIC=/amcl_pose
```

If a simple `PoseStamped` topic is preferred, run the optional publisher from
`nav_cont`. It reads TF `map -> base_link` and publishes `/robot_pose_map` at
1 Hz.

Manual start inside a running `nav_cont`:

```bash
docker exec -d nav_cont bash -lc \
  'source /opt/ros/humble/setup.bash && python3 /app/robot_pose_map_publisher.py'
```

Launch-file style:

```bash
docker exec -it nav_cont bash -lc \
  'source /opt/ros/humble/setup.bash && ros2 launch /app/robot_pose_map_publisher.launch.py'
```

Optional env flag in `nav_cont/start_nav.sh`:

```bash
ENABLE_ROBOT_POSE_MAP_PUBLISHER=1
ROBOT_POSE_MAP_TOPIC=/robot_pose_map
ROBOT_POSE_MAP_FRAME=map
ROBOT_POSE_BASE_FRAME=base_link
ROBOT_POSE_PUBLISH_RATE_HZ=1.0
```

The flag defaults to `0`, so the normal navigation startup remains unchanged.

## Jetson Run

In the sibling `jetson-stack` repo:

```bash
cp .env.example .env
docker compose up -d --build
```

Important Jetson settings:

```bash
ROSBRIDGE_URL=ws://raspberry.local:9090
CAMERA_TOPIC=/camera/color/image/compressed
MAP_TOPIC=/map
ROBOT_POSE_TOPIC=/robot_pose_map
ANOMALY_CLASSES=bottle
CONFIDENCE_THRESHOLD=0.5
USE_CAMERA_INTRINSICS=1
USE_DEPTH_DISTANCE=1
DEPTH_SYNC_TOLERANCE_S=0.25
YOLO_IMAGE_SIZE=640
YOLO_IOU_THRESHOLD=0.70
YOLO_HALF=1
YOLO_FILTER_CLASSES=1
PRIVACY_IMAGE_ENABLED=1
PRIVACY_IMAGE_TOPIC=/anomaly/privacy_image/compressed
PRIVACY_BLUR_KERNEL_SIZE=51
PRIVACY_USE_SEGMENTATION_MASKS=1
PRIVACY_DRAW_TRACK_ID=1
TRACKING_ENABLED=1
TRACKING_BACKEND=bytetrack.yaml
SEGMENTATION_ENABLED=1
MARKER_RAY_ENABLED=1
MARKER_RAY_TTL_S=2.0
MARKER_UNCERTAINTY_ENABLED=1
DETECTION_3D_ENABLED=1
DETECTION_3D_TOPIC=/anomaly/detections_3d
DETECTION_3D_REQUIRE_MASK=1
MARKER_TTL_S=180
YOLO_MODEL_PATH=yolov8n-seg.pt
```

## Event Example

`/anomaly/events` publishes `std_msgs/String` where `data` is JSON:

```json
{
  "id": "anom_00042",
  "timestamp": "2026-06-16T14:22:31Z",
  "label": "bottle",
  "type": "semantic_object_anomaly",
  "confidence": 0.87,
  "track_id": 7,
  "segmentation_mask_used": true,
  "status": "active",
  "ttl_sec": 180,
  "bbox_xyxy": [312, 210, 390, 420],
  "robot_pose_map": {"x": 1.52, "y": -0.48, "yaw": 1.31},
  "object_pose_map": {"x": 2.10, "y": -0.92, "z": 0.0},
  "localization": {
    "distance_m": 0.82,
    "distance_source": "depth",
    "distance_uncertainty_m": 0.03,
    "distance_valid_samples": 642,
    "depth_axial_m": 0.80,
    "rgb_depth_delta_s": 0.018,
    "bearing_source": "camera_intrinsics"
  },
  "jetson_files": {
    "original_image": "/home/jetson/anomaly_logs/images/original/anom_00042_bottle.jpg",
    "annotated_image": "/home/jetson/anomaly_logs/images/annotated/anom_00042_bottle.jpg",
    "map_snapshot": "/home/jetson/anomaly_logs/map_images/anom_00042_bottle_map.png",
    "event_log": "/home/jetson/anomaly_logs/events.jsonl"
  }
}
```

## Foxglove View

Open panels for:

- `/map`
- `/tf`, `/tf_static`
- `/scan` or `/scan_filtered`
- `/odom`
- `/robot_pose_map`
- `/anomaly/markers`
- `/anomaly/detections_3d`
- `/anomaly/events`
- `/anomaly/debug_image/compressed`
- `/anomaly/privacy_image/compressed`
- `/anomaly/map_snapshot/compressed`

`/anomaly/markers` contains an object marker, a `TEXT_VIEW_FACING` marker with
the tracker ID, a line from the robot to the object, and an approximate
localization-uncertainty circle. The observation line has a short independent
TTL and disappears when the bottle is no longer observed. Jetson republishes
active object markers at 1 Hz and deletes them after the configured TTL,
default 180 seconds.

`/anomaly/privacy_image/compressed` blurs the complete frame and restores only
the bottle segmentation mask. If masks are unavailable it falls back to the
detection bounding box.

Event deduplication and daily map summaries use only anomalies from the current
local day. Historical rows remain in `events.jsonl`, but do not suppress a new
day's events and are not drawn on the next day's map.

`/anomaly/detections_3d` contains a short-lived wireframe around the visible
3D points of the segmented bottle in the RealSense color optical frame.
Foxglove transforms it into the selected fixed frame through `/tf_static`.

## Test Procedure

1. Start the ROS 2 robot stack on the Raspberry Pi.
2. Start compressed camera publishing on the Raspberry Pi.
3. Start rosbridge on the Raspberry Pi.
4. Start foxglove_bridge on the Raspberry Pi.
5. Start `/robot_pose_map` publisher if needed.
6. Open Foxglove and connect to `ws://raspberry.local:8765`.
7. Start the Jetson YOLO rosbridge client.
8. Place a bottle in front of the robot camera.
9. Confirm Jetson detects the bottle.
10. Confirm Jetson saves original and annotated images locally.
11. Confirm Jetson appends `events.jsonl` locally.
12. Confirm Jetson saves a map snapshot PNG locally.
13. Confirm `/anomaly/events` publishes JSON.
14. Confirm `/anomaly/markers` publishes in `map` frame.
15. Confirm `/anomaly/debug_image/compressed` publishes.
16. Confirm `/anomaly/map_snapshot/compressed` publishes.
17. Confirm Foxglove shows `ANOMALY: bottle` on the map.
18. Confirm the marker remains visible for 180 seconds and then disappears.
19. Confirm Foxglove can show the event JSON, annotated image, and map snapshot.
20. Confirm the existing robot navigation stack still works.

