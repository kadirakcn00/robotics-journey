import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class MyPublisher(Node):
    def __init__(self):
        super().__init__('my_publisher')
        self.publisher_ = self.create_publisher(String, 'chatter', 10)
        self.timer = self.create_timer(0.5, self.timer_callback)
        self.sayac = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Merhaba ROS2: {self.sayac}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Yayinlaniyor: {msg.data}')
        self.sayac += 1


def main(args=None):
    rclpy.init(args=args)
    node = MyPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()