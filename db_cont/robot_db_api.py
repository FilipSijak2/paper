"""
Python API for working with the robot database.

The high-level CRUD interface stays the same, but connection settings can now
be resolved from explicit arguments or environment variables.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_DB_CONFIG = {
    "host": "db_cont",
    "port": 5432,
    "database": "robot_data",
    "user": "robot_user",
    "password": None,
    "connect_timeout": 5,
}


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return None


def _coerce_int(value, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def resolve_connection_params(
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    username: str | None = None,
    password: str | None = None,
    connect_timeout: int | None = None,
) -> Dict[str, Any]:
    """Resolve DB connection settings from args first, then environment."""
    return {
        "host": host or _env_first("ROBOT_DB_HOST", "DB_HOST") or DEFAULT_DB_CONFIG["host"],
        "port": _coerce_int(
            port if port is not None else _env_first("ROBOT_DB_PORT", "DB_PORT"),
            DEFAULT_DB_CONFIG["port"],
        ),
        "database": (
            database
            or _env_first("ROBOT_DB_NAME", "DB_NAME")
            or DEFAULT_DB_CONFIG["database"]
        ),
        "user": username or _env_first("ROBOT_DB_USER", "DB_USER") or DEFAULT_DB_CONFIG["user"],
        "password": password or _env_first("ROBOT_DB_PASSWORD", "DB_PASSWORD", "DB_PASS"),
        "connect_timeout": _coerce_int(
            connect_timeout
            if connect_timeout is not None
            else _env_first("ROBOT_DB_CONNECT_TIMEOUT", "DB_CONNECT_TIMEOUT"),
            DEFAULT_DB_CONFIG["connect_timeout"],
        ),
    }


class RobotDatabase:
    """Convenience wrapper around the robot PostgreSQL/PostGIS schema."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        username: str | None = None,
        password: str | None = None,
        connect_timeout: int | None = None,
    ):
        self.connection_params = resolve_connection_params(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            connect_timeout=connect_timeout,
        )
        self.connection = None
        self.connect()

    def connect(self):
        """Open the database connection."""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info(
                "Connected to database %s on %s:%s",
                self.connection_params["database"],
                self.connection_params["host"],
                self.connection_params["port"],
            )
        except Exception as exc:
            logger.error(f"Database connection failed: {exc}")
            raise

    def disconnect(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute a SQL query and optionally return fetched rows."""
        try:
            with self.connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cursor:
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                return cursor.rowcount
        except Exception as exc:
            logger.error(f"Query execution failed: {exc}")
            raise

    def save_map(
        self,
        name: str,
        map_data: bytes,
        resolution: float,
        origin_x: float,
        origin_y: float,
        width: int,
        height: int,
        description: str = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Store a map blob together with its metadata."""
        map_id = str(uuid.uuid4())

        query = """
        INSERT INTO robot_data.maps
        (id, name, description, map_data, resolution, origin_x, origin_y, width, height, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        params = (
            map_id,
            name,
            description,
            map_data,
            resolution,
            origin_x,
            origin_y,
            width,
            height,
            json.dumps(metadata) if metadata else None,
        )

        self._execute_query(query, params)
        logger.info("Map '%s' saved with id %s", name, map_id)
        return map_id

    def get_map(self, map_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a map, including the stored binary data."""
        query = """
        SELECT id, name, description, map_data, resolution, origin_x, origin_y,
               width, height, metadata, created_at, updated_at
        FROM robot_data.maps
        WHERE id = %s
        """

        result = self._execute_query(query, (map_id,), fetch=True)
        if result:
            map_data = dict(result[0])
            if map_data["metadata"]:
                map_data["metadata"] = json.loads(map_data["metadata"])
            return map_data
        return None

    def list_maps(self) -> List[Dict[str, Any]]:
        """List maps without returning the binary payload."""
        query = """
        SELECT id, name, description, resolution, origin_x, origin_y,
               width, height, metadata, created_at, updated_at
        FROM robot_data.maps
        ORDER BY created_at DESC
        """

        results = self._execute_query(query, fetch=True)
        maps = []
        for row in results:
            map_data = dict(row)
            if map_data["metadata"]:
                map_data["metadata"] = json.loads(map_data["metadata"])
            maps.append(map_data)
        return maps

    def save_camera_image(
        self,
        map_id: str,
        image_data: bytes,
        image_format: str,
        width: int,
        height: int,
        timestamp: datetime,
        robot_x: float = None,
        robot_y: float = None,
        robot_theta: float = None,
        gps_lat: float = None,
        gps_lon: float = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Store a camera image and its optional pose/GPS metadata."""
        image_id = str(uuid.uuid4())

        position_wkt = None
        if gps_lat is not None and gps_lon is not None:
            position_wkt = f"POINT({gps_lon} {gps_lat})"

        query = """
        INSERT INTO robot_data.camera_images
        (id, map_id, image_data, image_format, position, robot_x, robot_y,
         robot_theta, width, height, timestamp, metadata)
        VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s, %s)
        """

        params = (
            image_id,
            map_id,
            image_data,
            image_format.upper(),
            position_wkt,
            robot_x,
            robot_y,
            robot_theta,
            width,
            height,
            timestamp,
            json.dumps(metadata) if metadata else None,
        )

        self._execute_query(query, params)
        logger.info("Camera image saved with id %s", image_id)
        return image_id

    def get_camera_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single stored camera image."""
        query = """
        SELECT id, map_id, image_data, image_format,
               ST_X(position) as gps_lon, ST_Y(position) as gps_lat,
               robot_x, robot_y, robot_theta, width, height,
               timestamp, metadata, created_at
        FROM robot_data.camera_images
        WHERE id = %s
        """

        result = self._execute_query(query, (image_id,), fetch=True)
        if result:
            image_data = dict(result[0])
            if image_data["metadata"]:
                image_data["metadata"] = json.loads(image_data["metadata"])
            return image_data
        return None

    def list_camera_images(
        self, map_id: str = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """List stored images without returning the binary payload."""
        if map_id:
            query = """
            SELECT id, map_id, image_format,
                   ST_X(position) as gps_lon, ST_Y(position) as gps_lat,
                   robot_x, robot_y, robot_theta, width, height,
                   timestamp, metadata, created_at
            FROM robot_data.camera_images
            WHERE map_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """
            params = (map_id, limit)
        else:
            query = """
            SELECT id, map_id, image_format,
                   ST_X(position) as gps_lon, ST_Y(position) as gps_lat,
                   robot_x, robot_y, robot_theta, width, height,
                   timestamp, metadata, created_at
            FROM robot_data.camera_images
            ORDER BY timestamp DESC
            LIMIT %s
            """
            params = (limit,)

        results = self._execute_query(query, params, fetch=True)
        images = []
        for row in results:
            image_data = dict(row)
            if image_data["metadata"]:
                image_data["metadata"] = json.loads(image_data["metadata"])
            images.append(image_data)
        return images

    def save_waypoint(
        self,
        map_id: str,
        map_x: float,
        map_y: float,
        name: str = None,
        gps_lat: float = None,
        gps_lon: float = None,
        waypoint_type: str = "manual",
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Store a waypoint for a given map."""
        waypoint_id = str(uuid.uuid4())

        position_wkt = None
        if gps_lat is not None and gps_lon is not None:
            position_wkt = f"POINT({gps_lon} {gps_lat})"

        query = """
        INSERT INTO robot_data.waypoints
        (id, map_id, name, position, map_x, map_y, waypoint_type, metadata)
        VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s)
        """

        params = (
            waypoint_id,
            map_id,
            name,
            position_wkt,
            map_x,
            map_y,
            waypoint_type,
            json.dumps(metadata) if metadata else None,
        )

        self._execute_query(query, params)
        logger.info("Waypoint '%s' saved with id %s", name, waypoint_id)
        return waypoint_id

    def list_waypoints(self, map_id: str) -> List[Dict[str, Any]]:
        """List waypoints for a given map."""
        query = """
        SELECT id, map_id, name,
               ST_X(position) as gps_lon, ST_Y(position) as gps_lat,
               map_x, map_y, waypoint_type, metadata, created_at
        FROM robot_data.waypoints
        WHERE map_id = %s
        ORDER BY created_at
        """

        results = self._execute_query(query, (map_id,), fetch=True)
        waypoints = []
        for row in results:
            waypoint_data = dict(row)
            if waypoint_data["metadata"]:
                waypoint_data["metadata"] = json.loads(waypoint_data["metadata"])
            waypoints.append(waypoint_data)
        return waypoints

    def start_session(
        self,
        map_id: str = None,
        session_name: str = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Start a robot session."""
        session_id = str(uuid.uuid4())

        query = """
        INSERT INTO robot_data.robot_sessions
        (id, map_id, session_name, start_time, metadata)
        VALUES (%s, %s, %s, %s, %s)
        """

        params = (
            session_id,
            map_id,
            session_name,
            datetime.now(),
            json.dumps(metadata) if metadata else None,
        )

        self._execute_query(query, params)
        logger.info("Session started with id %s", session_id)
        return session_id

    def end_session(self, session_id: str, total_distance: float = None):
        """Finish a robot session."""
        query = """
        UPDATE robot_data.robot_sessions
        SET end_time = %s, total_distance = %s
        WHERE id = %s
        """

        params = (datetime.now(), total_distance, session_id)
        self._execute_query(query, params)
        logger.info("Session %s finished", session_id)


def get_database(**kwargs) -> RobotDatabase:
    """Create a RobotDatabase instance using env-aware defaults."""
    return RobotDatabase(**kwargs)


if __name__ == "__main__":
    db = get_database()
    try:
        maps = db.list_maps()
        print(f"Maps in database: {len(maps)}")
    except Exception as exc:
        print(f"Database error: {exc}")
    finally:
        db.disconnect()
