# AS5600 test za Arduino UNO R4 WiFi

Ovaj sketch sluzi za brzu provjeru radi li `AS5600` preko `I2C` veze na
`Arduino Uno R4 WiFi`.

## Spojevi

Koristi oznacene `SDA` i `SCL` pinove na `UNO R4 WiFi`:

- `AS5600 SDA -> UNO R4 SDA`
- `AS5600 SCL -> UNO R4 SCL`
- `AS5600 GND -> UNO R4 GND`
- `AS5600 VCC -> UNO R4 5V` ako breakout podrzava `5V`
- `AS5600 VCC -> UNO R4 3.3V` ako je tvoj modul samo za `3.3V`

Opcionalni pinovi:

- `DIR` nije potreban za ovaj test
- `OUT` nije potreban za ovaj test
- `PGO` nije potreban za ovaj test

## Kako testirati

1. Otvori `as5600_uno_r4_wifi_test.ino` u Arduino IDE-u.
2. Odaberi plocu `Arduino UNO R4 WiFi`.
3. Uploadaj sketch.
4. Otvori `Serial Monitor` na `115200 baud`.
5. Okreci magnet iznad senzora.

## Sto bi trebao vidjeti

- Ako je sve dobro spojeno, sketch javlja da je senzor pronaden na `0x36`.
- Ako okreces magnet, `raw` i `kut_deg` se trebaju mijenjati.
- `md=1` znaci da je magnet detektiran.
- `ml=1` znaci da je magnetsko polje preslabo.
- `mh=1` znaci da je magnetsko polje prejako.
- `status=OK` znaci da je magnet u dobrom rasponu.
- `MAGNET_NIJE_DETEKTIRAN` znaci da magnet nije iznad senzora ili je predaleko.
- `MAGNET_PREDALEKO` znaci da je magnetsko polje preslabo.
- `MAGNET_PREBLIZU` znaci da je magnetsko polje prejako.

## LED indikacija

- brzi blink: nema komunikacije sa senzorom
- spori blink: senzor odgovara, ali magnet nije u dobrom rasponu
- stalno upaljeno: senzor radi i magnet je u dobrom rasponu

## Napomena

Najcesci problem nije kod nego mehanika:

- magnet mora biti diametralno magnetiziran
- treba biti centriran iznad senzora
- razmak izmedu magneta i senzora mora biti mali i stabilan
