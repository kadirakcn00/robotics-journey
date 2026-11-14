"""Parkur test surucusu: robotu parkur boyunca surup fiziksel olarak gecilebildigini olcer.

Robotun gercek konumunu (Gazebo ground truth) ve kayar engelin konumunu bildigi icin
OTONOM DEGILDIR; amaci parkurun ve robotun fiziginin dogrulugunu test etmektir:
robot havuzdan cikabiliyor mu, dik engele ve %45 rampaya tirmanabiliyor mu, yan egimde
devriliyor mu? Takilirsa hangi asamada takildigini raporlar.

Calistirma:
    ros2 launch ugv_bringup course.launch.py tester:=true                # ana parkur
    ros2 launch ugv_bringup course.launch.py tester:=true start:=accel   # hizlanma parkuru

Yayinlar:
    /cmd_vel (geometry_msgs/Twist)           : hiz komutu (su fizigi node'undan gecer)
    /course/tester_status (std_msgs/String)  : anlik durum
"""

import math

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64, String

from ugv_course.path_follower import parse_waypoints, PathFollower
from ugv_course.water import yaw_from_quaternion

STAGE_NAMES = {
    0: 'baslangic', 1: 'su gecisi', 2: 'cakilli yol', 3: 'yan egim', 4: 'dik engel',
    5: 'koniler', 6: 'kayar engel', 7: 'engebeli arazi', 8: 'dik egim (cikis)',
    9: 'atis bolgesi', 10: 'dik egim (inis)', 11: 'hizlanma parkuru',
}


