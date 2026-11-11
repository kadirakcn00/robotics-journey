#!/usr/bin/env python3
"""TEKNOFEST 2026 IKA yarisma parkurunu (Sekil 1) Gazebo Fortress dunyasi olarak uretir.

Olcek: sartnamedeki tum uzunluklar x 0.4 (robotumuz kucuk oldugu icin). Egimler (%45, %20)
olcekten etkilenmez.

Uretilenler:
    worlds/teknofest_course.sdf          : parkur dunyasi
    models/teknofest_parts/meshes/*.obj  : yan egim zemini (yumusak gecisli %20 egim)
    models/traffic_cone, models/sliding_obstacle
    config/water_zones.yaml              : su fizigi icin havuz bilgisi
    docs/course_top_view.png             : parkurun ustten gorunusu

Yerlesim (x: robotun ilerleme ekseni, metre):
    A sirasi (y = 0, robot -x yonunde):  baslangic | 1 su gecisi | 2 cakil | 3 yan egim
    sol U donusu
    B sirasi (y = 3, robot +x yonunde):  4 dik engel | 5 koniler | 6 kayar engel
    sag U donusu
    C sirasi (y = 6, robot -x yonunde):  7 engebeli arazi | 8 rampa | 9 atis | 10 rampa | bitis
    hedef: bitisin solunda, atis bolgesinden 4 m'den uzakta
    D (y = 9.5): 11 hizlanma parkuru (12 m + 4 m durma)

Kullanim:
    python3 make_teknofest_course.py
"""

import math
import os
import random

S = 0.4                       # olcek
ROAD_W = 3.0 * S              # yol genisligi 1.2 m
HALF = ROAD_W / 2
BAR_H = 0.80 * S              # bariyer yuksekligi 0.32 m
BAR_T = 0.04                  # bariyer kalinligi
BAR_Y = HALF + BAR_T / 2      # bariyerin yol eksenine uzakligi
ROW_LEN = 20.0 * S            # duz bolum 8 m
ROW_GAP = 3.0                 # siralar arasi eksen mesafesi
TURN_R = ROW_GAP / 2          # U donusu yaricapi (yol ekseni)

ROW_A, ROW_B, ROW_C = 0.0, ROW_GAP, 2 * ROW_GAP
ROW_D = 2 * ROW_GAP + 3.5

POOL_X = (5.2, 6.6)
POOL_DEPTH = 0.40 * S         # 16 cm
POOL_RAMP = POOL_DEPTH / math.tan(math.radians(20))   # 20 derece (%36) giris/cikis
GRAVEL_X = (3.6, 4.8)
SIDE_X = (0.8, 2.8)
SIDE_GRADE = 0.20
SIDE_BLEND = 0.5
STEP_X = (1.0, 1.4)
STEP_H = 0.15 * S             # 6 cm
CONE_XS = (2.2, 2.9, 3.6, 4.3, 5.0)
SLIDER_X = 6.6
SLIDER_W = 1.0 * S            # 0.4 m
SLIDER_AMP = HALF + SLIDER_W / 2   # parkurun tamamen disina cikar
SLIDER_SPEED = 0.20 * S       # 8 cm/s
BUMPS_X = (6.0, 7.6)
RAMP_GRADE = 0.45
RAMP_H = 0.24
RAMP_UP_START = 5.4           # robot -x yonunde ilerler: rampa 5.4'ten baslar
PLATFORM_LEN = 1.6
FINISH_X = 1.2
ROW_C_END = 0.4
TARGET_POS = (-2.6, ROW_C)
ACCEL_LEN, STOP_LEN = 30.0 * S, 10.0 * S

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.normpath(os.path.join(HERE, '..'))
PARTS = 'teknofest_parts'


# ----------------------------------------------------------------------------- mesh
class Mesh:
    def __init__(self):
        self.v, self.f = [], []

    def add_v(self, p):
        self.v.append(tuple(float(c) for c in p))
        return len(self.v) - 1

    def tri(self, a, b, c, outward):
        """outward: ucgenin disari bakmasi gereken yon (vektor)."""
        pa, pb, pc = self.v[a], self.v[b], self.v[c]
        n = _cross(_sub(pb, pa), _sub(pc, pa))
        if _dot(n, outward) < 0:
            b, c = c, b
        self.f.append((a, b, c))

    def quad(self, a, b, c, d, outward):
        self.tri(a, b, c, outward)
        self.tri(a, c, d, outward)

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as fh:
            fh.write('# make_teknofest_course.py tarafindan uretildi\n')
            for p in self.v:
                fh.write('v %.5f %.5f %.5f\n' % p)
            for i, (a, b, c) in enumerate(self.f):
                n = _norm(_cross(_sub(self.v[b], self.v[a]), _sub(self.v[c], self.v[a])))
                fh.write('vn %.5f %.5f %.5f\n' % n)
            for i, (a, b, c) in enumerate(self.f):
                fh.write('f %d//%d %d//%d %d//%d\n' % (a + 1, i + 1, b + 1, i + 1, c + 1, i + 1))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return tuple(x / n for x in a)


