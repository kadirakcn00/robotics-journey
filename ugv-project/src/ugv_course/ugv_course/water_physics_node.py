"""Su gecisi fizigi node'u: hiz komutunu robotun suya batma miktarina gore degistirir.

    /cmd_vel (teleop, Nav2, avoid_node ...)  ->  water_physics  ->  /cmd_vel_gz  ->  Gazebo

Robotun konumu Gazebo'nun gercek konum (ground truth) yayinindan alinir. O gelmezse
/odom + baslangic konumu kullanilir.

Yayinlar:
    /cmd_vel_gz (geometry_msgs/Twist)      : Gazebo DiffDrive'a giden hiz
    /course/water_depth (std_msgs/Float32) : robotun bulundugu yerdeki su derinligi (m)

Parametreler:
    zones        : ["x_min, x_max, y_min, y_max, derinlik, egim_uzunlugu", ...]
    robot_height : batma oranini hesaplamak icin robot yuksekligi (m)
    spawn_x, spawn_y, spawn_yaw : /odom yedegi icin baslangic konumu
"""

import math
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32

from ugv_course.water import WaterModel, WaterZone, yaw_from_quaternion


def parse_zone(text):
    v = [float(t) for t in text.replace(',', ' ').split()]
    if len(v) != 6:
        raise ValueError(f'Havuz 6 sayi olmali (x_min x_max y_min y_max derinlik egim): {text}')
    return WaterZone(*v)


class WaterPhysicsNode(Node):

    def __init__(self):
        super().__init__('water_physics')
        self.declare_parameter('zones', [''])
        self.declare_parameter('robot_height', 0.30)
        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter('output_topic', '/cmd_vel_gz')
        self.declare_parameter('ground_truth_topic', '/ground_truth/odom')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('spawn_x', 0.0)
        self.declare_parameter('spawn_y', 0.0)
        self.declare_parameter('spawn_yaw', 0.0)
        self.declare_parameter('rate', 50.0)

        zones = [parse_zone(z) for z in self.get_parameter('zones').value if z.strip()]
        self.model = WaterModel(zones, self.get_parameter('robot_height').value)
        self.get_logger().info(f'{len(zones)} havuz yuklendi: {zones}')

        self.cmd = Twist()
        self.gt_xy = None
        self.gt_wall = 0.0
        self.odom_xy = None
        self.warned = False
        self.last = None

        g = self.get_parameter
        self.create_subscription(Twist, g('input_topic').value, self.on_cmd, 10)
        self.create_subscription(Odometry, g('ground_truth_topic').value, self.on_gt, 10)
        self.create_subscription(Odometry, g('odom_topic').value, self.on_odom, 10)
        self.pub = self.create_publisher(Twist, g('output_topic').value, 10)
        self.pub_depth = self.create_publisher(Float32, '/course/water_depth', 10)
        self.create_timer(1.0 / g('rate').value, self.on_timer)

    def on_cmd(self, msg):
        self.cmd = msg

    def on_gt(self, msg):
        self.gt_xy = (msg.pose.pose.position.x, msg.pose.pose.position.y)
        self.gt_wall = time.monotonic()

    def on_odom(self, msg):
        p = msg.pose.pose
        sx, sy = self.get_parameter('spawn_x').value, self.get_parameter('spawn_y').value
        syaw = self.get_parameter('spawn_yaw').value
        c, s = math.cos(syaw), math.sin(syaw)
        self.odom_xy = (sx + c * p.position.x - s * p.position.y,
                        sy + s * p.position.x + c * p.position.y)
        self.odom_yaw = syaw + yaw_from_quaternion(p.orientation)

    def position(self):
        if self.gt_xy is not None and time.monotonic() - self.gt_wall < 1.0:
            return self.gt_xy
        if self.odom_xy is not None:
            if not self.warned:
                self.get_logger().warn(
                    'Gercek konum (ground truth) gelmiyor, /odom + baslangic konumu kullaniliyor')
                self.warned = True
            return self.odom_xy
        return None

    def on_timer(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        dt = 0.0 if self.last is None else max(0.0, now - self.last)
        self.last = now

        xy = self.position()
        out = Twist()
        if xy is None:
            out = self.cmd        # konum yoksa komutu aynen ilet
            depth = 0.0
        else:
            depth = self.model.depth_at(*xy)
            v, w = self.model.step(self.cmd.linear.x, self.cmd.angular.z, xy[0], xy[1], dt)
            out.linear.x, out.angular.z = v, w
        self.pub.publish(out)
        self.pub_depth.publish(Float32(data=float(depth)))


def main(args=None):
    rclpy.init(args=args)
    node = WaterPhysicsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
