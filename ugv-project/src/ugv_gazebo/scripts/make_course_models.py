#!/usr/bin/env python3
"""TEKNOFEST IKA parkuru icin Gazebo modellerini (doku + model.sdf) uretir.

Uretilen modeller (ugv_gazebo/models/ altina):
    stage_sign_1 ... stage_sign_11 : parkur asama tabelalari (Sekil 2)
    shooting_target                : atis hedefi (Sekil 5)

Olcek: simulasyonda parkur 0.4 oraninda kucultulmustur (sartname degeri x 0.4).
    Tabela dis capi 60 cm -> 24 cm, hedef kagidi 36 x 24 cm -> 14.4 x 9.6 cm.

Sartnamede tabela fontu 'Arial Black'; Ubuntu'da bulunmadigi icin Arial ile ayni
olculere sahip Liberation Sans Bold kullanilir (--font ile degistirilebilir).

Kullanim:
    python3 make_course_models.py            # ugv_gazebo/models altina yazar
"""

import argparse
import os

from PIL import Image, ImageDraw, ImageFont

SCALE = 0.4
SIGN_DIAMETER = 0.60 * SCALE          # m
TARGET_W, TARGET_H = 0.36 * SCALE, 0.24 * SCALE   # m (Sekil 5 izgarasi)
DEFAULT_FONT = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'

MODEL_CONFIG = '''<?xml version="1.0"?>
<model>
  <name>{name}</name>
  <version>1.0</version>
  <sdf version="1.8">model.sdf</sdf>
  <description>{desc}</description>
</model>
'''


def sign_texture(number, font_path, size=512):
    img = Image.new('RGB', (size, size), 'white')
    d = ImageDraw.Draw(img)
    c = size / 2
    r_out, r_in = size * 0.49, size * 0.38
    d.ellipse([c - r_out, c - r_out, c + r_out, c + r_out], fill=(220, 0, 0))
    d.ellipse([c - r_in, c - r_in, c + r_in, c + r_in], fill='white')
    text = str(number)
    font = ImageFont.truetype(font_path, int(size * (0.42 if len(text) == 1 else 0.36)))
    d.text((c, c), text, fill='black', font=font, anchor='mm')
    return img


def target_texture(px_per_cm=30):
    w, h = int(36 * px_per_cm), int(24 * px_per_cm)
    img = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(img)
    for i in range(0, w + 1, px_per_cm):          # 1 cm izgara
        d.line([(i, 0), (i, h)], fill=(190, 190, 190), width=1)
    for j in range(0, h + 1, px_per_cm):
        d.line([(0, j), (w, j)], fill=(190, 190, 190), width=1)
    cx, cy = w / 2, h / 2
    d.line([(cx, 0), (cx, h)], fill=(220, 0, 0), width=3)   # eksenler
    d.line([(0, cy), (w, cy)], fill=(220, 0, 0), width=3)

    def disk(diam_cm, color):
        r = diam_cm / 2 * px_per_cm
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    disk(18, 'black')     # dis halka (18 cm)
    disk(12, 'white')     # orta halka (12 cm)
    disk(6, 'black')      # ic daire (6 cm)
    return img


def sign_sdf(name, number):
    board = SIGN_DIAMETER + 0.01
    pole_h = 0.25
    zc = pole_h + board / 2
    return f'''<?xml version="1.0"?>
<sdf version="1.8">
  <model name="{name}">
    <static>true</static>
    <link name="link">
      <!-- Direk -->
      <collision name="pole_collision">
        <pose>0 0 {pole_h / 2} 0 0 0</pose>
        <geometry><cylinder><radius>0.01</radius><length>{pole_h}</length></cylinder></geometry>
      </collision>
      <visual name="pole_visual">
        <pose>0 0 {pole_h / 2} 0 0 0</pose>
        <geometry><cylinder><radius>0.01</radius><length>{pole_h}</length></cylinder></geometry>
        <material><ambient>0.3 0.3 0.3 1</ambient><diffuse>0.3 0.3 0.3 1</diffuse></material>
      </visual>
      <!-- Tabela: on yuzu -x yonune bakar -->
      <collision name="board_collision">
        <pose>0 0 {zc:.4f} 0 0 0</pose>
        <geometry><box><size>0.005 {board:.4f} {board:.4f}</size></box></geometry>
      </collision>
      <visual name="board_visual">
        <pose>0 0 {zc:.4f} 0 0 0</pose>
        <geometry><box><size>0.005 {board:.4f} {board:.4f}</size></box></geometry>
        <material>
          <ambient>1 1 1 1</ambient>
          <diffuse>1 1 1 1</diffuse>
          <pbr><metal>
            <albedo_map>model://{name}/materials/textures/sign_{number}.png</albedo_map>
            <roughness>1.0</roughness>
            <metalness>0.0</metalness>
          </metal></pbr>
        </material>
      </visual>
    </link>
  </model>
</sdf>
'''


