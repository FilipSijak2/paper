# Diplomski Rad

Ovaj repozitorij sadrzi glavne softverske komponente robotskog sustava temeljenog na ROS 2, Dockeru i vise specijaliziranih servisa. Repo pokriva:

- prikupljanje podataka sa senzora
- komunikaciju s mikrokontrolerima
- SLAM i izradu mapa
- autonomnu navigaciju
- AI obradu slike
- snimanje ROS 2 bagova
- pohranu podataka u PostgreSQL bazu
- vizualizaciju preko rosbridge i Foxglove bridge

Operativni `docker-compose` stack je tipicno u sibling direktoriju `../stack/`, dok ovaj repo sadrzi imageove, skripte i aplikacijsku logiku.

## Glavne komponente

| Komponenta | Uloga | Najvazniji ulazi / izlazi |
| --- | --- | --- |
| `bridge_cont` | Serijski most prema mikrokontroleru robota | Publisha `/imu/arduino`, `/wheel_odom`, `/robot_status`; subscriba `/cmd_vel` |
| `laser_driver_cont` | ROS 2 driver za RPLidar | Publisha `/scan` |
| `realsense_cont` | Intel RealSense ROS 2 driver | Objavljuje RGB, depth, camera info i point cloud topice |
| `slam_cont` | `slam_toolbox`, mapiranje, save/export mape, upis u bazu | Koristi `/scan`, `/tf`, `/odom`, `/imu`; publisha `/map` |
| `nav_cont` | Nav2, prosljedivanje goalova i `cmd_vel` mux | Prima `/move_base_simple/goal`; publisha `/cmd_vel_auto` i anomaly topice |
| `bag_recorder_cont` | Kontinuirano snimanje ROS 2 bagova | Snima topice iz `TOPICS_FILE` u `BAG_OUTPUT_DIR` |
| `db_cont` | PostgreSQL/PostGIS baza | Sprema mape, slike, waypointove i sesije |
| `rosbridge_cont` | ROS 2 -> WebSocket za web klijente | Tipicno port `9090` |
| `foxglove_bridge_cont` | ROS 2 bridge za Foxglove Studio | Tipicno port `8765` |
| `ai_kit_cont` | Hailo AI obrada slike ili passthrough overlay | Prima RealSense sliku; publisha AI overlay topice |
| `sensor_fusion_cont` | ROS 2 paket za IMU ingest i filtriranje | Po defaultu filtrira RealSense IMU u `/imu/data`; u Arduino modu publisha `imu/data_raw`, `imu/raw_line`, `/diagnostics` |
| `camera_cont` | UDP video ulaz i objava u ROS 2 | Publisha `/camera/image_raw/compressed` i `/camera/camera_info` |
| `healthcheck_cont` | Provjera stanja kontejnera, portova, uredaja i ROS grafa | Pise health report u logove |

## Arhitektura ukratko

```text
Lidar --------> laser_driver_cont ----\
                                       \
RealSense ----> realsense_cont ---------> slam_cont ------> /map
                                         /       \
Microcontroller -> bridge_cont ---------/         \--> db_cont
            |               ^                      \--> bag_recorder_cont
            |               |
            +----- /cmd_vel-+

nav_cont <----- /map, /tf, /odom, /scan
   |
   +--> /cmd_vel_auto --> cmd_vel_mux --> /cmd_vel --> bridge_cont

rosbridge_cont / foxglove_bridge_cont --> RViz / Foxglove / web klijenti
ai_kit_cont <----- RealSense slike -----> AI overlay topici
```

## Tipicni scenariji rada

### Pokretanje sustava

Uobicajeni redoslijed je:

1. Buildati ili preuzeti imageove iz ovog repoa.
2. Pokrenuti runtime stack iz `../stack/`.
3. Provjeriti da su aktivni barem `bridge_cont`, `laser_driver_cont` i `slam_cont`.
4. Po potrebi dodati `realsense_cont`, `nav_cont`, `db_cont`, `ai_kit_cont` i ostale servise.

