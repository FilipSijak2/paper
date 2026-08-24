# Robot Database Container

This image provides the PostgreSQL/PostGIS database used for maps, images, waypoints and robot sessions.

## Runtime configuration

`robot-stack/docker-compose.yaml` supplies the active database settings:

- `POSTGRES_DB` from `DB_NAME`
- `POSTGRES_USER` from `DB_USER`
- `POSTGRES_PASSWORD` from `DB_PASS`
- `PGDATA` from `robot-stack/config/containers/database_cont.env`

No password is embedded in the image or application source. Define `DB_PASS` only in the ignored `robot-stack/.env` file or an equivalent secret store.

The Python API accepts the same `DB_*` variables and the explicit `ROBOT_DB_HOST`, `ROBOT_DB_PORT`, `ROBOT_DB_NAME`, `ROBOT_DB_USER`, `ROBOT_DB_PASSWORD` and `ROBOT_DB_CONNECT_TIMEOUT` aliases.

## Schema

`init-db.sql` enables PostGIS and creates:

- `robot_data.maps`
- `robot_data.camera_images`
- `robot_data.waypoints`
- `robot_data.robot_sessions`
