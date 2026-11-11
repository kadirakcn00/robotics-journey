"""Atis hedefi tespiti (ROS'tan bagimsiz, sadece OpenCV + NumPy).

Hedef (sartname Sekil 5): beyaz izgarali kagit uzerinde siyah dis halka (18 cm),
beyaz orta halka (12 cm) ve siyah ic daire (6 cm).

Yontem:
    1. HSV'nin V (parlaklik) kanalinda koyu pikseller maskelenir. Kirmizi eksenler ve gri
       izgara parlak oldugu icin maskeye girmez.
    2. Kontur hiyerarsisinde "delikli" bir kontur (dis halka) ve o deligin icinde ayni
       merkezli dolu bir kontur (ic daire) aranir.
    3. Ic dairenin merkezi = nisan noktasi. Goruntu merkezine gore sapma da hesaplanir.
"""

import cv2
import numpy as np


def _circle_of(contour):
    area = cv2.contourArea(contour)
    perim = cv2.arcLength(contour, True)
    circ = 4 * np.pi * area / (perim * perim) if perim > 0 else 0.0
    m = cv2.moments(contour)
    if m['m00'] == 0:
        return None
    cx, cy = m['m10'] / m['m00'], m['m01'] / m['m00']
    r = np.sqrt(area / np.pi)
    return cx, cy, r, circ


def detect_target(bgr, dark_threshold=90, min_outer_radius=4.0, min_circularity=0.6):
    """Hedefi bulursa sozluk, bulamazsa None dondurur.

    Donus degeri:
        center   : (x, y) ic dairenin merkezi (piksel)
        radius   : dis halkanin yaricapi (piksel)
        offset   : (dx, dy) merkezin goruntu merkezine gore sapmasi, [-1, 1] araliginda
                   (dx > 0: hedef sagda, dy > 0: hedef asagida)
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    dark = cv2.inRange(hsv[:, :, 2], 0, dark_threshold)
    contours, hierarchy = cv2.findContours(dark, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    if hierarchy is None:
        return None
    hierarchy = hierarchy[0]

    best = None
    for i, c in enumerate(contours):
        hole = hierarchy[i][2]                 # ilk cocuk = halkanin deligi
        if hole < 0:
            continue
        outer = _circle_of(c)
        if outer is None or outer[2] < min_outer_radius or outer[3] < min_circularity:
            continue
        inner = None
        disk = hierarchy[hole][2]              # deligin icindeki dolu kontur(lar)
        while disk >= 0:
            cand = _circle_of(contours[disk])
            if cand is not None and cand[3] > min_circularity * 0.8:
                ratio = cand[2] / outer[2]
                dist = np.hypot(cand[0] - outer[0], cand[1] - outer[1])
                if 0.18 < ratio < 0.55 and dist < 0.25 * outer[2]:
                    inner = cand
                    break
            disk = hierarchy[disk][0]
        if inner is None:
            continue
        if best is None or outer[2] > best['radius']:
            best = {'center': (inner[0], inner[1]), 'radius': outer[2]}

    if best is None:
        return None
    h, w = bgr.shape[:2]
    best['offset'] = ((best['center'][0] - w / 2) / (w / 2),
                      (best['center'][1] - h / 2) / (h / 2))
    return best