def side_slope_height(x, y):
    """Yan egim yuzeyi: +y kenari yuksek, girislerde egim 0'dan %20'ye yumusak gecis."""
    x0, x1 = SIDE_X
    k = min(1.0, (x - x0) / SIDE_BLEND, (x1 - x) / SIDE_BLEND)
    return max(0.0, k) * SIDE_GRADE * (y + HALF)


def side_slope_mesh():
    """Yolun ust yuzeyi z = h(x, y), alti z = -0.01 olan kapali kati (dunya koordinati)."""
    m = Mesh()
    x0, x1 = SIDE_X
    nx, ny = 41, 7
    xs = [x0 + (x1 - x0) * i / (nx - 1) for i in range(nx)]
    ys = [-HALF + ROAD_W * j / (ny - 1) for j in range(ny)]
    top = [[m.add_v((x, y, side_slope_height(x, y))) for y in ys] for x in xs]
    bot = [[m.add_v((x, y, -0.01)) for y in ys] for x in xs]
    for i in range(nx - 1):
        for j in range(ny - 1):
            m.quad(top[i][j], top[i + 1][j], top[i + 1][j + 1], top[i][j + 1], (0, 0, 1))
            m.quad(bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1], (0, 0, -1))
    for i in range(nx - 1):
        m.quad(top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0], (0, -1, 0))
        m.quad(top[i][-1], top[i + 1][-1], bot[i + 1][-1], bot[i][-1], (0, 1, 0))
    for j in range(ny - 1):
        m.quad(top[0][j], top[0][j + 1], bot[0][j + 1], bot[0][j], (-1, 0, 0))
        m.quad(top[-1][j], top[-1][j + 1], bot[-1][j + 1], bot[-1][j], (1, 0, 0))
    return m


def ramp_profile():
    """Rampa + atis platformu + rampa (C sirasinda robot -x yonunde gider), x-z profili."""
    run = RAMP_H / RAMP_GRADE
    a = RAMP_UP_START
    b = a - run
    c = b - PLATFORM_LEN
    d = c - run
    return [(a, -0.01), (a, 0.0), (b, RAMP_H), (c, RAMP_H), (d, 0.0), (d, -0.01)], (a, b, c, d)


# ----------------------------------------------------------------------------- sdf
def color(r, g, b, a=1.0):
    return (f'<material><ambient>{r} {g} {b} {a}</ambient><diffuse>{r} {g} {b} {a}</diffuse>'
            f'</material>')


RED, WHITE = color(0.85, 0.05, 0.05), color(0.95, 0.95, 0.95)
ROAD = color(0.25, 0.25, 0.27)
GRASS = color(0.45, 0.55, 0.40)


