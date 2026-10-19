import sys
import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts


class MyClient(Node):
    def __init__(self):
        super().__init__('my_client')
        self.cli = self.create_client(AddTwoInts, 'my_add_two_ints')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Service will be waiting...')

    def send_request(self, a, b):
        req = AddTwoInts.Request()
        req.a = a
        req.b = b
        future = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, future)
        return future.result()


def main(args=None):
    rclpy.init(args=args)
    if len(sys.argv) != 3:
        print('Usage: ros2 run py_srvcli my_client <a> <b>')
        rclpy.shutdown()
        return
    node = MyClient()
    a, b = int(sys.argv[1]), int(sys.argv[2])
    result = node.send_request(a, b)
    node.get_logger().info(f'Result: {a} + {b} = {result.sum}')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
