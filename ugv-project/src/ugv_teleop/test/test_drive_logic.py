"""Surucu konsolu mantiginin testleri (ROS ve ekran gerektirmez)."""

import pytest

from ugv_teleop.drive_logic import DriveController, GEARS


def run(c, seconds, dt=0.05):
    for _ in range(int(round(seconds / dt))):
        s = c.step(dt)
    return s


def test_hold_forward_accelerates_to_gear_speed():
    c = DriveController()
    c.press('forward')
    assert run(c, 0.2).v == pytest.approx(0.6 * 0.2)          # hizlanirken (0.25 s'de dolar)
    assert run(c, 2.0).v == pytest.approx(GEARS[1][0])         # vites 1 siniri


def test_release_brakes_smoothly_to_zero():
    c = DriveController()
    c.press('forward')
    run(c, 2.0)
    c.release('forward')
    assert 0 < c.step(0.05).v < GEARS[1][0]                    # aniden durmaz
    assert run(c, 1.0).v == 0.0


def test_gears_change_top_speed():
    c = DriveController()
    c.press('3')
    c.press('forward')
    assert run(c, 3.0).v == pytest.approx(GEARS[3][0])
    c.press('1')
    assert run(c, 2.0).v == pytest.approx(GEARS[1][0])


def test_turning_and_reverse():
    c = DriveController()
    c.press('backward')
    c.press('left')
    s = run(c, 2.0)
    assert s.v == pytest.approx(-GEARS[1][0]) and s.w == pytest.approx(GEARS[1][1])


def test_estop_latches_until_release():
    c = DriveController()
    c.press('forward')
    run(c, 1.0)
    c.press('estop')
    assert c.step(0.05).v == 0.0
    assert run(c, 1.0).v == 0.0                                 # tus hala basili ama durur
    c.press('release')
    assert run(c, 1.0).v > 0


def test_focus_loss_stops_robot():
    c = DriveController()
    c.press('forward')
    run(c, 1.0)
    c.release_all()
    assert run(c, 1.0).v == 0.0


def test_laser_locks_motion_and_turret():
    c = DriveController()
    c.press('pan_left')
    pan = run(c, 1.0).pan
    assert pan == pytest.approx(0.6)
    c.press('forward')
    c.press('fire')
    s = run(c, 1.2)
    assert s.laser_on and s.laser_time == pytest.approx(1.2)
    assert s.v == 0.0 and s.pan == pytest.approx(pan)           # lazer acikken hareket yok
    c.release('fire')
    s = run(c, 0.5)
    assert not s.laser_on and s.v > 0 and s.pan > pan


def test_turret_limits_and_center():
    c = DriveController()
    c.press('pan_right')
    c.press('tilt_down')
    s = run(c, 10.0)
    assert s.pan == pytest.approx(-DriveController.PAN_LIMIT)
    assert s.tilt == pytest.approx(DriveController.TILT_LIMIT)
    c.press('center')
    assert c.s.pan == 0.0 and c.s.tilt == 0.0
