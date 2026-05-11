# Diplomski Rad

Ovaj repozitorij sadrzi glavne softverske komponente robotskog sustava temeljenog
na ROS 2, Dockeru i vise specijaliziranih servisa.

Repo pokriva:

- prikupljanje podataka sa senzora
- komunikaciju s mikrokontrolerom robota
- SLAM i izradu mapa
- autonomnu navigaciju
- AI obradu slike
- snimanje ROS 2 bagova
- pohranu podataka u PostgreSQL bazu
- vizualizaciju preko rosbridge i Foxglove bridge

Operativni `docker-compose` stack tipicno zivi u sibling direktoriju
`../stack/`, dok ovaj repo sadrzi imageove, skripte, firmware i dokumentaciju.

## Trenutna hardverska arhitektura

Trenutna aktivna runtime arhitektura u `../stack/.env` je
`BRIDGE_MODE=rpi_direct`:

```text
Raspberry Pi -> GPIO -> DRV8833 -> motori
          |
          \-> I2C -> TCA9548A -> AS5600 LEFT / RIGHT (oziceno, trenutno ENCODERS_ENABLED=0)
```

Napomena:

- `Nano ESP32` ostaje podrzan kroz `BRIDGE_MODE=serial_legacy`, ali nije
  aktivni motor/encoder put u trenutnom stacku
- `DRV8833` je trenutni motor driver
- `robot_bridge` u aktivnom stacku koristi `/dev/i2c-1` i `/dev/gpiochip4`
- `ENCODERS_ENABLED=0`, pa bridge trenutno ne cita AS5600 enkodere nego
  koristi open-loop `/wheel_odom`, dok `slam_cont` pokrece rf2o odometriju
- `UNO R4` vise nije dio glavne implementacije

## Glavne komponente

