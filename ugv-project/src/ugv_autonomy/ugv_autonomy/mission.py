"""Otonom gorev (ROS'tan bagimsiz): parkuru robotun kendi sensorleriyle bastan sona surer.

Kullanilan bilgiler: odometri hizi, IMU (yon + egim), LIDAR, nisan kamerasindaki hedef,
harita (course_layout.yaml) ve yol (course_path.yaml). Gercek konum ve kayar engelin komutu
KULLANILMAZ.

Davranislar:
    yol takibi      : Pure Pursuit (ugv_course.path_follower), tahmini konumla
    koniler         : LIDAR'daki engellere gore yanal kaydirma (hakem konileri tasiyabilir)
    kayar engel     : LIDAR ile konum + yon izlenir, bosluk acilinca gecilir
    stop cizgileri  : 2.5 s tam durma (yoldaki 'stop:' noktalari)
    atis            : kaba nisan (harita) -> kamera ile ince ayar (lazer-kamera farki
                      telafili) -> robot ve taret sabitken lazer 1.4 s
"""

import math

import numpy as np

from ugv_course import geometry as g
from ugv_course.path_follower import parse_waypoints, PathFollower, Waypoint

from ugv_autonomy.localization import Localizer
from ugv_autonomy.obstacles import avoid_lateral, obstacle_points, SliderWatcher


class Shooter:
    """Atis durum makinesi: coarse -> settle -> servo -> fire -> done."""

    def __init__(self, layout, fire_time=1.4, timeout=30.0):
        self.L = layout
        t = layout['turret']
        self.th = math.tan(t['camera_hfov'] / 2)
        self.tv = self.th * t['image_h'] / t['image_w']
        self.dz = t['camera'][2] - t['laser'][2]          # lazer kameranin bu kadar altinda
        self.fire_time = fire_time
        self.timeout = timeout
        self.reset()

    def reset(self):
        self.phase = 'coarse'
        self.pan = self.tilt = 0.0
        self.t_phase = None
        self.good = 0
        self.last_target_t = None
        self.msg = ''
        if hasattr(self, 'pan0'):
            del self.pan0

    def _goto(self, phase, t):
        self.phase, self.t_phase = phase, t

    def step(self, t, pose, target, target_t):  # noqa: C901 (durum makinesi)
        """Bir adim: pose (x, y, z, yaw) tahmini, target (dx, dy, r_px) ya da None.

        Lazer acik mi (bool) dondurur; pan/tilt self.pan / self.tilt'tedir.
        """
        if self.t_phase is None:
            self.t_start = t
            self.t_phase = t
        if t - self.t_start > self.timeout and self.phase not in ('fire', 'done'):
            self.msg = 'atis zaman asimi: hedef bulunamadi'
            self._goto('done', t)
        if self.phase == 'coarse':
            # Hedefin haritadaki yerine gore pan/tilt (tahmini konumla, kameradan bakis)
            x, y, z, yaw = pose
            for _ in range(30):
                v = g.camera_view_of_target(self.L, x, y, z, yaw, self.pan, self.tilt)
                if v is None:
                    tg = self.L['target']
                    self.pan = math.atan2(tg['y'] - y, tg['x'] - x) - yaw
                    continue
                self.pan -= math.atan(v[0] * self.th)
                self.tilt += math.atan(v[1] * self.tv)
            self.msg = f'kaba nisan: pan {self.pan:+.3f} tilt {self.tilt:+.3f}'
            self._goto('settle', t)
            return False
        if self.phase == 'settle':
            if t - self.t_phase > 1.0:
                self._goto('servo', t)
            return False
        if self.phase == 'servo':
            if target is not None and target_t != self.last_target_t:
                self.last_target_t = target_t
                dx, dy, r_px = target
                # Uzaklik hedefin goruntudeki boyutundan: r_px = (R / d) / tan(hfov/2) * W/2
                dist = self.L['target']['rings'][2] / max(1e-6, r_px / 320.0 * self.th)
                # Lazer kameranin dz altinda: merkeze vursun diye hedef goruntude bu kadar asagida
                dy0 = (self.dz / dist) / self.tv
                e_pan = -math.atan(dx * self.th)
                e_tilt = math.atan((dy - dy0) * self.tv)
                self.pan += 0.6 * e_pan
                self.tilt += 0.6 * e_tilt
                self.good = self.good + 1 if abs(e_pan) < 0.0015 and abs(e_tilt) < 0.0015 else 0
                self.msg = (f'ince ayar: hata pan {e_pan * 1000:+.1f} mrad, '
                            f'tilt {e_tilt * 1000:+.1f} mrad, uzaklik {dist:.2f} m')
                if self.good >= 4:
                    self._goto('fire', t)
            elif target is None and t - self.t_phase > 3.0:
                # Hedef gorunmuyor: kaba nisan acisi etrafinda yavasca sag-sol tara
                if not hasattr(self, 'pan0'):
                    self.pan0 = self.pan
                self.pan = self.pan0 + 0.12 * math.sin(0.8 * (t - self.t_phase))
                self.msg = 'hedef araniyor'
            return False
        if self.phase == 'fire':
            if t - self.t_phase < self.fire_time:
                self.msg = f'LAZER {t - self.t_phase:.1f} s'
                return True
            self._goto('done', t)
            self.msg = 'atis tamam'
            return False
        return False

    @property
    def done(self):
        return self.phase == 'done'


