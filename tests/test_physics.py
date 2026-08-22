from core.pet.physics import STOP_THRESHOLD, PhysicsController

FLOOR = 500.0
LEFT = 0.0
RIGHT = 1000.0


def step(physics, dt=1 / 30, times=1):
    events = {}
    for _ in range(times):
        events = physics.update(dt, FLOOR, LEFT, RIGHT)
    return events


def test_body_rests_on_the_floor():
    physics = PhysicsController()
    physics.body.set_position(100, FLOOR)
    step(physics, times=10)
    assert physics.body.y == FLOOR
    assert physics.body.on_ground


def test_falls_under_gravity_and_lands():
    physics = PhysicsController()
    physics.body.set_position(100, 100)
    physics.body.on_ground = False
    step(physics, times=200)
    assert physics.body.y == FLOOR
    assert physics.body.on_ground
    assert physics.body.vy == 0.0


def test_a_gentle_drop_lands_once_without_bouncing():
    physics = PhysicsController()
    physics.body.set_position(100, FLOOR - 5)
    physics.body.on_ground = False
    landings = sum(1 for _ in range(200) if step(physics)["landed"])
    assert landings == 1


def test_a_long_fall_bounces_before_settling():
    physics = PhysicsController()
    physics.body.set_position(100, FLOOR - 400)
    physics.body.on_ground = False
    landings = sum(1 for _ in range(400) if step(physics)["landed"])
    assert landings > 1
    assert physics.body.y == FLOOR
    assert physics.body.on_ground


def test_fall_speed_is_capped():
    physics = PhysicsController()
    physics.body.set_position(100, -100_000)
    physics.body.on_ground = False
    step(physics, times=300)
    assert physics.body.vy <= 1800.0


def test_friction_brings_walking_to_a_stop():
    physics = PhysicsController()
    physics.body.set_position(100, FLOOR)
    physics.walk(200)
    step(physics, times=120)
    assert physics.body.vx == 0.0
    assert not physics.is_moving()


def test_left_edge_stops_movement():
    physics = PhysicsController()
    physics.body.set_position(LEFT + 5, FLOOR)
    physics.walk(-400)
    events = step(physics, times=5)
    assert events["hit_left"]
    assert physics.body.x == LEFT
    assert physics.body.vx == 0.0


def test_right_edge_stops_movement():
    physics = PhysicsController()
    physics.body.set_position(RIGHT - 5, FLOOR)
    physics.walk(400)
    events = step(physics, times=5)
    assert events["hit_right"]
    assert physics.body.x == RIGHT


def test_disabled_physics_does_not_move_the_body():
    physics = PhysicsController()
    physics.enabled = False
    physics.body.set_position(100, 100)
    physics.walk(500)
    step(physics, times=30)
    assert (physics.body.x, physics.body.y) == (100, 100)


def test_stop_clears_all_motion():
    physics = PhysicsController()
    physics.walk(300)
    physics.apply_impulse(vy=-500)
    physics.body.stop()
    assert (physics.body.vx, physics.body.vy) == (0.0, 0.0)


def test_is_moving_uses_the_stop_threshold():
    physics = PhysicsController()
    physics.body.vx = STOP_THRESHOLD / 2
    assert not physics.is_moving()
    physics.body.vx = STOP_THRESHOLD * 2
    assert physics.is_moving()
