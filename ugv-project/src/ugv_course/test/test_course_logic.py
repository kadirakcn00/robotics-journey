"""Su fizigi ve kayar engel hesaplarinin testleri (ROS gerektirmez)."""

import pytest

from ugv_course.slider import triangle_position
from ugv_course.water import WaterEffect, WaterModel, WaterZone

POOL = WaterZone(x_min=5.2, x_max=6.6, y_min=-0.6, y_max=0.6, depth=0.16, ramp_length=0.28)


def test_depth_profile():
    assert POOL.depth_at(5.9, 0.0) == pytest.approx(0.16)        # havuz ortasi
    assert POOL.depth_at(6.6 - 0.14, 0.0) == pytest.approx(0.08)  # giris egiminin ortasi
    assert POOL.depth_at(6.6, 0.0) == pytest.approx(0.0)          # havuz kenari
    assert POOL.depth_at(7.0, 0.0) == 0.0                          # havuz disi
    assert POOL.depth_at(5.9, 0.7) == 0.0                          # yol disi


def test_dry_ground_passes_command_unchanged():
    m = WaterModel([POOL])
    for v, w in ((0.3, 0.0), (-0.2, 0.5), (0.0, -1.0)):
        assert m.step(v, w, 3.0, 0.0, 0.05) == (v, w)


def test_water_slows_robot_down():
    m = WaterModel([POOL], effect=WaterEffect(yaw_noise=0.0))
    v = w = 0.0
    for _ in range(200):                     # 10 s havuz ortasinda, sabit komut
        v, w = m.step(0.4, 0.8, 5.9, 0.0, 0.05)
    s = 0.16 / 0.30
    assert v == pytest.approx(0.4 * (1 - 0.6 * s), rel=1e-6)
    assert w == pytest.approx(0.8 * (1 - 0.5 * s), rel=1e-6)
    assert v < 0.4 and w < 0.8


def test_acceleration_is_limited_in_water():
    m = WaterModel([POOL], effect=WaterEffect(yaw_noise=0.0))
    v, _ = m.step(0.4, 0.0, 5.9, 0.0, 0.1)
    s = 0.16 / 0.30
    accel = 1.0 + (0.3 - 1.0) * s
    assert v == pytest.approx(accel * 0.1)    # ilk adimda sadece izin verilen kadar hizlanir


def test_deeper_means_slower():
    m = WaterModel([POOL], effect=WaterEffect(yaw_noise=0.0))
    speeds = []
    for x in (6.55, 6.45, 6.35, 5.9):        # egimden asagi, gittikce derin
        m.v = 0.4
        speeds.append(m.step(0.4, 0.0, x, 0.0, 1.0)[0])
    assert speeds == sorted(speeds, reverse=True)


def test_yaw_noise_only_in_water_and_reproducible():
    a = WaterModel([POOL], seed=1)
    b = WaterModel([POOL], seed=1)
    wa = [a.step(0.3, 0.0, 5.9, 0.0, 0.05)[1] for _ in range(20)]
    wb = [b.step(0.3, 0.0, 5.9, 0.0, 0.05)[1] for _ in range(20)]
    assert wa == wb and any(abs(w) > 1e-6 for w in wa)
    assert WaterModel([POOL], seed=1).step(0.3, 0.0, 3.0, 0.0, 0.05)[1] == 0.0


@pytest.mark.parametrize('t,expected', [
    (0.0, -0.8), (10.0, 0.0), (20.0, 0.8), (30.0, 0.0), (40.0, -0.8), (50.0, 0.0),
])
def test_slider_triangle_wave(t, expected):
    # 0.8 m genlik, 0.08 m/s: uctan uca 1.6 m / 0.08 = 20 s, tam tur 40 s
    assert triangle_position(t, 0.8, 0.08) == pytest.approx(expected)


def test_slider_constant_speed():
    dt = 0.05
    pos = [triangle_position(i * dt, 0.8, 0.08) for i in range(1600)]
    speeds = [abs(b - a) / dt for a, b in zip(pos, pos[1:])]
    # Uclarda donerken bir adimda hiz yon degistirir; digerleri tam 0.08 m/s
    assert sum(abs(s - 0.08) < 1e-9 for s in speeds) >= len(speeds) - 4
    assert max(pos) == pytest.approx(0.8) and min(pos) == pytest.approx(-0.8)
