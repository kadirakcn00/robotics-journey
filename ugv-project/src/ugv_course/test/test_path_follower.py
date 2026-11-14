"""Test surucusunu parkurda kinematik bir simulasyonla bastan sona surer (ROS gerektirmez).

Fizik (egim, tutunma) burada yok; bu test yolun geometrisini dogrular: robot yolun icinde
kalir mi, konilere/kayar engele carpar mi, stop cizgilerinde bekler mi, bitise varir mi.
"""

import math
import os
import sys

import pytest
import yaml

from ugv_course.path_follower import parse_waypoints, PathFollower
from ugv_course.slider import triangle_position

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import make_teknofest_course as course  # noqa: E402

FOOT = (0.35, -0.30, 0.21)        # robot ayak izi: on, arka, yari genislik (m)
WHEELS = (0.28, -0.28, 0.19)      # zemin seviyesinde sadece tekerlekler var
CONE_R = 0.045                    # koni govdesi (carpisma silindiri)
CONE_PLATE = 0.08                 # koninin 16 x 16 cm taban plakasinin yarisi


def corners(x, y, yaw, foot=FOOT):
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for fx in (foot[0], foot[1]):
        for fy in (foot[2], -foot[2]):
            out.append((x + c * fx - s * fy, y + s * fx + c * fy))
    return out


def inside_road(px, py):
    """Nokta yolun icinde mi? (bariyerlerin ic yuzeyi = yol kenari)"""
    half = course.HALF
    rows = ((course.ROW_A, 0.0, course.ROW_LEN), (course.ROW_B, 0.0, course.ROW_LEN),
            (course.ROW_C, course.ROW_C_END, course.ROW_LEN))
    for row, x0, x1 in rows:
        if x0 <= px <= x1 and abs(py - row) <= half:
            return True
    for (cx, cy), side in (((0.0, (course.ROW_A + course.ROW_B) / 2), -1),
                           ((course.ROW_LEN, (course.ROW_B + course.ROW_C) / 2), 1)):
        if (px - cx) * side >= 0:
            r = math.hypot(px - cx, py - cy)
            if course.TURN_R - half <= r <= course.TURN_R + half:
                return True
    return False


def cone_positions():
    return [(x, course.ROW_B + (course.CONE_Y if i % 2 == 0 else -course.CONE_Y))
            for i, x in enumerate(course.CONE_XS)]


def foot_hits_circle(x, y, yaw, cx, cy, r, foot=FOOT):
    c, s = math.cos(yaw), math.sin(yaw)
    dx, dy = cx - x, cy - y
    fx, fy = c * dx + s * dy, -s * dx + c * dy
    nx = min(max(fx, foot[1]), foot[0])
    ny = min(max(fy, -foot[2]), foot[2])
    return math.hypot(fx - nx, fy - ny) < r


def hits_cone(x, y, yaw, cx, cy):
    """Govde: tum robot vs koni silindiri. Taban: tekerlekler vs taban plakasi (kare)."""
    if foot_hits_circle(x, y, yaw, cx, cy, CONE_R):
        return True
    for px, py in corners(x, y, yaw, WHEELS):
        if abs(px - cx) < CONE_PLATE and abs(py - cy) < CONE_PLATE:
            return True
    return foot_hits_circle(x, y, yaw, cx, cy, CONE_PLATE, WHEELS)


def foot_hits_slider(x, y, yaw, slider_y):
    """Kayar engel paneli: x = SLIDER_X +- 0.04, y = ROW_B + slider_y +- 0.2"""
    for px, py in corners(x, y, yaw) + [(x, y)]:
        if abs(px - course.SLIDER_X) < 0.04 + 0.01 and \
                abs(py - (course.ROW_B + slider_y)) < course.SLIDER_W / 2 + 0.01:
            return True
    # Panel koseleri robotun icinde mi?
    for sx in (course.SLIDER_X - 0.04, course.SLIDER_X + 0.04):
        for sy in (slider_y - 0.2, slider_y + 0.2):
            if foot_hits_circle(x, y, yaw, sx, course.ROW_B + sy, 0.001):
                return True
    return False


