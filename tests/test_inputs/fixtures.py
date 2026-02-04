import pytest
from unittest.mock import Mock

psycopg2 = pytest.importorskip("psycopg2")
import db_cont.robot_db_api as robot_db_api


@pytest.fixture
def robot_db_api_module():
    return robot_db_api


@pytest.fixture
def db_no_connect(monkeypatch):
    monkeypatch.setattr(robot_db_api.RobotDatabase, "connect", lambda self: None)
    db = robot_db_api.RobotDatabase()
    db.connection = Mock()
    return db
