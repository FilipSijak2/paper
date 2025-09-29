# Robot Database Container

Ovaj kontejner sadrži PostgreSQL bazu podataka s PostGIS ekstenzijom za snimanje mapa robota i slika kamere.

## Struktura baze podataka

Baza podataka `robot_data` sadrži sljedeće tabele:

### 1. `robot_data.maps`
- Sprema OGM (Occupancy Grid Map) podatke
- Metapodaci o mapi (rezolucija, početak koordinata, dimenzije)
- UUID identifikatori

### 2. `robot_data.camera_images`  
- Sprema slike kamere s pozicijskim podacima
- GPS koordinate i pozicija na mapi
- Podrška za JPEG, PNG i druge formate

### 3. `robot_data.waypoints`
- Sprema waypoint-ove i putanje
- GPS i map koordinate
- Tipovi: manual, auto_generated, landmark

### 4. `robot_data.robot_sessions`
- Sprema informacije o robot sesijama/putovanjima
- Početak/kraj sesije, ukupna udaljenost
- Metapodaci o misiji

## Korištenje

### Build kontejner
```python
python ../build/db_build.py
```

### Pokretanje kontejnera
```bash
docker run -d --name robot_db -p 5432:5432 db_cont:v0.0.1.rc3-dev
```

### Python API
```python
from robot_db_api import get_database

db = get_database()

# Snimanje mape
map_id = db.save_map(
    name="Test Mapa",
    map_data=map_bytes,
    resolution=0.05,
    origin_x=-10.0,
    origin_y=-10.0,
    width=400,
    height=400
)

# Snimanje slike
image_id = db.save_camera_image(
    map_id=map_id,
    image_data=jpeg_bytes,
    image_format="JPEG",
    width=640,
    height=480,
    timestamp=datetime.now(),
    robot_x=2.5,
    robot_y=3.1
)
```

## Konfiguracija

### Environment varijable
- `POSTGRES_DB=robot_data` - Ime baze podataka
- `POSTGRES_USER=robot_user` - Admin korisnik
- `POSTGRES_PASSWORD=robot_pass` - Admin lozinka

### App korisnik
- Korisničko ime: `app_user`
- Lozinka: `app_pass`
- Dozvole: SELECT, INSERT, UPDATE, DELETE na svim tabelama

## PostGIS ekstenzija

Baza koristi PostGIS za prostorne podatke:
- GPS koordinate su stored kao `GEOMETRY(POINT, 4326)`
- Prostorni indeksi za brže pretraživanje
- Podrška za spatial upite

## Performance

- Indeksi na često korištenim poljima
- Trigger za automatsko ažuriranje `updated_at`
- Optimizovano za velike količine slika i mapa

## Sigurnost

- Odvojeni korisnici za admin i aplikaciju
- Ograničene dozvole za app_user
- PostgreSQL sigurnosne postavke