from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = REPO_ROOT.parent / "stack"
PROFILE_DIR = STACK_ROOT / "config" / "drive_profiles"


pytestmark = pytest.mark.skipif(
    not STACK_ROOT.exists(), reason="Sibling stack directory is unavailable"
)


def parse_env(path: Path) -> dict[str, str]:
    values = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def test_compose_loads_selected_drive_profile_after_base_bridge_env():
    compose = (STACK_ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
    base_index = compose.index("./config/containers/bridge_rpi_direct.env")
    profile_index = compose.index("./config/drive_profiles/${DRIVE_PROFILE:-safe-demo}.env")
    assert profile_index > base_index


@pytest.mark.parametrize("name", ["safe-demo", "laminate", "carpet"])
def test_drive_profiles_enable_safe_slew_and_immediate_stop(name):
    values = parse_env(PROFILE_DIR / f"{name}.env")
    assert values["DRIVE_PROFILE_NAME"] == name
    assert values["MOTOR_SLEW_ENABLED"] == "1"
    assert 0.1 <= float(values["MOTOR_SLEW_RATE_UP"]) <= 2.0
    assert float(values["MOTOR_SLEW_RATE_DOWN"]) >= float(values["MOTOR_SLEW_RATE_UP"])
    assert 0.10 <= float(values["MOTOR_REVERSAL_NEUTRAL_S"]) <= 0.30
    assert values["MOTOR_IMMEDIATE_STOP"] == "1"


def test_profiles_do_not_guess_uncalibrated_motor_mapping():
    forbidden = {
        "MIN_MOTOR_CMD",
        "MAX_LINEAR_VEL",
        "MAX_ANGULAR_VEL",
        "LINEAR_TRACTION_ASSIST_ENABLED",
    }
    for path in PROFILE_DIR.glob("*.env"):
        assert forbidden.isdisjoint(parse_env(path)), path.name


def test_env_example_defaults_to_safe_demo_profile():
    values = parse_env(STACK_ROOT / ".env.example")
    assert values["DRIVE_PROFILE"] == "safe-demo"
    assert values["MOTOR_SLEW_ENABLED"] == "1"


def test_compose_exposes_one_global_motor_transition_switch():
    compose = (STACK_ROOT / "docker-compose.yaml").read_text(encoding="utf-8")
    assert "MOTOR_SLEW_ENABLED: ${MOTOR_SLEW_ENABLED:-1}" in compose
