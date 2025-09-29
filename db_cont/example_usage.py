"""
Primjer korištenja Robot Database API-ja
Demonstrira kako snimiti i čitati mape te slike kamere
"""

from robot_db_api import get_database
from datetime import datetime
import io

def example_usage():
    """Primjer korištenja baze podataka"""
    
    # Kreiranje konekcije sa bazom
    db = get_database()
    
    try:
        print("=== PRIMJER KORIŠTENJA ROBOT DATABASE API ===\n")
        
        # 1. Snimanje nove mape
        print("1. Snimanje nove mape...")
        
        # Simuliraj OGM podatke (u stvarnosti bi ovo bili podaci iz ROS-a)
        fake_map_data = b"fake_occupancy_grid_map_data_here"
        
        map_id = db.save_map(
            name="Test Mapa Ured",
            map_data=fake_map_data,
            resolution=0.05,  # 5cm po pikselu
            origin_x=-10.0,
            origin_y=-10.0, 
            width=400,
            height=400,
            description="Test mapa ureda kreirana za demonstraciju",
            metadata={
                "slam_algorithm": "gmapping",
                "scan_topic": "/scan",
                "map_frame": "map",
                "robot_frame": "base_link"
            }
        )
        print(f"   Mapa snimljena sa ID: {map_id}\n")
        
        # 2. Snimanje slike kamere
        print("2. Snimanje slike kamere...")
        
        # Simuliraj JPEG podatke
        fake_image_data = b"fake_jpeg_image_data_here"
        
        image_id = db.save_camera_image(
            map_id=map_id,
            image_data=fake_image_data,
            image_format="JPEG",
            width=640,
            height=480,
            timestamp=datetime.now(),
            robot_x=2.5,
            robot_y=3.1,
            robot_theta=1.57,  # 90 stupnjeva u radijanima
            gps_lat=45.815399,  # Zagreb koordinate
            gps_lon=15.966568,
            metadata={
                "camera_model": "RealSense D435i",
                "exposure_time": "1/60",
                "focal_length": "f/2.0"
            }
        )
        print(f"   Slika snimljena sa ID: {image_id}\n")
        
        # 3. Dodavanje waypoint-a
        print("3. Dodavanje waypoint-a...")
        
        waypoint_id = db.save_waypoint(
            map_id=map_id,
            map_x=5.0,
            map_y=2.0,
            name="Ulaz u ured",
            gps_lat=45.815399,
            gps_lon=15.966568,
            waypoint_type="landmark",
            metadata={
                "description": "Glavny ulaz u zgradu",
                "accessibility": "wheelchair_accessible"
            }
        )
        print(f"   Waypoint snimljen sa ID: {waypoint_id}\n")
        
        # 4. Pokretanje nove sesije
        print("4. Pokretanje robot sesije...")
        
        session_id = db.start_session(
            map_id=map_id,
            session_name="Test navigacija",
            metadata={
                "mission_type": "exploration",
                "battery_level": 85,
                "weather": "sunny"
            }
        )
        print(f"   Sesija pokrenuta sa ID: {session_id}\n")
        
        # 5. Čitanje podataka iz baze
        print("5. Čitanje podataka iz baze...\n")
        
        # Lista svih mapa
        maps = db.list_maps()
        print(f"   Ukupno mapa u bazi: {len(maps)}")
        for map_data in maps:
            print(f"   - {map_data['name']} ({map_data['width']}x{map_data['height']}, {map_data['resolution']}m/px)")
        
        # Lista slika za mapu
        images = db.list_camera_images(map_id=map_id)
        print(f"\n   Ukupno slika za mapu: {len(images)}")
        for image in images:
            print(f"   - {image['image_format']} {image['width']}x{image['height']} @ ({image['robot_x']:.1f}, {image['robot_y']:.1f})")
        
        # Lista waypoint-ova
        waypoints = db.list_waypoints(map_id=map_id)
        print(f"\n   Ukupno waypoint-ova: {len(waypoints)}")
        for wp in waypoints:
            print(f"   - {wp['name']} @ ({wp['map_x']:.1f}, {wp['map_y']:.1f}) [{wp['waypoint_type']}]")
        
        # 6. Završavanje sesije
        print(f"\n6. Završavanje sesije...")
        db.end_session(session_id, total_distance=12.5)  # 12.5 metara
        print("   Sesija završena\n")
        
        print("=== PRIMJER ZAVRŠEN USPJEŠNO ===")
        
    except Exception as e:
        print(f"Greška: {e}")
    finally:
        db.disconnect()


if __name__ == "__main__":
    example_usage()