class Course:
    def __init__(self):
        self.items = []       # (isim, sdf) statik parcalar
        self.n = 0
        self.preview = []     # ustten gorunus icin cizim komutlari

    def box(self, size, pose, mat, collide=True, name='box'):
        self.n += 1
        nm = f'{name}_{self.n}'
        sx, sy, sz = size
        geo = f'<geometry><box><size>{sx:.4f} {sy:.4f} {sz:.4f}</size></box></geometry>'
        p = ' '.join(f'{v:.4f}' for v in pose)
        s = f'<visual name="{nm}_v"><pose>{p}</pose>{geo}{mat}</visual>'
        if collide:
            s += f'<collision name="{nm}_c"><pose>{p}</pose>{geo}</collision>'
        self.items.append(s)

    def cylinder(self, r, length, pose, mat, collide=True, name='cyl'):
        self.n += 1
        nm = f'{name}_{self.n}'
        geo = (f'<geometry><cylinder><radius>{r:.4f}</radius><length>{length:.4f}</length>'
               f'</cylinder></geometry>')
        p = ' '.join(f'{v:.4f}' for v in pose)
        s = f'<visual name="{nm}_v"><pose>{p}</pose>{geo}{mat}</visual>'
        if collide:
            s += f'<collision name="{nm}_c"><pose>{p}</pose>{geo}</collision>'
        self.items.append(s)

    def slope_box(self, p_low, p_high, y, width, mat, thick=0.1, extend=0.05, name='slope'):
        """Egimli yuzey: ust yuzeyi (x, z) p_low'dan p_high'a giden dondurulmus kutu.

        Kutu, ust yuzeyi tam bu iki noktadan gececek sekilde zeminin icine gomulur. Alcak
        uctan 'extend' kadar uzatilir; uzayan kisim zeminin altinda kalir, dudak olusmaz.
        """
        (xl, zl), (xh, zh) = p_low, p_high
        run, rise = xh - xl, zh - zl
        length = math.hypot(run, rise)
        ux, uz = run / length, rise / length                  # yokus yukari yon
        xl, zl = xl - ux * extend, zl - uz * extend
        length += extend
        ax, az = (ux, uz) if ux >= 0 else (-ux, -uz)          # kutunun x ekseni (+x'e bakan)
        pitch = math.atan2(-az, ax)                           # -90..90 derece arasi
        nx, nz = math.sin(pitch), math.cos(pitch)             # ust yuzey normali (yukari)
        cx = (xl + xh) / 2 - nx * thick / 2
        cz = (zl + zh) / 2 - nz * thick / 2
        self.box((length, width, thick), (cx, y, cz, 0, pitch, 0), mat, name=name)
        return (xl + xh) / 2, (zl + zh) / 2, pitch, (nx, nz)

    def mesh(self, fname, mat, pose=(0, 0, 0, 0, 0, 0), name='mesh'):
        self.n += 1
        nm = f'{name}_{self.n}'
        geo = (f'<geometry><mesh><uri>model://{PARTS}/meshes/{fname}</uri></mesh>'
               f'</geometry>')
        p = ' '.join(f'{v:.4f}' for v in pose)
        self.items.append(f'<visual name="{nm}_v"><pose>{p}</pose>{geo}{mat}</visual>'
                          f'<collision name="{nm}_c"><pose>{p}</pose>{geo}</collision>')

    # -- bariyerler
    def barrier_segment(self, p0, p1, z0=0.0, idx=0):
        (x0, y0), (x1, y1) = p0, p1
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1e-6:
            return
        yaw = math.atan2(y1 - y0, x1 - x0)
        self.box((length + 0.005, BAR_T, BAR_H),
                 ((x0 + x1) / 2, (y0 + y1) / 2, z0 + BAR_H / 2, 0, 0, yaw),
                 RED if idx % 2 == 0 else WHITE, name='barrier')
        self.preview.append(('barrier', p0, p1))

    def barrier_line(self, p0, p1, seg=0.4, z_of=None):
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        k = max(1, int(math.ceil(length / seg)))
        for i in range(k):
            a = (p0[0] + (p1[0] - p0[0]) * i / k, p0[1] + (p1[1] - p0[1]) * i / k)
            b = (p0[0] + (p1[0] - p0[0]) * (i + 1) / k, p0[1] + (p1[1] - p0[1]) * (i + 1) / k)
            z0 = z_of((a[0] + b[0]) / 2) if z_of else 0.0
            self.barrier_segment(a, b, z0, i)

    def barrier_arc(self, c, r, a0, a1, seg=0.3):
        k = max(2, int(math.ceil(abs(a1 - a0) * r / seg)))
        pts = [(c[0] + r * math.cos(a0 + (a1 - a0) * i / k),
                c[1] + r * math.sin(a0 + (a1 - a0) * i / k)) for i in range(k + 1)]
        for i in range(k):
            self.barrier_segment(pts[i], pts[i + 1], 0.0, i)

    # -- yol yuzeyi (sadece gorsel)
    def road_line(self, x0, x1, y):
        self.box((abs(x1 - x0), ROAD_W, 0.002), ((x0 + x1) / 2, y, 0.001, 0, 0, 0), ROAD,
                 collide=False, name='road')
        self.preview.append(('road', (min(x0, x1), y - HALF), (max(x0, x1), y + HALF)))

    def road_arc(self, c, a0, a1):
        k = 18
        for i in range(k):
            a = a0 + (a1 - a0) * (i + 0.5) / k
            arc_len = abs(a1 - a0) / k * (TURN_R + HALF) + 0.02
            self.box((ROAD_W, arc_len, 0.002),
                     (c[0] + TURN_R * math.cos(a), c[1] + TURN_R * math.sin(a), 0.001, 0, 0, a),
                     ROAD, collide=False, name='road')
        self.preview.append(('road_arc', c, a0, a1))

    def sdf(self, name):
        body = '\n        '.join(self.items)
        return (f'    <model name="{name}">\n      <static>true</static>\n'
                f'      <link name="link">\n        {body}\n      </link>\n    </model>\n')