| Komponenta | Uloga | Najvazniji ulazi / izlazi |
| --- | --- | --- |
| `bridge_cont` | Robot bridge za motor/enkoder kontrolu; aktivno `rpi_direct`, podrzan `serial_legacy` | Publisha `/wheel_odom`, `/robot_status`; u serial modu i `/imu/arduino`; subscriba `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver za RPLidar | Publisha `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Objavljuje RGB, depth, camera info i IMU topice |
| `slam_cont` | `slam_toolbox`, mapiranje, save/export mape, upis u bazu | Koristi `/scan`, `/tf`, odometriju i IMU; publisha `/map` |
| `nav_cont` | Nav2, prosljedivanje goalova i `cmd_vel` mux | Prima `/move_base_simple/goal`; publisha `/cmd_vel_auto` i finalni `/cmd_vel` |
| `bag_recorder_cont` | Kontinuirano snimanje ROS 2 bagova | Snima topice iz `TOPICS_FILE` u `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS baza | Sprema mape, slike, waypointove i sesije |
| `rosbridge_cont` | ROS 2 -> WebSocket za web klijente | Tipicno port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge za Foxglove Studio | Tipicno port `8765` |
| `ai_kit_cont` | Hailo AI obrada slike ili passthrough overlay | Prima RealSense sliku; publisha AI overlay topice |
| `sensor_fusion_cont` | Filtriranje IMU podataka | Po defaultu pretvara RealSense IMU u `/imu/data`; Arduino IMU je debug/fallback stream samo u serial legacy modu |
| `healthcheck_cont` | Provjera stanja kontejnera, portova, uredaja i ROS grafa | Pise health report u logove |
| `container_log_collector_cont` | Skupljanje Docker logova | Pise dnevne logove u `../stack/logs/<dan>/<container>.log` |
| `bag_browser_cont` | Web pregled bagova i logova | `filebrowser/filebrowser`, port `8080`, read-only `bags/` i `logs/` |
| `camera_cont` | Opcionalni CSI/UDP kamera publisher | Trenutno je komentiran u composeu; RealSense je glavni aktivni camera path |

## Funkcionalnosti po kontejneru

Ovaj dio opisuje runtime stack iz `../stack/docker-compose.yaml` i imageove iz
ovog repozitorija. Vecina kontejnera koristi `network_mode: host`,
`rmw_cyclonedds_cpp` i zajednicki `CycloneDDS` config iz
`../stack/config/cyclonedds.xml`, koji je trenutno vezan na `wlan0`.

### `robot_bridge_cont` / `bridge_cont`

Image se gradi iz `bridge_cont/Dockerfile` na bazi `ros:humble`.
Instalirani su `python3-serial`, `python3-smbus2`, `python3-lgpio`,
`rpi-lgpio` i `ros-humble-rmw-cyclonedds-cpp`.

Funkcionalnosti:

- Docker image default je `serial_legacy`, ali aktivni runtime stack u
  `../stack/.env` koristi `BRIDGE_MODE=rpi_direct`.
- U `rpi_direct` modu `robot_rpi_direct_bridge.py` direktno vozi `DRV8833`
  preko Raspberry Pi GPIO PWM-a i cita `AS5600` enkodere preko `TCA9548A`
  I2C muxa.
- `serial_legacy` mod ostaje podrzan: `robot_serial_bridge.py` komunicira s
  Nano ESP32 preko custom serijskog protokola.
- Subscriba `/cmd_vel`.
- Publisha `/wheel_odom`, `/robot_status` i, u serial modu, `/imu/arduino`.
- Aktivni compose mapira `/dev/i2c-1` i `/dev/gpiochip4`; serial legacy
  koristi `/dev/ttyACM0`.
- `bridge_rpi_direct.env` drzi bitne geometrijske i pin postavke:
  `WHEEL_RADIUS_M=0.033`, `WHEEL_BASE_M=0.20`, `LEFT_MUX_CHANNEL=0`,
  `RIGHT_MUX_CHANNEL=4`, `MAX_LINEAR_VEL=0.5`, `MAX_ANGULAR_VEL=1.0`.

Napomena: aktualni bridge izlaz odometrije je `/wheel_odom`. Ako neki stariji
dio stacka ocekuje `/odom`, treba dodati remap ili adapter.

### `laser_driver_cont`

Image se gradi iz `laser_driver_cont/Dockerfile` na bazi `ros:humble`.
Driver paket je `rplidar_ros`, buildan iz GitHub repozitorija
`Slamtec/rplidar_ros` na branchu `ros2`.

Funkcionalnosti:

- Pokrece `ros2 launch rplidar_ros rplidar_a1_launch.py`.
- Publisha LIDAR scan na `/scan`.
- Koristi serijski uredaj iz compose varijable `LIDAR_DEVICE`, default
  `/dev/ttyUSB0`.
- Dodan je u `dialout` grupu da moze citati serijski port.

### `slam_cont`

Image se gradi iz `slam_cont/Dockerfile` na bazi `ros:humble`.
Glavni paket za SLAM je `ros-humble-slam-toolbox`; pokrece se
`async_slam_toolbox_node` s parametrima iz `/app/slam_params.yaml`.

Dodatni bitni paketi i alati:

- `ros-humble-nav2-map-server` za export occupancy mapa.
- `ros-humble-nav2-msgs` za `nav2_msgs/srv/SaveMap`.
- `ros-humble-rosbag2-storage-mcap` za MCAP podrsku.
- `rf2o_laser_odometry` builda se iz sourcea
  `MAPIRlab/rf2o_laser_odometry` jer Humble arm64 paket nije dostupan.
- `python3-psycopg2`, `python3-yaml`, `python3-pil` i `imagemagick` za
  map metadata, DB insert i PNG preview.

Funkcionalnosti:

- `slam_manager.py` drzi `slam_toolbox` zivim i publisha mapu na `/map`.
- `slam_params.yaml` koristi `map_frame=map`, `odom_frame=odom`,
  `base_frame=base_link`, `scan_topic=/scan`, `resolution=0.05` i
  `mode=mapping`.
- Static TF-ovi senzora se mogu pokrenuti iz `static_tf.yaml`.
- `START_RF2O=auto` pokrece `rf2o_laser_odometry` kada su enkoderi
  iskljuceni (`ENCODERS_ENABLED=0`). U trenutnom stacku je
  `ENCODERS_ENABLED=0`, pa se rf2o pokrece automatski.
- `run_mapping.sh` radi live mapping, opcionalno snima rosbag, sprema mapu
  preko `/slam_toolbox/save_map`, moze koristiti
  `nav2_map_server map_saver_cli`, generira `pgm/yaml/png`, upisuje mapu u
  `robot_data.maps` i azurira `MAP_ROOT/latest`.
- Default imenovanje mapping sesija je inkrementalno: `mapa1`, `mapa2`, ...

### `nav_cont`

Image se gradi iz `nav_cont/Dockerfile` na bazi `ros:humble`.
Instalirani su `ros-humble-navigation2`, `ros-humble-nav2-bringup`,
`ros-humble-nav2-map-server`, `ros-humble-nav2-amcl`,
`ros-humble-nav2-lifecycle-manager`, `ros-humble-joy` i
`ros-humble-teleop-twist-joy`.

Funkcionalnosti:

- `start_nav.sh` pokrece `/app/robot_nav_launch.py`, koji koristi Nav2
  `bringup_launch.py` s
  `nav2_params.yaml`.
- Mapa se bira preko `MAP_FILE`, `MAP_SESSION`, `active` ili `latest`; ako
  mapa ne postoji, generira se mala placeholder mapa da se stack moze podici.
- `goal_forwarder.py` prima `PoseStamped` goalove na
  `/move_base_simple/goal` i salje ih na Nav2 action `navigate_to_pose`.
- `cmd_vel_mux.py` bira izmedu `/cmd_vel_auto` i `/cmd_vel_joy`, publisha
  finalni `/cmd_vel` i exposea servis `/set_manual_mode`.
- Joystick je opcionalan preko `/dev/input/js0`, `joy_node` i
  `teleop_twist_joy`; Logitech F710 mapping je u `teleop_f710.yaml`.
- `nav2_params.yaml` koristi AMCL, DWB local planner, Navfn global planner,
  velocity smoother i costmap slojeve za `/scan` i RealSense pointcloud
  `/camera/realsense/depth/color/points`.
- Publisha anomalije/blokade na `/navigation/anomaly_on_path` i detalje na
  `/navigation/anomaly_detail`.

### `sensor_fusion_cont`

Image se gradi iz `sensor_fusion_cont/Dockerfile` na bazi `ros:humble`.
Bitni ROS paketi su `ros-humble-imu-filter-madgwick` i
`ros-humble-robot-localization`; custom Python paket je
`sensor_fusion_pkg`.

Funkcionalnosti:

- Default `SF_IMU_SOURCE=realsense`: `imu_filter_madgwick_node` cita
  RealSense IMU topic (`SF_IMU_INPUT_TOPIC`, default `/camera/realsense/imu`)
  i publisha filtrirani IMU na `/imu/data`.
- `arduino` mod je fallback/debug za serial legacy: `arduino_listener` cita
  `/imu/arduino`, republish-a `imu/data_raw`, a Madgwick filter ga pretvara u
  `/imu/data`.
- `robot_localization` EKF se pokrece iz `/app/robot_localization.yaml` i
  publisha `odom -> base_link` TF.
- U trenutnom `robot_localization.yaml` odometrijski ulaz je `/odom_rf2o`,
  sto odgovara trenutnom `START_RF2O=auto` + `ENCODERS_ENABLED=0` setupu.
  Ako se kasnije opet ukljuce enkoderi, treba ili ostaviti rf2o ukljucen ili
  uskladiti EKF odometrijski ulaz s aktivnim izvorom.

### `realsense_cont`

Image se gradi iz `realsense_cont/Dockerfile` na bazi `ros:humble`.
Instalira se Intel RealSense apt repo, `librealsense2-utils`,
`librealsense2-dev`, `ros-humble-realsense2-camera`,
`ros-humble-realsense2-description` i `ros-humble-image-transport-plugins`.

Funkcionalnosti:

- `start_realsense.sh` radi preflight s `rs-enumerate-devices` i pokrece
  `ros2 launch realsense2_camera rs_launch.py`.
- Kamera se bira preko `RS_SERIAL` ili `RS_USB_PORT_ID`; ako postoji vise
  kamera, selector je obavezan.
- Runtime default iz stacka: `RS_CAMERA_NAME=realsense`,
  `RS_BASE_FRAME_ID=realsense_link`, color `640x480x15`, depth `640x480x10`,
  `RS_ALIGN_DEPTH=true`, gyro/accel ukljuceni i
  `RS_ENABLE_POINTCLOUD=true`.
- Glavni outputi su RGB/depth/camera_info/IMU topici pod
  `/camera/realsense/...`; pointcloud je potreban za Nav2 costmap.
- `RS_COMPRESSED_JPEG_QUALITY` podesava kvalitetu compressed image transporta.

### `ai_kit_cont`

Image se gradi iz `ai_kit_cont/Dockerfile` na bazi `ros:jazzy-ros-base`.
Jazzy/Ubuntu 24.04 se koristi zbog Hailo/TAPPAS okoline. Hailo runtime se ne
instalira u image, nego se mounta s hosta na kojem je instaliran `hailo-all`.

Bitni paketi i alati:

- GStreamer pluginovi i Python GStreamer bindings.
- `ros-jazzy-cv-bridge`, `ros-jazzy-image-transport`,
  `ros-jazzy-compressed-image-transport` i `ros-jazzy-vision-msgs`.
- `hailo-rpi5-examples` se klonira u image, a model resources se skidaju na
  prvom pokretanju u persistent volume.

Funkcionalnosti:

- `start_ai_kit.sh` provjerava Hailo mountove i ceka RealSense image topic.
- `realsense_hailo_node.py` subscriba RealSense image/depth/camera_info.
- Ako je `HAILO_GST_PIPELINE` postavljen, pipeline mora imati `appsrc`
  imena `ros_src` i `appsink` imena `ros_sink`.
- Ako pipeline nije postavljen, node radi passthrough: republish-a overlay bez
  inferencea. U trenutnom stack env-u je `AI_KIT_REQUIRE_HAILO=0`, pa je taj
  mod dopusten.
- Publisha `/ai_kit/image_overlay`, `/ai_kit/image_overlay/compressed`,
  `/ai_kit/obstacles` i, kada postoji metadata-capable pipeline,
  `/ai_kit/detections`.

### `rosbridge_websocket_cont` / `rosbridge_cont`

Image se gradi iz `rosbridge_cont/Dockerfile` na bazi `ros:humble`.
Koristi paket `ros-humble-rosbridge-server`.

Funkcionalnosti:

- Pokrece `ros2 launch rosbridge_server rosbridge_websocket_launch.xml`.
- Otvara ROS 2 graf web klijentima preko WebSocketa, tipicno na portu
  `9090`.
- Builda lokalni `/ros_ws` workspace iz `rosbridge_cont/src`.

### `foxglove_bridge_cont`

Image se gradi iz `foxglove_bridge_cont/Dockerfile` na bazi `ros:humble`.
Koristi paket `ros-humble-foxglove-bridge`.

Funkcionalnosti:

- Pokrece `ros2 run foxglove_bridge foxglove_bridge`.
- Default endpoint je `0.0.0.0:8765`.
- TLS je opcionalan preko `FOXGLOVE_TLS`, `FOXGLOVE_TLS_CERT` i
  `FOXGLOVE_TLS_KEY`.
- Namijenjen je Foxglove Studio vizualizaciji topic-a, TF-a, mapa i slika.

### `bag_recorder_cont`

Image se gradi iz `bag_recorder_cont/Dockerfile` na bazi
`ros:humble-ros-base`. Koristi `ros-humble-ros2bag`,
`ros-humble-rosbag2-storage-default-plugins` i
`ros-humble-rosbag2-compression-zstd`.

Funkcionalnosti:

- `bag_recorder.sh` cita YAML listu topic-a iz
  `/config/recorded_topics.yaml`.
- Ceka aktivne publishere prije pokretanja snimanja.
- Snima u `/bags` s default rotacijom `MAX_BAG_MB=150`.
- Koristi file-level Zstd kompresiju.
- Ima alias resolution za RealSense topic prefikse, `/odom` vs
  `/wheel_odom`, te neke compressed image nazive.
- Trenutni `recorded_topics.yaml` snima `/scan`, `/tf`, `/tf_static`,
  `/map`, `/imu/data`, `/imu/arduino` i glavne RealSense image/IMU topice;
  `/imu/arduino` ima publisher samo u serial legacy modu, a `/wheel_odom` je
  ostavljen kao lako ukljuciva stavka.

### `database_cont` / `db_cont`

Image se gradi iz `db_cont/Dockerfile` na bazi `postgres:15`.
Instaliran je `postgresql-15-postgis-3`; `init-db.sql` ukljucuje PostGIS i
`uuid-ossp`.

Funkcionalnosti:

- Exposea PostgreSQL na portu `5432`.
- `PGDATA` je u runtime stacku postavljen na `/srv/db`.
- Shema je `robot_data`.
- Glavne tablice su `maps`, `camera_images`, `waypoints` i
  `robot_sessions`.
- `slam_cont/run_mapping.sh` upisuje spremljene mape u `robot_data.maps`
  zajedno s rezolucijom, originom, dimenzijama i YAML hash metapodacima.

### `healthcheck_cont`

Image se gradi iz `healthcheck_cont/Dockerfile` na bazi `ubuntu:22.04`.
Instalira Docker CLI, `netcat`, `usbutils` i ROS 2 Humble CLI
(`ros-humble-ros-base`, `ros-humble-rmw-cyclonedds-cpp`).

Funkcionalnosti:

- `healthcheck.py` provjerava Docker status i health status ocekivanih
  kontejnera.
- Provjerava portove `5432`, `9090` i `8765`.
- Provjerava hardverske putanje za lidar, RealSense USB i konfigurirani
  bridge device path. U aktivnom `rpi_direct` stacku taj path je `/dev/null`,
  pa healthcheck trenutno ne validira I2C/GPIO funkcionalnost.
- Provjerava ROS topice `/scan`, `/wheel_odom`, `/tf`, `/tf_static`,
  `/imu/data` i `/camera/realsense/color/image_raw`.
- Provjerava osnovno stanje hosta: load, memoriju, disk i temperaturu.
- Moze pisati report u `/logs` ako je `HEALTHCHECK_LOG_TO_FILE=1`.

### `container_log_collector_cont`

Koristi isti image kao `healthcheck_cont`, ali entrypoint je
`container_log_collector.py`.

Funkcionalnosti:

- Cita Docker logove preko read-only `/var/run/docker.sock`.
- Automatski prati sve kontejnere u compose projektu
  `COMPOSE_PROJECT_NAME`.
- Pise dnevne logove u `/logs/<dan>/<container>.log`.
- Sprema resume state u `/logs/.container-log-state.json` da ne duplicira
  linije nakon restarta.
- Konfigurira se kroz `../stack/config/containers/logging.yaml`.

### `bag_browser_cont`

Ovo nije lokalni image iz repozitorija, nego runtime helper iz composea:
`filebrowser/filebrowser:latest`.

Funkcionalnosti:

- Web preglednik za `../stack/bags` i `../stack/logs`.
- Exposea port `8080`.
- Mountovi su read-only.
- Compose ga pokrece bez autentikacije (`--noauth`), pa ga treba koristiti
  samo na kontroliranoj mrezi.

### `camera_cont` (opcionalno)

Image se gradi iz `camera_cont/Dockerfile` na bazi `ros:humble-ros-base`, ali
servis je trenutno komentiran u `../stack/docker-compose.yaml` jer je
RealSense glavni aktivni camera path.

Funkcionalnosti:

- `camera_node.py` koristi OpenCV + GStreamer pipeline.
- Default input je UDP/H264 pipeline na portu `5000`, ili custom
  `CAMERA_GSTREAMER_PIPELINE`.
- Publisha JPEG `CompressedImage` na `/camera/image_raw/compressed`.
- Publisha `CameraInfo` na `/camera/camera_info` ako je dostupan
  `camera_info.yaml`.

## Arhitektura ukratko

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> sensor_fusion_cont --> /imu/data
                                         \
RPi GPIO/I2C -> bridge_cont --------------> /wheel_odom, /robot_status
      ^                 |
      |                 +<------------------------------ /cmd_vel
      |
      +-- DRV8833 -> motori
      +-- TCA9548A -> AS5600 LEFT / RIGHT (oziceno, trenutno iskljuceno)

nav_cont <----- /map, /tf, odometrija, /scan
   |
   +--> /cmd_vel_auto --> cmd_vel_mux --> /cmd_vel --> bridge_cont

slam_cont <----- /scan, /tf, odometrija, /imu/data
```

