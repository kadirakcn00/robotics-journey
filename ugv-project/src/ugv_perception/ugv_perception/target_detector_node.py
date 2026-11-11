"""Nisan kamerasi goruntusunden atis hedefini bulan ROS 2 node'u.

Abone olur:
    image_topic (sensor_msgs/Image)          : nisan kamerasi goruntusu
Yayinlar (node'un namespace'i altinda):
    target (geometry_msgs/PointStamped)      : hedef bulundugunda
        point.x : yatay sapma [-1, 1]  (> 0: hedef goruntunun sagında)
        point.y : dikey sapma [-1, 1]  (> 0: hedef goruntunun altinda)
        point.z : dis halkanin yaricapi (piksel), mesafe hakkinda fikir verir
    target_debug (sensor_msgs/Image)         : hedefin ve nisangahin cizildigi goruntu
"""

import cv2
from cv_bridge import CvBridge
from geometry_msgs.msg import PointStamped
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from ugv_perception.target_detection import detect_target


class TargetDetectorNode(Node):

    def __init__(self):
        super().__init__('target_detector')
        self.declare_parameter('image_topic', '/camera/aim/image_raw')
        self.bridge = CvBridge()
        self.seen = False
        self.pub_target = self.create_publisher(PointStamped, 'target', 10)
        self.pub_debug = self.create_publisher(Image, 'target_debug', 1)
        topic = self.get_parameter('image_topic').value
        self.create_subscription(Image, topic, self.on_image, qos_profile_sensor_data)
        self.get_logger().info(f'Dinlenen kamera: {topic}')

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        t = detect_target(frame)

        if t is not None:
            p = PointStamped()
            p.header = msg.header
            p.point.x, p.point.y = float(t['offset'][0]), float(t['offset'][1])
            p.point.z = float(t['radius'])
            self.pub_target.publish(p)
        if (t is not None) != self.seen:
            self.seen = t is not None
            self.get_logger().info('Hedef bulundu' if self.seen else 'Hedef kayboldu')

        if self.pub_debug.get_subscription_count() > 0:
            h, w = frame.shape[:2]
            cv2.drawMarker(frame, (w // 2, h // 2), (0, 255, 255), cv2.MARKER_CROSS, 30, 1)
            if t is not None:
                c = (int(t['center'][0]), int(t['center'][1]))
                cv2.circle(frame, c, int(t['radius']), (0, 255, 0), 2)
                cv2.drawMarker(frame, c, (0, 255, 0), cv2.MARKER_CROSS, 12, 2)
                cv2.putText(frame, f"dx={t['offset'][0]:+.2f} dy={t['offset'][1]:+.2f}",
                            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            out = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            out.header = msg.header
            self.pub_debug.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = TargetDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
