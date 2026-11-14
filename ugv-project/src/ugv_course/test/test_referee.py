"""Hakem testleri: test surucusunun yolunu kinematik simulasyonda surup puanlari kontrol eder."""

import math
import os

import pytest
import yaml

from ugv_course import geometry as g
from ugv_course.path_follower import parse_waypoints, PathFollower, Waypoint
from ugv_course.referee import Referee
from ugv_course.slider import triangle_position

HERE = os.path.dirname(os.path.abspath(__file__))
L = g.load_layout()
SL = L['slider']


def path(skip_stops=False, cone_shift=0.0):
    p = yaml.safe_load(open(os.path.join(HERE, '..', 'config', 'course_path.yaml')))
    wps = parse_waypoints(p['course_tester']['ros__parameters']['waypoints'])
    out = []
    for w in wps:
        wait = '' if skip_stops and w.wait.startswith('stop:') else w.wait
        y = w.y + (cone_shift if w.stage == 5 else 0.0)
        out.append(Waypoint(w.x, y, w.speed, w.stage, wait))
    return out


def drive(wps, shooting=None):
    """Kinematik surus + hakem. shooting(t, ref, pose) taret/lazer durumunu dondurur."""
    f, ref = PathFollower(wps), Referee(L, autonomous=True)
    x, y, yaw = L['start']
    v = w = 0.0
    dt, t = 0.05, 0.0
    log = []
    for _ in range(int(500 / dt)):
        sy = triangle_position(t, SL['amp'], SL['speed'])
        z = L['ramps']['h'] if L['ramps']['rc'] <= x <= L['ramps']['rb'] and abs(y - 6) < 1 else 0
        pan, tilt, laser, hold = 0.0, 0.0, False, False
        if shooting and f.st.state == 'STOP_WAIT' and f.st.stage == 9:
            pan, tilt, laser = shooting(t, (x, y, z, yaw))
        vc, wc = f.update(x, y, yaw, t, v, sy)
        if hold:
            vc = wc = 0.0
        v += max(-dt, min(dt, vc - v))
        w += max(-4 * dt, min(4 * dt, wc - w))
        x += v * math.cos(yaw) * dt
        y += v * math.sin(yaw) * dt
        yaw += w * dt
        t += dt
        log += ref.update(t, x, y, z, yaw, pan, tilt, laser, sy, target_seen=True)
        if f.st.state == 'FINISHED':
            break
    return ref, log


def test_clean_run_scores_all_stages():
    ref, log = drive(path())
    assert ref.finish_t is not None, log
    assert ref.passed == {1: 10, 2: 5, 3: 5, 4: 5, 5: 50, 6: 50, 7: 5, 8: 0, 9: 0, 10: 15}
    assert ref.cone_contacts == 0 and ref.barrier_contacts == 0 and not ref.slider_contact
    assert ref.total() == 145 + 10                   # + otonom hedef tespiti


def test_skipping_stop_lines_loses_ramp_points():
    ref, _ = drive(path(skip_stops=True))
    assert ref.passed[10] == 0 and not any(ref.stop_ok.values())


def test_cone_contacts_are_penalized():
    ref, _ = drive(path(cone_shift=0.12))
    assert ref.cone_contacts >= 1
    assert ref.passed[5] == 50 - 5 * ref.cone_contacts


def _aim(pose, compensate):
    """Kamerayi hedefe cevir; compensate: lazer kameranin 2 cm altinda, hedefin 2 cm ustune bak."""
    x, y, z, yaw = pose
    pan = tilt = 0.0
    for _ in range(40):
        v = g.camera_view_of_target(L, x, y, z, yaw, pan, tilt)
        th = math.tan(0.125)
        pan -= math.atan(v[0] * th)
        tilt += math.atan(v[1] * th * 0.75)
    if compensate:
        hit = g.laser_hit(L, x, y, z, yaw, pan, tilt)
        dist = x - L['target']['x']
        tilt -= math.atan(-hit[1] / dist)
    return pan, tilt


def shooter(compensate=True, duration=1.3, move=False):
    state = {}

    def fn(t, pose):
        if 'pan' not in state:
            state['pan'], state['tilt'] = _aim(pose, compensate)
            state['t0'] = t + 0.5
        on = state['t0'] <= t <= state['t0'] + duration
        pan = state['pan'] + (0.05 if move and t > state['t0'] + 0.5 else 0.0)
        return pan, state['tilt'], on
    return fn


@pytest.mark.parametrize('compensate,expected', [(True, 50), (False, 25)])
def test_shot_scoring_depends_on_laser_offset_compensation(compensate, expected):
    ref, log = drive(path(), shooter(compensate))
    assert ref.shots == [expected], log


def test_short_laser_does_not_score():
    ref, _ = drive(path(), shooter(duration=0.6))
    assert ref.shots == [0]


def test_moving_turret_with_laser_on_is_penalized():
    ref, log = drive(path(), shooter(move=True))
    assert ref.laser_violation and ref.shots == []
    assert any('-10' in e for e in log)
