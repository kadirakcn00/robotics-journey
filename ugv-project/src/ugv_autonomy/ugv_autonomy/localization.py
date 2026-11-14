"""Otonom kosu icin konum tahmini (ROS'tan bagimsiz).

Gercek konum (ground truth) KULLANILMAZ. Kullanilanlar:
    odometri : tekerleklerden gidilen yol (mesafe icin iyi, donuste kayar)
    IMU      : yon (kaymaz) ve egim (havuza / rampaya girisi hissetmek icin)
    LIDAR    : bariyerler -> haritayla karsilastirip konumu duzeltmek
    harita   : config/course_layout.yaml (bariyer cizgileri, rampa ve havuz yerleri)

1) Tahmin: x += v * cos(yaw) * dt, y += v * sin(yaw) * dt  (v: odometri, yaw: IMU)
2) LIDAR duzeltmesi: her LIDAR noktasi en yakin bariyer cizgisiyle karsilastirilir. Nokta
   duvara r kadar uzaksa ve duvarin normali n ise konum d kadar kaydirildiginda kalan hata
   r + n.d olur. Tum noktalar icin toplam kare hata en kucuk olacak d bulunur:
       (sum n n^T + lam I) d = -sum n r
   Duz yolda sadece yan duvarlar gorulur: yanal (y) duzeltilir, ileri-geri bilgisi yoktur
   (lam bu yondeki duzeltmeyi sondurur). U donusu ve uc bariyerleri ileri-geri hatayi duzeltir.
3) Egim duzeltmesi: robot bir egime girdiginde (IMU egimi esigi asar) konum, haritadaki egimin
   baslangicina esitlenir (havuz girisi, rampa cikisi, rampa inisi).
"""

import math

import numpy as np

LIDAR_X = 0.30            # LIDAR'in base_link'e gore yeri (m)
FACE = 0.02               # bariyer kalinliginin yarisi: LIDAR yuzeyi gorur, harita ekseni verir
GATE = 0.15               # bariyere bundan uzak noktalar (koni, engel, zemin) kullanilmaz


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


class Localizer:

    def __init__(self, layout, start):
        self.L = layout
        self.x, self.y, self.yaw = start
        self.start_yaw = start[2]
        self.imu_yaw0 = None
        b = np.array(layout['barriers'], dtype=float)
        self.a = b[:, 0:2]
        self.ab = b[:, 2:4] - b[:, 0:2]
        self.ab2 = np.maximum((self.ab ** 2).sum(1), 1e-12)
        sl = layout['slider']
        # Hareketli engel bolgesi: haritayla karsilastirilmaz (kayar engel bariyer uclarina
        # yakin gecerken yanlis eslesip konumu ileri-geri iter)
        self.dynamic = [(sl['x'] - 0.5, sl['x'] + 0.5, sl['row_y'] - 1.0, sl['row_y'] + 1.0)]
        self.last_fix = 'baslangic'
        self.matched = 0
        self.slope_events = set()
        self.nose_up_prev = 0.0

    # ---------------------------------------------------------------- 1) tahmin
    def predict(self, v, imu_yaw, dt):
        if self.imu_yaw0 is None:
            self.imu_yaw0 = imu_yaw
        self.yaw = wrap(self.start_yaw + imu_yaw - self.imu_yaw0)
        self.x += v * math.cos(self.yaw) * dt
        self.y += v * math.sin(self.yaw) * dt

    # ---------------------------------------------------------------- 2) LIDAR
    def scan_points_world(self, ranges, angle_min, angle_inc, max_range=6.0):
        r = np.asarray(ranges, dtype=float)
        ang = angle_min + angle_inc * np.arange(len(r))
        ok = np.isfinite(r) & (r > 0.12) & (r < max_range)
        r, ang = r[ok], ang[ok]
        px = LIDAR_X + r * np.cos(ang)
        py = r * np.sin(ang)
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return np.stack([self.x + c * px - s * py, self.y + s * px + c * py], axis=1)

    def correct_with_scan(self, pts, gain=0.5, lam=8.0, max_step=0.1):
        """Bariyerlere uyan noktalarla konumu duzelt. Duzeltme vektorunu dondurur."""
        self.matched = 0
        for x0, x1, y0, y1 in self.dynamic:
            keep = ~((pts[:, 0] > x0) & (pts[:, 0] < x1) & (pts[:, 1] > y0) & (pts[:, 1] < y1))
            pts = pts[keep]
        if len(pts) == 0:
            return (0.0, 0.0)
        p = pts[:, None, :]                                    # (N, 1, 2)
        t = ((p - self.a) * self.ab).sum(2) / self.ab2         # (N, S)
        t = np.clip(t, 0.0, 1.0)
        q = self.a + t[..., None] * self.ab                    # en yakin noktalar
        diff = p - q
        dist = np.sqrt((diff ** 2).sum(2))
        k = dist.argmin(1)
        idx = np.arange(len(pts))
        dmin = dist[idx, k]
        resid = dmin - FACE                                    # yuzeye uzaklik
        use = np.abs(resid) < GATE
        if use.sum() < 8:
            return (0.0, 0.0)
        n = diff[idx, k][use] / np.maximum(dmin[use], 1e-9)[:, None]   # duvardan noktaya
        r = resid[use]
        wgt = 1.0 / (1.0 + (r / 0.05) ** 2)                    # uzak eslesmeye az guven
        a = (n * wgt[:, None]).T @ n + lam * np.eye(2)
        d = np.linalg.solve(a, -(n * (wgt * r)[:, None]).sum(0))
        d = np.clip(d * gain, -max_step, max_step)
        self.x += d[0]
        self.y += d[1]
        self.matched = int(use.sum())
        return (float(d[0]), float(d[1]))

    # ---------------------------------------------------------------- 3) egim
    def correct_with_slope(self, nose_up):
        """Egim esigini gecince (yarim egim) konumu egimin baslangicina esitle."""
        L = self.L
        rows = L['road']['rows']
        rp, pool = L['ramps'], L['pool']
        events = [
            # (ad, sira, beklenen x, kosul)
            ('havuz girisi', rows['A'][0], pool['x1'], nose_up < -math.radians(10)),
            ('rampa cikisi', rows['C'][0], rp['ra'], nose_up > math.radians(12)),
            ('rampa inisi', rows['C'][0], rp['rc'], nose_up < -math.radians(12)),
        ]
        for name, row_y, x_feat, cond in events:
            if name in self.slope_events or not cond:
                continue
            if abs(self.y - row_y) < 0.7 and abs(self.x - x_feat) < 1.2:
                self.slope_events.add(name)
                err = self.x - x_feat
                self.x = x_feat
                self.y = row_y + 0.5 * (self.y - row_y)
                self.last_fix = f'{name} (x hatasi {err:+.2f} m duzeltildi)'
                return name
        return None