def target_sdf(name):
    pole_h = 0.30
    zc = pole_h + TARGET_H / 2
    frame = f'0.004 {TARGET_W + 0.02:.4f} {TARGET_H + 0.02:.4f}'
    return f'''<?xml version="1.0"?>
<sdf version="1.8">
  <model name="{name}">
    <static>true</static>
    <link name="link">
      <!-- Cerceve ayagi -->
      <collision name="stand_collision">
        <pose>0 0 {pole_h / 2} 0 0 0</pose>
        <geometry><box><size>0.02 0.02 {pole_h}</size></box></geometry>
      </collision>
      <visual name="stand_visual">
        <pose>0 0 {pole_h / 2} 0 0 0</pose>
        <geometry><box><size>0.02 0.02 {pole_h}</size></box></geometry>
        <material><ambient>0.4 0.25 0.1 1</ambient><diffuse>0.4 0.25 0.1 1</diffuse></material>
      </visual>
      <!-- Cerceve -->
      <visual name="frame_visual">
        <pose>0.003 0 {zc:.4f} 0 0 0</pose>
        <geometry><box><size>{frame}</size></box></geometry>
        <material><ambient>0.4 0.25 0.1 1</ambient><diffuse>0.4 0.25 0.1 1</diffuse></material>
      </visual>
      <!-- Hedef kagidi: on yuzu -x yonune bakar -->
      <collision name="paper_collision">
        <pose>0 0 {zc:.4f} 0 0 0</pose>
        <geometry><box><size>{frame}</size></box></geometry>
      </collision>
      <visual name="paper_visual">
        <pose>0 0 {zc:.4f} 0 0 0</pose>
        <geometry><box><size>0.002 {TARGET_W:.4f} {TARGET_H:.4f}</size></box></geometry>
        <material>
          <ambient>1 1 1 1</ambient>
          <diffuse>1 1 1 1</diffuse>
          <pbr><metal>
            <albedo_map>model://{name}/materials/textures/target.png</albedo_map>
            <roughness>1.0</roughness>
            <metalness>0.0</metalness>
          </metal></pbr>
        </material>
      </visual>
    </link>
  </model>
</sdf>
'''


def write_model(out_dir, name, desc, sdf, textures):
    tex_dir = os.path.join(out_dir, name, 'materials', 'textures')
    os.makedirs(tex_dir, exist_ok=True)
    for fname, img in textures.items():
        img.save(os.path.join(tex_dir, fname), optimize=True)
    with open(os.path.join(out_dir, name, 'model.config'), 'w') as f:
        f.write(MODEL_CONFIG.format(name=name, desc=desc))
    with open(os.path.join(out_dir, name, 'model.sdf'), 'w') as f:
        f.write(sdf)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=os.path.join(here, '..', 'models'))
    ap.add_argument('--font', default=DEFAULT_FONT)
    a = ap.parse_args()

    for n in range(1, 12):
        name = f'stage_sign_{n}'
        write_model(a.out, name, f'TEKNOFEST IKA parkur asama tabelasi {n} (olcek x{SCALE})',
                    sign_sdf(name, n), {f'sign_{n}.png': sign_texture(n, a.font)})
    write_model(a.out, 'shooting_target', f'TEKNOFEST IKA atis hedefi (olcek x{SCALE})',
                target_sdf('shooting_target'), {'target.png': target_texture()})
    print('Modeller yazildi:', os.path.abspath(a.out))


if __name__ == '__main__':
    main()
