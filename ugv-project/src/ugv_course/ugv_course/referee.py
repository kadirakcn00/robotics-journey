"""Hakem: sartname Tablo 5'e gore puanlama (ROS'tan bagimsiz).

Hakem robotun gercek konumunu bilir (gercek yarismada hakemler gozle ve kameralarla izler).
Her zaman adiminda update() cagrilir; olaylar (puan, ceza) liste olarak doner.

Puanlar (otonom ve manuel kosu ayni tablo; hedef tespiti sadece otonomda):
    su gecisi 10, cakilli yol 5, yan egim 5, dik engel 5, engebeli arazi 5
    koniler 50 (her temas -5), kayar engel 50 (temassiz gecis)
    dik egim 15 (cikis ve iniste >= 2 s durma), 10 (birinde durmadan), 0 (ikisinde de)
    otonomda hedefi tespit 10, atis 50 / 25 / 15 (en fazla 3 deneme, en iyisi)
    lazer aktifken arac/taret hareketi -10, bariyere her temas -5
"""

import math

from ugv_course import geometry as g

STAGE_POINTS = {1: 10, 2: 5, 3: 5, 4: 5, 7: 5}
STOP_TIME = 2.0
STOP_TOL = 0.25          # stop cizgisine uzaklik toleransi (m)
MOVE_TOL = 0.01          # lazer acikken izin verilen kayma (m)
TURRET_TOL = 0.005       # lazer acikken izin verilen taret acisi degisimi (rad)
MAX_SHOTS = 3
TIME_LIMIT = 15 * 60


