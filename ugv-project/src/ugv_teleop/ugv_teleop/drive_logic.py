"""Surucu konsolunun karar mantigi (ROS'tan ve arayuzden bagimsiz).

Hangi tuslar basili, hangi vitesteyiz, acil durdurma acik mi, lazer ateslendi mi gibi
bilgilerden robota gidecek hiz, taret acisi ve lazer durumunu hesaplar. Arayuz sadece
tuslari bu sinifa iletir ve sonucu yayinlar; boylece mantik ekransiz test edilebilir.

Tuslar (arayuzdeki karsiliklari driver_station.py'de):
    ileri / geri / sol / sag      : W S A D (basili tutuldukca)
    vites 1 / 2 / 3               : 1 2 3
    acil durdurma                 : Space (kilitlenir), Enter ile birakilir
    taret                         : ok tuslari (basili tutuldukca), C ile merkez
    lazer                         : F (basili tutuldukca)
"""

from dataclasses import dataclass, field

GEARS = {1: (0.15, 0.8), 2: (0.30, 1.2), 3: (0.50, 1.6)}   # vites: (m/s, rad/s)


@dataclass
class DriveState:
    v: float = 0.0             # dogrusal hiz komutu (m/s)
    w: float = 0.0             # acisal hiz komutu (rad/s)
    pan: float = 0.0           # taret yatay acisi (rad)
    tilt: float = 0.0          # taret dikey acisi (rad), + asagi
    laser_on: bool = False
    laser_time: float = 0.0    # lazerin bu atista acik kaldigi sure (s)
    estop: bool = False
    gear: int = 1
    held: set = field(default_factory=set)


class DriveController:
    """Tus durumlarindan hiz/taret/lazer komutlarini ureten sinif.

    accel / decel   : dogrusal hizlanma ve frenleme (m/s^2)
    turn_accel      : acisal hizlanma (rad/s^2)
    turret_rate     : taret donus hizi (rad/s)
    """

    PAN_LIMIT = 2.8
    TILT_LIMIT = 0.6

    def __init__(self, accel=0.6, decel=1.5, turn_accel=4.0, turret_rate=0.6):
        self.s = DriveState()
        self.accel = accel
        self.decel = decel
        self.turn_accel = turn_accel
        self.turret_rate = turret_rate

    # -- tus olaylari
    def press(self, key):
        """Bir tus basildi (tekrarlanan basilmalar zararsizdir)."""
        s = self.s
        if key in ('1', '2', '3'):
            s.gear = int(key)
        elif key == 'estop':
            s.estop = True
            s.laser_on = False
        elif key == 'release':
            s.estop = False
        elif key == 'center':
            if not s.laser_on:
                s.pan = s.tilt = 0.0
        else:
            s.held.add(key)

    def release(self, key):
        self.s.held.discard(key)

    def release_all(self):
        """Pencere odagi kaybolunca: tum tuslar birakilmis sayilir (robot durur)."""
        self.s.held.clear()

    # -- zaman adimi
    def step(self, dt):
        """Dt saniye ilerle, guncel durumu dondur."""
        s = self.s
        h = s.held
        v_max, w_max = GEARS[s.gear]

        # Lazer: F basili ve acil durdurma yoksa acik
        firing = 'fire' in h and not s.estop
        if firing and not s.laser_on:
            s.laser_time = 0.0
        s.laser_on = firing
        if firing:
            s.laser_time += dt

        # Lazer acikken arac ve taret hareket edemez (sartname: -10 puan cezasi)
        locked = s.estop or s.laser_on
        fwd = (('forward' in h) - ('backward' in h)) if not locked else 0
        turn = (('left' in h) - ('right' in h)) if not locked else 0

        if s.estop:
            s.v = s.w = 0.0
        else:
            target_v = fwd * v_max
            rate = self.accel if abs(target_v) > abs(s.v) and target_v * s.v >= 0 else self.decel
            s.v = _approach(s.v, target_v, rate * dt)
            s.w = _approach(s.w, turn * w_max, self.turn_accel * dt)

        if not locked:
            pan_dir = ('pan_left' in h) - ('pan_right' in h)
            tilt_dir = ('tilt_down' in h) - ('tilt_up' in h)
            s.pan = _clamp(s.pan + pan_dir * self.turret_rate * dt, self.PAN_LIMIT)
            s.tilt = _clamp(s.tilt + tilt_dir * self.turret_rate * dt, self.TILT_LIMIT)
        return s


def _approach(value, target, max_step):
    if value < target:
        return min(target, value + max_step)
    return max(target, value - max_step)


def _clamp(value, limit):
    return max(-limit, min(limit, value))
