"""Surucu konsolu: manuel kosu icin kamera goruntuleri + klavye ile surus, taret ve lazer.

Sartnamedeki uzaktan kontrollu kosuda surucu parkuru goremez; robotu kameralara bakarak
surer. Bu pencere uc kamerayi, bilgi panelini ve tus kontrolunu bir araya getirir.

Calistirma:
    ros2 run ugv_teleop driver_station

Tuslar:
    W / S        ileri / geri (basili tut)       A / D      sola / saga don
    1 / 2 / 3    vites (0.15 / 0.30 / 0.50 m/s)
    Ok tuslari   taret (sol/sag: pan, yukari/asagi: tilt)    C   tareti ortala
    F            lazer (basili tut; acikken arac ve taret kilitlenir)
    Space        ACIL DURDURMA (kilitlenir)      Enter      acil durdurmayi birak
Pencere odagini kaybedince robot durur (haberlesme kesilmesi gibi).
"""

import sys
import time

from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Float32, Float64, Int32

try:
    from python_qt_binding.QtCore import Qt, QTimer
    from python_qt_binding.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
    from python_qt_binding.QtWidgets import (QApplication, QGridLayout, QLabel, QMainWindow,
                                             QWidget)
except ImportError:                                   # ROS disinda test icin
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
    from PyQt5.QtWidgets import QApplication, QGridLayout, QLabel, QMainWindow, QWidget

from ugv_teleop.drive_logic import DriveController, GEARS

KEYS = {
    Qt.Key_W: 'forward', Qt.Key_S: 'backward', Qt.Key_A: 'left', Qt.Key_D: 'right',
    Qt.Key_1: '1', Qt.Key_2: '2', Qt.Key_3: '3',
    Qt.Key_Space: 'estop', Qt.Key_Return: 'release', Qt.Key_Enter: 'release',
    Qt.Key_Left: 'pan_left', Qt.Key_Right: 'pan_right',
    Qt.Key_Up: 'tilt_up', Qt.Key_Down: 'tilt_down',
    Qt.Key_C: 'center', Qt.Key_F: 'fire',
}

CAMERA_NAMES = {'front': 'ON KAMERA', 'rear': 'GERI KAMERA', 'aim': 'NISAN KAMERASI'}

HELP = ('W/S ileri-geri  A/D don  1-2-3 vites  |  Oklar taret  C ortala  F lazer  |  '
        'SPACE acil durdur  ENTER birak')


