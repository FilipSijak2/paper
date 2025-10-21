# Sustav autonomnog robota – Arhitektura i Funkcioniranje

Ovaj dokument sumira trenutno stanje projekta: komponente, komunikaciju, tokove podataka, načine pokretanja, mapiranje, pohranu i održavanje. Namijenjen je i tehničkom i operativnom osoblju. Jezik: hrvatski s namjernim zadržavanjem engleskih tehničkih termina radi konzistentnosti s kodom.

---
## 1. Uvod
Sustav je modularan ROS 2 (Humble) deployment orkestriran Docker Compose-om. Glavne funkcije:
1. Senzorska akvizicija (LIDAR, IMU, eventualno dodatni senzori preko Arduino/ESP32).
2. SLAM (slam_toolbox) i potencijalna navigacija (nav2 komponentni dijelovi dodani djelomično – map_server za eksport mape).
3. Upravljanje robotom (serijski bridge prema mikrokontroleru – kontrola motora, očitanje senzora custom protokolom).
4. Mapiranje + snimanje bagova + generiranje occupancy mape (.pgm/.yaml) + spremanje u bazu.
5. Komunikacijski most (rosbridge za web/vanjske klijente, buduće UI / Foxglove vizualizacija).
6. Centralizirana baza (PostgreSQL) za pohranu mapa i eventualno drugih telemetrijskih podataka.

Glavni izazovi adresirani do sada: stabilno pokretanje containera, RMW konfiguracija, robustno mapiranje (sprječavanje blokiranja na SaveMap), generiranje occupancy mape i fallback mehanizmi.

---
## 2. Visokorazinska arhitektura

