"""Parkur test surucusunun yol takip mantigi (ROS'tan bagimsiz).

Robotu onceden belirlenmis bir yol boyunca surer (Pure Pursuit), stop cizgilerinde durup
bekler, kayar engelin gecmesini bekler ve takilirsa bunu fark eder.

Pure Pursuit: robotun onunde 'lookahead' kadar ileride yol uzerinde bir nokta secilir;
robot o noktaya giden cember yayini izler. Egrilik k = 2 * y / L^2 (y: noktanin robota gore
yan uzakligi, L: noktaya uzaklik), acisal hiz w = v * k.
"""

from dataclasses import dataclass, field
import math


@dataclass
class Waypoint:
    x: float
    y: float
    speed: float
    stage: int
    wait: str = ''              # '', 'stop:<s>', 'slider', 'finish', 'mark:<ad>', 'shoot'


def parse_waypoints(lines):
    out = []
    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        out.append(Waypoint(float(parts[0]), float(parts[1]), float(parts[2]),
                            int(parts[3]), parts[4] if len(parts) > 4 else ''))
    return out


@dataclass
class FollowerStatus:
    state: str = 'DRIVE'        # DRIVE, STOP_WAIT, SLIDER_WAIT, FINISHED, STUCK
    stage: int = 0
    index: int = 0
    message: str = ''
    stage_times: dict = field(default_factory=dict)
    marks: dict = field(default_factory=dict)      # olcum noktalari: ad -> (zaman, x, y)


