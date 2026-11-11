#!/usr/bin/env python3
"""Gazebo .sdf dunyasindaki statik kutu/silindirlerden Nav2 haritasi (.pgm + .yaml) uretir.

SLAM ile gercek harita cikarilana kadar Nav2'yi test etmek icin referans harita saglar.
Robotun (0, 0, yaw=0) noktasinda dogdugu varsayilir; boylece map cercevesi = dunya cercevesi.

Kullanim:
    python3 sdf_to_map.py ../../ugv_gazebo/worlds/ugv_world.sdf ../maps/ugv_world
"""

import argparse
import math
import xml.etree.ElementTree as ET

FREE, OCCUPIED = 254, 0


def parse_pose(text):
    v = [float(x) for x in (text or '0 0 0 0 0 0').split()]
    return v + [0.0] * (6 - len(v))


def shapes(world_file, min_z, max_z):
    """(x, y, yaw, tur, boyut) listesi dondurur. Sadece LIDAR yuksekligini kesenler alinir."""
    root = ET.parse(world_file).getroot()
    for model in root.iter('model'):
        if (model.findtext('static') or '').strip() not in ('true', '1'):
            continue
        mx, my, mz, _, _, myaw = parse_pose(model.findtext('pose'))
        for col in model.iter('collision'):
            geom = col.find('geometry')
            if geom is None:
                continue
            box, cyl = geom.find('box'), geom.find('cylinder')
            if box is not None:
                sx, sy, sz = (float(v) for v in box.findtext('size').split())
                if mz + sz / 2 < min_z or mz - sz / 2 > max_z:
                    continue
                yield mx, my, myaw, 'box', (sx, sy)
            elif cyl is not None:
                r = float(cyl.findtext('radius'))
                h = float(cyl.findtext('length'))
                if mz + h / 2 < min_z or mz - h / 2 > max_z:
                    continue
                yield mx, my, myaw, 'cylinder', (r,)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('world')
    ap.add_argument('output', help='uzantisiz cikti yolu, orn. maps/ugv_world')
    ap.add_argument('--resolution', type=float, default=0.05)
    ap.add_argument('--size', type=float, default=13.0, help='haritanin kenar uzunlugu (m)')
    ap.add_argument('--min-z', type=float, default=0.05)
    ap.add_argument('--max-z', type=float, default=2.0)
    a = ap.parse_args()

    n = int(round(a.size / a.resolution))
    origin = -a.size / 2.0
    grid = [[FREE] * n for _ in range(n)]

    for x, y, yaw, kind, dim in shapes(a.world, a.min_z, a.max_z):
        c, s = math.cos(yaw), math.sin(yaw)
        for j in range(n):          # satir -> y
            wy = origin + (j + 0.5) * a.resolution
            for i in range(n):      # sutun -> x
                wx = origin + (i + 0.5) * a.resolution
                dx, dy = wx - x, wy - y
                if kind == 'box':
                    lx, ly = c * dx + s * dy, -s * dx + c * dy
                    hit = abs(lx) <= dim[0] / 2 and abs(ly) <= dim[1] / 2
                else:
                    hit = dx * dx + dy * dy <= dim[0] ** 2
                if hit:
                    grid[j][i] = OCCUPIED

    # PGM'de ilk satir haritanin ustu (en buyuk y) olmali
    with open(a.output + '.pgm', 'wb') as f:
        f.write(f'P5\n{n} {n}\n255\n'.encode())
        for row in reversed(grid):
            f.write(bytes(row))

    name = a.output.rsplit('/', 1)[-1]
    with open(a.output + '.yaml', 'w') as f:
        f.write(f'image: {name}.pgm\n'
                'mode: trinary\n'
                f'resolution: {a.resolution}\n'
                f'origin: [{origin}, {origin}, 0.0]\n'
                'negate: 0\n'
                'occupied_thresh: 0.65\n'
                'free_thresh: 0.25\n')
    print(f'{a.output}.pgm/.yaml yazildi ({n}x{n} hucre)')


if __name__ == '__main__':
    main()
