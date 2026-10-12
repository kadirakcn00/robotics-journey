ROS2 Hakkında Notlar; 
1.Ros2’nin kurulumunu tamamladıktan sonra ortamını belirlememiz gerekiyor. Yoksa linux ros2 dosyalarını bulamıyor ve komutlarımızı algılayamıyor. 
//Buralara nasıl ortam eklediğimizi terminalde yaz

2.Ortam eklediğimizde artık source diye kaynak belirtmemize gerek kalmıyor ve terminalin ilk haliyle de işlemlerimizi gerçekleştirebiliyoruz. 

3.Listener ve talker testi yapmamız ros2’nin komutlarının çalışıp çalışmadığını gösterir. İlk terminalden talker açmanız ve sonraki terminalden listener açmanız gerekiyor. İki terminalden de veri alıyorsanız doğru yoldasınız demek oluyor. 

4.Ros2 için gerçek bir çalışma ortamı(work space) açmanız işleri kolaylaştıracak ve sistem dosyalarında kaybolmamanızı sağlayacaktır. 
//terminaldeki komutlardan ve colcon buildden bahset

5.Ros2’yi python üzerinden çalıştıracağımız için python kütüphanesini eklememiz gerekiyor.
//colcon build ve kütüphaneyi nasıl kurmaları hakkında bilgi ver

6.Ros2’deki en önemli konular Node ve topiclerdir. Nodeler bizim her biri bağımsız çalışan ve dışarıdan bilgi alan alanlarımızdır. Nodeların en önemli özelliği diğer nodelara bağımlı olmaması ve kendi başına çalışabilmesidir. Örneğin insansız kara aracında görüntü işleyen node bozuldu ve çalışmıyor bu durumda motor sürücü node’u çalışmaya devam edecek ve sistem diğer nodelar üzerinden veri alabilecektir. 

7.Topicler ise nodelara bilgi sağlayan kanallardır. Birden fazla topic birden fazla node’a bilgi sağlayabilir ama node’ların topiclere ihtiyacı yoktur. 

8.Node yazma işlemi; 

import rclpy
from rclpy.node import Node

def main(args=None):

# ROS2 sistemini başlatır
rclpy.init(args=args)

# Node oluşturur
node = Node("basic_node")

# Terminale mesaj basar
node.get_logger().info("Basic node started!")

# Node'un açık kalmasını sağlar
rclpy.spin(node)

# Kapanış işlemleri
node.destroy_node()
rclpy.shutdown()

if __name__ == "__main__":
main()



9.Node OOP işlemi ; 

//ROS2 ile pythonın köprüsünü kurar 
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

class MyNode(Node):
	#Kurucu method 
	def __init__(self):
		super().__init__("python_test")
		self.counter = 0 
		self.get_logger().info("Merhaba ROS2")
		self.create_timer(0.5,self.timer_callback)
	#Timer methodu
	def timer_callback(self):
		self.counter +=1
		self.get_logger().info(f"Hello {self.counter}")
#Main class	
def main(args=None):
	rclpy.init(args=args)
	node = MyNode()
	rclpy.spin(node)
	rclpy.shutdown()

#Maini çağırma işlemi
if __name__ == '__main__':
main()

10.Node Remmaping : 

Aynı kodu 5-6 kez çalıştırmak istediğimizde aynı executer adıyla çalıştırmamız terminalde mümkün değil. Bundan dolayı node remapping yapmamız gerekir. 

Eğer terminalde iki node’u aynı anda çalıştırdığımızda böyle bir uyarı alırız; 

WARNING: Be aware that are nodes in the graph that share an exact name, this can have unintended side effects.
/python_test
/python_test

Peki remapping işlemini hangi terminal komutuyla yapıyoruz ; 
ros2 run my_py_pkg [node executer ismi] –ros-args –remap __node:=[vermek istediğimiz isim]

Bu şekilde aynı node’u defalarca kullanabiliriz. 

Ros2 node list yazdığımızda ekran böyle görünür ; 

ros2 node list 
/abc
/def
/python_test

Rqt Komutu; 
Subscriber ve publisher nodelarımızı grafik şeklinde bize sunar. 

rqt_graph 

11.REMAPPING İÇİN KOMUTLAR ; 

ros2 run my_py_pkg [node ismi] –-ros-args -r __node:=[vermek istediğimiz isim]

TOPIC REMAPPING;

ros2 run my_py_pkg [node ismi] --ros-args -r __node:=[vermek istediğimiz isim] -r [topic ismi(executer ismi değil kodda kullandığımız topic adı)]:=[vermek istediğimiz isim] 

