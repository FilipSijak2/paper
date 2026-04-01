# Robot Database Container

This container provides the PostgreSQL/PostGIS database used for maps, camera
images, waypoints, and robot sessions.

## Schema overview

- `robot_data.maps`: stored occupancy maps plus metadata
- `robot_data.camera_images`: image blobs with optional pose and GPS data
- `robot_data.waypoints`: named map or GPS waypoints
- `robot_data.robot_sessions`: session lifecycle and summary data

## Runtime configuration

Container-side database variables:

- `POSTGRES_DB=robot_data`
- `POSTGRES_USER=robot_user`
- `POSTGRES_PASSWORD=robot_pass`

Python client variables supported by `robot_db_api.py`:

- `ROBOT_DB_HOST` or `DB_HOST`
- `ROBOT_DB_PORT` or `DB_PORT`
- `ROBOT_DB_NAME` or `DB_NAME`
- `ROBOT_DB_USER` or `DB_USER`
- `ROBOT_DB_PASSWORD` or `DB_PASSWORD` or `DB_PASS`
- `ROBOT_DB_CONNECT_TIMEOUT` or `DB_CONNECT_TIMEOUT`

## Example

```python
from db_cont.robot_db_api import get_database

db = get_database()
maps = db.list_maps()
print(len(maps))
```

## Notes

- PostGIS is enabled through `init-db.sql`.
- The app-facing defaults use the `app_user` credentials, not the admin user.
- Connection settings can now be overridden cleanly from other containers.
