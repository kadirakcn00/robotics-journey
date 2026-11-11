"""Su gecisi fizigi (ROS'tan bagimsiz).

Gazebo Fortress'ta kara araci icin hazir su fizigi yok. DiffDrive tekerlek hizini dogrudan
ayarladigi icin robota uygulanan bir direnc kuvveti onu yavaslatmaz. Bu yuzden suyun
etkisini hiz komutu uzerinden modelliyoruz:

    /cmd_vel  ->  WaterModel  ->  /cmd_vel_gz  ->  Gazebo DiffDrive

Robot suya ne kadar gomulurse (batma orani s = derinlik / robot yuksekligi):
    - ulasabildigi en yuksek hiz duser       (suyun direnci)
    - donus hizi duser                       (tekerlekler zeminde kayar)
    - hizlanma/yavaslama yumusar             (suyun ataleti)
    - yon hafifce rastgele sapar              (kaygan zemin, akinti)

Havuz: sartname 6.3, 40 cm derinlik (x 0.4 olcek = 16 cm), giris ve cikista egimli.
"""

from dataclasses import dataclass
import math
import random


@dataclass
class WaterZone:
    """Dikdortgen havuz. Giris/cikis egimleri x yonundedir (robot havuza x boyunca girer)."""

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    depth: float          # havuzun en derin yerindeki su derinligi (m)
    ramp_length: float    # giris/cikis egiminin yatay uzunlugu (m)

    def depth_at(self, x, y):
        """(x, y) noktasindaki su derinligi; havuz disinda 0."""
        if not (self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max):
            return 0.0
        edge = min(x - self.x_min, self.x_max - x)
        if self.ramp_length > 0 and edge < self.ramp_length:
            return self.depth * edge / self.ramp_length
        return self.depth


@dataclass
class WaterEffect:
    """Batma oranina gore hiz carpanlari."""

    linear_drag: float = 0.6      # tam batmada dogrusal hiz %60 duser
    angular_drag: float = 0.5     # tam batmada donus hizi %50 duser
    accel_dry: float = 1.0        # m/s^2, kuru zeminde izin verilen hizlanma
    accel_wet: float = 0.3        # m/s^2, tam batmada izin verilen hizlanma
    yaw_noise: float = 0.15       # rad/s, tam batmada rastgele yon sapmasi (std)


class WaterModel:
    """Hiz komutunu suyun etkisine gore degistirir.

    robot_height: robotun yerden govde ustune kadar yuksekligi (m), batma oranini hesaplamak
    icin kullanilir.
    """

    def __init__(self, zones, robot_height=0.27, effect=None, seed=0):
        self.zones = list(zones)
        self.robot_height = robot_height
        self.effect = effect or WaterEffect()
        self.rng = random.Random(seed)
        self.v = 0.0
        self.w = 0.0

    def depth_at(self, x, y):
        return max((z.depth_at(x, y) for z in self.zones), default=0.0)

    def submersion(self, x, y):
        """Batma orani [0, 1]."""
        return min(1.0, self.depth_at(x, y) / self.robot_height)

    def step(self, cmd_v, cmd_w, x, y, dt):
        """Bir zaman adimi: robotun (x, y) konumuna gore uygulanacak (v, w) dondurur."""
        e = self.effect
        s = self.submersion(x, y)
        v_target = cmd_v * (1.0 - e.linear_drag * s)
        w_target = cmd_w * (1.0 - e.angular_drag * s)
        if s > 0 and e.yaw_noise > 0:
            w_target += self.rng.gauss(0.0, e.yaw_noise * s)

        if s == 0.0:
            # Kuru zemin: komut aynen gecer (Gazebo'daki DiffDrive kendi limitlerini uygular)
            self.v, self.w = v_target, w_target
            return self.v, self.w

        accel = e.accel_dry + (e.accel_wet - e.accel_dry) * s
        self.v += _clamp(v_target - self.v, accel * dt)
        self.w += _clamp(w_target - self.w, 2.0 * accel * dt)
        return self.v, self.w


def _clamp(value, limit):
    return max(-limit, min(limit, value))


def zone_from_dict(d):
    return WaterZone(**{k: float(d[k]) for k in
                        ('x_min', 'x_max', 'y_min', 'y_max', 'depth', 'ramp_length')})


def yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
