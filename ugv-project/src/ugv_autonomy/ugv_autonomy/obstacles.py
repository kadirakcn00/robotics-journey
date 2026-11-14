"""LIDAR ile koni ve kayar engel algilama (ROS'tan bagimsiz).

Koniler: yolun icinde, bariyerlerden uzak noktalar engeldir. Robotun gecebilecegi yanal
konumlar (yol eksenine gore) engellerin etrafinda guvenlik payi birakilarak hesaplanir ve
hedef konuma en yakin bos yer secilir.

Kayar engel: engelin gecis hattindaki (x sabit) noktalarin ortalamasi engelin yanal konumunu,
zamanla degisimi de yonunu verir.
"""

import math

import numpy as np

ROBOT_HALF = 0.21          # govde + LIDAR yari genisligi (m)
# Engel noktasi (LIDAR'in gordugu koni yuzeyi) ile robot ekseni arasinda olmasi gereken yanal
# mesafe: tekerlek yari genisligi 0.19 + koni taban plakasi 0.08 + guvenlik 0.04
# - koninin LIDAR yuksekligindeki yaricapi 0.035 (nokta merkezden bu kadar yakinda)
CONE_CLEAR = 0.19 + 0.08 + 0.04 - 0.035


def obstacle_points(pts, row_y, heading, x_robot, half=0.6, ahead=(0.1, 1.3), wall_gap=0.1):
    """Yol icindeki, robotun onundeki engel noktalari (yol eksenine gore y)."""
    if len(pts) == 0:
        return np.zeros((0, 2))
    rel_y = pts[:, 1] - row_y
    along = (pts[:, 0] - x_robot) * heading
    keep = (np.abs(rel_y) < half - wall_gap) & (along > ahead[0]) & (along < ahead[1])
    return np.stack([along[keep], rel_y[keep]], axis=1)


def avoid_lateral(obs, current, half=0.6, robot_half=ROBOT_HALF, clear=CONE_CLEAR,
                  margin=0.08, rear=0.45, cluster=0.2, beside=0.45):
    """Robotun yanindaki ve henuz gecmedigi en yakin engel kumesine gore hedef yanal konum.

    obs: (ileri mesafe, yanal konum) noktalari, robot merkezine gore. Arkada kalan (robotun
    arka ucunu gecmis) engeller yok sayilir. Dikkate alinanlar: robotun govdesinin yaninda
    duranlar (ileri < beside) ve onundeki en yakin kume. Her engel [y - clear, y + clear]
    araligini kapatir; acik kalan yerlerden simdiki konuma en yakini secilir (bariyere
    'margin' pay birakarak). Hic yer yoksa iki engele en uzak nokta (en az kotu) secilir;
    yol tamamen kapaliysa None.
    """
    lim = half - robot_half - margin
    obs = [o for o in obs if o[0] > -rear]
    if not obs:
        return None if abs(current) > lim + 1e-9 else 0.0
    obs.sort(key=lambda o: o[0])
    ahead = [o for o in obs if o[0] >= beside]
    first = ahead[0][0] if ahead else None
    used = [o for o in obs if o[0] < beside or (first is not None and o[0] - first < cluster)]
    ys = sorted(o[1] for o in used)
    blocked = [(y - clear, y + clear) for y in ys]
    # Acik araliklar
    free, lo = [], -lim
    for b0, b1 in sorted(blocked):
        if b0 > lo:
            free.append((lo, min(b0, lim)))
        lo = max(lo, b1)
    if lo < lim:
        free.append((lo, lim))
    free = [(a, b) for a, b in free if b >= a]
    if free:
        return min((max(a, min(b, current)) for a, b in free), key=lambda c: abs(c - current))
    # Tam pay yok: engellerden en uzak nokta
    cands = np.arange(-lim, lim + 1e-9, 0.005)
    dist = np.min(np.abs(cands[:, None] - np.array(ys)[None, :]), axis=1)
    if dist.max() < robot_half * 0.5:
        return None
    return float(cands[np.argmax(dist)])


def free_lateral(obs, preferred, half=0.6, robot_half=ROBOT_HALF, clear=CONE_CLEAR,
                 margin=0.03, step=0.01):
    """Tum engellerden ayni anda uzak, 'preferred'e en yakin yanal konum (ya da None)."""
    lim = half - robot_half - margin
    cands = np.arange(-lim, lim + 1e-9, step)
    ok = np.ones(len(cands), dtype=bool)
    for _, oy in obs:
        ok &= np.abs(cands - oy) >= clear
    if not ok.any():
        return None
    free = cands[ok]
    return float(free[np.argmin(np.abs(free - preferred))])


class SliderWatcher:
    """Kayar engelin yanal konumunu ve yonunu LIDAR'dan izler."""

    def __init__(self, x, row_y, band=0.15, reach=1.0):
        self.x, self.row_y = x, row_y
        self.band, self.reach = band, reach
        self.history = []

    def update(self, t, pts):
        if len(pts):
            sel = (np.abs(pts[:, 0] - self.x) < self.band) & \
                  (np.abs(pts[:, 1] - self.row_y) < self.reach)
            if sel.sum() >= 2:
                self.history.append((t, float(np.mean(pts[sel, 1]) - self.row_y)))
        self.history = [h for h in self.history if t - h[0] < 1.0]

    def state(self):
        """(yanal konum, hiz) ya da gorunmuyorsa None."""
        if len(self.history) < 3:
            return None
        t0, y0 = self.history[0]
        t1, y1 = self.history[-1]
        vel = (y1 - y0) / (t1 - t0) if t1 > t0 else 0.0
        return y1, vel

    def clear(self, min_edge=0.45, min_speed=0.03):
        """Gecilebilir mi? Sadece engel DISARI giderken ve robotun yolundan uzaksa.

        Robot engel hattini ~4.3 s'de gecer. Engel |y| >= 0.45'te disari giderken yola
        cikilirsa, uca gidip donse bile ic kenari gecis boyunca 0.25 m'nin disinda kalir
        (robotun yari genisligi 0.21 m). Ice donen engel, ne kadar disarida olursa olsun
        beklenir: donup robotun yoluna girer.
        """
        s = self.state()
        if s is None:
            return False
        y, vel = s
        outward = vel * math.copysign(1.0, y) > min_speed
        return outward and abs(y) >= min_edge
