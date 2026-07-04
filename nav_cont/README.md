# nav_cont

Navigacijski kontejner (`ROS 2 Humble + Nav2`) za autonomno kretanje robota po mapi uz:

- prihvat goalova iz UI-a (Foxglove/RViz)
- planiranje i pracenje putanje
- `cmd_vel` mux (auto/manual)
- signalizaciju blokade puta ("anomaly on path")
- fuziju prepreka iz LIDAR-a i RealSense point clouda u costmap

## Trenutne funkcionalnosti

1. Nav2 bringup

- Starta `/app/robot_nav_launch.py`, koji koristi Nav2 `bringup_launch.py`
  za map_server + AMCL + navigation.
- Ucitava mapu preko `MAP_FILE` (ili automatski trazi mapu preko `MAP_SESSION`, `active`, `latest`).
- Ako mapa ne postoji, generira privremenu placeholder mapu da stack moze dignuti servise.

1. Goal forwarding (Foxglove -> Nav2 action)

- `goal_forwarder.py` subscriba na `GOAL_TOPIC` (default: `/move_base_simple/goal`).
- Goal transformira u `map` frame (ako je moguce) i salje na `navigate_to_pose` action.
- Ako stigne novi goal, moze otkazati prethodni aktivni goal (`cancel_previous_goal`).

1. Replaniranje i izbjegavanje prepreka

- Nav2 planira prema costmapu i dinamicki replana kad se okolina promijeni.
- Prepreke ulaze iz:
- `/scan` (LaserScan)
- `/camera/realsense/depth/color/points` (PointCloud2)
- `/ai_kit/obstacles` (PointCloud2, za buduce semanticke prepreke)
- Ako postoji prolaz, robot pokusava obici prepreku i nastaviti prema goalu.

1. Signalizacija anomalije / blokade

- `goal_forwarder.py` publisha:
- `/navigation/anomaly_on_path` (`std_msgs/Bool`)
- `/navigation/anomaly_detail` (`std_msgs/String`)
- Anomalija se postavlja npr. kod:
- nedostupnog action servera
- neuspjele transformacije goala
- `goal_aborted`
- zaglavljenosti (stall + recovery)

1. `cmd_vel` multiplexing (auto/manual)

- Nav2 izlaz ide na `/cmd_vel_auto`.
- Joystick/teleop ide na `/cmd_vel_joy`.
- `cmd_vel_mux.py` publisha finalni `/cmd_vel`.
- Mod se mijenja servisom:
- `/set_manual_mode` (`std_srvs/SetBool`)
- `true` = manual (uzima `/cmd_vel_joy`)
- `false` = auto (uzima `/cmd_vel_auto`)
- Uveden fail-safe timeout:
- `auto_timeout_s` i `manual_timeout_s`
- ako komande zastare, mux salje stop (`Twist()`).

1. Joystick teleop (opcionalno)

- `joy_node` + `teleop_twist_joy` se pokrecu ako postoji joystick uredaj (`/dev/input/js0`).
- Konfiguracija tipki/osi je u `teleop_f710.yaml`.

## Arhitektura toka podataka

1. Foxglove/RViz publisha `PoseStamped` na `/move_base_simple/goal`.
1. `goal_forwarder.py` goal pretvara u `map` frame i salje na `navigate_to_pose`.
1. Nav2 planira putanju i publisha `cmd_vel` (remapan na `/cmd_vel_auto`).
1. `cmd_vel_mux.py` bira izmedu `/cmd_vel_auto` i `/cmd_vel_joy`.
1. Finalni `/cmd_vel` ide prema bridge/motor kontroleru.

## Kljucne datoteke

- `start_nav.sh`: startup orchestration (Nav2 + goal forwarder + mux + joystick)
- `nav2_params.yaml`: planner/controller/costmap parametri
- `goal_forwarder.py`: topic -> NavigateToPose action + anomaly signalizacija
- `cmd_vel_mux.py`: auto/manual arbitraza + fail-safe timeouti
- `set_initial_pose.py`: helper za inicijalnu pozu AMCL-a
- `move.py`: mali test publisher (primarno za manual/mux test)

## Environment varijable (najbitnije)

- `MAP_ROOT` (default `/srv/maps`)
- `MAP_SESSION` (opcionalno)
- `MAP_FILE` (eksplicitna putanja do `map.yaml`)
- `NAV2_PARAMS_FILE` (default `/app/nav2_params.yaml`)
- `GOAL_TOPIC` (default `/move_base_simple/goal`)
- `FORCE_MAP_WAIT` (`0`/`1`)
- `ENABLE_CMD_VEL_MUX` (`0`/`1`)
- `ENABLE_JOYSTICK` (`0`/`1`)
- `CMD_VEL_AUTO` (default `/cmd_vel_auto`)
- `CMD_VEL_JOY` (default `/cmd_vel_joy`)
- `CMD_VEL_OUT` (default `/cmd_vel`)
- `MANUAL_DEFAULT` (`true`/`false`)
- `MANUAL_TIMEOUT_S` (default `0.5`)
- `AUTO_TIMEOUT_S` (default `0.7`)
- `ENABLE_ANOMALY_INSPECTION` (`0`/`1`, default `0`)
- `INSPECTION_ONLY_WHEN_IDLE` (default `true`)
- `INSPECTION_DEFAULT_STANDOFF_M` (default `0.70`)
- `INSPECTION_NAVIGATION_TIMEOUT_S` (default `45.0`)
- `INSPECTION_SETTLE_TIME_S` (default `1.0`)