## Tipicni scenariji rada

### Pokretanje sustava

Uobicajeni redoslijed je:

1. Buildati ili preuzeti imageove iz ovog repoa.
2. Pokrenuti runtime stack iz `../stack/`.
3. Provjeriti da su aktivni barem `bridge_cont`, `laser_driver_cont` i `slam_cont`.
4. Za aktivni `rpi_direct` mod provjeriti `/dev/i2c-1` i `/dev/gpiochip4`.
   Nano `/dev/ttyACM0` treba provjeravati samo ako se namjerno koristi
   `BRIDGE_MODE=serial_legacy`.

Healthcheck primjer:

```bash
docker exec -it healthcheck_cont /usr/local/bin/healthcheck.py
```

### Mapiranje

Glavni alat za mapiranje je `slam_cont/run_mapping.sh`.

Tijekom mapiranja korisno je pratiti:

- `/map`
- `/scan`
- `/tf`
- `/wheel_odom`
- `/imu/data`

Napomena:

- bridge trenutno publisha `/wheel_odom`
- dio starijih konfiguracija i skripti jos uvijek koristi `/odom` kao legacy naziv

### Navigacija

`nav_cont/start_nav.sh` pokrece:

- Nav2 bringup
- `goal_forwarder.py`
- `cmd_vel_mux.py`
- opcionalno joystick i teleop