class Referee:

    def __init__(self, layout, autonomous=True, run='main'):
        self.L = layout
        self.autonomous = autonomous
        self.run = run
        self.rows = {r[0]: r[3] for r in layout['road']['rows'].values()}   # y -> yon
        self.stages = {s[0]: s for s in layout['stages']}
        self.inside = {}
        self.passed = {}                  # asama -> puan
        self.cone_contacts = 0
        self.cone_touching = set()
        self.barrier_contacts = 0
        self.barrier_touching = False
        self.slider_contact = False
        self.stops = {'up': 0.0, 'down': 0.0}
        self.stop_ok = {'up': False, 'down': False}
        self.shots = []                   # puanlar
        self.shooting_closed = False
        self.laser_violation = False
        self.shot = None
        self.target_detected = False
        self.start_t = None
        self.finish_t = None
        self.prev = None
        self.start_pose = None
        self.accel_line_t = None
        self.events = []
        self.last_t = None

    # ---------------------------------------------------------------- yardimcilar
    def _event(self, t, text):
        self.events.append((t, text))
        return f'[{t - (self.start_t or t):6.1f} s] {text}'

    def _row_of(self, y):
        for row_y, heading in self.rows.items():
            if abs(y - row_y) < 0.7:
                return row_y, heading
        return None, None

    # ---------------------------------------------------------------- ana adim
    def update(self, t, x, y, z, yaw, pan=0.0, tilt=0.0, laser_on=False, slider_y=None,
               target_seen=False):
        out = []
        speed = 0.0
        if self.prev is not None and t > self.prev[0]:
            speed = math.hypot(x - self.prev[1], y - self.prev[2]) / (t - self.prev[0])
        self.prev = (t, x, y)
        if self.start_pose is None:
            self.start_pose = (x, y)
        if self.start_t is None:
            if math.hypot(x - self.start_pose[0], y - self.start_pose[1]) > 0.05:
                self.start_t = t
                out.append(self._event(t, 'KOSU BASLADI'))
            else:
                return out
        if self.finish_t is not None:
            return out

        if self.run == 'accel':
            return out + self._update_accel(t, x, y, speed)

        L = self.L
        row_y, heading = self._row_of(y)

        # Bariyer temasi (yukselen kenar)
        touching = g.hits_barrier(L, x, y, yaw)
        if touching and not self.barrier_touching:
            self.barrier_contacts += 1
            out.append(self._event(t, 'BARIYER TEMASI -5'))
        self.barrier_touching = touching

        # Koni temaslari
        for i, (cx, cy) in enumerate(L['cones']):
            hit = g.hits_cone(L, x, y, yaw, cx, cy)
            if hit and i not in self.cone_touching:
                self.cone_touching.add(i)
                self.cone_contacts += 1
                out.append(self._event(t, f'KONI {i + 1} TEMASI -5'))
            elif not hit:
                self.cone_touching.discard(i)

        # Kayar engel temasi
        if slider_y is not None and not self.slider_contact and \
                g.hits_slider(L, x, y, yaw, slider_y):
            self.slider_contact = True
            out.append(self._event(t, 'KAYAR ENGEL TEMASI: asama puani 0'))

        # Stop cizgileri (C sirasinda, cizgiye yakin ve duruyorken)
        rp = L['ramps']
        dt = t - self.last_t if self.last_t is not None else 0.0
        self.last_t = t
        if row_y == L['road']['rows']['C'][0]:
            for key, sx in (('up', rp['stop_up']), ('down', rp['stop_down'])):
                if self.stop_ok[key]:
                    continue
                if abs(x - sx) <= STOP_TOL and speed < 0.01:
                    self.stops[key] += dt               # cizgide duruyor: sureyi biriktir
                    if self.stops[key] >= STOP_TIME:
                        self.stop_ok[key] = True
                        out.append(self._event(t, f'STOP ({"cikis" if key == "up" else "inis"})'
                                                  f' >= {STOP_TIME:.0f} s: tamam'))
                else:
                    self.stops[key] = 0.0               # hareket etti: bastan say

        # Atis bolgesi: hedef tespiti ve lazer atislari
        s9 = self.stages[9]
        in_zone = row_y == s9[2] and s9[3] <= x <= s9[4]
        if in_zone and self.autonomous and target_seen and not self.target_detected:
            self.target_detected = True
            out.append(self._event(t, 'OTONOM HEDEF TESPITI +10'))
        out += self._update_laser(t, x, y, z, yaw, pan, tilt, laser_on, in_zone)

        # Asama gecisleri
        for sid, (_, name, sy, x0, x1) in self.stages.items():
            if sid in self.passed or abs(y - sy) >= 0.7:
                continue
            h = self.rows[sy]
            if x0 <= x <= x1:
                self.inside[sid] = True
            elif self.inside.get(sid) and ((h < 0 and x < x0) or (h > 0 and x > x1)):
                pts = self._stage_points(sid)
                self.passed[sid] = pts
                out.append(self._event(t, f'ASAMA {sid} ({name}) GECILDI: {pts} puan'))

        # Bitis: aracin onu cizgiyi gecince
        front_x = x + g.FOOT[0] * math.cos(yaw)
        if 10 in self.passed and row_y == L['road']['rows']['C'][0] and front_x < L['finish_x']:
            self.finish_t = t
            out.append(self._event(t, f'BITIS: kosu suresi {t - self.start_t:.1f} s'))
        return out

    def _stage_points(self, sid):
        if sid in STAGE_POINTS:
            return STAGE_POINTS[sid]
        if sid == 5:
            return max(0, 50 - 5 * self.cone_contacts)
        if sid == 6:
            return 0 if self.slider_contact else 50
        if sid == 8:
            return 0                                    # rampa puani 10. asamada verilir
        if sid == 9:
            return 0                                    # atis puani ayrica sayilir
        if sid == 10:
            n = sum(self.stop_ok.values())
            return {2: 15, 1: 10, 0: 0}[n]
        return 0

    def _update_laser(self, t, x, y, z, yaw, pan, tilt, laser_on, in_zone):
        out = []
        if self.shooting_closed:
            return out
        if laser_on and self.shot is None:
            if not in_zone:
                return out
            self.shot = {'t0': t, 'pose': (x, y), 'pan': pan, 'tilt': tilt, 'moved': False}
        elif laser_on and self.shot is not None:
            s = self.shot
            if math.hypot(x - s['pose'][0], y - s['pose'][1]) > MOVE_TOL or \
                    abs(pan - s['pan']) > TURRET_TOL or abs(tilt - s['tilt']) > TURRET_TOL:
                if not s['moved']:
                    s['moved'] = True
                    self.laser_violation = True
                    self.shooting_closed = True
                    out.append(self._event(t, 'LAZER ACIKKEN HAREKET -10: atis sona erdi'))
                    self.shot = None
        elif not laser_on and self.shot is not None:
            s, self.shot = self.shot, None
            dur = t - s['t0']
            hit = g.laser_hit(self.L, x, y, z, yaw, pan, tilt)
            pts = g.ring_points(self.L, hit) if dur >= 1.0 else 0
            self.shots.append(pts)
            where = f'merkezden {math.hypot(*hit) * 100:.1f} cm' if hit else 'hedef disi'
            out.append(self._event(t, f'ATIS {len(self.shots)}: lazer {dur:.1f} s, {where} '
                                      f'-> {pts} puan' + ('' if dur >= 1.0 else ' (1 s alti)')))
            if len(self.shots) >= MAX_SHOTS:
                self.shooting_closed = True
        return out

    def _update_accel(self, t, x, y, speed):
        a = self.L['accel']
        out = []
        if self.accel_line_t is None and x >= a['line']:
            self.accel_line_t = t
            out.append(self._event(t, f'HIZLANMA CIZGISI: {t - self.start_t:.2f} s'))
        if self.accel_line_t is not None and speed < 0.01 and t - self.accel_line_t > 0.5:
            self.finish_t = t
            stop = x - a['line']
            ok = stop <= a['stop_zone'] and not g.hits_barrier(self.L, x, y, 0.0)
            out.append(self._event(t, f'DURDU: cizgiden {stop:.2f} m '
                                      f'({"guvenli" if ok else "DURMA ALANI ASILDI"})'))
        return out

    # ---------------------------------------------------------------- ozet
    def total(self):
        pts = sum(self.passed.values())
        pts += max(self.shots) if self.shots else 0
        pts += 10 if self.target_detected else 0
        pts -= 10 if self.laser_violation else 0
        pts -= 5 * self.barrier_contacts
        return pts

    def summary(self, t_now=None):
        lines = ['==================== HAKEM RAPORU ====================']
        if self.run == 'accel':
            if self.accel_line_t is not None:
                lines.append(f'Hizlanma: {self.accel_line_t - self.start_t:.2f} s '
                             f'(siralama puani takimlar arasi karsilastirmayla verilir)')
            else:
                lines.append('Hizlanma cizgisi gecilmedi')
            return lines
        for sid, (_, name, *_r) in sorted(self.stages.items()):
            if sid in (8, 9):
                continue
            mark = f'{self.passed[sid]:3d}' if sid in self.passed else '  -'
            lines.append(f'  {sid:2d} {name:18s} {mark}')
        lines.append(f'     stoplar: cikis {"tamam" if self.stop_ok["up"] else "YOK"}, '
                     f'inis {"tamam" if self.stop_ok["down"] else "YOK"}')
        best = max(self.shots) if self.shots else 0
        lines.append(f'  atislar: {self.shots or "-"} -> en iyi {best}'
                     + ('  (lazer hareket cezasi -10)' if self.laser_violation else ''))
        if self.autonomous:
            lines.append(f'  hedef tespiti: {10 if self.target_detected else 0}')
        lines.append(f'  koni temasi: {self.cone_contacts}   '
                     f'bariyer temasi: {self.barrier_contacts} (-{5 * self.barrier_contacts})')
        end = self.finish_t if self.finish_t is not None else t_now
        if self.start_t is not None and end is not None:
            dur = end - self.start_t
            lines.append(f'  kosu suresi: {dur:.1f} s' + ('' if self.finish_t else ' (bitmedi)')
                         + ('  15 DK ASILDI' if dur > TIME_LIMIT else ''))
        lines.append(f'  TOPLAM: {self.total()} puan (+ sure siralamasi en fazla 100)')
        return lines