```
┌────────────────────────────────────────────────────────────────┐
│                          Host / Edge                           │
│  docker-compose orchestrira više servisa (network=host)        │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ bridge   │  │ slam_cont │  │ nav_cont │  │ sensor_f │ ...    │
│  │ (serial) │  │ (SLAM +   │  │ (planer) │  │ fusion   │        │
│  └────┬─────┘  │ mapping)  │  └────┬─────┘  └────┬─────┘        │
│       │         └────┬─────┘       │            │              │
│       │ TF/odom/...   │ topics     │ cmd_vel     │ fused data   │
│       ▼               ▼            ▼            ▼              │
│                   ┌────────────────────┐                       │
│                   │   rosbridge_cont   │ (JSON/WebSocket)       │
│                   └─────────┬──────────┘                       │
│                             │                                   │
│                             ▼                                   │
│                        External UI / Tools (Foxglove, WebApp)   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                        db_cont (PostgreSQL)              │   │
│  │   tabela robot_data.maps – pohrana mapa (+ metapodaci)   │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

Komunikacija: ROS 2 DDS (CycloneDDS – `rmw_cyclonedds_cpp`). Bridge kontejner izlaže serijski protokol prema mikrokontroleru (motori / senzori) i publisha u ROS topike. SLAM kontejner konzumira /scan, /tf, /odom, /imu. Navigacija (nav_cont) može kasnije konzumirati mapu i lokalizaciju.

---
## 3. Hardverske komponente i spajanje
Referenca: `HARDWARE_WIRING_GUIDE.md`, `HARDWARE_SETUP_CUSTOM_PROTOCOL.md` (postojeći dokumenti). Sažetak:
- Mikrokontroler(i): Arduino / ESP32 (devastator kontroler + senzorski modul). Komunikacija serijski USB / UART.
- Senzori: LIDAR (publisha /scan kroz driver ili most), IMU (/imu), enkoderi (indirektno kroz /odom).
- Računalo: Edge uređaj (npr. Raspberry Pi) pokreće Docker Compose stack.
- Napajanje: Odvojene grane za motore i logiku (detalji u postojećim hardware dokumentima).

Ključni signali:
- Serijski protokol -> bridge_cont -> ROS topici (npr. /wheel_ticks, /battery, custom status).
- LIDAR driver (može biti unutar zasebnog driver containera ili putem host OS-a) -> /scan.
- IMU driver -> /imu.
- Odom integracija (fusion / nav stack) -> /odom.

---
## 4. Softverske komponente (Docker servisi)

| Kontejner | Uloga | Ključne tehnologije |
|-----------|-------|---------------------|
| bridge_cont | Serijski most (microcontroller <-> ROS) | Python, pyserial |
| slam_cont | SLAM + mapiranje + bag recording | ROS 2 Humble, slam_toolbox, nav2 map_server, custom `run_mapping.sh` |
| nav_cont | Navigacija / path planning (planer) | nav2 / custom Python skripte |
| rosbridge_cont | WebSocket most za vanjske klijente | rosbridge_suite |
| sensor_fusion_cont | Spaja senzorske podatke (npr. IMU+odom) | ROS 2, custom pkg |
| db_cont | Postgres baza | PostgreSQL 15 (pretpostavljeno) |
| laser_driver_cont | Driver za LIDAR (ako nije host) | ROS 2 driver |
| rosbridge_cont | Publikacija ROS preko JSON ws | rosbridge |

Deployment logika: `docker-compose.yaml` (u drugoj mapi `stack/`). Većina kontejnera koristi `network_mode: host` radi lakšeg pristupa serijskim uređajima i multicast DDS-a.

---
## 5. ROS 2 graf i teme / servisi

Minimalni skup za SLAM:
- `/scan` (sensor_msgs/LaserScan)
- `/tf`, `/tf_static` (transformi)
- `/odom` (nav_msgs/Odometry)
- `/imu` (sensor_msgs/Imu) – opcionalno za bolje praćenje orijentacije
- `/slam_toolbox/save_map` (slam_toolbox/srv/SaveMap ili nav2_msgs/srv/SaveMap)
- `/map` (nav_msgs/OccupancyGrid) – objavljuje se samo ako `publish_map=true` ili nav2 map_server.

Internal bridging:
- Serijski bridge može objavljivati /battery, /cmd_vel echo, /wheel_ticks – nisu još standardizirani (treba definirati u kasnijoj fazi).

Servisi / komande:
- SaveMap (dinamički tip detektiran u skripti) – razlika: nav2 verzija generira .pgm/.yaml, slam_toolbox verzija ne.
- Mogući budući /clear_costmaps, /navigate_to_pose kad se nav2 stack proširi.

---
## 6. SLAM i generiranje mape

Glavni procesi:
1. Live SLAM: `slam_toolbox` u online_async načinu (pokreće ga `slam_manager.py` ili ručno). Parametri (nije još zasebni YAML u repou – potencijal za buduće izdvajanje).
2. Snimanje: `ros2 bag record` (sqlite3 ili mcap) inicirano iz `run_mapping.sh`.
3. Završetak sesije: CTRL+C hvata trap; skripta gasi recording, pokušava SaveMap (internal), zatim eksport occupancy.
4. Export occupancy prioritet:
	- nav2 SaveMap servis (ako tip = nav2_msgs/srv/SaveMap)
	- nav2 `map_saver_cli` (ako postoji /map)
	- fallback Python exporter (direktno /map, generira PGM + YAML) ako prethodno zakaže.
5. Replay (opcionalno, default OFF) – omogućuje reproducibilno čišćenje grafa, sada se izbjegava radi jednostavnosti.

Robusnost uvedena:
- Timeouts (timeout alat) za svaki servisni poziv.
- Reentrancy lock sprječava višestruke cleanup sekvence.
- Uniqueness bag direktorija (suffix) – izbjegava prepisivanje.
- Detekcija tipa SaveMap servisa.
- Fallback exporter kad nema .yaml/.pgm.
- Symlink `maps/latest` na zadnju sesiju.

Otvorene točke / moguće poboljšanje:
- FORCE_NEW_SLAM opcija (restart instance radi param inject-a) – predloženo, nije implementirano.
- Param datoteka za slam_toolbox (umjesto implicitnih defaulta).
- Stabilnost heuristika (čekanje konvergencije umjesto fiksnog TIME_WAIT u replay modu).

---
## 7. Baza podataka i persistencija

Kontejner: `db_cont` (PostgreSQL). Inicijalizacija: `init-db.sql` definira shemu `robot_data` i tablicu `maps` (kolone: id, name, description, map_data (bytea), resolution, origin_x/y, width, height, metadata JSONB). 

Insert logika (inline Python u `run_mapping.sh`):
1. Čita YAML + PGM (ako postoji) i parsira dimenzije.
2. Računa sha256 hash YAML-a (sprema u metadata -> yaml_sha256) da izbjegne dupliciranje.
3. Sprema PGM binarno (ili YAML bytes fallback) u `map_data`.
4. Upisuje resolution, origin_x, origin_y (YAML origin). width / height iz PGM headera.

Mogućnosti proširenja:
- Dodati indeks na `(metadata->>'yaml_sha256')` za brže pretraživanje.
- Čuvati i `.mcap` / `.db3` reference (trenutno se čuvaju samo u filesystemu).
- Dodati map_version i tagove (npr. indoor/outdoor, test/prod).

Backup strategija (još neformalna): snapshot volumena baze ili `pg_dump` (nije skriptirano ovdje – preporuka dodati u CI cron / GitHub Actions schedule).

---
## 8. Skripte za deployment i build

U korijenu i `stack/`:
- `deploy_robot_system.sh` / `deploy.sh`: pokretanje compose stacka.
- `rollback.sh`: vraćanje prethodne verzije (detalji su u stack README-u – pregledati za formalizaciju).
- `build/` Python skripte (db_build.py, slam_build.py …) – služe za izdvojeno buildanje specifičnih containera (pseudonametnuta automatizacija – može se refaktorisati u Makefile ili GitHub Actions workflow).
- GitHub Actions: `.github/workflows/docker-build.yml` – CI izrada slike (provjeriti radi li tagging prema .env varijablama).

---
## 9. Tok podataka (end-to-end scenariji)

Scenarij A: Mapiranje prostorije
1. Pokretanje stacka.
2. `slam_cont` aktivan (slam_manager drži slam_toolbox running).
3. Operator: `docker exec -it slam_cont bash /app/run_mapping.sh --bag-prefix hala1`.
4. Robot se vozi; senzori publishaju /scan, /tf, /odom.
5. CTRL+C -> skripta: stop record → SaveMap (internal) → occupancy export → fallback ako treba → DB insert → symlink update.
6. Operater preuzima `maps/latest/final/` za nav2 ili daljnju analizu.

Scenarij B: Ponovno korištenje mape (lokalizacija)
1. (Planirano) Pokretanje slam_toolbox u localization modu (launch param) s prethodno generiranom mapom.
2. Navigacijski modul koristi mapu za path planning.

Scenarij C: Vanjski klijent (UI) spaja se preko rosbridge:
1. rosbridge_cont izlaže WebSocket (default port 9090).
2. Klijent (Foxglove / custom dashboard) subscriba na /tf, /scan, /odom, /map.

---
## 10. Konfiguracija i parametri

Ključne env varijable (compose ili run-time):
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`
- `USE_NAV2_EXPORT` (auto|always|never)
- `USE_REPLAY` (0/1)
- `STORAGE_BACKEND` (sqlite3|mcap)
- `MAP_ROOT` (default /app/maps ili bind mount /srv/maps)
- `WAIT_MAP_TOPIC` (default /map)