Healthcheck primjer:

```bash
docker exec -it healthcheck_cont /usr/local/bin/healthcheck.py
```

### Mapiranje

Glavni alat za mapiranje je `slam_cont/run_mapping.sh`. Skripta:

- pokrece ili reuse-a `slam_toolbox`
- pokrece `ros2 bag record`
- tijekom voznje objavljuje live mapu na `/map`
- na `Ctrl+C` sprema live mapu i pokusava occupancy export
- po potrebi upisuje rezultat u bazu

Primjer:

```bash
docker exec -it slam_cont bash
bash /app/run_mapping.sh --name mapa1
```

Tijekom mapiranja korisno je pratiti:

- `/map`
- `/scan`
- `/tf`
- `/odom`

Napomena: `/map` moze postojati i prije finalnog spremanja. To je live mapa u memoriji. Na disk se sprema tek u save/export koraku.

### Navigacija

`nav_cont/start_nav.sh` pokrece:

- Nav2 bringup
- `goal_forwarder.py`
- `cmd_vel_mux.py`
- opcionalno joystick i teleop

Ako prava mapa nije zadana, skripta moze generirati placeholder mapu da servisi ostanu aktivni. Za stvarnu voznju treba koristiti stvarni `map.yaml`.

### AI obrada slike

`ai_kit_cont` je namijenjen Raspberry Pi AI Kitu s Hailo akceleratorom:

- Hailo runtime se ocekuje na hostu, nije bake-an u image
- kontejner ceka RealSense image topic prije starta noda
- bez `HAILO_GST_PIPELINE` radi u passthrough modu
- s pipelineom objavljuje AI overlay topice

### Snimanje bagova

Ako zelis neovisno snimati topice:

```bash
docker exec -it bag_recorder_cont /app/bag_recorder.sh
```

`TOPICS_FILE` se u praksi cesto mounta iz `../stack/config/recorded_topics.yaml`.

## Najvazniji ROS topici i servisi

Topici:

- `/scan`
- `/tf`
- `/tf_static`
- `/odom`
- `/map`
- `/cmd_vel`
- `/cmd_vel_auto`
- `/cmd_vel_joy`
- `/move_base_simple/goal`
- `/navigation/anomaly_on_path`
- `/ai_kit/image_overlay/compressed`

Servisi i actioni:

- `/slam_toolbox/save_map`
- `/set_manual_mode`
- `navigate_to_pose`

## Baza podataka

`db_cont/init-db.sql` inicijalizira `robot_data` schemu i glavne tablice:

- `robot_data.maps`
- `robot_data.camera_images`
- `robot_data.waypoints`
- `robot_data.robot_sessions`

U praksi je najvaznije da `slam_cont` moze nakon mapiranja spremiti finalnu mapu i metadata zapis u `robot_data.maps`.

## Preduvjeti

Projekt tipicno pretpostavlja:

- ROS 2 Humble za vecinu kontejnera
- Docker i Docker Compose
- lidar i/ili kameru spojenu na host
- serijski uredaj za mikrokontroler
- pristup uredajima poput `/dev/ttyUSB0`, `/dev/ttyACM0` i `/dev/bus/usb`

Za `ai_kit_cont` dodatno:

- arm64 host
- instaliran Hailo runtime na hostu
- bind mount Hailo biblioteka u kontejner

## Dodatna dokumentacija

Za detaljniji tehnicki opis pogledaj:

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md)
- [HARDWARE_SETUP_CUSTOM_PROTOCOL.md](./HARDWARE_SETUP_CUSTOM_PROTOCOL.md)
- [bridge_cont/README.md](./bridge_cont/README.md)
- [nav_cont/README.md](./nav_cont/README.md)
- [db_cont/README.md](./db_cont/README.md)
