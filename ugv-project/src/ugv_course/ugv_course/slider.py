"""Kayar engel hareketi (ROS'tan bagimsiz).

Sartname 6.8: engel sabit hizla saga sola gider gelir, parkurun tamamen disina cikar ve
beklemeden ters yonde hareketine devam eder. Bu bir ucgen dalgadir: konum zamanla dogrusal
artar, uca gelince dogrusal azalir.
"""


def triangle_position(t, amplitude, speed, phase=0.0):
    """Zaman t aninda konum: -amplitude ile +amplitude arasinda 'speed' hiziyla gider gelir.

    phase: hareketin baslangic noktasini kaydirmak icin (saniye).
    """
    if amplitude <= 0 or speed <= 0:
        return 0.0
    leg = 2.0 * amplitude / speed            # bir uctan digerine gitme suresi
    u = ((t + phase) % (2.0 * leg)) / leg    # 0..2
    if u <= 1.0:
        return -amplitude + 2.0 * amplitude * u
    return amplitude - 2.0 * amplitude * (u - 1.0)
