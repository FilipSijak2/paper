# Trenutna shema ozicenja (`rpi_direct`)

Ovaj dokument opisuje **trenutnu aktivnu** shemu ozicenja robota. Starije verzije dokumentacije spominjale su TCA9548A I2C multiplexor i AS5600 enkodere, ali to vise nije aktivni dio implementacije.

## Aktivna arhitektura

Trenutno aktivna arhitektura je:

- `Raspberry Pi 5 -> GPIO -> DRV8833 -> lijevi i desni motor`
- motori imaju vanjsko napajanje
- `SLP` / `nSLEEP` pin na DRV8833 mora biti `HIGH`
- svi GND pinovi moraju biti zajednicki
- wheel enkoderi