def build():
    rng = random.Random(2026)
    course = Course()
    terrain = Course()
    parts_dir = os.path.join(PKG, 'models', PARTS, 'meshes')

    # ---------------------------------------------------------------- zemin (z = 0 ust yuzey)
    # Havuz icin zeminde delik birakilir; havuzun tabani yer duzlemi (z = -0.16).
    big = (-6.0, 20.0, -5.0, 14.0)
    px0, px1 = POOL_X
    for (x0, x1, y0, y1) in ((big[0], px0, big[2], big[3]), (px1, big[1], big[2], big[3]),
                             (px0, px1, big[2], -HALF), (px0, px1, HALF, big[3])):
        terrain.box((x1 - x0, y1 - y0, 0.5), ((x0 + x1) / 2, (y0 + y1) / 2, -0.25, 0, 0, 0),
                    GRASS, name='terrain')

    # ---------------------------------------------------------------- yollar
    course.road_line(0.0, POOL_X[0], ROW_A)            # havuzun ustunu ortmesin
    course.road_line(POOL_X[1], ROW_LEN, ROW_A)
    course.road_line(0.0, ROW_LEN, ROW_B)
    course.road_line(ROW_C_END, ROW_LEN, ROW_C)
    course.road_arc((0.0, (ROW_A + ROW_B) / 2), -math.pi / 2, -3 * math.pi / 2)
    course.road_arc((ROW_LEN, (ROW_B + ROW_C) / 2), -math.pi / 2, math.pi / 2)
    course.road_line(-0.5, ACCEL_LEN + STOP_LEN, ROW_D)

    # ---------------------------------------------------------------- bariyerler
    def straight_barriers(y, x0, x1, gaps=(), z_upper=None):
        for side in (-1, 1):
            cuts = [x0] + [g for gap in gaps for g in gap] + [x1]
            for a, b in zip(cuts[::2], cuts[1::2]):
                course.barrier_line((a, y + side * BAR_Y), (b, y + side * BAR_Y),
                                    z_of=z_upper if side == 1 else None)

    straight_barriers(ROW_A, 0.0, ROW_LEN, z_upper=lambda x: side_slope_height(x, HALF)
                      if SIDE_X[0] <= x <= SIDE_X[1] else 0.0)
    straight_barriers(ROW_B, 0.0, ROW_LEN,
                      gaps=[(SLIDER_X - SLIDER_W / 2 - 0.05, SLIDER_X + SLIDER_W / 2 + 0.05)])
    straight_barriers(ROW_C, ROW_C_END, ROW_LEN)
    course.barrier_line((ROW_LEN, ROW_A - BAR_Y), (ROW_LEN, ROW_A + BAR_Y))      # A sonu
    course.barrier_line((ROW_C_END, ROW_C - BAR_Y), (ROW_C_END, ROW_C + BAR_Y))  # C sonu
    cl = (0.0, (ROW_A + ROW_B) / 2)
    course.barrier_arc(cl, TURN_R - BAR_Y, -math.pi / 2, -3 * math.pi / 2)
    course.barrier_arc(cl, TURN_R + BAR_Y, -math.pi / 2, -3 * math.pi / 2)
    cr = (ROW_LEN, (ROW_B + ROW_C) / 2)
    course.barrier_arc(cr, TURN_R - BAR_Y, -math.pi / 2, math.pi / 2)
    course.barrier_arc(cr, TURN_R + BAR_Y, -math.pi / 2, math.pi / 2)
    straight_barriers(ROW_D, -0.5, ACCEL_LEN + STOP_LEN)
    course.barrier_line((-0.5, ROW_D - BAR_Y), (-0.5, ROW_D + BAR_Y))
    course.barrier_line((ACCEL_LEN + STOP_LEN, ROW_D - BAR_Y),
                        (ACCEL_LEN + STOP_LEN, ROW_D + BAR_Y))

    # ---------------------------------------------------------------- cizgiler
    def line_across(x, y, mat, width=0.06):
        course.box((width, ROAD_W, 0.003), (x, y, 0.0025, 0, 0, 0), mat, collide=False,
                   name='line')

    line_across(7.0, ROW_A, WHITE)                                  # baslangic
    for i in range(12):                                             # bitis (damali)
        for j in range(2):
            course.box((0.1, ROAD_W / 12, 0.003),
                       (FINISH_X + 0.05 + j * 0.1, ROW_C - HALF + (i + 0.5) * ROAD_W / 12,
                        0.0025, 0, 0, 0),
                       color(0.05, 0.05, 0.05) if (i + j) % 2 else WHITE, collide=False,
                       name='finish')
    line_across(0.0, ROW_D, WHITE)                                  # hizlanma baslangic
    line_across(ACCEL_LEN, ROW_D, WHITE)                            # hizlanma bitis
    course.preview.append(('label', (7.6, ROW_A + 0.95), 'START'))
    course.preview.append(('label', (FINISH_X, ROW_C - 1.0), 'BITIS'))

    # ---------------------------------------------------------------- 1) su gecisi + yagmur
    pool_mat = color(0.45, 0.42, 0.38)
    course.slope_box((px1 - POOL_RAMP, -POOL_DEPTH), (px1, 0.0), ROW_A, ROAD_W, pool_mat,
                     name='pool_ramp')                                  # giris
    course.slope_box((px0 + POOL_RAMP, -POOL_DEPTH), (px0, 0.0), ROW_A, ROAD_W, pool_mat,
                     name='pool_ramp')                                  # cikis
    water = (f'<visual name="water"><pose>{(px0 + px1) / 2:.3f} 0 {-POOL_DEPTH / 2 - 0.005:.4f}'
             f' 0 0 0</pose><geometry><box><size>{px1 - px0:.3f} {ROAD_W:.3f} '
             f'{POOL_DEPTH - 0.01:.4f}</size></box></geometry>'
             f'<material><ambient>0.15 0.35 0.7 0.55</ambient>'
             f'<diffuse>0.15 0.35 0.7 0.55</diffuse></material>'
             f'<transparency>0.45</transparency></visual>')
    course.items.append(water)
    fx = (px0 + px1) / 2
    for side in (-1, 1):                                            # yagmurlama cercevesi
        course.cylinder(0.015, 0.7, (fx, side * (BAR_Y + 0.12), 0.35, 0, 0, 0),
                        color(0.3, 0.4, 0.7), name='rain_pole')
    course.box((0.03, 2 * (BAR_Y + 0.12), 0.03), (fx, 0, 0.7, 0, 0, 0),
               color(0.3, 0.4, 0.7), name='rain_bar')
    course.preview.append(('zone', (px0, -HALF), (px1, HALF), (70, 120, 220), '1'))

    # ---------------------------------------------------------------- 2) cakilli / tasli yol
    for _ in range(90):
        sz = rng.uniform(0.012, 0.02)                               # en buyuk 5 cm x 0.4
        course.box((sz, sz * rng.uniform(0.7, 1.0), sz * rng.uniform(0.5, 0.9)),
                   (rng.uniform(*GRAVEL_X), rng.uniform(-HALF + 0.05, HALF - 0.05),
                    sz * 0.3, 0, 0, rng.uniform(0, math.pi)),
                   color(0.55, 0.52, 0.48), name='gravel')
    course.preview.append(('zone', (GRAVEL_X[0], -HALF), (GRAVEL_X[1], HALF), (150, 140, 120),
                           '2'))

    # ---------------------------------------------------------------- 3) yan egim (%20)
    side_slope_mesh().write(os.path.join(parts_dir, 'side_slope.obj'))
    course.mesh('side_slope.obj', color(0.85, 0.75, 0.2), name='side_slope')
    course.preview.append(('zone', (SIDE_X[0], -HALF), (SIDE_X[1], HALF), (230, 200, 60),
                           '3'))

    # ---------------------------------------------------------------- 4) dik engel
    course.box((STEP_X[1] - STEP_X[0], ROAD_W, STEP_H),
               ((STEP_X[0] + STEP_X[1]) / 2, ROW_B, STEP_H / 2, 0, 0, 0),
               color(0.8, 0.8, 0.82), name='step')
    course.preview.append(('zone', (STEP_X[0], ROW_B - HALF), (STEP_X[1], ROW_B + HALF),
                           (200, 200, 205), '4'))

    # ---------------------------------------------------------------- 7) engebeli arazi
    # Tumsek (Sekil 4, 20 x 5 cm -> 8 x 2 cm): yarisi gomulu yatay silindir. Kirisi 8 cm,
    # yuksekligi 2 cm olan daire yayi: r = (4^2 + 2^2) / (2 * 2) = 5 cm, merkez z = -3 cm.
    bump_r = (0.04 ** 2 + 0.02 ** 2) / (2 * 0.02)
    bx0, bx1 = BUMPS_X
    for i, x in enumerate(bx0 + (bx1 - bx0) * (k + 0.5) / 6 for k in range(6)):
        for y in ((-0.3, 0.3) if i % 2 == 0 else (0.0,)):
            course.cylinder(bump_r, 0.3, (x, ROW_C + y, 0.02 - bump_r, math.pi / 2, 0, 0),
                            color(0.6, 0.45, 0.25), name='bump')
            course.preview.append(('zone', (x - 0.04, ROW_C + y - 0.15),
                                   (x + 0.04, ROW_C + y + 0.15), (150, 110, 60), ''))
    course.preview.append(('label', ((bx0 + bx1) / 2, ROW_C - 0.9), '7'))

    # ---------------------------------------------------------------- 8-9-10) rampa + atis
    _, (ra, rb, rc, rd) = ramp_profile()
    ramp_mat = color(0.7, 0.55, 0.85)
    up = course.slope_box((ra, 0.0), (rb, RAMP_H), ROW_C, ROAD_W, ramp_mat, name='ramp_up')
    down = course.slope_box((rd, 0.0), (rc, RAMP_H), ROW_C, ROAD_W, ramp_mat, name='ramp_down')
    course.box((rb - rc, ROAD_W, RAMP_H), ((rb + rc) / 2, ROW_C, RAMP_H / 2, 0, 0, 0),
               color(0.78, 0.65, 0.9), name='platform')
    for xm, zm, pitch, (nx, nz) in (up, down):                      # "stop" seritleri
        course.box((0.06, ROAD_W, 0.004), (xm + nx * 0.003, ROW_C, zm + nz * 0.003, 0, pitch, 0),
                   WHITE, collide=False, name='stop_line')
    course.preview.append(('zone', (rb, ROW_C - HALF), (ra, ROW_C + HALF), (170, 120, 210),
                           '8'))
    course.preview.append(('zone', (rc, ROW_C - HALF), (rb, ROW_C + HALF), (200, 160, 230),
                           '9'))
    course.preview.append(('zone', (rd, ROW_C - HALF), (rc, ROW_C + HALF), (170, 120, 210),
                           '10'))

    # ---------------------------------------------------------------- tabelalar
    # Robotun sag tarafinda, bariyerin disinda, robota donuk
    signs = []

    def sign(n, x, row, heading_neg_x):
        y = row + (0.85 if heading_neg_x else -0.85)
        yaw = math.pi if heading_neg_x else 0.0
        signs.append((n, x, y, yaw))

    sign(1, px1 + 0.3, ROW_A, True)
    sign(2, GRAVEL_X[1] + 0.3, ROW_A, True)
    sign(3, SIDE_X[1] + 0.3, ROW_A, True)
    sign(4, STEP_X[0] - 0.3, ROW_B, False)
    sign(5, CONE_XS[0] - 0.4, ROW_B, False)
    sign(6, SLIDER_X - 0.9, ROW_B, False)
    sign(7, bx1 + 0.3, ROW_C, True)
    sign(8, ra + 0.3, ROW_C, True)
    sign(9, rb, ROW_C, True)
    sign(10, rc, ROW_C, True)
    signs.append((11, -0.3, ROW_D - 0.85, 0.0))
    signs.append((11, ACCEL_LEN + 0.3, ROW_D - 0.85, 0.0))

    includes = []
    for n, x, y, yaw in signs:
        includes.append(('stage_sign_%d' % n, f'sign_{n}_{len(includes)}', (x, y, 0, 0, 0, yaw)))
        course.preview.append(('sign', (x, y), str(n)))

    # ---------------------------------------------------------------- 5) koniler
    for i, x in enumerate(CONE_XS):
        y = ROW_B + (0.3 if i % 2 == 0 else -0.3)
        includes.append(('traffic_cone', f'cone_{i + 1}', (x, y, 0, 0, 0, 0)))
        course.preview.append(('cone', (x, y), ''))

    # ---------------------------------------------------------------- hedef
    includes.append(('shooting_target', 'target', (TARGET_POS[0], TARGET_POS[1], 0, 0, 0,
                                                   math.pi)))
    course.preview.append(('target', TARGET_POS, 'hedef'))

    # ---------------------------------------------------------------- 6) kayar engel
    includes.append(('sliding_obstacle', 'sliding_obstacle', (SLIDER_X, ROW_B, 0, 0, 0, 0)))
    course.preview.append(('slider', (SLIDER_X, ROW_B), ''))

    return course, terrain, includes, signs, (ra, rb, rc, rd)


