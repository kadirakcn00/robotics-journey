"""Kayar engeli (sartname 6.8) sabit hizla saga sola gidip getiren node.

Yayinlar:
    /course/slider_cmd (std_msgs/Float64) : engelin hedef konumu (m), Gazebo'daki
                                             JointPositionController bunu takip eder.

Parametreler (olcek x 0.4):
    amplitude : merkezden en uzak konum (m). Engel parkurun tamamen disina cikar.
    speed     : hiz (m/s), sartnamede 20 cm/s -> 0.08 m/s
"""

from rclpy.node import Node
import rclpy
from std_msgs.msg import Float64

from ugv_course.slider import triangle_position


class SlidingObstacleNode(Node):

    def __init__(self):
        super().__init__('sliding_obstacle')
        self.declare_parameter('amplitude', 0.8)
        self.declare_parameter('speed', 0.08)
        self.declare_parameter('phase', 0.0)
        self.declare_parameter('rate', 20.0)
        self.declare_parameter('topic', '/course/slider_cmd')
        self.pub = self.create_publisher(Float64, self.get_parameter('topic').value, 10)
        self.start = None
        self.create_timer(1.0 / self.get_parameter('rate').value, self.on_timer)
        self.get_logger().info(
            f"Kayar engel: +-{self.get_parameter('amplitude').value} m, "
            f"{self.get_parameter('speed').value} m/s")

    def on_timer(self):
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.start is None:
            self.start = now
        g = self.get_parameter
        pos = triangle_position(now - self.start, g('amplitude').value, g('speed').value,
                                g('phase').value)
        self.pub.publish(Float64(data=pos))


def main(args=None):
    rclpy.init(args=args)
    node = SlidingObstacleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
