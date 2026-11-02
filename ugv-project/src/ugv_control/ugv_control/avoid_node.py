import math
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist


class AvoidNode(Node):
    def __init__(self):
        super().__init__('avoid_node')
        self.sub = self.create_subscription(
            LaserScan, 'scan', self.scan_callback, 10)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.safe_dist = 2.0

    def sector_min(self, msg, ranges, deg_a, deg_b):
        i = int(round((math.radians(deg_a) - msg.angle_min) / msg.angle_increment))
        j = int(round((math.radians(deg_b) - msg.angle_min) / msg.angle_increment))
        return float(np.min(ranges[i:j + 1]))

    def scan_callback(self, msg):
        ranges = np.array(msg.ranges)
        ranges[np.isinf(ranges)] = msg.range_max
        ranges[np.isnan(ranges)] = msg.range_max

        front = self.sector_min(msg, ranges, -15, 15)
        left = self.sector_min(msg, ranges, 30, 90)
        right = self.sector_min(msg, ranges, -90, -30)

        cmd = Twist()
        if front > self.safe_dist:
            cmd.linear.x = 0.2
        else:
            cmd.angular.z = 0.5 if left > right else -0.5
        self.pub.publish(cmd)
        self.get_logger().info(f'on={front:.2f} sol={left:.2f} sag={right:.2f}')


def main(args=None):
    rclpy.init(args=args)
    node = AvoidNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