ROS param patching (ad hoc): publish_map se pokušava postaviti kroz `ros2 param set` nakon starta nove slam_toolbox instance.

Preporuka: izdvojiti slam_toolbox param YAML datoteku (npr. `config/slam_toolbox_params.yaml`) i loadati preko launch-a za determinističnost.

---
## 11. Sigurnost, robustnost i oporavak

Mjere uvedene:
- `set -euo pipefail` u skriptama + selektivno isključivanje `-u` pri sourceanju ROS env-a radi AMENT_TRACE_SETUP_FILES edge case-a.
- Timeout-i servisnih poziva.
- Reentrancy lock u cleanup-u sprječava višestruke overlappirane SaveMap pozive.
- Fallback export ako nav2 map_saver zakaže.
- Detekcija tipa SaveMap usluge runtime (smanjuje ručne promjene).

Potencijalna poboljšanja:
- Health check za /scan rate (ako premalo poruka, abort mapiranje).
- Integracija watchdog procesa (supervisor) koji restarta slam_toolbox ako ne objavljuje /tf.
- Verzijski tagging mapa (npr. semver + kontekst: hala1.v1, hala1.v2).

---
## 12. Debugging i troubleshooting

Uobičajeni problemi:
| Problem | Uzrok | Rješenje |
|---------|-------|----------|
| Nema .yaml/.pgm | /map se ne objavljuje | Provjeri publish_map param, node list, nav2 map_server instaliran |
| SaveMap timeout | Preopterećenje CPU / servis nedostupan | Povećaj MAX_SAVEMAP_SECONDS, provjeri `ros2 service list` |
| Bag prazan | Recorder startan prerano ili nema topika | Provjeri `ros2 topic echo /scan`, čekaj senzorske podatke |
| Duplicate map insert skip | Ista YAML hash | Promijeni mapu ili naziv (hash se bazira na sadržaju) |
| AMENT_TRACE_SETUP_FILES unbound | Bash `-u` + ROS setup | Dodana zaštita `: "${AMENT_TRACE_SETUP_FILES:=}"` |

Brzi debug koraci:
```
ros2 node list
ros2 topic list | grep map
ros2 service type /slam_toolbox/save_map
ros2 bag info /srv/maps/<session>/bag/record
```

---
## 13. Znane limitacije i preporučeni budući rad

