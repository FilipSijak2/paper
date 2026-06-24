# Trenutna shema ozicenja (`rpi_direct`)

Ovaj dokument opisuje **trenutnu aktivnu** shemu ozicenja robota. Starije verzije dokumentacije spominjale su TCA9548A I2C multiplexor i AS5600 enkodere, ali to vise nije aktivni dio implementacije.

## Aktivna arhitektura

Trenutno aktivna arhitektura je:

- `Raspberry Pi 5 -> GPIO -> DRV8833 -> lijevi i desni motor`
- motori imaju vanjsko napajanje
- `SLP` / `nSLEEP` pin na DRV8833 mora biti `HIGH`
- svi GND pinovi moraju biti zajednicki
- wheel enkoderi se **ne koriste** u aktualnoj konfiguraciji
- TCA9548A I2C multiplexor se **ne koristi** u aktualnoj konfiguraciji
- odometrija/navigacija oslanja se na LiDAR/SLAM/AMCL/Nav2 i postojece ROS izvore poze, a ne na wheel enkodere

## Motor driver

Aktivna implementacija koristi DRV8833 u `rpi_direct` nacinu rada. Raspberry Pi upravlja motorima direktno preko GPIO pinova i `libgpiod` sucelja.

Primjer konfiguracije:

```env
BRIDGE_MODE=rpi_direct
GPIOCHIP=/dev/gpiochip4
DRIVER=drv8833
ENCODERS_ENABLED=0
CMD_VEL_TOPIC=/cmd_vel
```

## Napajanje

Za pouzdan rad bitno je:

- Raspberry Pi 5 napajati stabilnim USB-C napajanjem ili kvalitetnim powerbankom koji ne prekida izlaz
- motore napajati odvojeno od Raspberry Pi-ja
- obavezno povezati zajednicki GND izmedju Raspberry Pi-ja, DRV8833 i motornog napajanja
- izbjegavati gasenje robota cupanjem napajanja dok Linux radi; prije toga koristiti `sudo shutdown -h now`

## Napomena o staroj dokumentaciji

Ako se u starijim dokumentima ili kodu jos spominju:

- `TCA9548A`
- `AS5600`
- `left_encoder`
- `right_encoder`
- `multiplexer`
- `ENCODERS_ENABLED=1`

te reference treba tretirati kao **legacy/eksperimentalne**. One vise ne opisuju aktualni hardverski setup robota.