# ----------------------------------------------------------------------------- modeller
def write_models():
    base = os.path.join(PKG, 'models')
    cfg = ('<?xml version="1.0"?>\n<model>\n  <name>{n}</name>\n  <version>1.0</version>\n'
           '  <sdf version="1.8">model.sdf</sdf>\n  <description>{d}</description>\n</model>\n')

    def write(name, desc, sdf):
        os.makedirs(os.path.join(base, name), exist_ok=True)
        with open(os.path.join(base, name, 'model.config'), 'w') as f:
            f.write(cfg.format(n=name, d=desc))
        if sdf:
            with open(os.path.join(base, name, 'model.sdf'), 'w') as f:
                f.write(sdf)

    write(PARTS, 'TEKNOFEST parkuru yan egim zemini (mesh)', None)

    # Trafik konisi: 40x40 cm taban, 75 cm (izin verilen ust sinir 80 cm) -> x 0.4
    h = 0.31
    stripes = []
    k = 6
    for i in range(k):
        r = 0.06 - 0.045 * (i + 0.5) / k
        z = 0.012 + h * (i + 0.5) / k
        mat = color(1.0, 0.45, 0.0) if i % 2 == 0 else WHITE
        stripes.append(f'<visual name="body_{i}"><pose>0 0 {z:.4f} 0 0 0</pose><geometry>'
                       f'<cylinder><radius>{r:.4f}</radius><length>{h / k:.4f}</length>'
                       f'</cylinder></geometry>{mat}</visual>')
    cone = f'''<?xml version="1.0"?>
<sdf version="1.8">
  <model name="traffic_cone">
    <static>true</static>
    <link name="link">
      <visual name="base"><pose>0 0 0.006 0 0 0</pose>
        <geometry><box><size>0.16 0.16 0.012</size></box></geometry>{color(1.0, 0.45, 0.0)}
      </visual>
      {''.join(stripes)}
      <collision name="base_c"><pose>0 0 0.006 0 0 0</pose>
        <geometry><box><size>0.16 0.16 0.012</size></box></geometry></collision>
      <collision name="body_c"><pose>0 0 {h / 2:.4f} 0 0 0</pose>
        <geometry><cylinder><radius>0.045</radius><length>{h:.4f}</length></cylinder>
        </geometry></collision>
    </link>
  </model>
</sdf>
'''
    write('traffic_cone', 'Trafik konisi (sartname 6.7, olcek x0.4)', cone)

    # Kayar engel: dunyaya sabit taban + y ekseninde kayan panel (prismatic eklem)
    slider = f'''<?xml version="1.0"?>
<sdf version="1.8">
  <!-- Kayar engel (sartname 6.8, olcek x0.4): 40 cm genislik, 8 cm/s ile gider gelir.
       Konum komutu: /course/slider_cmd (std_msgs/Float64), sliding_obstacle node'u gonderir. -->
  <model name="sliding_obstacle">
    <link name="base">
      <inertial><mass>1.0</mass>
        <inertia><ixx>0.01</ixx><iyy>0.01</iyy><izz>0.01</izz></inertia></inertial>
    </link>
    <joint name="world_joint" type="fixed">
      <parent>world</parent>
      <child>base</child>
    </joint>
    <link name="panel">
      <pose>0 0 {0.02 + 0.2:.3f} 0 0 0</pose>
      <inertial><mass>2.0</mass>
        <inertia><ixx>0.05</ixx><iyy>0.03</iyy><izz>0.03</izz></inertia></inertial>
      <visual name="panel_v">
        <geometry><box><size>0.08 {SLIDER_W:.3f} 0.4</size></box></geometry>
        {color(0.1, 0.15, 0.45)}
      </visual>
      <visual name="light_1"><pose>-0.045 -0.1 0.1 0 1.5708 0</pose>
        <geometry><cylinder><radius>0.035</radius><length>0.01</length></cylinder></geometry>
        {color(0.95, 0.75, 0.0)}
      </visual>
      <visual name="light_2"><pose>-0.045 0.1 0.1 0 1.5708 0</pose>
        <geometry><cylinder><radius>0.035</radius><length>0.01</length></cylinder></geometry>
        {color(0.95, 0.75, 0.0)}
      </visual>
      <collision name="panel_c">
        <geometry><box><size>0.08 {SLIDER_W:.3f} 0.4</size></box></geometry>
      </collision>
    </link>
    <joint name="slide_joint" type="prismatic">
      <parent>base</parent>
      <child>panel</child>
      <axis>
        <xyz>0 1 0</xyz>
        <limit><lower>{-SLIDER_AMP - 0.05:.3f}</lower><upper>{SLIDER_AMP + 0.05:.3f}</upper>
          <effort>100</effort><velocity>1.0</velocity></limit>
        <dynamics><damping>5.0</damping></dynamics>
      </axis>
    </joint>
    <plugin filename="ignition-gazebo-joint-position-controller-system"
            name="ignition::gazebo::systems::JointPositionController">
      <joint_name>slide_joint</joint_name>
      <topic>/course/slider_cmd</topic>
      <p_gain>300</p_gain>
      <i_gain>10</i_gain>
      <d_gain>40</d_gain>
      <cmd_max>100</cmd_max>
      <cmd_min>-100</cmd_min>
    </plugin>
  </model>
</sdf>
'''
    write('sliding_obstacle', 'Kayar engel (sartname 6.8, olcek x0.4)', slider)


