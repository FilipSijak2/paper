# Analiza komunikacije sustava

Ovaj dokument opisuje komunikacijski model aktualne arhitekture robota.

## Sažetak

Sustav koristi tri komunikacijske cjeline:

| Cjelina | Uloga |
| --- | --- |
| Raspberry Pi 5 | ROS 2 robot graph, LiDAR, kamera, SLAM, Nav2, motorni bridge, rosbridge i foxglove_bridge |
| Jetson Orin | YOLO detekcija anomalija, lokalno spremanje artefakata i objava anomaly topic-a |
| Foxglove | Vizualizacija robota, mape i anomaly podataka kroz Raspberry Pi foxglove_bridge |

Aktualna granica između Raspberry Pi računala i Jetsona je `rosbridge` WebSocket. ROS 2 DDS graph živi na Raspberry Pi robot runtimeu, a Jetson koristi aplikacijsku WebSocket vezu za odabrane topic-e.

## Raspberry Pi komunikacijska uloga

Raspberry Pi hosta:

- ROS 2 robot graph
- `rosbridge_server`, obično `ws://raspberry.local:9090`
- `foxglove_bridge`, obično `ws://raspberry.local:8765`

Raspberry Pi prema Jetsonu izlaže odabrane podatke:

- `/camera/.../compressed` za YOLO input
- `/map` za izradu slike mape s oznakom anomalije
- `/robot_pose_map` ili `/amcl_pose` za procjenu pozicije anomalije

Raspberry Pi kroz rosbridge prima anomaly topic-e koje Jetson objavljuje:

- `/anomaly/events`
- `/anomaly/markers`
- `/anomaly/debug_image/compressed`
- `/anomaly/map_snapshot/compressed`

## Jetson komunikacijska uloga

Jetson koristi rosbridge WebSocket klijent prema Raspberry Pi računalu.

Jetson prima:

- komprimirani slikovni tok kamere
- kartu prostora
- pozu robota u mapi

Jetson objavljuje:

- JSON anomaly evente
- vizualizacijske markere u `map` frameu
- anotiranu sliku kamere
- sliku mape s oznakom anomalije

Jetson lokalno sprema:

- originalnu sliku
- anotiranu sliku
- map snapshot PNG
- `events.jsonl`

## Foxglove komunikacijska uloga

Foxglove koristi Raspberry Pi `foxglove_bridge` endpoint:

```text
ws://raspberry.local:8765
```

Foxglove prikazuje normalne robot topic-e i anomaly topic-e koje Jetson objavljuje kroz rosbridge.

Preporučeni topic-i za Foxglove prikaz:

- `/map`
- `/tf`
- `/tf_static`
- `/scan` ili `/scan_filtered`
- `/odom`
- `/robot_pose_map` ili `/amcl_pose`
- `/anomaly/markers`
- `/anomaly/events`
- `/anomaly/debug_image/compressed`
- `/anomaly/map_snapshot/compressed`

## Slikovni tok

Slikovni tok za Jetson inference koristi compressed image topic-e. Osnovni tok je:

```text
Raspberry Pi camera publisher
    -> /camera/.../compressed
    -> rosbridge_server :9090
    -> Jetson YOLO anomaly client
```

Anotirani rezultat koristi zaseban compressed image topic:

```text
Jetson YOLO anomaly client
    -> /anomaly/debug_image/compressed
    -> rosbridge_server :9090
    -> Raspberry Pi ROS graph
    -> foxglove_bridge :8765
    -> Foxglove
```

## Motorna i senzorska komunikacija

Motorni put koristi direktni Raspberry Pi GPIO bridge:

```text
Raspberry Pi GPIO -> DRV8833 -> motori
```

Senzorski i navigacijski tokovi:

```text
RPLidar /scan -> SLAM / AMCL / Nav2 -> /map + lokalizacija
RealSense / kamera -> compressed image topic-i -> Jetson inference
Nav2 / cmd_vel -> bridge_cont -> DRV8833 -> motori
```

## Runtime granice

- Raspberry Pi vodi robotiku, navigaciju, mapu, ROS 2 graph, rosbridge i foxglove_bridge.
- Jetson vodi YOLO inference, anomaly logiku i spremanje artefakata.
- Foxglove koristi Raspberry Pi foxglove_bridge kao jedinstveni ulaz u prikaz sustava.
- Compressed image topic-i čine osnovni slikovni transport prema Jetsonu.
- Anomaly topic-i čine osnovni transport rezultata prema Foxglove prikazu.
