"""
Python API za rad sa robotskom bazom podataka
Omogućuje jednostavno snimanje i čitanje mapa i slika kamere
"""

import psycopg2
import psycopg2.extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import io
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import uuid
import logging

# Konfiguracija logiranja
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RobotDatabase:
    """Klasa za rad sa robotskom bazom podataka"""
    
    def __init__(self, 
                 host: str = "db_cont", 
                 port: int = 5432,
                 database: str = "robot_data",
                 username: str = "app_user",
                 password: str = "app_pass"):
        """
        Inicijalizacija konekcije na bazu podataka
        
        Args:
            host: Hostname baze podataka
            port: Port baze podataka  
            database: Ime baze podataka
            username: Korisničko ime
            password: Lozinka
        """
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': username,
            'password': password
        }
        self.connection = None
        self.connect()
    
    def connect(self):
        """Uspostavljanje konekcije sa bazom podataka"""
        try:
            self.connection = psycopg2.connect(**self.connection_params)
            self.connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info("Uspješno povezano sa bazom podataka")
        except Exception as e:
            logger.error(f"Greška pri povezivanju sa bazom: {e}")
            raise
    
    def disconnect(self):
        """Zatvaranje konekcije sa bazom podataka"""
        if self.connection:
            self.connection.close()
            logger.info("Konekcija sa bazom zatvorena")
    
    def _execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """
        Izvršavanje SQL upita
        
        Args:
            query: SQL upit
            params: Parametri za upit
            fetch: Da li vratiti rezultate
            
        Returns:
            Rezultati upita ako je fetch=True
        """
        try:
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Greška pri izvršavanju upita: {e}")
            raise
    
    # MAPE - CRUD operacije
    
    def save_map(self, 
                 name: str,
                 map_data: bytes,
                 resolution: float,
                 origin_x: float,
                 origin_y: float,
                 width: int,
                 height: int,
                 description: str = None,
                 metadata: Dict[str, Any] = None) -> str:
        """
        Snimanje mape u bazu podataka
        
        Args:
            name: Ime mape
            map_data: Binarni podaci mape
            resolution: Rezolucija u metrima po pikselu
            origin_x: X koordinata početka mape
            origin_y: Y koordinata početka mape  
            width: Širina mape u pikselima
            height: Visina mape u pikselima
            description: Opis mape
            metadata: Dodatni podaci o mapi
            
        Returns:
            UUID nove mape
        """
        map_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO robot_data.maps 
        (id, name, description, map_data, resolution, origin_x, origin_y, width, height, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (map_id, name, description, map_data, resolution, 
                 origin_x, origin_y, width, height, json.dumps(metadata) if metadata else None)
        
        self._execute_query(query, params)
        logger.info(f"Mapa '{name}' snimljena sa ID: {map_id}")
        return map_id
    
    def get_map(self, map_id: str) -> Optional[Dict[str, Any]]:
        """
        Dohvaćanje mape iz baze podataka
        
        Args:
            map_id: UUID mape
            
        Returns:
            Podaci o mapi ili None ako ne postoji
        """
        query = """
        SELECT id, name, description, map_data, resolution, origin_x, origin_y, 
               width, height, metadata, created_at, updated_at
        FROM robot_data.maps 
        WHERE id = %s
        """
        
        result = self._execute_query(query, (map_id,), fetch=True)
        if result:
            map_data = dict(result[0])
            if map_data['metadata']:
                map_data['metadata'] = json.loads(map_data['metadata'])
            return map_data
        return None
    
    def list_maps(self) -> List[Dict[str, Any]]:
        """
        Dohvaćanje liste svih mapa (bez binarnih podataka)
        
        Returns:
            Lista mapa
        """
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
            if map_data['metadata']:
                map_data['metadata'] = json.loads(map_data['metadata'])
            maps.append(map_data)
        return maps
    
    # SLIKE KAMERE - CRUD operacije
    
    def save_camera_image(self,
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
                         metadata: Dict[str, Any] = None) -> str:
        """
        Snimanje slike kamere u bazu podataka
        
        Args:
            map_id: UUID mape kojoj slika pripada
            image_data: Binarni podaci slike
            image_format: Format slike (JPEG, PNG, etc.)
            width: Širina slike
            height: Visina slike
            timestamp: Vrijeme snimanja
            robot_x: X pozicija robota u map koordinatama
            robot_y: Y pozicija robota u map koordinatama
            robot_theta: Orijentacija robota u radijanima
            gps_lat: GPS latitude
            gps_lon: GPS longitude
            metadata: Dodatni podaci o slici
            
        Returns:
            UUID nove slike
        """
        image_id = str(uuid.uuid4())
        
        # Kreiraj PostGIS POINT ako imamo GPS koordinate
        position_wkt = None
        if gps_lat is not None and gps_lon is not None:
            position_wkt = f"POINT({gps_lon} {gps_lat})"
        
        query = """
        INSERT INTO robot_data.camera_images 
        (id, map_id, image_data, image_format, position, robot_x, robot_y, 
         robot_theta, width, height, timestamp, metadata)
        VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (image_id, map_id, image_data, image_format.upper(), position_wkt,
                 robot_x, robot_y, robot_theta, width, height, timestamp,
                 json.dumps(metadata) if metadata else None)
        
        self._execute_query(query, params)
        logger.info(f"Slika snimljena sa ID: {image_id}")
        return image_id
    
    def get_camera_image(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        Dohvaćanje slike kamere iz baze podataka
        
        Args:
            image_id: UUID slike
            
        Returns:
            Podaci o slici ili None ako ne postoji
        """
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
            if image_data['metadata']:
                image_data['metadata'] = json.loads(image_data['metadata'])
            return image_data
        return None
    
    def list_camera_images(self, map_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Dohvaćanje liste slika kamere (bez binarnih podataka)
        
        Args:
            map_id: UUID mape (opciono za filtriranje)
            limit: Maksimalni broj rezultata
            
        Returns:
            Lista slika
        """
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
            if image_data['metadata']:
                image_data['metadata'] = json.loads(image_data['metadata'])
            images.append(image_data)
        return images
    
    # WAYPOINTS - CRUD operacije
    
    def save_waypoint(self,
                     map_id: str,
                     map_x: float,
                     map_y: float,
                     name: str = None,
                     gps_lat: float = None,
                     gps_lon: float = None,
                     waypoint_type: str = "manual",
                     metadata: Dict[str, Any] = None) -> str:
        """
        Snimanje waypoint-a u bazu podataka
        
        Args:
            map_id: UUID mape
            map_x: X pozicija u map koordinatama
            map_y: Y pozicija u map koordinatama
            name: Ime waypoint-a
            gps_lat: GPS latitude
            gps_lon: GPS longitude
            waypoint_type: Tip waypoint-a (manual, auto_generated, landmark)
            metadata: Dodatni podaci
            
        Returns:
            UUID novog waypoint-a
        """
        waypoint_id = str(uuid.uuid4())
        
        # Kreiraj PostGIS POINT
        position_wkt = None
        if gps_lat is not None and gps_lon is not None:
            position_wkt = f"POINT({gps_lon} {gps_lat})"
        
        query = """
        INSERT INTO robot_data.waypoints 
        (id, map_id, name, position, map_x, map_y, waypoint_type, metadata)
        VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s)
        """
        
        params = (waypoint_id, map_id, name, position_wkt, map_x, map_y, 
                 waypoint_type, json.dumps(metadata) if metadata else None)
        
        self._execute_query(query, params)
        logger.info(f"Waypoint '{name}' snimljen sa ID: {waypoint_id}")
        return waypoint_id
    
    def list_waypoints(self, map_id: str) -> List[Dict[str, Any]]:
        """
        Dohvaćanje liste waypoint-ova za mapu
        
        Args:
            map_id: UUID mape
            
        Returns:
            Lista waypoint-ova
        """
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
            if waypoint_data['metadata']:
                waypoint_data['metadata'] = json.loads(waypoint_data['metadata'])
            waypoints.append(waypoint_data)
        return waypoints
    
    # ROBOT SESSIONS
    
    def start_session(self, 
                     map_id: str = None,
                     session_name: str = None,
                     metadata: Dict[str, Any] = None) -> str:
        """
        Pokretanje nove robot session
        
        Args:
            map_id: UUID mape (opciono)
            session_name: Ime sesije
            metadata: Dodatni podaci
            
        Returns:
            UUID nove sesije
        """
        session_id = str(uuid.uuid4())
        
        query = """
        INSERT INTO robot_data.robot_sessions 
        (id, map_id, session_name, start_time, metadata)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        params = (session_id, map_id, session_name, datetime.now(),
                 json.dumps(metadata) if metadata else None)
        
        self._execute_query(query, params)
        logger.info(f"Nova sesija pokrenuta sa ID: {session_id}")
        return session_id
    
    def end_session(self, session_id: str, total_distance: float = None):
        """
        Završavanje robot session
        
        Args:
            session_id: UUID sesije
            total_distance: Ukupna udaljenost prijeđena u sesiji
        """
        query = """
        UPDATE robot_data.robot_sessions 
        SET end_time = %s, total_distance = %s
        WHERE id = %s
        """
        
        params = (datetime.now(), total_distance, session_id)
        self._execute_query(query, params)
        logger.info(f"Sesija {session_id} završena")


# Convenience funkcije za lakše korištenje

def get_database() -> RobotDatabase:
    """Factory funkcija za kreiranje database objekta"""
    return RobotDatabase()


if __name__ == "__main__":
    # Test kod
    db = get_database()
    try:
        # Test konekcije
        maps = db.list_maps()
        print(f"Broj mapa u bazi: {len(maps)}")
        
    except Exception as e:
        print(f"Greška: {e}")
    finally:
        db.disconnect()