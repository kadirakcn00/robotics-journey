"""Tabela ve hedef tespitinin sentetik goruntulerle testi (ROS gerektirmez).

Dokular ugv_gazebo/models altindaki tabela/hedef resimlerinden alinir, perspektifle
farkli mesafe, aci, isik ve gurultu kosullarinda bir sahneye yerlestirilir.
"""

import os

import cv2
import numpy as np
import pytest

from ugv_perception.sign_detection import SignDetector
from ugv_perception.target_detection import detect_target

MODELS = os.path.join(os.path.dirname(__file__), '..', '..', 'ugv_gazebo', 'models')
W, H = 640, 480


def background(rng):
    img = np.full((H, W, 3), (120, 150, 110), np.uint8)          # yesilimsi zemin
    img[: H // 2] = (200, 180, 160)                              # gokyuzu/duvar
    noise = rng.normal(0, 8, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def paste(scene, tex, center, size, squash=1.0, tilt=0.0):
    """tex'i sahneye yerlestirir. squash<1: yatay sikistirma (egik bakis)."""
    h, w = tex.shape[:2]
    sx = size[0] * squash / 2
    sy = size[1] / 2
    cx, cy = center
    dst = np.float32([[cx - sx, cy - sy + tilt], [cx + sx, cy - sy - tilt],
                      [cx + sx, cy + sy + tilt], [cx - sx, cy + sy - tilt]])
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(tex, M, (W, H), flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (W, H))
    scene[mask > 0] = warped[mask > 0]
    return scene


def degrade(img, rng, brightness=1.0, blur=1):
    img = np.clip(img.astype(np.float32) * brightness + rng.normal(0, 4, img.shape), 0, 255)
    img = img.astype(np.uint8)
    return cv2.GaussianBlur(img, (blur * 2 + 1, blur * 2 + 1), 0) if blur else img


def sign_tex(n):
    return cv2.imread(os.path.join(MODELS, f'stage_sign_{n}', 'materials', 'textures',
                                   f'sign_{n}.png'))


@pytest.fixture(scope='module')
def detector():
    return SignDetector.from_texture_dir(MODELS)


def test_templates_loaded(detector):
    assert sorted(detector.templates) == list(range(1, 12))


@pytest.mark.parametrize('number', range(1, 12))
@pytest.mark.parametrize('size,squash,brightness,blur', [
    (120, 1.0, 1.0, 0),     # yakin, karsidan
    (60, 1.0, 0.8, 1),      # orta mesafe, biraz karanlik
    (40, 0.7, 1.0, 1),      # uzak, ~45 derece egik
    (80, 0.5, 0.6, 1),      # cok egik (~60 derece), karanlik
])
def test_sign_read(detector, number, size, squash, brightness, blur):
    rng = np.random.default_rng(number * 100 + size)
    scene = paste(background(rng), sign_tex(number), (380, 200), (size, size), squash, 2)
    scene = degrade(scene, rng, brightness, blur)
    found = detector.detect(scene)
    assert [n for n, _, _ in found] == [number], found


def test_multiple_signs(detector):
    rng = np.random.default_rng(7)
    scene = background(rng)
    for n, x in ((2, 100), (6, 260), (9, 420), (11, 560)):
        paste(scene, sign_tex(n), (x, 180), (70, 70))
    found = sorted(n for n, _, _ in detector.detect(degrade(scene, rng)))
    assert found == [2, 6, 9, 11]


def test_no_sign_no_detection(detector):
    rng = np.random.default_rng(3)
    scene = background(rng)
    cv2.rectangle(scene, (100, 300), (200, 360), (0, 0, 220), -1)   # kirmizi kutu
    cv2.circle(scene, (450, 150), 40, (0, 0, 200), 6)               # bos kirmizi halka
    assert detector.detect(degrade(scene, rng)) == []


def test_rotated_texture_with_rotations_enabled():
    det = SignDetector.from_texture_dir(MODELS, rotations=(0, 90, 180, 270))
    rng = np.random.default_rng(5)
    tex = np.rot90(sign_tex(4)).copy()
    scene = degrade(paste(background(rng), tex, (300, 220), (90, 90)), rng)
    found = det.detect(scene)
    assert [n for n, _, _ in found] == [4]


TARGET = os.path.join(MODELS, 'shooting_target', 'materials', 'textures', 'target.png')


@pytest.mark.parametrize('width,center,squash,brightness', [
    (300, (320, 240), 1.0, 1.0),     # tam karsida, buyuk
    (120, (200, 300), 1.0, 0.8),     # kucuk, kenarda
    (60, (450, 150), 0.8, 1.0),      # uzak (dis halka ~15 px cap)
    (200, (330, 230), 0.6, 0.7),     # egik ve karanlik
])
def test_target(width, center, squash, brightness):
    rng = np.random.default_rng(width)
    tex = cv2.imread(TARGET)
    h = width * tex.shape[0] / tex.shape[1]
    scene = paste(background(rng), tex, center, (width, h), squash)
    scene = degrade(scene, rng, brightness, 1)
    t = detect_target(scene)
    assert t is not None
    assert abs(t['center'][0] - center[0]) < 3 and abs(t['center'][1] - center[1]) < 3
    expected_r = width * 18 / 36 / 2 * np.sqrt(squash)   # dis halka ~ alan esdeger yaricap
    assert t['radius'] == pytest.approx(expected_r, rel=0.2)
    assert t['offset'][0] == pytest.approx((center[0] - W / 2) / (W / 2), abs=0.02)


def test_no_target():
    rng = np.random.default_rng(1)
    scene = background(rng)
    cv2.circle(scene, (300, 200), 50, (20, 20, 20), -1)     # tek siyah daire: hedef degil
    cv2.circle(scene, (500, 300), 40, (20, 20, 20), 8)      # ici bos halka: hedef degil
    assert detect_target(degrade(scene, rng)) is None
