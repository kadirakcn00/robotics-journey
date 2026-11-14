"""Otonom gorev testleri: 2B simulatorde hakemle bastan sona kosu (ROS gerektirmez).

Simulator gercegi bilir (gercek konum, konilerin gercek yeri, kayar engel); gorev sadece
sensorleri kullanir. Puanlari hakem verir.
"""

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_sim  # noqa: E402
from ugv_autonomy.localization import Localizer  # noqa: E402
from ugv_autonomy.mission import Shooter  # noqa: E402
from ugv_autonomy.obstacles import SliderWatcher  # noqa: E402
from ugv_course import geometry as g  # noqa: E402

L = g.load_layout()
MAX_POINTS = 10 + 5 + 5 + 5 + 50 + 50 + 5 + 15 + 10 + 50     # sure siralamasi haric


def clean(r):
    ref = r['ref']
    return (ref.cone_contacts == 0 and ref.barrier_contacts == 0 and not ref.slider_contact)


# ----------------------------------------------------------------------------- tam kosular
@pytest.fixture(scope='module')
def default_run():
    return run_sim.run()


def test_autonomous_run_scores_maximum(default_run):
    ref = default_run['ref']
    assert ref.finish_t is not None, default_run['events']
    assert clean(default_run), default_run['events']
    assert all(ref.stop_ok.values())
    assert ref.shots and max(ref.shots) == 50
    assert ref.total() == MAX_POINTS
    assert ref.finish_t - ref.start_t < 15 * 60


def test_localization_error_stays_small(default_run):
    assert default_run['max_err'] < 0.15


@pytest.mark.parametrize('phase', [5.0, 12.0, 21.0, 33.0])
def test_sliding_obstacle_any_timing(phase):
    r = run_sim.run(slider_phase=phase)
    assert r['ref'].finish_t is not None and not r['ref'].slider_contact, r['events']


def test_bad_odometry_is_corrected():
    r = run_sim.run(slip=0.05, turn_eff=0.8)
    assert r['ref'].finish_t is not None and clean(r), r['events']
    assert r['max_err'] < 0.25


def test_cones_moved_by_referee_are_avoided():
    """Hakem konileri duzensiz kaydirir; gorev yeni yerleri bilmez, LIDAR ile gorur.

    3. ve 4. koni arasinda robotun sigacagi bosluk sadece ~1 cm: robot ikisini de ayni anda
    hesaba katmazsa 4. koniye surtunur.
    """
    cones = [[2.3, 3.28], [2.95, 2.68], [3.7, 3.30], [4.25, 2.74], [5.0, 3.33]]
    r = run_sim.run(cones=cones)
    assert r['ref'].finish_t is not None, r['events']
    assert r['ref'].cone_contacts == 0 and r['ref'].barrier_contacts == 0, r['events']


def test_avoid_lateral_uses_cone_beside_robot():
    from ugv_autonomy.obstacles import avoid_lateral
    # Biri robotun yaninda (sol, +0.30), biri onunde (sag, -0.26): tek gecis yeri ortada
    y = avoid_lateral([(0.0, 0.30), (0.5, -0.26)], -0.05)
    assert 0.0 < y < 0.04
    # Sadece ondeki koni olsaydi robot sola kacardi; yandaki koni bunu engeller
    assert avoid_lateral([(0.5, -0.26)], 0.0) > 0.0
    # Arkada kalan koni artik onemsiz: robot yol eksenine doner
    assert avoid_lateral([(-0.6, 0.30)], 0.1) == 0.0


def test_without_corrections_bad_odometry_fails():
    """Ters test: LIDAR ve egim duzeltmeleri kapatilirsa ayni odometriyle kosu bozulur."""
    r = run_sim.run(slip=0.05, turn_eff=0.8, correct=False, t_max=400)
    assert r['ref'].finish_t is None or not clean(r) or r['ref'].total() < MAX_POINTS


def test_acceleration_run():
    r = run_sim.run(run='accel', t_max=60)
    ref = r['ref']
    assert ref.accel_line_t is not None
    sim = r['sim']
    assert 0 < sim.x - L['accel']['line'] <= L['accel']['stop_zone']
    assert ref.barrier_contacts == 0


# ----------------------------------------------------------------------------- birim
def test_scan_correction_removes_lateral_error():
    """Robot gercekte y=0.10'da, tahmin y=0'da: yan duvarlar hatayi duzeltmeli."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sim2d import Sim
    sim = Sim(L, (3.0, 0.10, math.pi))
    loc = Localizer(L, (3.0, 0.0, math.pi))
    for _ in range(20):
        loc.correct_with_scan(loc.scan_points_world(*sim.scan()))
    assert loc.y == pytest.approx(0.10, abs=0.02)
    assert loc.x == pytest.approx(3.0, abs=0.05)          # duz yolda x'e dokunmaz


def test_slider_watcher_rules():
    w = SliderWatcher(6.6, 3.0)

    def feed(ys):
        w.history = []
        for i, y in enumerate(ys):
            w.update(i * 0.1, np.array([[6.6, 3.0 + y], [6.6, 3.0 + y + 0.01]]))
        return w.clear()
    assert feed([0.40 + 0.008 * i for i in range(10)])       # disari gidiyor, uzak: gec
    assert not feed([0.20 + 0.008 * i for i in range(10)])   # disari ama yakin: bekle
    assert not feed([0.79 - 0.008 * i for i in range(10)])   # disarida ama iceri donuyor
    assert not feed([])                                      # gorunmuyor: bekle


def test_shooter_compensates_laser_offset():
    """Ayni atis noktasinda telafili nisan 50 puan verir (telafisiz 25, bkz. ugv_course)."""
    rp = L['ramps']
    x, y, z, yaw = (rp['rb'] + rp['rc']) / 2, L['target']['y'], rp['h'], math.pi
    sh = Shooter(L)
    pan = tilt = 0.0
    t, laser_seen = 0.0, False
    while not sh.done and t < 30:
        v = g.camera_view_of_target(L, x, y, z, yaw, pan, tilt)
        laser = sh.step(t, (x, y, z, yaw), v, t)
        pan, tilt = sh.pan, sh.tilt
        if laser:
            laser_seen = True
            hit = g.laser_hit(L, x, y, z, yaw, pan, tilt)
        t += 0.05
    assert laser_seen and g.ring_points(L, hit) == 50
    assert math.hypot(*hit) < 0.005