## Pokretanje

`nav_cont` image ulazna tocka je:

```bash
/app/start_nav.sh
```

Script pokrece:

- Nav2 bringup
- `goal_forwarder.py`
- `cmd_vel_mux.py` (ako je ukljucen)
- joystick nodeove (ako su ukljuceni i uredaj postoji)

## Operativni check-list (rucno testiranje)

1. Provjeri da Nav2 servisi/radni nodeovi postoje:

```bash
ros2 node list
ros2 action list | grep navigate_to_pose
```

1. Postavi inicijalnu pozu (AMCL):

```bash
python3 /app/set_initial_pose.py 0.0 0.0 0
```

1. Posalji goal iz Foxglove-a na `/move_base_simple/goal`.

1. Prati stanje:

```bash
ros2 topic echo /navigation/anomaly_on_path
ros2 topic echo /navigation/anomaly_detail
ros2 topic hz /cmd_vel
```

1. Manual override test:

```bash
ros2 service call /set_manual_mode std_srvs/srv/SetBool "{data: true}"
ros2 service call /set_manual_mode std_srvs/srv/SetBool "{data: false}"
```

## Automatski inspection boce

`anomaly_inspection_coordinator.py` prima potvrdeni zahtjev s Jetsona, racuna
standoff goal u `map` frameu i koristi isti `NavigateToPose` action kao rucni
goalovi. Fizicka lokacija boce nikada se ne salje kao goal.

Funkcija je zadano iskljucena. U aktivnom
`stack/config/containers/nav_cont.env` ukljucuje se ovako:

```env
ENABLE_ANOMALY_INSPECTION=1
INSPECTION_ONLY_WHEN_IDLE=true
INSPECTION_DEFAULT_STANDOFF_M=0.70
INSPECTION_NAVIGATION_TIMEOUT_S=45.0
INSPECTION_SETTLE_TIME_S=1.0
```

Sigurnosna pravila:

- novi zahtjev prihvaca se samo kada nema drugog Nav2 goala
- manual mode blokira zahtjev
- prelazak u manual mode otkazuje aktivni inspection
- prihvacaju se samo depth/laser zahtjevi unutar praga nesigurnosti
- navigation i capture imaju neovisne timeoute
- collision monitor, costmap i `cmd_vel_safety_filter` ostaju aktivni

Stanje se moze pratiti:

```bash
ros2 topic echo /anomaly/inspection/request
ros2 topic echo /anomaly/inspection/status
ros2 topic echo /anomaly/inspection/result
```

## Trenutna ogranicenja (vazno)

1. Klasifikacija anomalije kamerom NIJE u `nav_cont`.

- `nav_cont` trenutno samo signalizira da je put blokiran/stuck.
- AI dio (detekcija klase, spremanje slike, logiranje poznata/nepoznata anomalija) ide kroz `ai_kit_cont`.

1. Footprint je trenutno definiran kao poligon u `nav2_params.yaml`.

- Trenutna vrijednost je asimetricna: okvirno `27 cm x 33 cm`, uz `1 cm`
  costmap paddinga sa svake strane.
- Za pouzdano zaobilazenje treba potvrditi stvarne dimenzije robota i
  sigurnosni margin kroz test voznju.

1. Placeholder mapa je fallback za podizanje stacka.

- Za stvarnu navigaciju treba koristiti stvarnu mapu (`MAP_FILE` ili `MAP_SESSION`).

## Profil za uski hodnik

Aktivni profil je namjerno blazi, ali ne mijenja fizicki footprint ni neposredne
LiDAR stop-udaljenosti:

- DWB koristi `vtheta_samples: 15`, pa medu kandidatima postoji i potpuno ravna
  putanja bez prisilnog skretanja prema jednom zidu.
- Lokalni inflation je `0.25 m / 6.0`, a globalni `0.33 m / 5.0`; trosak zida
  brze opada izvan footprinta, ali zauzete i inscribed celije ostaju prepreke.
- Collision Monitor predvida `0.8 s` unaprijed.
- Dodatni safety filter trazi 7 susjednih LiDAR tocaka i provjerava mapu
  `0.20 m` unaprijed u pojasu od `+/-0.08 m`.
- Neposredne stop-udaljenosti ostaju `0.24 m` naprijed i `0.20 m` straga.

Nakon izmjene runtime konfiguracije dovoljno je ponovno stvoriti `nav_cont`:

```bash
docker compose up -d --force-recreate nav_cont
```

Za provjeru uzroka zaustavljanja:

```bash
ros2 topic echo /cmd_vel_safety_status
ros2 topic echo /collision_monitor_state
ros2 topic echo /local_costmap/costmap
```

## Sljedeci korak (preporuka)

Kad se potvrde stvarne dimenzije robota, treba:

1. po potrebi prilagoditi `footprint` poligon u `nav2_params.yaml`
1. prilagoditi inflation radius/tolerance prema stvarnom clearanceu
1. napraviti kratki obstacle-course test i fino podesiti pragove