# ----------------------------------------------------------------------------- dunya
def write_world(course, terrain, includes):
    inc = ''.join(
        f'    <include>\n      <uri>model://{uri}</uri>\n      <name>{name}</name>\n'
        f'      <pose>{" ".join(f"{v:.4f}" for v in pose)}</pose>\n    </include>\n'
        for uri, name, pose in includes)
    fx = (POOL_X[0] + POOL_X[1]) / 2
    world = f'''<?xml version="1.0"?>
<!--
  TEKNOFEST 2026 Insansiz Kara Araci yarisma parkuru (Sekil 1), olcek x {S}.
  Bu dosya ugv_course/scripts/make_teknofest_course.py ile uretilir; elle duzenlemeyin.
  Robot baslangici: (7.5, 0) -x yonune bakar. Hizlanma parkuru: (-0.3, {ROW_D}) +x yonune bakar.
-->
<sdf version="1.8">
  <world name="teknofest_course">

    <physics name="1ms" type="ignored">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>

    <plugin filename="ignition-gazebo-physics-system"
            name="ignition::gazebo::systems::Physics"/>
    <plugin filename="ignition-gazebo-user-commands-system"
            name="ignition::gazebo::systems::UserCommands"/>
    <plugin filename="ignition-gazebo-scene-broadcaster-system"
            name="ignition::gazebo::systems::SceneBroadcaster"/>
    <plugin filename="ignition-gazebo-sensors-system"
            name="ignition::gazebo::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>
    <!-- Yagmur icin parcacik sistemi -->
    <plugin filename="ignition-gazebo-particle-emitter2-system"
            name="ignition::gazebo::systems::ParticleEmitter2"/>

    <scene>
      <ambient>0.6 0.6 0.6 1</ambient>
      <background>0.7 0.8 0.9 1</background>
    </scene>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.9 0.9 0.9 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.3 0.4 -0.85</direction>
    </light>

    <!-- Havuzun tabani: yer duzlemi z = {-POOL_DEPTH}. Diger her yer zemin bloklariyla z = 0. -->
    <model name="ground_plane">
      <static>true</static>
      <pose>0 0 {-POOL_DEPTH} 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>100 100</size></plane></geometry>
          {color(0.35, 0.3, 0.25)}
        </visual>
      </link>
    </model>

{terrain.sdf('terrain')}
{course.sdf('course')}
    <!-- Yagmur (sartname 6.3): havuzun ustunden asagi yagan parcaciklar -->
    <model name="rain">
      <static>true</static>
      <pose>{fx:.3f} 0 0.68 0 1.5708 0</pose>
      <link name="emitter">
        <particle_emitter name="rain_emitter" type="box">
          <emitting>true</emitting>
          <size>0.1 {ROAD_W:.2f} {POOL_X[1] - POOL_X[0]:.2f}</size>
          <particle_size>0.004 0.004 0.03</particle_size>
          <lifetime>0.35</lifetime>
          <min_velocity>2.0</min_velocity>
          <max_velocity>2.5</max_velocity>
          <rate>600</rate>
          <material>
            <ambient>0.6 0.7 0.9 0.6</ambient>
            <diffuse>0.6 0.7 0.9 0.6</diffuse>
          </material>
        </particle_emitter>
      </link>
    </model>

{inc}
  </world>
</sdf>
'''
    path = os.path.join(PKG, 'worlds', 'teknofest_course.sdf')
    with open(path, 'w') as f:
        f.write(world)
    return path


