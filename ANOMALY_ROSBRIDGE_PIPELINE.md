# YOLO Anomaly Pipeline over rosbridge

The Raspberry Pi publishes robot data through rosbridge, while the Jetson runs YOLO and returns visualization topics. The Jetson does not join the ROS 2 DDS network.

## Active endpoints

- rosbridge: `ws://raspberry.local:9090`
- Foxglove: `ws://raspberry.local:8765`

## Jetson inputs

- `/camera/realsense/color/image_raw/compressed`
- `/camera/realsense/aligned_depth_to_color/image_raw/compressedDepth`
- `/camera/realsense/color/camera_info`
- `/map`
- `/robot_pose_map`
- `/scan`

`nav_cont` publishes `/robot_pose_map` from the `map -> base_link` transform. The deployed `robot-stack/config/containers/nav_cont.env` enables this publisher at 2 Hz.

## Jetson outputs

- `/anomaly/events`
- `/anomaly/events/readable`
- `/anomaly/markers`
- `/anomaly/detections_3d`
- `/anomaly/debug_image/compressed`
- `/anomaly/privacy_image/compressed`
- `/anomaly/map_snapshot/compressed`
- `/anomaly/inspection/request`
- `/anomaly/inspection/status`
- `/anomaly/inspection/result`
- `/anomaly/inspection/privacy_image/compressed`

## Deployed behavior

The Jetson detects the `bottle` class with a YOLO segmentation model, associates detections with ByteTrack, estimates distance from aligned RealSense depth and publishes map markers. It stores images, daily map summaries and JSONL events under `/home/jetson/anomaly_logs`.

Close-up inspection is enabled on both sides. The Jetson requests an inspection when a confirmed object has a metric distance within the configured range. `nav_cont` computes a standoff goal, uses Nav2 to approach it and reports the result. The Jetson then captures privacy-filtered evidence.

All thresholds, timeouts and topic names are maintained in:

- `jetson-stack/config/anomaly_rosbridge.yaml`
- `jetson-stack/config/containers/jetson_anomaly.env`
- `robot-stack/config/containers/nav_cont.env`

## Start

On the Raspberry Pi:

```bash
docker compose up -d rosbridge_websocket foxglove_bridge nav_cont realsense_cont
```

On the Jetson:

```bash
docker compose up -d
docker compose logs -f jetson_anomaly
```

## Verification

1. Confirm the RealSense RGB, aligned depth, camera-info, map, pose and scan topics arrive at the Jetson.
2. Place a bottle in front of the camera.
3. Confirm an event and marker are published.
4. Confirm the original, annotated, privacy-filtered and map images are stored on the Jetson.
5. Confirm the inspection status and result topics complete when autonomous inspection is requested.
6. Confirm Foxglove renders the map marker, 3D detection and debug images.
