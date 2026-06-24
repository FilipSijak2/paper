# Diplomski rad

Ovaj repozitorij sadrzi dokumentaciju i softverske komponente za ROS 2 robotski sustav diplomskog rada. Raspberry Pi ostaje glavno robotsko racunalo za kretanje, SLAM, Nav2, mapu, LiDAR i kameru, dok je detekcija anomalija prebacena na Jetson Orin.

## Aktualna odluka arhitekture

Trenutna aktivna arhitektura je:

```text
Raspberry Pi 5
├─ ROS 2 robot stack
├─ LiDAR, SLAM, AMCL/Nav2, /map, /tf, /scan, /odom
├─ RealSense/kamera publisher
├─ rosbridge_server :9090
└─ foxglove_bridge :8765

Jetson Orin
├─ spaja se na Raspberry Pi preko rosbridge WebSocketa
├─ prima compressed camera stream, mapu i pozu robota
├─ pokrece YOLO detekciju anomalija
├─ za prvi scenarij tretira bottle/bocu kao anomaliju
├─ lokalno sprema originalnu sliku, anotiranu sliku, map snapshot i JSONL log
└─ vraca samo anomaly vizualizacijske topice prema Raspberry Pi-ju

Foxglove
└─ spaja se na Raspberry Pi foxglove_bridge i prikazuje mapu, robota i anomaly topice
```

Jetson se **ne spaja direktno u ROS 2 DDS mrezu** jer je to u ranijim testovima nepotrebno opteretilo Raspberry Pi. Umjesto toga koristi se `rosbridge` WebSocket kanal.

## Trenutna hardverska arhitektura

Aktualna motorna arhitektura vise ne koristi wheel enkodere ni I2C multiplexor:

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> motori
```

Napomene:

- `BRIDGE_MODE=rpi_direct` je aktivni bridge mode.
- `DRV8833` je trenutni motor driver.
- wheel enkoderi se trenutno **ne koriste**.
- `TCA9548A` I2C multiplexor se trenutno **ne koristi**.
- AS5600 enkoderi i encoder mux dokumenti su legacy/eksperimentalni.
- `UNO R4` i `Nano ESP32 serial_legacy` put vise nisu glavni aktivni motorni put.
- odometrija/navigacija oslanja se na LiDAR/SLAM/AMCL/Nav2 i postojece ROS izvore poze, a ne na wheel enkodere.

## AI / anomaly detection

Aktivna odluka je da se anomaly detection ne izvodi preko Raspberry Pi AI Kita / Hailo-a. AI Kit/Hailo dokumentaciju i container treba tretirati kao legacy/eksperimentalni dio.

Aktivni anomaly workflow je:

```text
Raspberry Pi compressed camera + map + robot pose
        |
        v
Jetson Orin YOLO
        |
        +--> sprema slike i logove lokalno na Jetsonu
        |
        v
/anomaly/events
/anomaly/markers
/anomaly/debug_image/compressed
/anomaly/map_snapshot/compressed
        |
        v
Raspberry Pi rosbridge -> foxglove_bridge -> Foxglove prikaz
```

Detaljan opis nalazi se u [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md).

## Glavne komponente

| Komponenta | Trenutna uloga |
| --- | --- |
| `bridge_cont` | Raspberry Pi direct GPIO motor bridge za DRV8833; bez aktivnih wheel enkodera |
| `laser_driver_cont` | RPLidar ROS 2 driver, objavljuje `/scan` |
| `realsense_cont` | RealSense/camera topics za RGB/depth/camera_info/IMU |
| `slam_cont` | SLAM Toolbox, mapa `/map`, map save/export |
| `nav_cont` | Nav2, AMCL, goal forwarder, cmd_vel mux/safety logic |
| `sensor_fusion_cont` | IMU/filter/robot_localization, ovisno o aktivnim izvorima |
| `rosbridge_cont` | WebSocket pristup odabranim ROS topicima, port `9090` |
| `foxglove_bridge_cont` | Foxglove prikaz preko WebSocketa, port `8765` |
| `ai_kit_cont` | Legacy/eksperimentalni Hailo path; nije aktivni anomaly pipeline |
| `bag_recorder_cont` | Snimanje ROS bagova |
| `db_cont` | PostgreSQL/PostGIS baza |
| `healthcheck_cont` | Provjera stanja kontejnera i ROS grafa |

## Vazni dokumenti

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) - aktualni pregled arhitekture.
- [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md) - aktualna shema ozicenja bez enkodera/multiplexora.
- [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md) - preporuceno ozicenje.
- [HARDWARE_COMPONENTS.md](./HARDWARE_COMPONENTS.md) - aktualne hardverske komponente.
- [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md) - Jetson YOLO anomaly pipeline.
- [COMMUNICATION_ANALYSIS.md](./COMMUNICATION_ANALYSIS.md) - komunikacijski model izmedju RPi, Jetsona i Foxglovea.

## Legacy napomene

Ako dokument ili kod spominje `TCA9548A`, `AS5600`, `ENCODERS_ENABLED=1`, `Hailo`, `AI Kit` ili `serial_legacy`, to ne treba tumaciti kao trenutno aktivni smjer sustava. Trenutni smjer je:

```text
Raspberry Pi: navigacija + senzori + ROS bridge
Jetson: YOLO anomaly detection + spremanje slika/snapshotova/logova
Foxglove: vizualizacija preko Raspberry Pi foxglove_bridge
```