def write_water_yaml():
    path = os.path.join(PKG, 'config', 'water_zones.yaml')
    with open(path, 'w') as f:
        f.write('# make_teknofest_course.py tarafindan uretildi: su gecisi havuzu (sartname 6.3)\n'
                'water_physics:\n  ros__parameters:\n'
                f'    zones: ["{POOL_X[0]:.3f}, {POOL_X[1]:.3f}, {-HALF:.3f}, {HALF:.3f}, '
                f'{POOL_DEPTH:.3f}, '
                f'{POOL_RAMP:.3f}"]\n'
                '    # x_min, x_max, y_min, y_max, derinlik, egim uzunlugu (m)\n'
                '    robot_height: 0.30   # yerden govde ustune (m)\n')
    return path


def write_preview(course, signs):
    from PIL import Image, ImageDraw, ImageFont
    ppm = 40
    x_lo, x_hi, y_lo, y_hi = -3.5, 17.0, -1.6, 11.0
    w, h = int((x_hi - x_lo) * ppm), int((y_hi - y_lo) * ppm)
    img = Image.new('RGB', (w, h), (115, 140, 100))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
                                  14)
    except OSError:
        font = ImageFont.load_default()

    def P(x, y):
        return ((x - x_lo) * ppm, (y_hi - y) * ppm)

    for kind, *a in course.preview:
        if kind == 'road':
            (x0, y0), (x1, y1) = a
            d.rectangle([P(x0, y1), P(x1, y0)], fill=(70, 70, 75))
        elif kind == 'road_arc':
            c, a0, a1 = a
            for i in range(60):
                t = a0 + (a1 - a0) * i / 59
                x, y = c[0] + TURN_R * math.cos(t), c[1] + TURN_R * math.sin(t)
                r = HALF * ppm
                px, py = P(x, y)
                d.ellipse([px - r, py - r, px + r, py + r], fill=(70, 70, 75))
    for kind, *a in course.preview:
        if kind == 'zone':
            (x0, y0), (x1, y1), col, label = a
            d.rectangle([P(x0, y1), P(x1, y0)], fill=col)
            if label:
                px, py = P((x0 + x1) / 2, y0)
                d.text((px, py + 14), label, fill='white', font=font, anchor='mm')
        elif kind == 'barrier':
            d.line([P(*a[0]), P(*a[1])], fill=(220, 30, 30), width=3)
        elif kind == 'label':
            d.text(P(*a[0]), a[1], fill='white', font=font, anchor='mm')
        elif kind == 'cone':
            px, py = P(*a[0])
            d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(255, 120, 0))
        elif kind == 'slider':
            px, py = P(*a[0])
            d.rectangle([px - 3, py - SLIDER_W / 2 * ppm, px + 3, py + SLIDER_W / 2 * ppm],
                        fill=(30, 40, 120))
            d.line([P(a[0][0], a[0][1] - SLIDER_AMP), P(a[0][0], a[0][1] + SLIDER_AMP)],
                   fill=(30, 40, 120), width=1)
            d.text((px, py - 40), a[1], fill='white', font=font, anchor='mm')
        elif kind == 'target':
            px, py = P(*a[0])
            for r, c in ((10, 'black'), (7, 'white'), (4, 'black')):
                d.ellipse([px - r, py - r, px + r, py + r], fill=c)
            d.text((px, py + 18), a[1], fill='white', font=font, anchor='mm')
        elif kind == 'sign':
            px, py = P(*a[0])
            d.ellipse([px - 9, py - 9, px + 9, py + 9], fill='white', outline=(220, 0, 0),
                      width=3)
            d.text((px, py), a[1], fill='black', font=font, anchor='mm')
    sx, sy = P(7.5, 0)
    d.polygon([(sx - 12, sy), (sx + 6, sy - 8), (sx + 6, sy + 8)], fill=(40, 90, 230))
    d.text(P(ACCEL_LEN / 2, ROW_D + 0.95), '11 hizlanma parkuru (12 m + 4 m durma)',
           fill='white', font=font, anchor='mm')
    legend = ['TEKNOFEST 2026 IKA parkuru', f'olcek x{S}, cizgiler 1 m arayla', '',
              '1  su gecisi + yagmur (16 cm)', '2  cakilli / tasli yol', '3  yan egim %20',
              '4  dik engel (6 cm)', '5  trafik konileri', '6  kayar engel (8 cm/s)',
              '7  engebeli arazi (tumsekler)', '8  dik egim %45 (cikis, stop)',
              '9  atis bolgesi', '10 dik egim %45 (inis, stop)', '11 hizlanma parkuru']
    lx, ly = P(10.0, 7.2)
    for i, line in enumerate(legend):
        d.text((lx, ly + i * 19), line, fill='white', font=font)
    for gx in range(int(x_lo), int(x_hi) + 1):
        d.line([P(gx, y_lo), P(gx, y_lo + 0.15)], fill='white')
    path = os.path.join(PKG, 'docs', 'course_top_view.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, optimize=True)
    return path


def main():
    course, terrain, includes, signs, _ = build()
    write_models()
    print('dunya   :', write_world(course, terrain, includes))
    print('su      :', write_water_yaml())
    print('gorunus :', write_preview(course, signs))
    print(f'parca sayisi: {course.n} (+{len(includes)} model)')


if __name__ == '__main__':
    main()