Limitacije:
- /map ovisnost o publish_map parametru – treba formalizirati param YAML.
- Replay default isključen → finalna mapa = stanje u trenutku zaustavljanja (bez offline refina).
- Nema verzioniranja / potpunog metapodatkovnog modela (samo hash + YAML raw).
- Navigacijski dio nije potpuno integriran (još nema automatskog launch nav2 stacka).

Preporučeni rad:
1. Izdvojiti config fajlove (slam_toolbox, nav2, fusion) u `config/`.
2. FORCE_NEW_SLAM flag + param injection deterministički.
3. Dodati `ingest_map.py` umjesto inline DB koda (bolji test coverage, error handling).
4. CI: test skripta koja simulira lažni /map i provjerava generiranje fajlova.
5. Map metadata: polja `area_m2`, `created_at`, `source_bag`, `storage_backend`.
6. Export API (REST) za dohvat zadnje mape iz DB (mali FastAPI servis). 

---
## 14. Kratki TL;DR za operativno korištenje

1. Pokreni compose stack.
2. Uđi u slam_cont kontejner: `docker exec -it slam_cont bash`.
3. Start mapping: `bash /app/run_mapping.sh --bag-prefix test1`.
4. Vozi robota dok prostor nije pokriven.
5. CTRL+C jednom – pričekaj završetak.
6. Artefakti: `maps/latest/final/map.yaml|pgm` (ako fallback nav2 radi) + zapis u DB.
7. Provjera: `ros2 bag info maps/latest/bag/record`.

---
## 15. Konverzija dokumenta (PDF / Word)

Lokalno (ako imaš pandoc i latex minimalnu instalaciju):
```
pandoc ARCHITECTURE_OVERVIEW.md -o ARCHITECTURE_OVERVIEW.pdf
pandoc ARCHITECTURE_OVERVIEW.md -o ARCHITECTURE_OVERVIEW.docx
```
Ako nemaš pandoc u slici, na hostu (Windows PowerShell):
```
pandoc .\ARCHITECTURE_OVERVIEW.md -o ARCHITECTURE_OVERVIEW.pdf
```

Online alternativa: upload Markdown u npr. GitHub i koristi export (ili VS Code ekstenzija “Markdown PDF”).

---
## 16. Brzi pojmovnik
| Pojam | Objašnjenje |
|-------|-------------|
| SLAM | Simultaneous Localization and Mapping |
| Occupancy mapa | Raster (PGM + YAML) slobodnih / zauzetih ćelija |
| Bag | Snimljeni ROS 2 podaci (sqlite3 .db3 ili mcap) |
| SaveMap servis | Servis za spremanje mape (nav2 ili slam_toolbox varijanta) |
| Fallback exporter | Python rutina koja generira PGM/YAML iz prvog OccupancyGrid-a |
| RMW | ROS Middleware implementacija (CycloneDDS) |

---
## 17. Kontakt / održavanje
Trenutno nema formalnog ownership metadata; preporuka dodati MAINTAINERS.md s ulogama (npr. “SLAM”, “DB”, “CI”).

*Kraj dokumenta.*

---
## 18. Web UI (Robot Web UI)

Dodana je integrirana web aplikacija (React + Vite) pod `webui_cont/` koja se builda u zasebnu Docker sliku za vizualizaciju podataka (teme, connection parametri) i osnovno upravljanje. Slika se pokreće kroz `stack/docker-compose.yaml` servis `webui` (port 8080:80). 

### Komunikacijski tok
Browser -> WebSocket (`VITE_ROSBRIDGE_URL`) -> rosbridge (port 9090 na hostu) -> ROS 2 graf.

`VITE_ROSBRIDGE_URL` se injektira kao env var (compose) i može pokazivati na lokalni host ili Tailscale IP: `ws://tailscale_ip:9090`. Fallback ako nije postavljeno: `ws://<browser-hostname>:9090`.

### Build
```
cd diplomski_rad/webui_cont
docker build -t robot-web-ui:local .
```

Za razvoj bez containera:
```
npm ci
npm run dev
```

### Širenje funkcionalnosti
Minimalni set komponenti migriran (EntrySection, MainControlView, konekcijski hook). Dodatne vizualizacije (point cloud, TF, gamepad layouti) mogu se naknadno prenijeti iz originalnog izvora prije brisanja starog direktorija.

### Sigurnost i mreža
Servis `webui` ne koristi `network_mode: host` jer web klijent direktno komunicira s rosbridge na hostu. Za Tailscale pristup dovoljno je izložiti port 8080 na hostu i koristiti Tailscale IP u URL-u.

---
