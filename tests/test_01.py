import json
from datetime import datetime

from tests.test_inputs.fixtures import db_no_connect, robot_db_api_module


def test_save_map_calls_execute_query(db_no_connect, robot_db_api_module, monkeypatch):
    fixed_uuid = "11111111-1111-1111-1111-111111111111"
    monkeypatch.setattr(robot_db_api_module.uuid, "uuid4", lambda: fixed_uuid)

    captured = {}

    def fake_execute(query, params, fetch=False):
        captured["query"] = query
        captured["params"] = params
        captured["fetch"] = fetch
        return 1

    monkeypatch.setattr(db_no_connect, "_execute_query", fake_execute)

    map_id = db_no_connect.save_map(
        name="map_a",
        map_data=b"abc",
        resolution=0.05,
        origin_x=1.0,
        origin_y=2.0,
        width=100,
        height=200,
        description="desc",
        metadata={"a": 1},
    )

    assert map_id == fixed_uuid
    assert "INSERT INTO robot_data.maps" in captured["query"]
    assert captured["params"][0] == fixed_uuid
    assert captured["params"][1] == "map_a"
    assert captured["params"][2] == "desc"
    assert captured["params"][3] == b"abc"
    assert captured["params"][9] == json.dumps({"a": 1})


def test_get_map_decodes_metadata(db_no_connect, monkeypatch):
    payload = {
        "id": "id1",
        "name": "m",
        "description": None,
        "map_data": b"x",
        "resolution": 0.1,
        "origin_x": 0.0,
        "origin_y": 0.0,
        "width": 10,
        "height": 20,
        "metadata": json.dumps({"k": "v"}),
        "created_at": None,
        "updated_at": None,
    }
    monkeypatch.setattr(db_no_connect, "_execute_query", lambda *args, **kwargs: [payload])
    result = db_no_connect.get_map("id1")
    assert result["metadata"] == {"k": "v"}


def test_list_maps_decodes_metadata(db_no_connect, monkeypatch):
    payload = [
        {
            "id": "id1",
            "name": "m",
            "description": None,
            "resolution": 0.1,
            "origin_x": 0.0,
            "origin_y": 0.0,
            "width": 10,
            "height": 20,
            "metadata": json.dumps({"k": "v"}),
            "created_at": None,
            "updated_at": None,
        }
    ]
    monkeypatch.setattr(db_no_connect, "_execute_query", lambda *args, **kwargs: payload)
    result = db_no_connect.list_maps()
    assert result[0]["metadata"] == {"k": "v"}


def test_save_camera_image_wkt_and_format(db_no_connect, robot_db_api_module, monkeypatch):
    fixed_uuid = "22222222-2222-2222-2222-222222222222"
    monkeypatch.setattr(robot_db_api_module.uuid, "uuid4", lambda: fixed_uuid)

    captured = {}

    def fake_execute(query, params, fetch=False):
        captured["query"] = query
        captured["params"] = params
        return 1

    monkeypatch.setattr(db_no_connect, "_execute_query", fake_execute)

    img_id = db_no_connect.save_camera_image(
        map_id="map1",
        image_data=b"img",
        image_format="jpeg",
        width=640,
        height=480,
        timestamp=datetime(2020, 1, 1, 12, 0, 0),
        gps_lat=45.0,
        gps_lon=16.0,
        metadata={"note": "x"},
    )

    assert img_id == fixed_uuid
    assert "INSERT INTO robot_data.camera_images" in captured["query"]
    assert captured["params"][0] == fixed_uuid
    assert captured["params"][3] == "JPEG"
    assert captured["params"][4] == "POINT(16.0 45.0)"
    assert captured["params"][11] == json.dumps({"note": "x"})


def test_save_waypoint_wkt(db_no_connect, robot_db_api_module, monkeypatch):
    fixed_uuid = "33333333-3333-3333-3333-333333333333"
    monkeypatch.setattr(robot_db_api_module.uuid, "uuid4", lambda: fixed_uuid)

    captured = {}

    def fake_execute(query, params, fetch=False):
        captured["query"] = query
        captured["params"] = params
        return 1

    monkeypatch.setattr(db_no_connect, "_execute_query", fake_execute)

    waypoint_id = db_no_connect.save_waypoint(
        map_id="map1",
        map_x=1.0,
        map_y=2.0,
        name="wp1",
        gps_lat=45.1,
        gps_lon=16.2,
        waypoint_type="manual",
        metadata={"m": 1},
    )

    assert waypoint_id == fixed_uuid
    assert "INSERT INTO robot_data.waypoints" in captured["query"]
    assert captured["params"][3] == "POINT(16.2 45.1)"
    assert captured["params"][7] == json.dumps({"m": 1})


def test_list_camera_images_decodes_metadata(db_no_connect, monkeypatch):
    payload = [
        {
            "id": "id1",
            "map_id": "map1",
            "image_format": "JPEG",
            "gps_lon": 16.0,
            "gps_lat": 45.0,
            "robot_x": None,
            "robot_y": None,
            "robot_theta": None,
            "width": 10,
            "height": 20,
            "timestamp": None,
            "metadata": json.dumps({"k": "v"}),
            "created_at": None,
        }
    ]
    monkeypatch.setattr(db_no_connect, "_execute_query", lambda *args, **kwargs: payload)
    result = db_no_connect.list_camera_images(map_id="map1", limit=10)
    assert result[0]["metadata"] == {"k": "v"}


def test_list_waypoints_decodes_metadata(db_no_connect, monkeypatch):
    payload = [
        {
            "id": "id1",
            "map_id": "map1",
            "name": "wp1",
            "gps_lon": 16.0,
            "gps_lat": 45.0,
            "map_x": 1.0,
            "map_y": 2.0,
            "waypoint_type": "manual",
            "metadata": json.dumps({"k": "v"}),
            "created_at": None,
        }
    ]
    monkeypatch.setattr(db_no_connect, "_execute_query", lambda *args, **kwargs: payload)
    result = db_no_connect.list_waypoints(map_id="map1")
    assert result[0]["metadata"] == {"k": "v"}