### AI obrada slike

`ai_kit_cont` je namijenjen Raspberry Pi AI Kitu s Hailo akceleratorom:

- Hailo runtime se ocekuje na hostu
- bez `HAILO_GST_PIPELINE` radi u passthrough modu
- s pipelineom objavljuje AI overlay topice

### Snimanje bagova

Ako zelis neovisno snimati topice:

```bash
docker exec -it bag_recorder_cont /app/bag_recorder.sh
```

## Najvazniji ROS topici i servisi

Topici:

- `/scan`
- `/tf`
- `/tf_static`
- `/wheel_odom`
- `/imu/data`
- `/imu/arduino` (samo serial legacy/debug)
- `/map`
- `/cmd_vel`
- `/cmd_vel_auto`
- `/cmd_vel_joy`

Servisi i actioni:

- `/slam_toolbox/save_map`
- `navigate_to_pose`

## Preduvjeti

Projekt tipicno pretpostavlja:

- ROS 2 Humble za vecinu kontejnera
- Docker i Docker Compose
- lidar i/ili kameru spojenu na host
- za aktivni `rpi_direct` mod pristup `/dev/i2c-1` i `/dev/gpiochip4`
- za legacy `serial_legacy` mod Nano ESP32 spojen kao serijski uredaj
- pristup uredajima poput `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/i2c-1`,
  `/dev/gpiochip4` i `/dev/bus/usb`

Za `ai_kit_cont` dodatno:

- arm64 host
- instaliran Hailo runtime na hostu
- bind mount Hailo biblioteka u kontejner

## Dodatna dokumentacija

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [COMMUNICATION_ANALYSIS.md](./COMMUNICATION_ANALYSIS.md)
- [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md)
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md)
- [HARDWARE_SETUP_CUSTOM_PROTOCOL.md](./HARDWARE_SETUP_CUSTOM_PROTOCOL.md)
- [bridge_cont/README.md](./bridge_cont/README.md)
- [nav_cont/README.md](./nav_cont/README.md)
- [db_cont/README.md](./db_cont/README.md)
