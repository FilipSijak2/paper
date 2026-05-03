import pytest
from unittest.mock import Mock

psycopg2 = pytest.importorskip("psycopg2")


@pytest.fixture
def robot_db_api_module():
    import db_cont.robot_db_api as robot_db_api

    return robot_db_api


@pytest.fixture
def db_no_connect(monkeypatch, robot_db_api_module):
    monkeypatch.setattr(robot_db_api_module.RobotDatabase, "connect", lambda self: None)
    db = robot_db_api_module.RobotDatabase()
    db.connection = Mock()
    return db
