"""Otonom kodu ROS ve Gazebo olmadan test etmek icin 2B parkur simulatoru.

Uretilen sensor verileri, Gazebo'daki karsiliklarina benzer:
    LIDAR   : on tamponda, +-90 derece, 181 isin; bariyerlere, konilere ve kayar engele
              isin izleme (ray casting). Robot rampada/platformdayken bariyerlerin ustunden
              bakar (isabet yok); asagi egimliyken zemine carpar (sahte noktalar).
    IMU     : yon (kucuk gurultu) ve egim (on/arka aks yuksekliklerinden)
    odometri: tekerlek hizi; gercek hareket %slip daha az (konum tahmini kayar)
    hedef   : nisan kamerasinda hedef merkezi (geometri + gurultu)
Robot hareketi: ivme sinirli, donuste kayma (skid-steer komut edilenden az doner),
havuzda su fizigi (ugv_course.water).
"""

import math

import numpy as np

from ugv_course import geometry as g
from ugv_course.slider import triangle_position
from ugv_course.water import WaterModel, WaterZone

LIDAR_X, LIDAR_H = 0.30, 0.20
N_RAYS = 181


class Sim:

    def __init__(self, layout, start, slip=0.02, turn_eff=0.9, slider_phase=0.0, seed=0,
                 lidar=True):
        self.L = layout
        self.x, self.y, self.yaw = start
        self.v = self.w = 0.0
        self.pan = self.tilt = 0.0
        self.t = 0.0
        self.slip, self.turn_eff = slip, turn_eff
        self.slider_phase = slider_phase
        self.rng = np.random.default_rng(seed)
        self.lidar_on = lidar
        b = np.array(layout['barriers'], dtype=float)
        self.seg_a, self.seg_e = b[:, 0:2], b[:, 2:4] - b[:, 0:2]
        p = layout['pool']
        rows = layout['road']['rows']
        self.water = WaterModel([WaterZone(p['x0'], p['x1'], rows['A'][0] - 0.6,
                                           rows['A'][0] + 0.6, p['depth'], p['ramp'])],
                                robot_height=0.30)
        self.angles = np.linspace(-math.pi / 2, math.pi / 2, N_RAYS)

    # ---------------------------------------------------------------- arazi
    def ground(self, x, y):
        """Zemin yuksekligi (m): rampa/platform, havuz."""
        L = self.L
        rows = L['road']['rows']
        rp, pool = L['ramps'], L['pool']
        if abs(y - rows['C'][0]) < 0.6:
            if rp['rb'] <= x <= rp['ra']:
                return rp['h'] * (rp['ra'] - x) / (rp['ra'] - rp['rb'])
            if rp['rc'] <= x <= rp['rb']:
                return rp['h']
            if rp['rd'] <= x <= rp['rc']:
                return rp['h'] * (x - rp['rd']) / (rp['rc'] - rp['rd'])
        if abs(y - rows['A'][0]) < 0.6 and pool['x0'] <= x <= pool['x1']:
            edge = min(x - pool['x0'], pool['x1'] - x)
            return -pool['depth'] * min(1.0, edge / pool['ramp'])
        return 0.0

    def pitch_nose_up(self):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        hf = self.ground(self.x + 0.16 * c, self.y + 0.16 * s)
        hr = self.ground(self.x - 0.16 * c, self.y - 0.16 * s)
        return math.atan2(hf - hr, 0.32)

    def z(self):
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return 0.5 * (self.ground(self.x + 0.16 * c, self.y + 0.16 * s)
                      + self.ground(self.x - 0.16 * c, self.y - 0.16 * s))

    def slider_y(self):
        sl = self.L['slider']
        return triangle_position(self.t, sl['amp'], sl['speed'], self.slider_phase)

    # ---------------------------------------------------------------- sensorler
    def scan(self):
        if not self.lidar_on:
            return None
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        o = np.array([self.x + LIDAR_X * c, self.y + LIDAR_X * s])
        ang = self.yaw + self.angles
        d = np.stack([np.cos(ang), np.sin(ang)], axis=1)            # (R, 2)
        ranges = np.full(N_RAYS, np.inf)
        pitch = self.pitch_nose_up()
        lidar_z = self.z() + LIDAR_H
        if pitch < -math.radians(6):                                # asagi egim: zemin
            hit = LIDAR_H / math.sin(-pitch)
            ranges[np.abs(self.angles) < math.radians(40)] = hit
        if lidar_z < 0.30 and abs(pitch) < math.radians(15):         # bariyerler gorunur
            segs_a, segs_e = [self.seg_a], [self.seg_e]
            sl = self.L['slider']
            cx, cy = sl['x'], sl['row_y'] + self.slider_y()
            hx, hy = sl['thick'] / 2, sl['width'] / 2
            corners = [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy),
                       (cx - hx, cy + hy)]
            for i in range(4):
                a, b = np.array(corners[i]), np.array(corners[(i + 1) % 4])
                segs_a.append(a[None]), segs_e.append((b - a)[None])
            A, E = np.concatenate(segs_a), np.concatenate(segs_e)
            ao = A - o                                                # (S, 2)
            den = d[:, None, 0] * E[None, :, 1] - d[:, None, 1] * E[None, :, 0]
            with np.errstate(divide='ignore', invalid='ignore'):
                tt = (ao[None, :, 0] * E[None, :, 1] - ao[None, :, 1] * E[None, :, 0]) / den
                uu = (ao[None, :, 0] * d[:, None, 1] - ao[None, :, 1] * d[:, None, 0]) / den
            ok = (tt > 0) & (uu >= 0) & (uu <= 1)
            tt = np.where(ok, tt, np.inf)
            nb = len(self.seg_a)
            bar = tt[:, :nb].min(1) - 0.02                            # bariyer yuzeyi
            ranges = np.minimum(ranges, np.minimum(bar, tt[:, nb:].min(1)))
            r = self.L['cone']['r_at_lidar']
            for cx, cy in self.L['cones']:
                f = o - np.array([cx, cy])
                bq = d @ f
                disc = bq * bq - (f @ f - r * r)
                th = -bq - np.sqrt(np.maximum(disc, 0))
                ranges = np.where((disc >= 0) & (th > 0), np.minimum(ranges, th), ranges)
        ranges = ranges + self.rng.normal(0, 0.005, N_RAYS)
        ranges[ranges > 10.0] = np.inf
        return ranges, -math.pi / 2, math.pi / (N_RAYS - 1)

    def imu(self):
        return self.yaw + self.rng.normal(0, 0.002), self.pitch_nose_up()

    def target_view(self):
        v = g.camera_view_of_target(self.L, self.x, self.y, self.z(), self.yaw, self.pan,
                                    self.tilt)
        if v is None or v[2] < 4:
            return None
        return v[0] + self.rng.normal(0, 0.002), v[1] + self.rng.normal(0, 0.002), v[2]

    # ---------------------------------------------------------------- hareket
    def step(self, v_cmd, w_cmd, pan, tilt, dt):
        v_cmd, w_cmd = self.water.step(v_cmd, w_cmd, self.x, self.y, dt)
        self.v += max(-1.0 * dt, min(1.0 * dt, v_cmd - self.v))
        self.w += max(-4.0 * dt, min(4.0 * dt, w_cmd - self.w))
        v_true = self.v * (1 - self.slip)
        self.x += v_true * math.cos(self.yaw) * dt
        self.y += v_true * math.sin(self.yaw) * dt
        self.yaw += self.w * self.turn_eff * dt
        # Taret: konum kontrolcusu, hizli ama aninda degil
        self.pan += max(-2.0 * dt, min(2.0 * dt, pan - self.pan))
        self.tilt += max(-2.0 * dt, min(2.0 * dt, tilt - self.tilt))
        self.t += dt
        return self.v                                                  # odometri hizi