ros2 run my_py_pkg [subscriber ismi] --ros-args -r __node:=[vermek istediğimiz subscriber ismi] -r [topic ismi]:=[öncesinde belirlediğimiz topic ismi]

12.TOPIC TERMINAL KOMUTLARI: 
ros2 topic list : O anda veri yayınlayan topicleri gösterir. 

ros2 topic info /(hakkında bilgi almak istediğimiz topic) : Kaç tane subs,publisher olduğunu gösterir. 

ros2 interface show : Topicte hangi tür veri paylaştığını gösterir. 

ros2 topic hz /(hakkında bilgi almak istediğimiz topic): Mesajların kaç hz olduğunu gösterir.

 ros2 topic bw /(hakkında bilgi almak istediğimiz topic) : Bant genişliğini gösterir. 

ros2 topic echo /(publisher adı) : Bunu kullanarak abone olup veri çekebiliyoruz.

ros2 topic echo pub -r (hz) /(topic adı) [veri türü] “{data: ‘(Vermek istediğimiz mesaj)’}”:
 Bunu kullanarak terminalden publisher oluşturabiliriz ve ekstra yazdığımız koda ek mesajları yansıtabiliriz subscriberlara.

13.TURTLESIM 

ros2 turtlesim : Bir arayüzdür ve belli topicler ,subslar ve publisherlar aracılığı ile çalışır.




14.INTERFACE

Example_interfaces ; https://github.com/ros2/example_interfaces/tree/rolling/msg
Common_interfaces ; https://github.com/ros2/common_interfaces/tree/rolling/geometry_msgs

15.SERVICES ve CLIENTS
Sürekli bir mesajın gerekli olmadığı durumlarda servisler ve kullanıcılar kullanılır. Mesela 2+2 isteği kullanıcıdan geldi ve sonucu servis 4 olarak yazdı. Burda amacımız tek bir bilgi ve sürekli olarak yazılmasına gerek yok. 

--SERVICE SERVER YAZMAK; 

#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts

class AddTwoIntServer(Node):
	def __init__(self):
		super().__init__("add_two_int_server")

		self.get_logger().info("Add Two Int Server has been started")
		self.server_ = 						 		         	self.create_service(AddTwoInts,"add_two_ints",self.callback_add_two_ints)
def callback_add_two_ints(self,request,response):
	response.sum = request.a + request.b 
	self.get_logger().info(f"{request.a} + {request.b} = {response.sum}") 
	return response

def main(args=None):
	rclpy.init(args=args)
	node = AddTwoIntServer()
	rclpy.spin(node)
	rclpy.shutdown()

if __name__ == '__main__':
main()

--Client Yazmak 
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from example_interfaces.srv import AddTwoInts

def main(args=None):
rclpy.init(args=args)
node = Node("add_two_ints_client")
client = node.create_client(AddTwoInts,"add_two_ints")
node.get_logger().info("Client has been started")
while not client.wait_for_service(1.0):
node.get_logger().warn("Waiting for service")

request = AddTwoInts.Request()
request.a = 5 
request.b = 14 
future = client.call_async(request)
rclpy.spin_until_future_complete(node,future)
try:
response = future.result()
node.get_logger().info(f"{request.a} + {request.b} = {response.sum}") 

except Exception as e :
node.get_logger().error("Service call has failed %r" & (e,))
rclpy.shutdown()

if __name__ == '__main__':
main()

--OOP Client Yazmak
#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts
from functools import partial

class ClientNode(Node): 

def __init__(self):
	super().__init__("add_two_ints_client") 
	self.call_add_two_ints_client(5,6)
	self.call_add_two_ints_client(1111,111191)
	self.call_add_two_ints_client(67,69)

def call_add_two_ints_client(self,a,b):
	client = self.create_client(AddTwoInts,"add_two_ints")
	while not client.wait_for_service(1.0):
		self.get_logger().warn("Waiting for service: add_two_ints")

request = AddTwoInts.Request()
request.a = a 
request.b = b 

future = client.call_async(request)
future.add_done_callback(partial(self.callback_call_add_two_ints,a=a,b=b))

def callback_call_add_two_ints(self,future,a,b):
	try:
	response = future.result()
	self.get_logger().info(f"{a} + {b} = {response.sum}") 

except Exception as e :
	self.get_logger().error("Service call has failed %r" & (e,))



def main(args=None):
	rclpy.init(args=args)
	node = ClientNode() 
	rclpy.spin(node)
	rclpy.shutdown()

if __name__ == "__main__":
main()

16.Launch Dosyası 
Launch Remapping

17.URDF Dosyası ve RVIZ
