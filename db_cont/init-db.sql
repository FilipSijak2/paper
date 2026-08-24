-- Initialize the robot database.
-- Enable required extensions.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the application schema.
CREATE SCHEMA IF NOT EXISTS robot_data;

-- Robot maps.
CREATE TABLE robot_data.maps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    map_data BYTEA NOT NULL, -- Binarni podaci mape (OGM format)
    resolution DOUBLE PRECISION NOT NULL, -- Rezolucija u metrima po pikselu
    origin_x DOUBLE PRECISION NOT NULL, -- Map origin X coordinate.
    origin_y DOUBLE PRECISION NOT NULL, -- Map origin Y coordinate.
    width INTEGER NOT NULL, -- Map width in pixels.
    height INTEGER NOT NULL, -- Visina mape u pikselima
    metadata JSONB, -- Dodatni podaci o mapi
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Camera images.
CREATE TABLE robot_data.camera_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id UUID REFERENCES robot_data.maps(id) ON DELETE CASCADE,
    image_data BYTEA NOT NULL, -- Binarni podaci slike
    image_format VARCHAR(10) NOT NULL DEFAULT 'JPEG', -- Format slike (JPEG, PNG, etc.)
    position GEOMETRY(POINT, 4326), -- Robot position when the image was captured (latitude/longitude).
    robot_x DOUBLE PRECISION, -- X pozicija robota u map koordinatama
    robot_y DOUBLE PRECISION, -- Y pozicija robota u map koordinatama
    robot_theta DOUBLE PRECISION, -- Orijentacija robota u radijanima
    width INTEGER NOT NULL, -- Image width.
    height INTEGER NOT NULL, -- Visina slike
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB, -- Dodatni podaci o slici (exposure, camera params, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Waypoints and paths.
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

-- Robot sessions.
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

-- Performance indexes.
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

-- Keep updated_at current.
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
