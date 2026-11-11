"""Parkur asama tabelasi tespiti (ROS'tan bagimsiz, sadece OpenCV + NumPy).

Tabela: kirmizi cember icinde siyah numara (sartname Sekil 2).

Yontem:
    1. HSV'de kirmizi renk maskesi -> dairesel konturlar (tabela adaylari)
    2. Adayin cevreleyen kutusu kare bir yamaya (patch) olceklenir. Kamera tabelaya
       egik bakiyorsa elips gorunur; kareye olceklemek onu tekrar daireye cevirir.
    3. Ic beyaz bolgedeki koyu pikseller (numara) Otsu esigiyle ayrilir, numara kendi
       sinirlarina gore kirpilip en-boy orani korunarak sabit boyuta olceklenir.
    4. Numara, sablonlarla (tabela dokularindan ayni yontemle uretilir) karsilastirilir.
       Normalize korelasyon skoru en yuksek olan numara secilir.
"""

import glob
import os
import re

import cv2
import numpy as np

PATCH = 96            # normalize edilmis tabela yamasinin boyutu (px)
DIGIT = 48            # numara goruntusunun boyutu (px)
INNER_RATIO = 0.70    # numaranin arandigi ic dairenin, dis capa orani


def red_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    low = cv2.inRange(hsv, (0, 90, 60), (10, 255, 255))
    high = cv2.inRange(hsv, (165, 90, 60), (180, 255, 255))
    mask = cv2.bitwise_or(low, high)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def _digit_patch(bgr, rect):
    """Tabela kutusundan numarayi kirpar ve DIGIT x DIGIT boyutlu goruntuye cevirir.

    Numara kendi sinirlarina gore kirpilir ve en-boy orani korunarak olceklenir.
    Boylece '1' dar, '11' genis kalir; bu da numaralari ayirt etmeye yardim eder.
    """
    x, y, w, h = rect
    crop = cv2.resize(bgr[y:y + h, x:x + w], (PATCH, PATCH), interpolation=cv2.INTER_CUBIC)
    # Parlaklik (V = max(R, G, B)): kirmizi halka parlak, siyah numara koyu gorunur.
    # Gri tonlamada kirmizi da koyu gorunur ve halkanin kenari numaraya karisir.
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2]
    circle = np.zeros((PATCH, PATCH), np.uint8)
    cv2.circle(circle, (PATCH // 2, PATCH // 2), int(PATCH / 2 * INNER_RATIO), 255, -1)
    inside = gray[circle > 0]
    if inside.size == 0 or int(inside.max()) - int(inside.min()) < 40:
        return None                                 # kontrastsiz: numara yok
    thr, _ = cv2.threshold(inside.reshape(-1, 1), 0, 255,
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = ((gray < thr) & (circle > 0)).astype(np.uint8) * 255
    ys, xs = np.nonzero(dark)
    if len(xs) < 8:
        return None
    dark = dark[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    dh, dw = dark.shape
    scale = (DIGIT - 8) / max(dh, dw)
    dark = cv2.resize(dark, (max(1, int(round(dw * scale))), max(1, int(round(dh * scale)))),
                      interpolation=cv2.INTER_AREA)
    out = np.zeros((DIGIT, DIGIT), np.float32)
    oy, ox = (DIGIT - dark.shape[0]) // 2, (DIGIT - dark.shape[1]) // 2
    out[oy:oy + dark.shape[0], ox:ox + dark.shape[1]] = dark
    return cv2.GaussianBlur(out, (3, 3), 0)


def _score(a, b):
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else 0.0


def find_sign_candidates(bgr, min_area=120, min_circularity=0.6):
    """Kirmizi, dairesel konturlarin cevreleyen kutularini dondurur."""
    contours, _ = cv2.findContours(red_mask(bgr), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(c)
        # Egik bakista elips olur: kutunun icini ne kadar doldurdugunu kontrol et
        fill = area / (np.pi * w * h / 4.0)
        aspect = min(w, h) / max(w, h)
        perim = cv2.arcLength(c, True)
        circ = 4 * np.pi * area / (perim * perim) if perim > 0 else 0
        if fill > 0.75 and aspect > 0.35 and circ > min_circularity * aspect:
            rects.append((x, y, w, h))
    return rects


class SignDetector:
    """Tabela numarasi okuyucu.

    rotations: kamera goruntusunun sablona gore donuk olabilecegi acilar (90 derecenin
    katlari). Gercek kamerada 0 yeterlidir; simulasyonda doku yonu modele gore degisebilir.
    """

    def __init__(self, templates, rotations=(0,), min_score=0.45, min_margin=0.05):
        self.templates = templates
        self.rotations = rotations
        self.min_score = min_score
        self.min_margin = min_margin

    @classmethod
    def from_texture_dir(cls, models_dir, **kwargs):
        """ugv_gazebo/models/stage_sign_N/materials/textures/sign_N.png dosyalarindan sablon."""
        templates = {}
        for path in glob.glob(os.path.join(models_dir, 'stage_sign_*', 'materials',
                                           'textures', 'sign_*.png')):
            number = int(re.search(r'sign_(\d+)\.png$', path).group(1))
            img = cv2.imread(path)
            rects = find_sign_candidates(img)
            if rects:
                rect = max(rects, key=lambda r: r[2] * r[3])
                patch = _digit_patch(img, rect)
                if patch is not None:
                    templates[number] = patch
        if not templates:
            raise RuntimeError(f'Tabela sablonu bulunamadi: {models_dir}')
        return cls(templates, **kwargs)

    def read(self, bgr, rect):
        """(numara, skor, donus) ya da None dondurur."""
        patch = _digit_patch(bgr, rect)
        if patch is None:
            return None
        scores = []
        for rot in self.rotations:
            p = np.rot90(patch, k=rot // 90) if rot else patch
            for number, tmpl in self.templates.items():
                scores.append((_score(p, tmpl), number, rot))
        scores.sort(reverse=True)
        best = scores[0]
        runner_up = next((s for s in scores[1:] if s[1] != best[1]), (0.0, None, 0))
        if best[0] < self.min_score or best[0] - runner_up[0] < self.min_margin:
            return None
        return best[1], best[0], best[2]

    def detect(self, bgr):
        """Goruntudeki tum tabelalari [(numara, skor, (x, y, w, h)), ...] olarak dondurur."""
        results = []
        for rect in find_sign_candidates(bgr):
            r = self.read(bgr, rect)
            if r is not None:
                results.append((r[0], r[1], rect))
        return results
