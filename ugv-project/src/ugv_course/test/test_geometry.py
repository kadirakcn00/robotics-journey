"""Parkur geometrisi ve taret kinematigi testleri."""

import math

import pytest

from ugv_course import geometry as g

L = g.load_layout()
TG = L['target']
RB, RC = L['ramps']['rb'], L['ramps']['rc']
PLATFORM = ((RB + RC) / 2, TG['y'], L['ramps']['h'], math.pi)   # atis bolgesi, -x yonune


def aim_at_target(x, y, z, yaw):
    """Kameranin hedef merkezine bakmasi icin pan/tilt (sayisal, kamera ile)."""
    pan, tilt = 0.0, 0.0
    for _ in range(50):
        v = g.camera_view_of_target(L, x, y, z, yaw, pan, tilt)
        th = math.tan(L['turret']['camera_hfov'] / 2)
        tv = th * 480 / 640
        pan -= math.atan(v[0] * th)
        tilt += math.atan(v[1] * tv)
    return pan, tilt


def test_road_containment():
    assert g.inside_road(L, 4.0, 0.0) and not g.inside_road(L, 4.0, 0.7)
    assert g.inside_road(L, -1.5, 1.5)                  # sol U donusu
    assert g.inside_road(L, 6.0, L['accel']['row_y'])   # hizlanma parkuru
    assert not g.hits_barrier(L, 7.5, 0.0, math.pi)
    assert g.hits_barrier(L, 7.5, 0.45, math.pi)


def test_cone_contact():
    cx, cy = L['cones'][0]
    assert g.hits_cone(L, cx, cy - 0.25, 0.0, cx, cy)        # tekerlek tabana basar
    assert not g.hits_cone(L, cx, 3.0, 0.0, cx, cy)          # yol ekseni: degmez


def test_slider_contact():
    sl = L['slider']
    assert g.hits_slider(L, sl['x'], sl['row_y'], 0.0, 0.0)
    assert not g.hits_slider(L, sl['x'], sl['row_y'], 0.0, 0.8)
    assert not g.hits_slider(L, sl['x'] - 0.6, sl['row_y'], 0.0, 0.0)


def test_laser_points_forward_and_down_with_tilt():
    o, d = g.laser_ray(L, 0, 0, 0, 0.0, 0.0, 0.0)
    assert d == pytest.approx([1, 0, 0])
    _, d = g.laser_ray(L, 0, 0, 0, 0.0, 0.0, 0.2)
    assert d[2] < 0                                       # pozitif tilt = asagi
    _, d = g.laser_ray(L, 0, 0, 0, 0.0, 0.5, 0.0)
    assert d[1] > 0                                       # pozitif pan = sola


def test_camera_centered_laser_hits_slightly_below_center():
    """Lazer kameranin 2 cm altinda: kamera merkeze bakinca lazer ~2 cm asagi vurur."""
    x, y, z, yaw = PLATFORM
    pan, tilt = aim_at_target(x, y, z, yaw)
    v = g.camera_view_of_target(L, x, y, z, yaw, pan, tilt)
    assert abs(v[0]) < 1e-3 and abs(v[1]) < 1e-3
    hit = g.laser_hit(L, x, y, z, yaw, pan, tilt)
    assert hit[1] == pytest.approx(-0.02, abs=0.004)        # 2 cm asagi
    assert g.ring_points(L, hit) == 25                       # orta halka, ic daire degil


def test_ring_scoring():
    assert g.ring_points(L, (0.0, 0.0)) == 50
    assert g.ring_points(L, (0.012, 0.0)) == 50              # cizgi uzeri: yuksek puan
    assert g.ring_points(L, (0.02, 0.0)) == 25
    assert g.ring_points(L, (0.03, 0.0)) == 15
    assert g.ring_points(L, (0.05, 0.0)) == 0
    assert g.ring_points(L, None) == 0


def test_target_visible_from_platform_with_expected_size():
    x, y, z, yaw = PLATFORM
    v = g.camera_view_of_target(L, x, y, z, yaw, 0.0, 0.0)
    assert v is not None
    dist = x - TG['x']
    expected = (TG['rings'][2] / dist) / math.tan(0.125) * 320
    assert v[2] == pytest.approx(expected, rel=0.02)
