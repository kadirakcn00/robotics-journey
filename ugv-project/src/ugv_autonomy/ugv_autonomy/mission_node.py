"""Otonom gorev node'u: parkuru robotun kendi sensorleriyle bastan sona surer.

Abone olur (gercek konum /ground_truth/odom KULLANILMAZ):
    /odom (nav_msgs/Odometry)                     : tekerlek odometrisi (hiz)
    /imu (sensor_msgs/Imu)                        : yon ve egim
    /scan (sensor_msgs/LaserScan)                 : LIDAR
    /perception/aim/target (PointStamped)         : nisan kamerasinda hedef (dx, dy, yaricap)
    /perception/front/stage_sign (std_msgs/Int32) : okunan asama tabelasi (kayit icin)
Yayinlar:
    /cmd_vel, /aim/pan_cmd, /aim/tilt_cmd, /aim/laser, /mission/status (std_msgs/String)

Calistirma:
    ros2 launch ugv_bringup course.launch.py mission:=true
    ros2 launch ugv_bringup course.launch.py mission:=true start:=accel
"""

import math
import os

from geometry_msgs.msg import PointStamped, Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Bool, Float64, Int32, String
import yaml

from ugv_course import geometry as g

from ugv_autonomy.mission import Mission


def yaw_pitch(q):
    yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))
    pitch = math.asin(max(-1.0, min(1.0, 2.0 * (q.w * q.y - q.z * q.x))))
    return yaw, pitch


def default_path_file():
    from ament_index_python.packages import get_package_share_directory
    return os.path.join(get_package_share_directory('ugv_course'), 'config', 'course_path.yaml')


class MissionNode(Node):

    def __init__(self):
        super().__init__('mission')
        self.declare_parameter('run', 'main')
        self.declare_parameter('path_file', '')
        self.declare_parameter('rate', 20.0)
        self.declare_parameter('start_delay', 5.0)
        run = self.get_parameter('run').value
        path_file = self.get_parameter('path_file').value or default_path_file()
        prm = yaml.safe_load(open(path_file))['course_tester']['ros__parameters']
        lines = prm['accel_waypoints' if run == 'accel' else 'waypoints']
        self.mission = Mission(g.load_layout(), lines, run=run)
        self.odom_v = None
        self.imu = None
        self.scan = None
        self.t_last = None
        self.t_start = None
        self.done = False
        self.notes = 0
        self.last_turret = None
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(Imu, '/imu', self.on_imu, qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(PointStamped, '/perception/aim/target', self.on_target, 10)
        self.create_subscription(Int32, '/perception/front/stage_sign', self.on_sign, 10)
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_pan = self.create_publisher(Float64, '/aim/pan_cmd', 10)
        self.pub_tilt = self.create_publisher(Float64, '/aim/tilt_cmd', 10)
        self.pub_laser = self.create_publisher(Bool, '/aim/laser', 10)
        self.pub_status = self.create_publisher(String, '/mission/status', 10)
        self.create_timer(1.0 / self.get_parameter('rate').value, self.on_timer)
        self.get_logger().info(f'Otonom gorev: {run}, sensorler bekleniyor (odom, imu, scan)')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_odom(self, msg):
        self.odom_v = msg.twist.twist.linear.x

    def on_imu(self, msg):
        self.imu = yaw_pitch(msg.orientation)

    def on_scan(self, msg):
        self.scan = (list(msg.ranges), msg.angle_min, msg.angle_increment)

    def on_target(self, msg):
        self.mission.on_target(self.now(), msg.point.x, msg.point.y, msg.point.z)

    def on_sign(self, msg):
        n = len(self.mission.signs)
        self.mission.on_sign(self.now(), msg.data)
        if len(self.mission.signs) > n:
            self.get_logger().info(f'Tabela {msg.data} okundu (gorev asamasi '
                                   f'{self.mission.follower.st.stage})')

    def on_timer(self):
        t = self.now()
        if self.done or self.odom_v is None or self.imu is None or self.scan is None:
            return
        if self.t_start is None:
            self.t_start = t + self.get_parameter('start_delay').value
            self.get_logger().info('Sensorler hazir, gorev birazdan basliyor')
        if t < self.t_start:
            return
        dt = 0.0 if self.t_last is None else max(0.0, min(0.2, t - self.t_last))
        self.t_last = t
        yaw, pitch = self.imu
        # ROS'ta pozitif pitch burun asagi demek; gorev 'burun yukari' bekler
        cmd = self.mission.step(t, dt, self.odom_v, yaw, -pitch, self.scan)

        tw = Twist()
        tw.linear.x, tw.angular.z = float(cmd['v']), float(cmd['w'])
        self.pub_cmd.publish(tw)
        turret = (round(cmd['pan'], 4), round(cmd['tilt'], 4))
        if turret != self.last_turret:
            self.pub_pan.publish(Float64(data=float(cmd['pan'])))
            self.pub_tilt.publish(Float64(data=float(cmd['tilt'])))
            self.last_turret = turret
        self.pub_laser.publish(Bool(data=bool(cmd['laser'])))
        self.pub_status.publish(String(data=cmd['status']))
        for tn, text in self.mission.log[self.notes:]:
            self.get_logger().info(text)
        self.notes = len(self.mission.log)
        if cmd['finished'] or cmd['stuck']:
            self.done = True
            self.pub_cmd.publish(Twist())
            log = self.get_logger().info if cmd['finished'] else self.get_logger().error
            log(f'GOREV {"TAMAMLANDI" if cmd["finished"] else "TAKILDI"}: {cmd["status"]}')


def main(args=None):
    rclpy.init(args=args)
    node = MissionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    try:
        if rclpy.ok():
            node.pub_cmd.publish(Twist())
            node.pub_laser.publish(Bool(data=False))
    except Exception:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
