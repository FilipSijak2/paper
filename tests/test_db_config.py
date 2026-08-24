import db_cont.robot_db_api as robot_db_api


def test_resolve_connection_params_reads_environment(monkeypatch):
    monkeypatch.setenv("ROBOT_DB_HOST", "db.example")
    monkeypatch.setenv("ROBOT_DB_PORT", "6543")
    monkeypatch.setenv("ROBOT_DB_NAME", "robot_prod")
    monkeypatch.setenv("ROBOT_DB_USER", "robot_user")
    monkeypatch.setenv("ROBOT_DB_PASSWORD", "secret")
    monkeypatch.setenv("ROBOT_DB_CONNECT_TIMEOUT", "9")

    params = robot_db_api.resolve_connection_params()

    assert params == {
        "host": "db.example",
        "port": 6543,
        "database": "robot_prod",
        "user": "robot_user",
        "password": "secret",
        "connect_timeout": 9,
    }


def test_robot_database_prefers_explicit_args_over_environment(monkeypatch):
    monkeypatch.setattr(robot_db_api.RobotDatabase, "connect", lambda self: None)
    monkeypatch.setenv("ROBOT_DB_HOST", "env-host")
    monkeypatch.setenv("ROBOT_DB_PORT", "9999")

    db = robot_db_api.RobotDatabase(host="explicit-host", port=1234, database="explicit-db")

    assert db.connection_params["host"] == "explicit-host"
    assert db.connection_params["port"] == 1234
    assert db.connection_params["database"] == "explicit-db"
    assert db.connection_params["user"] == "robot_user"


def test_resolve_connection_params_supports_legacy_db_pass(monkeypatch):
    monkeypatch.delenv("ROBOT_DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.setenv("DB_PASS", "legacy-secret")

    params = robot_db_api.resolve_connection_params()

    assert params["password"] == "legacy-secret"
