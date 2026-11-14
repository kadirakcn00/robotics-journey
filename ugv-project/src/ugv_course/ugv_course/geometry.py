"""Parkur geometrisi: yol siniri, temas kontrolleri ve taret (lazer / nisan kamerasi) kinematigi.

Hakem, simulator ve otonom kod ayni hesaplari kullanir. Parkur olculeri
config/course_layout.yaml dosyasindan okunur (make_teknofest_course.py uretir).
"""

import math
import os

import numpy as np

FOOT = (0.35, -0.30, 0.21)        # robot ayak izi: on (LIDAR dahil), arka, yari genislik (m)
WHEELS = (0.28, -0.28, 0.19)      # zemin seviyesinde sadece tekerlekler


def load_layout(path=None):
    import yaml
    if path is None:
        path = os.path.join(os.path.dirname(__file__), '..', 'config', 'course_layout.yaml')
        if not os.path.exists(path):
            from ament_index_python.packages import get_package_share_directory
            path = os.path.join(get_package_share_directory('ugv_course'), 'config',
                                'course_layout.yaml')
    with open(path) as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------------- ayak izi
def corners(x, y, yaw, foot=FOOT):
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + c * fx - s * fy, y + s * fx + c * fy)
            for fx in (foot[0], foot[1]) for fy in (foot[2], -foot[2])]


def foot_hits_circle(x, y, yaw, cx, cy, r, foot=FOOT):
    c, s = math.cos(yaw), math.sin(yaw)
    dx, dy = cx - x, cy - y
    fx, fy = c * dx + s * dy, -s * dx + c * dy
    nx = min(max(fx, foot[1]), foot[0])
    ny = min(max(fy, -foot[2]), foot[2])
    return math.hypot(fx - nx, fy - ny) < r


def inside_road(L, px, py):
    """Nokta yolun icinde mi: ana parkur siralari, U donusleri ve hizlanma parkuru."""
    rd = L['road']
    half = rd['half']
    for row_y, x0, x1, _ in rd['rows'].values():
        if x0 <= px <= x1 and abs(py - row_y) <= half:
            return True
    for cx, cy, side in rd['turns']:
        if (px - cx) * side >= 0:
            r = math.hypot(px - cx, py - cy)
            if rd['turn_r'] - half <= r <= rd['turn_r'] + half:
                return True
    a = L['accel']
    return a['x0'] <= px <= a['line'] + a['stop_zone'] and abs(py - a['row_y']) <= half


def hits_barrier(L, x, y, yaw):
    return any(not inside_road(L, px, py) for px, py in corners(x, y, yaw))


def hits_cone(L, x, y, yaw, cx, cy):
    """Govde: tum robot vs koni govdesi. Taban: tekerlekler vs taban plakasi."""
    cone = L['cone']
    if foot_hits_circle(x, y, yaw, cx, cy, cone['body_r']):
        return True
    return foot_hits_circle(x, y, yaw, cx, cy, cone['plate_half'], WHEELS)


def hits_slider(L, x, y, yaw, slider_y):
    sl = L['slider']
    cx, cy = sl['x'], sl['row_y'] + slider_y
    hx, hy = sl['thick'] / 2, sl['width'] / 2
    c, s = math.cos(yaw), math.sin(yaw)
    # panelin koseleri robotun icinde mi, robotun koseleri panelin icinde mi?
    for px, py in corners(x, y, yaw):
        if abs(px - cx) <= hx and abs(py - cy) <= hy:
            return True
    for sx in (cx - hx, cx + hx):
        for sy in (cy - hy, cy + hy):
            dx, dy = sx - x, sy - y
            fx, fy = c * dx + s * dy, -s * dx + c * dy
            if FOOT[1] <= fx <= FOOT[0] and abs(fy) <= FOOT[2]:
                return True
    return False


# ----------------------------------------------------------------------------- taret
def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def turret_frame(L, x, y, z, yaw, pan, tilt):
    """Tilt kafasinin dunyadaki konumu ve donusu (R: kafa -> dunya)."""
    t = L['turret']
    r_base = _rz(yaw)
    r_pan = r_base @ _rz(pan)
    origin = np.array([x, y, z]) + r_base @ np.array(t['pan_xyz']) \
        + r_pan @ np.array([0.0, 0.0, t['tilt_dz']])
    return origin, r_pan @ _ry(tilt)          # pozitif tilt = asagi


def laser_ray(L, x, y, z, yaw, pan, tilt):
    origin, rot = turret_frame(L, x, y, z, yaw, pan, tilt)
    return origin + rot @ np.array(L['turret']['laser']), rot @ np.array([1.0, 0.0, 0.0])


def laser_hit(L, x, y, z, yaw, pan, tilt):
    """Lazerin hedef kagidina degdigi nokta: (dy, dz) hedef merkezine gore (m) ya da None."""
    tg = L['target']
    o, d = laser_ray(L, x, y, z, yaw, pan, tilt)
    if abs(d[0]) < 1e-9:
        return None
    s = (tg['x'] - o[0]) / d[0]
    if s <= 0:
        return None
    hit = o + s * d
    dy, dz = hit[1] - tg['y'], hit[2] - tg['z']
    if abs(dy) > tg['width'] / 2 or abs(dz) > tg['height'] / 2:
        return (dy, dz)                         # kagidin disi (puan 0)
    return (dy, dz)


def ring_points(L, hit):
    """Isabet noktasina gore puan. Cizgi uzerindeki atis yuksek puanli halkaya sayilir."""
    if hit is None:
        return 0
    r = math.hypot(*hit)
    for radius, points in zip(L['target']['rings'], L['target']['points']):
        if r <= radius + 1e-9:
            return points
    return 0


def camera_view_of_target(L, x, y, z, yaw, pan, tilt):
    """Nisan kamerasinda hedef merkezi: (dx, dy, yaricap_px) ya da gorunmuyorsa None.

    dx, dy [-1, 1]: goruntu merkezine gore (dx > 0 sag, dy > 0 asagi), target_detector ile ayni.
    """
    t, tg = L['turret'], L['target']
    origin, rot = turret_frame(L, x, y, z, yaw, pan, tilt)
    cam = origin + rot @ np.array(t['camera'])
    v = rot.T @ (np.array([tg['x'], tg['y'], tg['z']]) - cam)    # kafa cercevesinde
    if v[0] <= 0.1:
        return None
    th = math.tan(t['camera_hfov'] / 2)
    tv = th * t['image_h'] / t['image_w']
    dx = (-v[1] / v[0]) / th
    dy = (-v[2] / v[0]) / tv
    if abs(dx) > 0.95 or abs(dy) > 0.95:
        return None
    r_px = (tg['rings'][2] / v[0]) / th * (t['image_w'] / 2)
    return dx, dy, r_px
