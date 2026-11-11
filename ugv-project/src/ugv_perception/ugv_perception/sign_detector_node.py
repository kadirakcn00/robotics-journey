"""Kamera goruntusunden parkur asama tabelasini okuyan ROS 2 node'u.

Abone olur:
    image_topic (sensor_msgs/Image)       : kamera goruntusu
Yayinlar (node'un namespace'i altinda):
    stage_sign (std_msgs/Int32)           : okunan tabela numarasi (en buyuk/en yakin tabela)
    sign_debug (sensor_msgs/Image)        : tespitlerin cizildigi goruntu (RViz icin)

Parametreler:
    image_topic : /camera/front/image_raw
    models_dir  : tabela dokularinin oldugu klasor (varsayilan: ugv_gazebo/models)
    rotations   : goruntunun sablona gore donuk olabilecegi acilar, orn. [0, 90, 180, 270]
"""

import os

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import Int32

from ugv_perception.sign_detection import SignDetector


def default_models_dir():
    try:
        from ament_index_python.packages import get_package_share_directory
        return os.path.join(get_package_share_directory('ugv_gazebo'), 'models')
    except Exception:
        return ''


class SignDetectorNode(Node):

    def __init__(self):
        super().__init__('sign_detector')
        self.declare_parameter('image_topic', '/camera/front/image_raw')
        self.declare_parameter('models_dir', default_models_dir())
        self.declare_parameter('rotations', [0])

        models_dir = self.get_parameter('models_dir').value
        rotations = tuple(int(r) for r in self.get_parameter('rotations').value)
        self.detector = SignDetector.from_texture_dir(models_dir, rotations=rotations)
        self.get_logger().info(
            f'{len(self.detector.templates)} tabela sablonu yuklendi ({models_dir})')

        self.bridge = CvBridge()
        self.last_number = None
        self.pub_sign = self.create_publisher(Int32, 'stage_sign', 10)
        self.pub_debug = self.create_publisher(Image, 'sign_debug', 1)
        topic = self.get_parameter('image_topic').value
        self.create_subscription(Image, topic, self.on_image, qos_profile_sensor_data)
        self.get_logger().info(f'Dinlenen kamera: {topic}')

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        found = self.detector.detect(frame)

        if found:
            number, score, _ = max(found, key=lambda f: f[2][2] * f[2][3])
            self.pub_sign.publish(Int32(data=number))
            if number != self.last_number:
                self.get_logger().info(f'Asama tabelasi: {number} (skor {score:.2f})')
                self.last_number = number

        if self.pub_debug.get_subscription_count() > 0:
            for number, score, (x, y, w, h) in found:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, f'{number} ({score:.2f})', (x, max(15, y - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            out = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            out.header = msg.header
            self.pub_debug.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = SignDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
