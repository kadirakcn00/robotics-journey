import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts 

class MyServer(Node):
	def __init__(self):
		super().__init__('myy_server')
		self.srv = self.create_service(
			AddTwoInts, 'my_add_two_ints', self.add_callback)

	def add_callback(self,request,response):
		response.sum = request.a + request.b
		self.get_logger().info(f'Request has come: {request.a} + {request.b}')
		return response

def main(args=None):
	rclpy.init(args=args)
	node = MyServer()
	rclpy.spin(node)
	node.destroy_node()
	rclpy.shutdown()

if __name__ == '__main__':
	main()
