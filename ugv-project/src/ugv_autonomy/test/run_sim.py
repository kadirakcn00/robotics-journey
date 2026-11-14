"""Otonom gorevi 2B simulatorde hakemle birlikte calistirir (testler ve elle deneme icin)."""

import copy
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sim2d import Sim  # noqa: E402
from ugv_autonomy.mission import Mission  # noqa: E402
from ugv_course import geometry as g  # noqa: E402
from ugv_course.referee import Referee  # noqa: E402


def load_path(run='main'):
    p = os.path.join(HERE, '..', '..', 'ugv_course', 'config', 'course_path.yaml')
    prm = yaml.safe_load(open(p))['course_tester']['ros__parameters']
    return prm['accel_waypoints' if run == 'accel' else 'waypoints']


def run(run='main', cones=None, slip=0.02, turn_eff=0.9, slider_phase=0.0, correct=True,
        t_max=600.0, dt=0.05, verbose=False):
    layout = g.load_layout()
    world = copy.deepcopy(layout)                      # gercek dunya (hakem + simulator)
    if cones is not None:
        world['cones'] = cones                         # hakem konilerin yerini degistirdi
    m = Mission(layout, load_path(run), run=run)       # gorev haritadaki konileri bilmez
    if not correct:
        m.loc.correct_with_scan = lambda *a, **k: (0.0, 0.0)
        m.loc.correct_with_slope = lambda *a, **k: None
    start = m.loc.x, m.loc.y, m.loc.yaw
    sim = Sim(world, start, slip=slip, turn_eff=turn_eff, slider_phase=slider_phase)
    ref = Referee(world, autonomous=True, run=run)
    odom_v, events, max_err = 0.0, [], 0.0
    cmd = {'v': 0, 'w': 0, 'pan': 0, 'tilt': 0, 'laser': False}
    while sim.t < t_max:
        t = sim.t
        tv = sim.target_view()
        if tv is not None:
            m.on_target(t, *tv)
        yaw, nose = sim.imu()
        cmd = m.step(t, dt, odom_v, yaw, nose, sim.scan())
        odom_v = sim.step(cmd['v'], cmd['w'], cmd['pan'], cmd['tilt'], dt)
        events += ref.update(sim.t, sim.x, sim.y, sim.z(), sim.yaw, sim.pan, sim.tilt,
                             cmd['laser'], sim.slider_y(), target_seen=tv is not None)
        max_err = max(max_err, math.hypot(m.loc.x - sim.x, m.loc.y - sim.y))
        if verbose and int(t / dt) % 200 == 0:
            print(f'{t:6.1f} {cmd["status"]}')
        if cmd['finished'] or cmd['stuck'] or ref.finish_t is not None and run == 'main':
            break
    return {'ref': ref, 'mission': m, 'sim': sim, 'events': events, 'max_err': max_err,
            'cmd': cmd}


if __name__ == '__main__':
    r = run(verbose=True)
    print('\n'.join(r['events']))
    print('\n'.join(r['ref'].summary(r['sim'].t)))
    print('max konum hatasi', round(r['max_err'], 3), '| gorev notlari:', r['mission'].log)