class CourseTesterNode(Node):

    def __init__(self):
        super().__init__('course_tester')
        self.declare_parameter('waypoints', [''])
        self.declare_parameter('accel_waypoints', [''])
        self.declare_parameter('accel_line', 12.0)
        self.declare_parameter('accel_stop_zone', 4.0)
        self.declare_parameter('run', 'main')           # main: ana parkur, accel: hizlanma
        self.declare_parameter('rate', 20.0)
        self.declare_parameter('start_delay', 5.0)
        self.run = self.get_parameter('run').value
        key = 'accel_waypoints' if self.run == 'accel' else 'waypoints'
        lines = [w for w in self.get_parameter(key).value if w.strip()]
        # Hizlanmada tam hizla gidilir; fren cizgiden sonra baslar
        self.follower = PathFollower(parse_waypoints(lines),
                                     brake=0.7 if self.run == 'accel' else 0.8)
        self.pose = None
        self.prev = None
        self.speed = 0.0
        self.slider = None
        self.start = None
        self.last_stage = None
        self.last_state = None
        self.reported = False
        self.aborted = False
        self.last_clock = None
        first = parse_waypoints(lines[:1])[0] if lines else None
        self.expected_start = (first.x, first.y) if first else None
        self.create_subscription(Odometry, '/ground_truth/odom', self.on_pose, 10)
        self.create_subscription(Float64, '/course/slider_cmd', self.on_slider, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_status = self.create_publisher(String, '/course/tester_status', 10)
        self.create_timer(1.0 / self.get_parameter('rate').value, self.on_timer)
        self.get_logger().info(f'Kosu: {self.run} | {len(lines)} noktalik yol yuklendi, '
                               f'gercek konum bekleniyor')

    def on_pose(self, msg):
        p = msg.pose.pose
        self.pose = (p.position.x, p.position.y, yaw_from_quaternion(p.orientation))

    def on_slider(self, msg):
        self.slider = msg.data

    def on_timer(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.pose is None:
            return
        if self.aborted:
            return
        if self.last_clock is not None and now < self.last_clock - 0.5:
            if self.start is None or self.last_clock < self.start:     # kosu henuz baslamadi
                # Gazebo acilirken saat bir kez sifirlanabilir: geri sayimi bastan baslat
                self.get_logger().warn('Simulasyon saati sifirlandi, test geri sayimi yeniden')
                self.start = None
                self.prev = None
            else:
                self.abort(f'Simulasyon saati kosu sirasinda geriye atladi '
                           f'({self.last_clock:.1f} -> {now:.1f} s)')
                return
        self.last_clock = now
        if self.start is None:
            if self.expected_start is not None:
                dist = math.hypot(self.pose[0] - self.expected_start[0],
                                  self.pose[1] - self.expected_start[1])
                if dist > 1.0:
                    self.abort(f'Robot beklenen baslangicta degil: ({self.pose[0]:.2f}, '
                               f'{self.pose[1]:.2f}), beklenen {self.expected_start}')
                    return
            self.start = now + self.get_parameter('start_delay').value
            self.get_logger().info('Gercek konum geldi, test birazdan basliyor')
        if now < self.start:
            return
        t = now - self.start
        x, y, yaw = self.pose
        if self.prev is not None and t > self.prev[2]:
            inst = math.hypot(x - self.prev[0], y - self.prev[1]) / (t - self.prev[2])
            self.speed = 0.7 * self.speed + 0.3 * inst
        self.prev = (x, y, t)

        v, w = self.follower.update(x, y, yaw, t, self.speed, self.slider)
        cmd = Twist()
        cmd.linear.x, cmd.angular.z = float(v), float(w)
        self.pub.publish(cmd)

        st = self.follower.st
        if st.stage != self.last_stage:
            self.get_logger().info(f'[{t:6.1f} s] Asama {st.stage}: '
                                   f'{STAGE_NAMES.get(st.stage, "?")}')
            self.last_stage = st.stage
        if st.state != self.last_state and st.state in ('STOP_WAIT', 'SLIDER_WAIT'):
            self.get_logger().info(f'[{t:6.1f} s] {st.message}')
        self.last_state = st.state
        self.pub_status.publish(String(data=f'{st.state} | {st.message} | {t:.1f} s'))
        if st.state in ('FINISHED', 'STUCK') and not self.reported:
            self.report(t, x, y)

    def abort(self, reason):
        """Test anlamsizlasti: robotu durdur, sebebi ve olasi cozumu yaz."""
        self.aborted = True
        self.pub.publish(Twist())
        log = self.get_logger()
        log.error(f'TEST DURDURULDU: {reason}')
        log.error('Arkada baska bir Gazebo acik olabilir (iki simulasyon ayni topic\'lere '
                  'yaziyor). Hepsini kapatip tekrar dene:  pkill -f "ign gazebo"')

    def report(self, t, x, y):
        st = self.follower.st
        self.reported = True
        log = self.get_logger()
        if st.state == 'FINISHED':
            log.info(f'PARKUR TAMAMLANDI: {t:.1f} s ({t / 60:.1f} dk)')
        else:
            log.error(f'{st.message} | konum ({x:.2f}, {y:.2f}) | '
                      f'{STAGE_NAMES.get(st.stage, "?")} asamasinda ilerleyemedi')
        if self.run == 'accel':
            self.report_accel(t, x)
            return
        times = sorted((v, k) for k, v in st.stage_times.items() if k != 'finish')
        for (t0, k), nxt in zip(times, times[1:] + [(st.stage_times.get('finish', t), None)]):
            log.info(f'   asama {k:2d} {STAGE_NAMES.get(k, "?"):18s} {nxt[0] - t0:6.1f} s')

    def report_accel(self, t, x):
        """Hizlanma: cizgiyi gecme suresi ve cizgiden sonraki durma mesafesi."""
        log = self.get_logger()
        line = self.get_parameter('accel_line').value
        zone = self.get_parameter('accel_stop_zone').value
        mark = self.follower.st.marks.get('accel_line')
        if mark is None:
            log.error('Hizlanma cizgisi gecilemedi')
            return
        t_line = mark[0]
        stop = x - line
        log.info(f'   {line:.1f} m (sartname 30 m) suresi : {t_line:.2f} s '
                 f'(ortalama {line / t_line:.2f} m/s)')
        verdict = 'GUVENLI' if stop <= zone else 'DURMA ALANI ASILDI (ceza)'
        log.info(f'   cizgiden sonra durma mesafesi : {stop:.2f} m / {zone:.1f} m -> {verdict}')


def main(args=None):
    rclpy.init(args=args)
    node = CourseTesterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    try:
        if rclpy.ok():
            node.pub.publish(Twist())       # kapanirken robotu durdur
    except Exception:
        pass                                # Ctrl+C sonrasi ROS baglami kapanmis olabilir
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