class DriverNode(Node):
    """ROS tarafi: kamera ve durum bilgilerini toplar, komutlari yayinlar."""

    def __init__(self):
        super().__init__('driver_station')
        self.bridge = CvBridge()
        self.images = {}
        self.water = 0.0
        self.sign = None
        self.sign_time = 0.0
        self.target = None
        self.target_time = 0.0
        self.speed = 0.0
        for cam in ('front', 'rear', 'aim'):
            self.create_subscription(Image, f'/camera/{cam}/image_raw',
                                     lambda m, c=cam: self.on_image(c, m),
                                     qos_profile_sensor_data)
        self.create_subscription(Float32, '/course/water_depth', self.on_water, 10)
        self.create_subscription(Int32, '/perception/front/stage_sign', self.on_sign, 10)
        self.create_subscription(PointStamped, '/perception/aim/target', self.on_target, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_pan = self.create_publisher(Float64, '/aim/pan_cmd', 10)
        self.pub_tilt = self.create_publisher(Float64, '/aim/tilt_cmd', 10)
        self.pub_laser = self.create_publisher(Bool, '/aim/laser', 10)

    def on_image(self, cam, msg):
        self.images[cam] = self.bridge.imgmsg_to_cv2(msg, desired_encoding='rgb8')

    def on_water(self, msg):
        self.water = msg.data

    def on_sign(self, msg):
        self.sign, self.sign_time = msg.data, time.monotonic()

    def on_target(self, msg):
        self.target, self.target_time = (msg.point.x, msg.point.y), time.monotonic()

    def on_odom(self, msg):
        self.speed = msg.twist.twist.linear.x

    def publish(self, s, turret_changed):
        cmd = Twist()
        cmd.linear.x, cmd.angular.z = float(s.v), float(s.w)
        self.pub_cmd.publish(cmd)
        if turret_changed:
            self.pub_pan.publish(Float64(data=float(s.pan)))
            self.pub_tilt.publish(Float64(data=float(s.tilt)))
        self.pub_laser.publish(Bool(data=bool(s.laser_on)))


def to_pixmap(rgb, width, height):
    h, w, _ = rgb.shape
    img = QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(img).scaled(width, height, Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)


class DriverStation(QMainWindow):
    RATE = 20.0

    def __init__(self, node):
        super().__init__()
        self.node = node
        self.ctrl = DriveController()
        self.last_turret = None
        self.last = time.monotonic()
        self.setWindowTitle('UGV Surucu Konsolu')
        self.setFocusPolicy(Qt.StrongFocus)

        self.views = {}
        grid = QGridLayout()
        for cam, (row, col, rs, w, h) in {'front': (0, 0, 2, 800, 600),
                                          'aim': (0, 1, 1, 400, 300),
                                          'rear': (1, 1, 1, 400, 300)}.items():
            label = QLabel(f'{cam} kamera bekleniyor...')
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(w // 2, h // 2)
            label.setStyleSheet('background:#202020; color:#aaa;')
            grid.addWidget(label, row, col, rs, 1)
            self.views[cam] = (label, w, h)
        self.hud = QLabel()
        self.hud.setFont(QFont('Monospace', 11))
        self.hud.setStyleSheet('background:#111; color:#eee; padding:6px;')
        grid.addWidget(self.hud, 2, 0, 1, 2)
        help_label = QLabel(HELP)
        help_label.setStyleSheet('background:#111; color:#8ab4f8; padding:4px;')
        grid.addWidget(help_label, 3, 0, 1, 2)
        self.hud.setFixedHeight(56)
        help_label.setFixedHeight(28)
        grid.setRowStretch(0, 1)                # alan kameralarin
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)
        central = QWidget()
        central.setLayout(grid)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(int(1000 / self.RATE))

    # -- klavye ve odak
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        key = KEYS.get(event.key())
        if key:
            self.ctrl.press(key)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        key = KEYS.get(event.key())
        if key:
            self.ctrl.release(key)

    def changeEvent(self, event):
        if not self.isActiveWindow():
            self.ctrl.release_all()      # odak kaybi = haberlesme kesildi: dur
        super().changeEvent(event)

    # -- dongu
    def tick(self):
        rclpy.spin_once(self.node, timeout_sec=0.0)
        now = time.monotonic()
        dt, self.last = now - self.last, now
        s = self.ctrl.step(min(dt, 0.2))
        turret = (round(s.pan, 3), round(s.tilt, 3))
        self.node.publish(s, turret != self.last_turret)
        self.last_turret = turret
        self.draw_cameras(s)
        self.draw_hud(s)

    def draw_cameras(self, s):
        for cam, (label, w, h) in self.views.items():
            rgb = self.node.images.get(cam)
            if rgb is None:
                continue
            pix = to_pixmap(rgb, label.width(), label.height())
            if cam == 'aim':
                self.draw_aim_overlay(pix, s)
            p = QPainter(pix)
            p.setPen(QColor(255, 255, 255))
            p.setFont(QFont('Sans', 11, QFont.Bold))
            p.drawText(8, 20, CAMERA_NAMES[cam])
            p.end()
            label.setPixmap(pix)

    def draw_aim_overlay(self, pix, s):
        p = QPainter(pix)
        cx, cy = pix.width() // 2, pix.height() // 2
        p.setPen(QPen(QColor(255, 255, 0), 1))
        p.drawLine(cx - 20, cy, cx + 20, cy)
        p.drawLine(cx, cy - 20, cx, cy + 20)
        if self.node.target and time.monotonic() - self.node.target_time < 0.5:
            tx = int(cx + self.node.target[0] * cx)
            ty = int(cy + self.node.target[1] * cy)
            p.setPen(QPen(QColor(0, 255, 0), 2))
            p.drawEllipse(tx - 12, ty - 12, 24, 24)
        if s.laser_on:
            p.setBrush(QColor(255, 0, 0))
            p.setPen(Qt.NoPen)
            p.drawEllipse(cx - 4, cy - 4, 8, 8)
        p.end()

    def draw_hud(self, s):
        n = self.node
        sign = n.sign if n.sign is not None and time.monotonic() - n.sign_time < 2.0 else '-'
        target = 'GORULUYOR' if n.target and time.monotonic() - n.target_time < 0.5 else '-'
        state = ('<span style="color:#ff4444"><b>ACIL DURDURMA (ENTER ile birak)</b></span>'
                 if s.estop else '<span style="color:#44ff44">HAZIR</span>')
        laser = (f'<span style="color:#ff4444"><b>LAZER ACIK {s.laser_time:.1f} s</b></span>'
                 if s.laser_on else 'kapali')
        v_max = GEARS[s.gear][0]
        self.hud.setText(
            f'{state} &nbsp; Vites {s.gear} (max {v_max:.2f} m/s) &nbsp; '
            f'Komut v={s.v:+.2f} w={s.w:+.2f} &nbsp; Gercek hiz {n.speed:+.2f} m/s<br>'
            f'Taret pan={s.pan:+.2f} tilt={s.tilt:+.2f} &nbsp; Lazer {laser} &nbsp; '
            f'Tabela {sign} &nbsp; Hedef {target} &nbsp; Su {n.water * 100:.0f} cm')


def main(args=None):
    rclpy.init(args=args)
    node = DriverNode()
    app = QApplication(sys.argv)
    win = DriverStation(node)
    win.resize(1220, 820)
    win.show()
    code = app.exec_()
    node.pub_cmd.publish(Twist())     # kapanirken robotu durdur
    node.destroy_node()
    rclpy.try_shutdown()
    sys.exit(code)


if __name__ == '__main__':
    main()