def load_path(skip_slider_wait=False):
    path = os.path.join(HERE, '..', 'config', 'course_path.yaml')
    lines = yaml.safe_load(open(path))['course_tester']['ros__parameters']['waypoints']
    if skip_slider_wait:
        lines = [line.replace(', slider', ', ') for line in lines]
    return parse_waypoints(lines)


def simulate(wps, slider_phase=0.0):
    f = PathFollower(wps)
    x, y, yaw = 7.5, 0.0, math.pi
    v = w = 0.0
    dt, t = 0.05, 0.0
    log = {'off_road': [], 'cone': [], 'slider': [], 'stops': {}}
    stop_started = None
    for _ in range(int(600 / dt)):
        slider_y = triangle_position(t, course.SLIDER_AMP, course.SLIDER_SPEED, slider_phase)
        v_cmd, w_cmd = f.update(x, y, yaw, t, v, slider_y)
        # Basit arac modeli: ivme sinirli
        v += max(-1.0 * dt, min(1.0 * dt, v_cmd - v))
        w += max(-4.0 * dt, min(4.0 * dt, w_cmd - w))
        x += v * math.cos(yaw) * dt
        y += v * math.sin(yaw) * dt
        yaw += w * dt
        t += dt
        for px, py in corners(x, y, yaw):
            if not inside_road(px, py):
                log['off_road'].append((round(t, 1), round(px, 2), round(py, 2)))
        for cx, cy in cone_positions():
            if hits_cone(x, y, yaw, cx, cy):
                log['cone'].append((round(t, 1), cx, cy))
        if foot_hits_slider(x, y, yaw, slider_y):
            log['slider'].append((round(t, 1), round(slider_y, 2)))
        if f.st.state == 'STOP_WAIT' and abs(v) < 1e-3:
            stop_started = stop_started if stop_started is not None else t
        elif stop_started is not None:
            log['stops'][round(x, 2)] = t - stop_started
            stop_started = None
        if f.st.state in ('FINISHED', 'STUCK'):
            break
    log['state'] = f.st.state
    log['time'] = t
    log['stage_times'] = f.st.stage_times
    return log


@pytest.fixture(scope='module')
def run_result():
    return simulate(load_path())


def test_reaches_finish(run_result):
    assert run_result['state'] == 'FINISHED', run_result
    assert run_result['time'] < 15 * 60                        # 15 dk siniri


def test_stays_on_road(run_result):
    assert run_result['off_road'] == [], run_result['off_road'][:10]


def test_no_cone_contact(run_result):
    assert run_result['cone'] == [], run_result['cone'][:10]


PHASES = [k * 5.0 for k in range(8)]      # kayar engel 8 farkli baslangic aninda


@pytest.mark.parametrize('phase', PHASES)
def test_no_slider_contact_any_timing(phase):
    log = simulate(load_path(), phase)
    assert log['state'] == 'FINISHED'
    assert log['slider'] == [], log['slider'][:5]


def test_not_waiting_for_slider_would_collide():
    """Testin carpismayi gercekten yakalayabildigini gosterir."""
    hits = [simulate(load_path(skip_slider_wait=True), p)['slider'] for p in PHASES]
    assert any(hits)


def test_waits_at_stop_lines(run_result):
    waits = sorted(run_result['stops'].values())
    assert len(waits) == 3, run_result['stops']                # cikis, atis, inis
    assert min(waits) >= 2.0


def test_passes_all_stages_in_order(run_result):
    times = run_result['stage_times']
    order = [k for k in sorted(times, key=lambda k: times[k]) if k != 'finish']
    assert order == sorted(order) and set(range(1, 12)) <= set(order)


def test_stuck_detection():
    wps = parse_waypoints(['0, 0, 0.2, 1, ', '5, 0, 0.2, 1, ', '6, 0, 0.2, 1, finish'])
    f = PathFollower(wps, stuck_time=3.0)
    for k in range(100):                                       # komut var, robot kipirdamiyor
        f.update(0.0, 0.0, 0.0, k * 0.05, 0.0)
    assert f.st.state == 'STUCK' and 'asama 1' in f.st.message
