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

Trenutna podrzana robot arhitektura je:

```text
Raspberry Pi -> USB -> Nano ESP32 -> DRV8833 -> motori
                           |
                           \-> TCA9548A -> AS5600 LEFT / RIGHT
```

Napomena:

- `UNO R4` vise nije dio glavne implementacije
- `DRV8833` je trenutni motor driver
- `robot_bridge` tipicno koristi `/dev/ttyACM0`

## Glavne komponente

| Komponenta | Uloga | Najvazniji ulazi / izlazi |
| --- | --- | --- |
| `bridge_cont` | Serijski most prema Nano ESP32 | Publisha `/imu/arduino`, `/wheel_odom`, `/robot_status`; subscriba `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver za RPLidar | Publisha `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Objavljuje RGB, depth, camera info i IMU topice |
| `slam_cont` | `slam_toolbox`, mapiranje, save/export mape, upis u bazu | Koristi `/scan`, `/tf`, odometriju i IMU; publisha `/map` |
| `nav_cont` | Nav2, prosljedivanje goalova i `cmd_vel` mux | Prima `/move_base_simple/goal`; publisha `/cmd_vel_auto` i finalni `/cmd_vel` |
| `bag_recorder_cont` | Kontinuirano snimanje ROS 2 bagova | Snima topice iz `TOPICS_FILE` u `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS baza | Sprema mape, slike, waypointove i sesije |
| `rosbridge_cont` | ROS 2 -> WebSocket za web klijente | Tipicno port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge za Foxglove Studio | Tipicno port `8765` |
| `ai_kit_cont` | Hailo AI obrada slike ili passthrough overlay | Prima RealSense sliku; publisha AI overlay topice |
| `sensor_fusion_cont` | Filtriranje IMU podataka | Po defaultu pretvara RealSense IMU u `/imu/data`; Arduino IMU ostaje debug/fallback stream |
| `healthcheck_cont` | Provjera stanja kontejnera, portova, uredaja i ROS grafa | Pise health report u logove |

## Arhitektura ukratko

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> sensor_fusion_cont --> /imu/data
                                         \
Microcontroller -> bridge_cont -----------> /wheel_odom, /imu/arduino, /robot_status
            ^               |
            |               +<------------------------------ /cmd_vel
            |
            +-- Nano ESP32 -> DRV8833 -> motori

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
4. Provjeriti da je Nano vidljiv kao `/dev/ttyACM0`.

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
- `/imu/arduino`
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
- Nano ESP32 spojen kao serijski uredaj
- pristup uredajima poput `/dev/ttyUSB0`, `/dev/ttyACM0` i `/dev/bus/usb`

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