class Mission:

    def __init__(self, layout, path_lines, run='main'):
        self.L = layout
        self.run = run
        wps = parse_waypoints(path_lines)
        if run == 'main':
            # Atis bolgesindeki bekleme -> otonom atis
            wps = [Waypoint(w.x, w.y, w.speed, w.stage,
                            'shoot' if w.stage == 9 and w.wait.startswith('stop:') else w.wait)
                   for w in wps]
            start = layout['start']
        else:
            a = layout['accel']
            start = [a['spawn_x'], a['row_y'], 0.0]
        sl = layout['slider']
        self.slider = SliderWatcher(sl['x'], sl['row_y'])
        self.follower = PathFollower(wps, brake=0.7 if run == 'accel' else 0.8,
                                     slider_clear=lambda _y: self.slider.clear())
        self.loc = Localizer(layout, start)
        self.shooter = Shooter(layout)
        self.offset = 0.0
        self.memory = {}          # koni bolgesinde gorulen engel noktalari: 5 cm hucre -> (x, y)
        self.pts = None
        self.target = None
        self.target_t = None
        self.signs = []
        self.log = []

    def on_scan(self, ranges, angle_min, angle_inc):
        self.scan = (ranges, angle_min, angle_inc)

    def on_target(self, t, dx, dy, r_px):
        self.target, self.target_t = (dx, dy, r_px), t

    def on_sign(self, t, number):
        if not self.signs or self.signs[-1][1] != number:
            self.signs.append((t, number))

    def _note(self, t, text):
        self.log.append((t, text))

    def step(self, t, dt, odom_v, imu_yaw, nose_up, scan=None):
        """Bir kontrol adimi. Doner: dict(v, w, pan, tilt, laser, status)."""
        loc, f = self.loc, self.follower
        loc.predict(odom_v, imu_yaw, dt)
        ev = loc.correct_with_slope(nose_up)
        if ev:
            self._note(t, f'egim: {loc.last_fix}')
        pts = []
        if scan is not None:
            pts = loc.scan_points_world(*scan)
            if abs(nose_up) < math.radians(6):           # egimde LIDAR zemine/gokyuzune bakar
                loc.correct_with_scan(pts)
                pts = loc.scan_points_world(*scan)
            else:
                pts = pts[:0]
        self.slider.update(t, pts)

        # Koniler: LIDAR'daki engellere gore yanal kaydirma. Konilerin 1 m oncesinden kayar
        # engele 0.6 m kalana kadar (kayar engel kacinilmaz, beklenir)
        rows = self.L['road']['rows']
        s5 = next(st for st in self.L['stages'] if st[0] == 5)
        cone_zone = (abs(loc.y - rows['B'][0]) < 0.7 and abs(loc.yaw) < math.radians(60)
                     and s5[3] - 1.0 <= loc.x <= self.L['slider']['x'] - 0.6)
        target_off = 0.0
        if not cone_zone:
            self.memory.clear()
        if cone_zone:
            # Engel hafizasi: LIDAR on tamponda ve +-90 derece gorur; robot bir koninin
            # yanina gelince koni gorus disinda kalir. Gorulen noktalar dunyada saklanir.
            row_y = rows['B'][0]
            # Kayar engelin paneli koni degildir: ondan kacilmaz, beklenir
            x_max = self.L['slider']['x'] - 0.3
            for px, py in (pts if len(pts) else []):
                if abs(py - row_y) < 0.5 and px - loc.x < 1.6 and px < x_max:
                    self.memory[(round(px / 0.05), round(py / 0.05))] = (px, py)
            mem = np.array(list(self.memory.values())) if self.memory else np.zeros((0, 2))
            obs = obstacle_points(mem, row_y, 1, loc.x, ahead=(-0.45, 1.4))
            # obstacle_points yanal konumu yol eksenine gore verir; robotun kaydirmasi
            # da yol eksenine gore oldugu icin dogrudan karsilastirilir
            free = avoid_lateral([tuple(o) for o in obs], self.offset)
            if free is not None:
                target_off = free
            else:
                target_off = self.offset
        step_max = 0.2 * dt
        self.offset += max(-step_max, min(step_max, target_off - self.offset))
        f.offset = self.offset

        slider_state = self.slider.state()
        slider_y = slider_state[0] if slider_state else None
        v, w = f.update(loc.x, loc.y, loc.yaw, t, abs(odom_v), slider_y)

        pan = tilt = 0.0
        laser = False
        if f.st.state == 'SHOOT':
            z = self.L['ramps']['h']
            fresh = self.target if self.target_t is not None and t - self.target_t < 0.3 else None
            laser = self.shooter.step(t, (loc.x, loc.y, z, loc.yaw), fresh, self.target_t)
            pan, tilt = self.shooter.pan, self.shooter.tilt
            if self.shooter.done:
                f.external_done = True
                self._note(t, self.shooter.msg)
        status = (f'{f.st.state} | asama {f.st.stage} | tahmin ({loc.x:.2f}, {loc.y:.2f}, '
                  f'{math.degrees(loc.yaw):.0f} deg) | eslesen nokta {loc.matched}'
                  + (f' | kaydirma {self.offset:+.2f}' if abs(self.offset) > 0.01 else '')
                  + (f' | {self.shooter.msg}' if f.st.state == 'SHOOT' else ''))
        return {'v': v, 'w': w, 'pan': pan, 'tilt': tilt, 'laser': laser, 'status': status,
                'finished': f.st.state == 'FINISHED', 'stuck': f.st.state == 'STUCK'}
