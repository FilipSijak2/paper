# Diplomski rad

Ovaj repozitorij sadrži dokumentaciju za ROS 2 robotski sustav diplomskog rada. Raspberry Pi 5 vodi robotiku, navigaciju i ROS 2 infrastrukturu. Jetson Orin vodi YOLO detekciju anomalija i lokalno spremanje dokaznih artefakata.

## Brzi pregled sustava

```text
Raspberry Pi 5
├─ ROS 2 robot stack
├─ GPIO motor bridge: rpi_direct -> DRV8833 -> motori
├─ LiDAR, kamera, SLAM, AMCL/Nav2, mapa i lokalizacija
├─ rosbridge_server :9090
└─ foxglove_bridge :8765

Jetson Orin
├─ rosbridge WebSocket klijent prema Raspberry Pi računalu
├─ YOLO detekcija anomalija
├─ prva anomaly klasa: bottle
├─ lokalno spremanje originalne slike, anotirane slike, slike mape i JSONL loga
└─ objava anomaly topic-a za Foxglove prikaz

Foxglove
└─ WebSocket veza prema Raspberry Pi foxglove_bridge servisu
```

## Aktualni tok sustava

```text
navigacija i pogon:
/cmd_vel -> Nav2 / safety -> bridge_cont -> DRV8833 -> motori

percepcija i anomalije:
/camera/.../compressed + /map + /robot_pose_map ili /amcl_pose
    -> rosbridge
    -> Jetson YOLO anomaly client
    -> Jetson local artifact storage
    -> /anomaly/events + /anomaly/markers + anomaly image topic-i
    -> rosbridge
    -> Raspberry Pi ROS graph
    -> foxglove_bridge
    -> Foxglove
```

## Dokumentacija

| Dokument | Svrha |
| --- | --- |
| [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) | Glavni pregled arhitekture sustava, tokova podataka i Mermaid vizualizacije. |
| [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md) | Trenutno fizičko ožičenje Raspberry Pi 5 -> DRV8833 -> motori, uključujući GPIO pinove. |
| [HARDWARE_WIRING_GUIDE.md](./HARDWARE_WIRING_GUIDE.md) | Praktična checklista za spajanje, provjeru ožičenja i sigurno gašenje. |
| [HARDWARE_COMPONENTS.md](./HARDWARE_COMPONENTS.md) | Popis hardverskih komponenti i njihovih trenutnih uloga. |
| [ANOMALY_ROSBRIDGE_PIPELINE.md](./ANOMALY_ROSBRIDGE_PIPELINE.md) | Operativne upute za Jetson YOLO anomaly pipeline, topic-e, env varijable i testiranje. |
| [COMMUNICATION_ANALYSIS.md](./COMMUNICATION_ANALYSIS.md) | Komunikacijski model između Raspberry Pi računala, Jetsona i Foxglovea. |

## Trenutne ključne konfiguracije

```env
BRIDGE_MODE=rpi_direct
GPIOCHIP=/dev/gpiochip4
DRIVER=drv8833
ENCODERS_ENABLED=0
```

Anomaly pipeline koristi `bottle` kao prvu realnu anomaly klasu. Jetson lokalno sprema slike, map snapshot i `events.jsonl`, a prema Raspberry Pi računalu objavljuje topic-e za vizualizaciju u Foxgloveu.
