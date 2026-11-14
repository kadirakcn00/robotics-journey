"""Hakem node'u: kosuyu sartnamenin puan tablosuna gore puanlar.

Abone olur:
    /ground_truth/odom (nav_msgs/Odometry)      : robotun gercek konumu (hakem gorur)
    /joint_states (sensor_msgs/JointState)      : taret acilari (aim_pan_joint, aim_tilt_joint)
    /aim/laser (std_msgs/Bool)                  : lazer acik mi
    /course/slider_cmd (std_msgs/Float64)       : kayar engelin konumu
    /perception/aim/target (PointStamped)       : hedef tespiti (otonomda +10)
Yayinlar:
    /course/referee (std_msgs/String)           : anlik puan durumu
Kosu bitince (ya da kapatilinca) hakem raporunu yazar.

Parametreler:
    run        : main (ana parkur) ya da accel (hizlanma)
    autonomous : true ise otonom kosu (hedef tespiti puani verilir)
"""

import time

from geometry_msgs.msg import PointStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Bool, Float64, String

from ugv_course import geometry as g
from ugv_course.referee import Referee
from ugv_course.water import yaw_from_quaternion


class RefereeNode(Node):

    def __init__(self):
        super().__init__('referee')
        self.declare_parameter('run', 'main')
        self.declare_parameter('autonomous', False)
        self.declare_parameter('rate', 20.0)
        run = self.get_parameter('run').value
        auto = bool(self.get_parameter('autonomous').value)
        self.ref = Referee(g.load_layout(), autonomous=auto, run=run)
        self.pose = None
        self.pan = self.tilt = 0.0
        self.laser = False
        self.slider = None
        self.target_wall = 0.0
        self.reported = False
        self.create_subscription(Odometry, '/ground_truth/odom', self.on_pose, 10)
        self.create_subscription(JointState, '/joint_states', self.on_joints, 10)
        self.create_subscription(Bool, '/aim/laser', self.on_laser, 10)
        self.create_subscription(Float64, '/course/slider_cmd', self.on_slider, 10)
        self.create_subscription(PointStamped, '/perception/aim/target', self.on_target, 10)
        self.pub = self.create_publisher(String, '/course/referee', 10)
        self.create_timer(1.0 / self.get_parameter('rate').value, self.on_timer)
        self.get_logger().info(f'Hakem hazir: kosu={run}, '
                               f'{"otonom" if auto else "manuel"}')

    def on_pose(self, msg):
        p = msg.pose.pose
        self.pose = (p.position.x, p.position.y, p.position.z, yaw_from_quaternion(p.orientation))

    def on_joints(self, msg):
        for name, pos in zip(msg.name, msg.position):
            if name == 'aim_pan_joint':
                self.pan = pos
            elif name == 'aim_tilt_joint':
                self.tilt = pos

    def on_laser(self, msg):
        self.laser = msg.data

    def on_slider(self, msg):
        self.slider = msg.data

    def on_target(self, msg):
        self.target_wall = time.monotonic()

    def on_timer(self):
        if self.pose is None:
            return
        t = self.get_clock().now().nanoseconds * 1e-9
        seen = time.monotonic() - self.target_wall < 0.5
        for line in self.ref.update(t, *self.pose, self.pan, self.tilt, self.laser,
                                    self.slider, seen):
            self.get_logger().info('HAKEM ' + line)
        self.pub.publish(String(data=f'puan {self.ref.total()} | asamalar '
                                     f'{sorted(self.ref.passed)} | atislar {self.ref.shots}'))
        if self.ref.finish_t is not None and not self.reported:
            self.report(t)

    def report(self, t=None):
        self.reported = True
        for line in self.ref.summary(t):
            self.get_logger().info(line)


def main(args=None):
    rclpy.init(args=args)
    node = RefereeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    if not node.reported:
        try:
            node.report(node.get_clock().now().nanoseconds * 1e-9)
        except Exception:
            pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
