# Vodič za fizičko ožičenje

Ovaj dokument služi kao praktična checklista za spajanje i provjeru fizičkog ožičenja robota. Detaljna shema i tablica GPIO pinova nalaze se u [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md).

## Aktualni fizički sklop

```text
Raspberry Pi 5 -> GPIO -> DRV8833 -> lijevi i desni motor
```

Sustav koristi:

- Raspberry Pi 5 kao računalo za motorni bridge
- DRV8833 kao driver lijevog i desnog motora
- vanjsko napajanje za motore
- zajedničku masu između Raspberry Pi računala, DRV8833 modula i motornog napajanja

## Korišteni upravljački signali

Aktualni upravljački signali prema DRV8833 modulu su:

```text
GPIO17 -> SLP / nSLEEP
GPIO24 -> BIN2
GPIO19 -> BIN1
GPIO23 -> AIN2
GPIO18 -> AIN1
GND    -> zajednička masa
```

Fizički pinovi i uloge pojedinih signala navedeni su u [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md#korišteni-pinovi).

## Checklista prije spajanja

1. Isključi USB-C napajanje Raspberry Pi računala.
2. Isključi vanjsko napajanje motora.
3. Provjeri orijentaciju DRV8833 modula i oznake pinova.
4. Provjeri kontinuitet GND vodova multimetrom.
5. Provjeri da motorno napajanje ide samo na `VM` / `VIN+` i `GND` dio DRV8833 modula.
6. Provjeri da GPIO pinovi Raspberry Pi računala idu samo na logičke ulaze DRV8833 modula.

## Redoslijed spajanja

1. Spoji GND Raspberry Pi računala na GND DRV8833 modula.
2. Spoji GND vanjskog motornog napajanja na zajednički GND.
3. Spoji `VM` / `VIN+` DRV8833 modula na pozitivni pol vanjskog motornog napajanja.
4. Spoji `AOUT1` / `AOUT2` na lijevi motor.
5. Spoji `BOUT1` / `BOUT2` na desni motor.
6. Spoji GPIO signale s Raspberry Pi računala na DRV8833 ulaze prema tablici pinova.
7. Pokreni Raspberry Pi i provjeri motorni bridge bez opterećenja robota.
8. Pokreni kratki test lijevog i desnog motora pri maloj brzini.

## Provjera nakon spajanja

```text
zajednička masa: Raspberry Pi GND <-> DRV8833 GND <-> motor supply GND
motorno napajanje: supply + -> DRV8833 VM/VIN+
lijevi motor: DRV8833 AOUT1/AOUT2
right motor: DRV8833 BOUT1/BOUT2
SLP/nSLEEP: GPIO17
```

Preporučena softverska provjera:

```bash
cd ~/robot-stack
cat config/containers/cmd_vel_safety_filter.env 2>/dev/null || true
```

Aktualna konfiguracija bridgea:

```env
BRIDGE_MODE=rpi_direct
GPIOCHIP=/dev/gpiochip4
DRIVER=drv8833
ENCODERS_ENABLED=0
CMD_VEL_TOPIC=/cmd_vel
```

## Sigurno gašenje

Prije prekida napajanja pokreni:

```bash
sudo shutdown -h now
```

Nakon što se sustav zaustavi, isključi powerbank ili napajanje. Ovaj redoslijed čuva filesystem, SSD i boot particiju.

## Povezani dokumenti

- [CURRENT_WIRING_DIAGRAM.md](./CURRENT_WIRING_DIAGRAM.md) — fizička shema i pinovi
- [HARDWARE_COMPONENTS.md](./HARDWARE_COMPONENTS.md) — hardverske komponente
- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) — cjelokupna arhitektura sustava
