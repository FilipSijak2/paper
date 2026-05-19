# Nav safety review and bridge follow-up notes

This branch reviews the recent navigation tuning commits and captures the proposed direction for the next test.

## Main finding

The current runtime stack moved back toward safer localization, but it also removed some of the stronger obstacle-safety changes from the previous commit. For the desired behavior, the next test should combine:

- the more predictable rotation limits and `RotationShimController` from the latest commit,
- the stronger obstacle collision checking from the previous commit,
- moderate adaptive rotation boost,
- forward-biased turns for near-in-place rotation,
- no extra physical footprint enlargement.

## Required Nav2 direction

Keep the physical footprint unchanged:

```yaml
footprint: "[[0.16, 0.165], [0.16, -0.165], [-0.11, -0.165], [-0.11, 0.165]]"
footprint_padding: 0.0
```

Obstacle clearance should come from inflation and critics:

```yaml
ObstacleFootprint.scale: 120.0
BaseObstacle.scale: 0.20
inflation_radius: 0.75
cost_scaling_factor: 2.2
```

The local costmap should include the static map as well as live obstacle sources:

```yaml
plugins: [static_layer, voxel_layer, inflation_layer]
```

This helps prevent the controller from driving into static obstacles that are visible on the map, even when the local rolling window is used.

## Bridge follow-up

The existing bridge already implements:

- adaptive rotation boost from `/imu/data`,
- forward-arc turn commands,
- `/robot_status` fields for `PWR_BOOST`, `IMU_WZ`, `FWD_ARC`, and `FWD_ARC_ACTIVE`.

Recommended follow-up code tweak:

```python
use_forward_arc_turn = (
    self.forward_arc_turn_enabled
    and self.cmd_linear >= 0.0
    and abs(self.cmd_angular) >= self.forward_arc_turn_min_angular
    and abs(self.cmd_linear) <= self.forward_arc_turn_max_linear
)
```

Rationale: if Nav2 requests reverse motion, do not convert it into a forward arc. This keeps the rule simple: forward turns are preferred, but if reverse is required it should stay reverse and should be constrained by Nav2 behavior tuning to be straight/limited.

## Runtime values suggested for next test

```env
MIN_MOTOR_CMD=0.35
POWER_ADAPT_ENABLED=1
POWER_ADAPT_HIGH_RATIO=1.10
POWER_ADAPT_MAX_BOOST=0.65
POWER_ADAPT_STEP_UP=0.02
POWER_ADAPT_STEP_DOWN=0.006
FORWARD_ARC_TURN_ENABLED=1
FORWARD_ARC_TURN_MAX_LINEAR=0.04
FORWARD_ARC_TURN_INNER_CMD=0.18
```

## Test procedure

1. Test laminate first.
2. Verify localization does not jump during rotations.
3. Verify local and global costmaps show inflated obstacles.
4. Place an obstacle visible in `/scan_filtered` and ensure the footprint does not touch it.
5. Watch `/robot_status` and confirm `PWR_BOOST` rises only when yaw feedback is below target.
6. Test carpet after laminate is stable.
