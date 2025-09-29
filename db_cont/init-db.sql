-- Inicijalizacija baze podataka za robotske podatke
-- Kreiranje ekstenzija
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Kreiranje schema za organizaciju podataka
CREATE SCHEMA IF NOT EXISTS robot_data;

-- Tabela za mape robota
CREATE TABLE robot_data.maps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    map_data BYTEA NOT NULL, -- Binarni podaci mape (OGM format)
    resolution DOUBLE PRECISION NOT NULL, -- Rezolucija u metrima po pikselu
    origin_x DOUBLE PRECISION NOT NULL, -- X koordinata početka mape
    origin_y DOUBLE PRECISION NOT NULL, -- Y koordinata početka mape
    width INTEGER NOT NULL, -- Širina mape u pikselima
    height INTEGER NOT NULL, -- Visina mape u pikselima
    metadata JSONB, -- Dodatni podaci o mapi
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela za slike kamere
CREATE TABLE robot_data.camera_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id UUID REFERENCES robot_data.maps(id) ON DELETE CASCADE,
    image_data BYTEA NOT NULL, -- Binarni podaci slike
    image_format VARCHAR(10) NOT NULL DEFAULT 'JPEG', -- Format slike (JPEG, PNG, etc.)
    position GEOMETRY(POINT, 4326), -- Pozicija robota kada je slika snimljena (lat/lon)
    robot_x DOUBLE PRECISION, -- X pozicija robota u map koordinatama
    robot_y DOUBLE PRECISION, -- Y pozicija robota u map koordinatama
    robot_theta DOUBLE PRECISION, -- Orijentacija robota u radijanima
    width INTEGER NOT NULL, -- Širina slike
    height INTEGER NOT NULL, -- Visina slike
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB, -- Dodatni podaci o slici (exposure, camera params, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela za waypoints i putanje
CREATE TABLE robot_data.waypoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id UUID REFERENCES robot_data.maps(id) ON DELETE CASCADE,
    name VARCHAR(255),
    position GEOMETRY(POINT, 4326) NOT NULL, -- GPS pozicija
    map_x DOUBLE PRECISION NOT NULL, -- X pozicija u map koordinatama
    map_y DOUBLE PRECISION NOT NULL, -- Y pozicija u map koordinatama
    waypoint_type VARCHAR(50) DEFAULT 'manual', -- manual, auto_generated, landmark
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela za robot sessions/putovanja
CREATE TABLE robot_data.robot_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id UUID REFERENCES robot_data.maps(id),
    session_name VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_distance DOUBLE PRECISION,
    metadata JSONB, -- mission params, battery info, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Kreiranje indeksa za performanse
CREATE INDEX idx_maps_name ON robot_data.maps(name);
CREATE INDEX idx_maps_created_at ON robot_data.maps(created_at);

CREATE INDEX idx_camera_images_map_id ON robot_data.camera_images(map_id);
CREATE INDEX idx_camera_images_timestamp ON robot_data.camera_images(timestamp);
CREATE INDEX idx_camera_images_position ON robot_data.camera_images USING GIST(position);

CREATE INDEX idx_waypoints_map_id ON robot_data.waypoints(map_id);
CREATE INDEX idx_waypoints_position ON robot_data.waypoints USING GIST(position);
CREATE INDEX idx_waypoints_type ON robot_data.waypoints(waypoint_type);

CREATE INDEX idx_sessions_map_id ON robot_data.robot_sessions(map_id);
CREATE INDEX idx_sessions_start_time ON robot_data.robot_sessions(start_time);

-- Trigger za ažuriranje updated_at polja
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_maps_updated_at 
    BEFORE UPDATE ON robot_data.maps 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Kreiranje osnovnog korisnika za aplikaciju
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD 'app_pass';
    END IF;
END
$$;

-- Davanje dozvola
GRANT USAGE ON SCHEMA robot_data TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA robot_data TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA robot_data TO app_user;

-- Postavljanje zadanih dozvola za buduće tabele
ALTER DEFAULT PRIVILEGES IN SCHEMA robot_data 
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA robot_data 
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;