class PathFollower:

    def __init__(self, waypoints, lookahead=0.35, w_max=1.2, reach=0.12,
                 stuck_time=6.0, stuck_speed=0.02, brake=0.8, slider_clear=None):
        self.wp = waypoints
        self.lookahead = lookahead
        self.w_max = w_max
        self.reach = reach
        self.stuck_time = stuck_time
        self.stuck_speed = stuck_speed
        self.brake = brake               # durma noktasina yaklasirken v <= brake * mesafe
        self.offset = 0.0                # yolun soluna (+) / sagina (-) kaydirma (m), koniler icin
        self.external_done = False       # 'shoot' beklemesini disaridan bitirmek icin
        if slider_clear is not None:     # kayar engel karari disaridan (otonom: LIDAR)
            self.slider_clear = slider_clear
        self.i = 1                       # hedeflenen nokta
        self.st = FollowerStatus()
        self.wait_until = None
        self.slow_since = None
        self.slider_prev = None

    # -- yardimcilar
    def _is_stop(self, wp):
        """Robotun durmasi gereken nokta mi? 'mark:' noktalari sadece zaman kaydeder."""
        return bool(wp.wait) and not wp.wait.startswith('mark:')

    def _passed(self, k, x, y):
        """Nokta gecildi mi.

        Yakinsa ya da robot yol yonunde noktayi gectiyse gecilmis sayilir (yana kaymis olsa
        bile; koni kacinirken robot yolun yanindan gecer).
        """
        wp = self.wp[k]
        dx, dy = x - wp.x, y - wp.y
        if math.hypot(dx, dy) < self.reach + 0.1:
            return True
        if k == 0:
            return False
        px, py = self.wp[k - 1].x, self.wp[k - 1].y
        seg = math.hypot(wp.x - px, wp.y - py)
        if seg < 1e-6:
            return False
        along = (dx * (wp.x - px) + dy * (wp.y - py)) / seg
        return along > 0.0 and math.hypot(dx, dy) < 0.8

    def _next_wait(self):
        for k in range(self.i, len(self.wp)):
            if self._is_stop(self.wp[k]):
                return k
        return len(self.wp) - 1

    def _lookahead_point(self, x, y, limit):
        """Yol uzerinde robottan 'lookahead' uzaktaki nokta (limit indeksini gecmez)."""
        for k in range(self.i, limit + 1):
            if math.hypot(self.wp[k].x - x, self.wp[k].y - y) >= self.lookahead:
                return self.wp[k].x, self.wp[k].y
        return self.wp[limit].x, self.wp[limit].y

    def _enter_stage(self, stage, t):
        self.st.stage = stage
        self.st.stage_times.setdefault(stage, t)

    # -- ana adim
    def update(self, x, y, yaw, t, speed, slider_y=None):
        """Robot konumu/yonu, zaman ve olculen hizdan (v, w) dondurur."""
        st = self.st
        if st.state in ('FINISHED', 'STUCK'):
            return 0.0, 0.0

        # Gecilen noktalari atla (bekleme noktalarinda durulmadan atlanmaz). Olcum noktasi
        # (mark) gecilirken zaman ve konum kaydedilir.
        while self.i < len(self.wp) - 1 and not self._is_stop(self.wp[self.i]) and \
                self._passed(self.i, x, y):
            wp = self.wp[self.i]
            if wp.wait.startswith('mark:'):
                st.marks.setdefault(wp.wait[5:], (t, x, y))
            self.i += 1
        target = self.wp[self.i]
        self._enter_stage(target.stage, t)
        st.index = self.i

        # Bekleme noktasina varildi mi?
        if self._is_stop(target) and math.hypot(target.x - x, target.y - y) < self.reach:
            return self._handle_wait(target, t, speed, slider_y)

        # Pure Pursuit
        limit = self._next_wait()
        lx, ly = self._lookahead_point(x, y, limit)
        if self.offset and self.i > 0:
            # Yolun yonune dik (sola) kaydir
            ax, ay = self.wp[self.i - 1].x, self.wp[self.i - 1].y
            seg = math.hypot(target.x - ax, target.y - ay)
            if seg > 1e-6:
                lx -= (target.y - ay) / seg * self.offset
                ly += (target.x - ax) / seg * self.offset
        dx, dy = lx - x, ly - y
        c, s = math.cos(yaw), math.sin(yaw)
        fx, fy = c * dx + s * dy, -s * dx + c * dy     # robot cercevesinde
        dist = math.hypot(fx, fy)
        alpha = math.atan2(fy, fx)
        v = target.speed
        wait_wp = self.wp[limit]
        d_wait = math.hypot(wait_wp.x - x, wait_wp.y - y)
        if self._is_stop(wait_wp):
            v = min(v, max(0.05, self.brake * d_wait))  # bekleme noktasina yavasla
        if abs(alpha) > math.radians(60):              # hedef arkada: yerinde don
            v, w = 0.0, math.copysign(0.6, alpha)
        else:
            k = 2.0 * fy / (dist * dist) if dist > 1e-6 else 0.0
            w = max(-self.w_max, min(self.w_max, v * k))
        self._check_stuck(v, speed, t)
        st.message = f'asama {target.stage}, nokta {self.i}/{len(self.wp) - 1}'
        return v, w

    def _handle_wait(self, wp, t, speed, slider_y):
        st = self.st
        self.slow_since = None
        if wp.wait == 'finish':
            st.state = 'FINISHED'
            st.stage_times.setdefault('finish', t)
            st.message = 'BITIS'
            return 0.0, 0.0
        if wp.wait.startswith('stop:'):
            if self.wait_until is None:
                if abs(speed) > 0.01:                    # once tam dur
                    st.state = 'STOP_WAIT'
                    st.message = 'stop: duruluyor'
                    return 0.0, 0.0
                self.wait_until = t + float(wp.wait.split(':')[1])
            st.state = 'STOP_WAIT'
            st.message = f'stop: {max(0.0, self.wait_until - t):.1f} s'
            if t < self.wait_until:
                return 0.0, 0.0
        elif wp.wait == 'shoot':
            st.state = 'SHOOT'
            if not self.external_done:
                st.message = 'atis yapiliyor'
                return 0.0, 0.0
            self.external_done = False
        elif wp.wait == 'slider':
            st.state = 'SLIDER_WAIT'
            if not self.slider_clear(slider_y):
                st.message = 'kayar engel bekleniyor'
                return 0.0, 0.0
        # Bekleme bitti: bir sonraki noktaya gec
        self.wait_until = None
        self.slider_prev = None
        st.state = 'DRIVE'
        self.i = min(self.i + 1, len(self.wp) - 1)
        return 0.0, 0.0

    def slider_clear(self, slider_y, out=0.62, moving_out=0.5):
        """Kayar engel yolu bosaltti mi? Konum (m, yol eksenine gore) ve hareket yonune bakar."""
        if slider_y is None:
            return False
        prev, self.slider_prev = self.slider_prev, slider_y
        if prev is None:
            return False                 # yonu anlamak icin ikinci olcum gerekir
        if abs(slider_y) >= out:
            # Disarida ve geri donmuyorsa ya da donse bile uzaksa gecilir
            return abs(slider_y) >= abs(prev) or abs(slider_y) > 0.75
        moving_away = abs(slider_y) > abs(prev)
        return moving_away and abs(slider_y) >= moving_out

    def _check_stuck(self, v_cmd, speed, t):
        if v_cmd > 0.08 and abs(speed) < self.stuck_speed:
            if self.slow_since is None:
                self.slow_since = t
            elif t - self.slow_since > self.stuck_time:
                self.st.state = 'STUCK'
                self.st.message = f'TAKILDI: asama {self.st.stage}, nokta {self.i}'
        else:
            self.slow_since = None
