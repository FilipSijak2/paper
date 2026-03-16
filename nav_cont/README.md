# nav_cont

Navigacijski kontejner (`ROS 2 Humble + Nav2`) za autonomno kretanje robota po mapi uz:
- prihvat goalova iz UI-a (Foxglove/RViz),
- planiranje i pracenje putanje,
- `cmd_vel` mux (auto/manual),
- signalizaciju blokade puta ("anomaly on path"),
- fuziju prepreka iz LIDAR-a i RealSense point clouda u costmap.

## Trenutne funkcionalnosti

1. Nav2 bringup
- Starta `navigation_launch.py` sa `nav2_params.yaml`.
- Ucitava mapu preko `MAP_FILE` (ili automatski trazi mapu preko `MAP_SESSION`, `active`, `latest`).
- Ako mapa ne postoji, generira privremenu placeholder mapu da stack moze dignuti servise.

2. Goal forwarding (Foxglove -> Nav2 action)
- `goal_forwarder.py` subscriba na `GOAL_TOPIC` (default: `/move_base_simple/goal`).
- Goal transformira u `map` frame (ako je moguce) i salje na `navigate_to_pose` action.
- Ako stigne novi goal, moze otkazati prethodni aktivni goal (`cancel_previous_goal`).

3. Replaniranje i izbjegavanje prepreka
- Nav2 planira prema costmapu i dinamicki replana kad se okolina promijeni.
- Prepreke ulaze iz:
- `/scan` (LaserScan),
- `/realsense/depth/color/points` (PointCloud2).
- Ako postoji prolaz, robot pokusava obici prepreku i nastaviti prema goalu.

4. Signalizacija anomalije / blokade
- `goal_forwarder.py` publisha:
- `/navigation/anomaly_on_path` (`std_msgs/Bool`)
- `/navigation/anomaly_detail` (`std_msgs/String`)
- Anomalija se postavlja npr. kod:
- nedostupnog action servera,
- neuspjele transformacije goala,
- `goal_aborted`,
- zaglavljenosti (stall + recovery).

5. `cmd_vel` multiplexing (auto/manual)
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

6. Joystick teleop (opcionalno)
- `joy_node` + `teleop_twist_joy` se pokrecu ako postoji joystick uredaj (`/dev/input/js0`).
- Konfiguracija tipki/osi je u `teleop_f710.yaml`.

## Arhitektura toka podataka

1. Foxglove/RViz publisha `PoseStamped` na `/move_base_simple/goal`.
2. `goal_forwarder.py` goal pretvara u `map` frame i salje na `navigate_to_pose`.
3. Nav2 planira putanju i publisha `cmd_vel` (remapan na `/cmd_vel_auto`).
4. `cmd_vel_mux.py` bira izmedu `/cmd_vel_auto` i `/cmd_vel_joy`.
5. Finalni `/cmd_vel` ide prema bridge/motor kontroleru.

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

## Pokretanje

`nav_cont` image ulazna tocka je:

```bash
/app/start_nav.sh
```

Script pokrece:
- Nav2 bringup,
- `goal_forwarder.py`,
- `cmd_vel_mux.py` (ako je ukljucen),
- joystick nodeove (ako su ukljuceni i uredaj postoji).

## Operativni check-list (rucno testiranje)

1. Provjeri da Nav2 servisi/radni nodeovi postoje:
```bash
ros2 node list
ros2 action list | grep navigate_to_pose
```

2. Postavi inicijalnu pozu (AMCL):
```bash
python3 /app/set_initial_pose.py 0.0 0.0 0
```

3. Posalji goal iz Foxglove-a na `/move_base_simple/goal`.

4. Prati stanje:
```bash
ros2 topic echo /navigation/anomaly_on_path
ros2 topic echo /navigation/anomaly_detail
ros2 topic hz /cmd_vel
```

5. Manual override test:
```bash
ros2 service call /set_manual_mode std_srvs/srv/SetBool "{data: true}"
ros2 service call /set_manual_mode std_srvs/srv/SetBool "{data: false}"
```

## Trenutna ogranicenja (vazno)

1. Klasifikacija anomalije kamerom NIJE u `nav_cont`.
- `nav_cont` trenutno samo signalizira da je put blokiran/stuck.
- AI dio (detekcija klase, spremanje slike, logiranje poznata/nepoznata anomalija) ide kroz `ai_kit_cont`.

2. Footprint je trenutno aproksimiran (`robot_radius: 0.22`).
- Za pouzdano zaobilazenje treba unijeti stvarne dimenzije robota i sigurnosni margin.

3. Placeholder mapa je fallback za podizanje stacka.
- Za stvarnu navigaciju treba koristiti stvarnu mapu (`MAP_FILE` ili `MAP_SESSION`).

## Sljedeci korak (preporuka)

Kad posaljes dimenzije robota, treba:
1. zamijeniti `robot_radius` tocnim `footprint` poligonom u `nav2_params.yaml`,
2. prilagoditi inflation radius/tolerance prema stvarnom clearanceu,
3. napraviti kratki obstacle-course test i fino podesiti pragove.
