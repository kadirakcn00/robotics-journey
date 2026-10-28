# M1: URDF (Robot Modeli)

**Ortam:** Ubuntu 20.04 + ROS 2 Foxy  
**Proje:** Dört tekerlekli kara robotu (UGV)  
**Dosya:** ~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf/ugv.urdf

## 1. URDF
**Tanım:** URDF, robotun fiziksel yapısını XML ile anlatan formattır. Parçalarını, şekillerini, parçaların birbirine bağlantısını ve hareketli eklemlerini bununla tanımlarız. Hepsi `<robot>` etiketinin içine yazılır.

```xml
<?xml version="1.0"?>
<robot name="ugv">

    <!-- Parçalar (link) burada -->

    <!-- Bağlantılar (joint) burada -->

</robot>
```

**Komutlar:**
```bash
cd ~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf
ls -l ugv.urdf
check_urdf ugv.urdf
```
ls -l ugv.urdf: Dosyanın orada olduğunu kontrol eder.

check_urdf ugv.urdf: Dosyayı doğrular. Başarılıysa `Successfully Parsed XML` yazar.

Ör: Fabrikada araç monte edilmeden önce hangi parça nereye gidecek çizilir. URDF robotun o çizimidir.

Not: `check_urdf` geçmesi tasarımın doğru olduğu anlamına gelmez, sadece dosyanın okunabildiğini gösterir.

---

## 2. Link
**Tanım:** Link robotun bir parçasıdır. Bizim robotta 5 link var:

| Link | Görevi |
|---|---|
| `base_link` | Ana gövde |
| `right_front_wheel` | Sağ ön tekerlek |
| `right_back_wheel` | Sağ arka tekerlek |
| `left_front_wheel` | Sol ön tekerlek |
| `left_back_wheel` | Sol arka tekerlek |

```xml
<link name="base_link">
</link>
```
İçi boş bir link görünmez. Şekli için `visual` yazmak gerekir.

**Komutlar:**
```bash
check_urdf ugv.urdf
grep -n '<link' ugv.urdf
```
grep -n '<link' ugv.urdf: Dosyadaki link tanımlarını satır numarasıyla listeler.

Ör: Oyuncak arabanın gövdesi ve dört tekerleği ayrı parçalardır. URDF'de her biri ayrı bir link.

**Görsel:**
<!-- ![check_urdf çıktısı](images/ugv_check_urdf.png) -->

**Akılda tut:** Link parçadır. İki parçayı bağlayan şey joint'tir.

---

## 3. Visual, Geometry, Material
**Tanım:** Robotun RViz2'de nasıl görüneceğini belirler.

- `visual`: Parçanın görünüşü
- `geometry`: Şekli ve ölçüleri
- `material`: Rengi

Şasi kutu, tekerlekler silindir.

```xml
<visual>
    <geometry>
        <box size="0.5 0.3 0.2"/>
    </geometry>
</visual>
```
Değerler metre. Sırayla uzunluk 0.5, genişlik 0.3, yükseklik 0.2.

```xml
<visual>
    <geometry>
        <cylinder radius="0.07" length="0.04"/>
    </geometry>
</visual>
```
Tekerlek: yarıçap 0.07, kalınlık 0.04.

Silindir varsayılan olarak dik durur. Tekerleği yatırmak için yönelim veriyoruz:

```xml
<origin xyz="0 0 0" rpy="1.5708 0 0"/>
```
`1.5708` radyan, yaklaşık 90 derece.

**Komutlar:**
```bash
grep -n -E 'visual|geometry|box|cylinder|material' ugv.urdf
```
grep -n -E '...': Görsel tanımlarının geçtiği satırları gösterir.

Ör: CAD'de şasiyi dikdörtgen prizma, tekerleği silindir çizmek gibi. Şimdilik basit şekiller kullanıyoruz, detayı sonra CAD ile ekleyeceğiz.

**Görsel:**
<!-- ![RViz2'de UGV](images/ugv_rviz.png) -->

Not: RViz2'de bir tekerleğin kırmızı görünmesi tek başına hata değil, renk tanımına bağlı.

---

## 4. Collision
**Tanım:** Collision, çarpışma hesabı için kullanılan şekildir. Görünüşle aynı olmak zorunda değil.

| | Görevi |
|---|---|
| `visual` | Nasıl göründüğü |
| `collision` | Çarpışmada nasıl hesaplanacağı |

```xml
<collision>
    <geometry>
        <box size="0.5 0.3 0.2"/>
    </geometry>
</collision>
```

**Komutlar:**
```bash
grep -n -A8 '<collision>' ugv.urdf
```
grep -n -A8 '<collision>': Collision satırını ve altındaki 8 satırı gösterir.

Ör: Robotun üstünde vida başları, küçük çıkıntılar olabilir. Hepsini hesaba katmak simülasyonu yavaşlatır, onun yerine gövdeyi tek bir basit kutu olarak alırız.

Not: Collision'ın olması Gazebo'ya hazır olduğumuz anlamına gelmez. Fizik için kütle (`inertial`) ve kontrol sistemi de gerekiyor.

---

## 5. Joint
**Tanım:** Joint, iki link arasındaki bağlantıdır.

| Tür | Anlamı |
|---|---|
| `fixed` | Hareket etmez |
| `revolute` | Belli bir açı aralığında döner |
| `continuous` | Tam tur dönebilir |
| `prismatic` | Bir eksen boyunca kayar |

Bizim tekerlekler `continuous`.

```xml
<joint name="right_front_wheel_joint" type="continuous">
    <parent link="base_link"/>
    <child link="right_front_wheel"/>
    <origin xyz="0.16 -0.17 0.07" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
</joint>
```

- `name`: Eklemin adı
- `type`: Hareket türü
- `parent`: Ana link
- `child`: Bağlanan link
- `origin`: Konum ve yönelim
- `axis`: Dönme ekseni

**Komutlar:**
```bash
grep -n -E '<joint|<parent|<child|<origin|<axis' ugv.urdf
```
grep -n -E '...': Joint ile ilgili satırları listeler.

Ör: Arabanın tekerleği gövdeye bağlıdır ama kendi ekseninde döner. Joint bu ilişkiyi anlatır.


---

## 6. Origin ve Axis
**Tanım:** Origin parçanın nerede duracağını, axis eklemin hangi eksende döneceğini belirler.

```xml
<origin xyz="0.16 -0.17 0.07" rpy="0 0 0"/>
```
- `xyz`: Konum (x, y, z), metre
- `rpy`: Dönüş (roll, pitch, yaw), radyan

```xml
<axis xyz="0 1 0"/>
```
Eklem Y ekseni etrafında döner.

**Komutlar:**
```bash
grep -n -A5 '<joint' ugv.urdf
```
grep -n -A5 '<joint': Her joint'in altındaki 5 satırı gösterir.

Ör: Sağ ön tekerleğin şasinin ne kadar önünde, hangi yanında ve yerden ne kadar yüksekte durduğu origin ile belirlenir. Hangi eksende döneceği axis ile.

**Origin konumu belirler, axis dönme eksenini belirler.**

---

## 7. Robot State Publisher
**Tanım:** URDF'deki bağlantı ağacını kullanarak linkler arasındaki koordinat dönüşümlerini hesaplar ve TF üzerinden yayınlar. Eklem konumları değişince dönüşümleri de günceller.

**Komutlar:**
```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat ugv.urdf)"
ros2 topic list
```
İlk komutu URDF dosyasının olduğu klasörde çalıştırıyoruz.

ros2 topic list: Yayınlanan topic'leri listeler.

Ör: Gerçek robotta tekerlek enkoderleri dönüşü ölçer. Bu değerlerle tekerleğin gövdeye göre konumu hesaplanır. Robot State Publisher bu bilgiyi diğer node'lara iletir.

Not: Motorları çalıştırmaz. Sadece robotun yapısını ve dönüşümleri yayınlar.

---

## 8. Joint State Publisher GUI
**Tanım:** Eklemlere elle değer göndermemizi sağlayan küçük bir arayüz. Tekerlekleri test etmek için kullandık.

**Komutlar:**
```bash
ros2 run joint_state_publisher_gui joint_state_publisher_gui
ros2 topic echo /joint_states
```
İlk komut slider'lı pencereyi açar.

ros2 topic echo /joint_states: Slider'ı oynattıkça eklem değerlerinin değiştiğini terminalde gösterir.

Ör: Robotu henüz üretmedik. Motor olmadan tekerlek açılarını bu arayüzle değiştirip bağlantıların doğru çalıştığını kontrol ediyoruz.

**Sonuç:** Slider'ları oynatınca tekerlekler RViz2'de dönüyor.

**Görsel:**
<!-- ![Joint State Publisher GUI](images/ugv_joint_gui.png) -->

Not: Bu robotun zeminde ilerlediği anlamına gelmez, sadece eklem hareketini görüyoruz.

---

## 9. RViz2
**Tanım:** Robot modelini ve robotla ilgili verileri görselleştiren araç.

- `RobotModel`: URDF'deki robotu gösteren eklenti
- `Fixed Frame`: Görünümün referans aldığı koordinat çerçevesi. Biz `base_link` kullanıyoruz.

**Komutlar:**
```bash
rviz2
```
Açıldıktan sonra:

1. `Add` düğmesine bas
2. `RobotModel` ekle
3. `Global Options` içinde `Fixed Frame` değerini `base_link` yap
4. Robotun göründüğünü kontrol et

İstersek `TF` eklentisini de ekleyip koordinat çerçevelerini görebiliriz.

Ör: Robotun gövdesine kamera bağladığımızda kameranın gövdeye göre nerede durduğunu RViz2'de görürüz.


---

## 10. Topic ve TF
**Tanım:** Bu çalışmada gördüğümüz topic'ler:

| Topic | Görevi |
|---|---|
| `/joint_states` | Eklemlerin konum, hız ve efor bilgisi |
| `/robot_description` | Robotun URDF tanımı |
| `/tf` | Değişen koordinat dönüşümleri |
| `/tf_static` | Sabit koordinat dönüşümleri |

**TF:** Robotun parçalarının koordinat sistemleri arasındaki ilişkiyi tutan sistem.

**Komutlar:**
```bash
ros2 topic list
ros2 topic echo /joint_states
ros2 topic info /joint_states
```

Ör: Robotun önüne kamera, gövdesine IMU koyduk. Sensörlerin gövdeye göre yerini bilirsek gelen verileri doğru yorumlarız. TF bu ilişkiyi takip eder.

---

## 11. Tekerlek Konumları
**Tanım:** Dört tekerlek, her biri ayrı link ve joint. Konumlar `base_link`'e göre:

| Tekerlek | Joint | `origin xyz` |
|---|---|---|
| Sağ ön | `right_front_wheel_joint` | `0.16 -0.17 0.07` |
| Sağ arka | `right_back_wheel_joint` | `-0.16 -0.17 0.07` |
| Sol ön | `left_front_wheel_joint` | `0.16 0.17 0.07` |
| Sol arka | `left_back_wheel_joint` | `-0.16 0.17 0.07` |

**Komutlar:**
```bash
grep -n -A5 '<joint' ugv.urdf
```

Ör: Arabada iki tekerlek önde, iki tekerlek arkada. Burada aynı yerleşimi sayılarla yazıyoruz. Değerleri değiştirince tekerlekler yer değiştirir.



--

## 12. Projeyi Yeniden Çalıştırma
**Tanım:** Üç parça lazım ve her biri ayrı terminalde çalışır. Birini kapatırsan o parça durur.

1. `robot_state_publisher`: Dönüşümleri yayınlar
2. `joint_state_publisher_gui`: Eklem açılarını değiştirir
3. `rviz2`: Gösterir

**Komutlar:**
```bash
cd ~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf
check_urdf ugv.urdf
```

Terminal 1:
```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat ugv.urdf)"
```

Terminal 2:
```bash
ros2 run joint_state_publisher_gui joint_state_publisher_gui
```

Terminal 3:
```bash
rviz2
```

Her yeni terminalde önce `source /opt/ros/foxy/setup.bash` yapmayı unutma.

---

# M2 : TF2 ve Odometri 


**Koordinat Çerçevesi Kavramı**

Koordinat çerçevesinde üç temel eksen bulunur: 

X: İleri-geri 
Y: Sağ-Sol
Z: Yukarı-aşağı 


**Örnek:** Robot sağa-sola veya ileri-geri hareket yaptığında burda robotun koordinat çevresi değişir. 

## base_link , odom , map 

**base_link**

Robotun gövdesine bağlanan koordinat çerçevesidir. Robot ileri gider base_link'te onunla beraber hareket eder. 

**odom**

Robotun hareketini takip etmek için kullanılan koordinat çerçevesidir. Odometri, robotun konum ve hareketlerinde değişimleri tahmin etmede kullanılır.


**map(Harita Referansı)**

Robotun hareketini harita üzerinde gösteren koordinat çerçevesidir. SLAM veya başka bir konum belirleme sistemi , robotun haritadaki konumunu tahmin etmeye yardımcı olabilir.


| Koordinat çerçevesi | Ne anlatır? | Basit örnek |
|---|---|---|
| `base_link` | Robotun kendisine bağlı konum ve yönler | Gövdeye göre kamera nerede? |
| `odom` | Hareket boyunca takip edilen konum | Başlangıçtan beri ne kadar ilerledik? |
| `map` | Haritaya göre konum | Haritada hangi noktadayız? |


Üçünün ilişkileri şu şekildedir; 

map → odom → base_link

## TF Bilgisini Robot Modelde Kontrol Etmek 

Önce topic bilgisini alırız: 

```bash 
ros2 topic list | grep tf 
```


![ros2_topic_list](images/tf2.png)

---

Sonra TF mesajlarına bakarız : 

```bash 
ros2 topic echo /tf 
```


![ros2_topic_list](images/tf2_echo.png)


**Burdaki parçalar bize hangi bilgileri veriyor ?**

**1. frame_id: base_link**

Referans koordinat çerçevesinin robotun gövdesinde olduğunu söylüyor. Yani referans noktamızı base_link'e göre alıyoruz

**2. child_frame_id: right_front_wheel**

Hedef çerçevesinde sağ ön tekerleğin olduğunu gösterir. Yani sağ ön tekerleğin koordinat çerçevesi base_link'e bağlı

**3. translation: Tekerlek Nerde?**

translation:
  x: 0.16
  y: -0.17
  z: 0.07
  
  Tekerlek konumunu gösterir. 


**4. rotation: Tekerlek Hangi Yönde?**

rotation:
  x: 0.0
  y: 0.0
  z: 0.0
  w: 1.0
  
  Ek bir hareket görünmüyor çünkü aracımız sabit bekliyor. 
**5. stamp: Bu Dönüşüm Ne Zaman Yayınlandı?**

stamp:
  sec: 1792685855
  nanosec: 236565646
  
Bu alan, dönüşümün zaman bilgisini taşır.
- sec: Saniye bölümü
- nanosec: Saniyenin milyarda biri cinsinden ek süre

Zaman bilgisi özellikle hareketli robotlarda önemlidir. Çünkü sensör verilerini ve robotun konumunu aynı zaman anına göre değerlendirmek iyi olur. 
  
---
/tf_static mesajlarını da echo yöntemiyle görüntülüyebiliriz.

```bash 
ros2 topic echo /tf_static
```

![ros2_topic_list](images/tf2_2.png)

## 5. İlk Odometri Düğümümüz: `cmd_vel` Okumak

İlk Python kodumuz, `cmd_vel` topic'ini dinleyerek gelen hız komutlarını ekrana yazdırır.

### Kod

```python
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class OdomNode(Node):
    def __init__(self):
        super().__init__('odom_node')

        self.sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.cmd_callback,
            10
        )

    def cmd_callback(self, msg):
        self.get_logger().info(
            f'v = {msg.linear.x}, w = {msg.angular.z}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = OdomNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
```

### 5.1. Kullanılan kütüphaneler

**`rclpy`**

Python ile ROS 2 düğümleri geliştirmemizi sağlar.

**`Node`**

ROS 2 düğümümüzün temel sınıfıdır.

**`Twist`**

Doğrusal ve açısal hız komutlarını taşımak için kullanılan mesaj türüdür.

### 5.2. Düğümü oluşturmak

```python
super().__init__('odom_node')
```

ROS 2 düğümünün adını `odom_node` olarak belirler.

### 5.3. Subscription oluşturmak

```python
self.sub = self.create_subscription(
    Twist,
    'cmd_vel',
    self.cmd_callback,
    10
)
```

Bu satır, `cmd_vel` topic'ine abone olur.

Parametrelerin anlamları:

- `Twist`: Beklenen mesaj türü.
- `cmd_vel`: Dinlenecek topic.
- `self.cmd_callback`: Mesaj geldiğinde çalıştırılacak fonksiyon.
- `10`: Aboneliğin mesaj kuyruğu derinliği.

### 5.4. Hız değerlerini okumak

```python
def cmd_callback(self, msg):
    self.get_logger().info(
        f'v = {msg.linear.x}, w = {msg.angular.z}'
    )
```

Burada:

- `msg.linear.x`: X eksenindeki doğrusal hız.
- `msg.angular.z`: Z ekseni etrafındaki açısal hız.

ROS'ta bu değerler standart olarak doğrusal hız için metre/saniye, açısal hız için radyan/saniye birimleriyle kullanılır.

Bu ilk kod, hızları kullanarak konum hesaplamaz. Yalnızca gelen değerleri ekrana yazdırır.

---

## 6. İkinci Odometri Düğümümüz: Konum Tahmini ve TF Yayınlama

İkinci kodumuz, ilk koddan farklı olarak hız komutlarını zaman boyunca işler.

Bu kodun amacı:

1. `cmd_vel` üzerinden hız komutlarını almak.
2. Başlangıç konumunu sıfır kabul etmek.
3. Hız ve geçen süre üzerinden yaklaşık konum hesaplamak.
4. `odom → base_link` dönüşümünü TF üzerinden yayınlamak.

Bu yaklaşım, odometrinin temel mantığını öğrenmek için hazırlanmış basitleştirilmiş bir modeldir.

### 6.1. Kullanılan kütüphaneler

```python
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from tf2_ros import TransformBroadcaster
```

- `math`: Trigonometrik hesaplamalar için kullanılır.
- `rclpy`: ROS 2 Python arayüzüdür.
- `Node`: ROS 2 düğüm sınıfıdır.
- `Twist`: Hız komutlarını taşır.
- `TransformStamped`: Zaman damgası ve koordinat dönüşümü bilgilerini taşır.
- `TransformBroadcaster`: Dinamik TF dönüşümlerini yayınlar.

### 6.2. Başlangıç değişkenleri

```python
self.x = 0.0
self.y = 0.0
self.theta = 0.0

self.v = 0.0
self.w = 0.0

self.last_time = self.get_clock().now()
```

Değişkenlerin görevleri:

| Değişken    | Anlamı                                 |
| ----------- | -------------------------------------- |
| `x`         | Tahmini X konumu                       |
| `y`         | Tahmini Y konumu                       |
| `theta`     | Tahmini yönelim açısı                  |
| `v`         | Son alınan doğrusal hız                |
| `w`         | Son alınan açısal hız                  |
| `last_time` | Bir önceki güncellemenin zaman bilgisi |

Başlangıçta robotun konumu ve yönelimi sıfır kabul edilir.

### 6.3. TF yayınlayıcısını oluşturmak

```python
self.tf_broadcaster = TransformBroadcaster(self)
```

Bu nesne, düğümün TF dönüşümleri yayınlamasını sağlar.

### 6.4. Zamanlayıcı oluşturmak

```python
self.timer = self.create_timer(0.05, self.update)
```

`update()` fonksiyonu yaklaşık her 0,05 saniyede bir çağrılır.

Hesaplama:

`1 / 0.05 = 20 Hz`

Yani düğüm, normal koşullarda saniyede yaklaşık 20 kez konumunu güncellemeye çalışır.

### 6.5. Gelen hızları saklamak

```python
def cmd_callback(self, msg):
    self.v = msg.linear.x
    self.w = msg.angular.z
```

Bu fonksiyon yeni bir hız komutu geldiğinde doğrusal ve açısal hızları günceller.

Burada önemli bir nokta vardır: Kod, yeni bir mesaj gelmediğinde hızları otomatik olarak sıfırlamaz. Son alınan değerler değişene kadar kullanılmaya devam eder.

### 6.6. Geçen süreyi hesaplamak

```python
now = self.get_clock().now()

dt = (now - self.last_time).nanoseconds / 1e9

self.last_time = now
```

`dt`, iki güncelleme arasındaki süreyi saniye cinsinden hesaplar.

Nanosecond değerini saniyeye çevirmek için `1e9`, yani bir milyar kullanılır.

Örneğin iki güncelleme arasında 0,05 saniye geçtiyse `dt` yaklaşık `0.05` olur.

Gerçek zamanlama gecikebileceğinden bu değerin her zaman tam olarak 0,05 olması garanti değildir.

### 6.7. Konumu güncellemek

```python
self.x += self.v * math.cos(self.theta) * dt
self.y += self.v * math.sin(self.theta) * dt
self.theta += self.w * dt
```

Bu bölüm, kodun hareket hesabını yapan kısmıdır.

Kullanılan basitleştirilmiş diferansiyel hareket modeli:

- X yönündeki hız: `v * cos(theta)`
- Y yönündeki hız: `v * sin(theta)`
- Yönelim değişim hızı: `w`

Bu hızlar, geçen süreyle çarpılarak yaklaşık konum değişimine dönüştürülür.

#### Örnek: Düz ilerleme

Başlangıçta:

```text
x = 0
y = 0
theta = 0
v = 0.2 m/s
w = 0 rad/s
```

Yönelim sıfır olduğu için:

`cos(0) = 1`

`sin(0) = 0`

Yaklaşık 0,05 saniyelik bir güncellemede:

`Δx = 0.2 × 1 × 0.05 = 0.01 m`

`Δy = 0.2 × 0 × 0.05 = 0 m`

Robotun tahmini konumu X yönünde yaklaşık 1 cm ilerler.

Bu işlem tekrarlandıkça X konumu artar.

#### Örnek: Dönerek ilerleme

Doğrusal hız `0.2 m/s`, açısal hız `0.5 rad/s` olduğunda robot hem ileri gider hem de yönelim açısı değişir.

Kod, yönelim açısını her güncellemede değiştirir. Sonraki konum hesaplamalarında bu yeni açı kullanılır.

Bu yöntem öğrenme amacıyla yeterlidir; ancak adım adım sayısal integrasyon yaptığı için hesaplanan konum yaklaşık değerdir.

### 6.8. Transform mesajını hazırlamak

```python
t = TransformStamped()

t.header.stamp = now.to_msg()
t.header.frame_id = 'odom'
t.child_frame_id = 'base_link'
```

Bu bölüm, `odom → base_link` dönüşüm mesajını oluşturur.

- `header.stamp`: Dönüşümün zaman damgası.
- `header.frame_id`: Referans çerçevesi, `odom`.
- `child_frame_id`: Konumu ifade edilen çerçeve, `base_link`.

Bu nedenle mesaj, robot gövdesinin odometri referansına göre tahmini konumunu temsil eder.

### 6.9. Konum değerlerini mesaja aktarmak

```python
t.transform.translation.x = self.x
t.transform.translation.y = self.y
t.transform.translation.z = 0.0
```

Hesaplanan X ve Y konumları mesaja aktarılır.

Z değeri sıfır tutulduğu için robotun dikey yönde hareket etmediği varsayılır.

### 6.10. Yönelim değerlerini hesaplamak

```python
t.transform.rotation.x = 0.0
t.transform.rotation.y = 0.0

t.transform.rotation.z = math.sin(self.theta / 2.0)
t.transform.rotation.w = math.cos(self.theta / 2.0)
```

TF, yönelimi quaternion biçiminde ifade eder.

Yalnızca Z ekseni etrafında dönüş olduğu varsayıldığında, yönelim açısı `theta` şu şekilde quaternion'a çevrilir:

- `z = sin(theta / 2)`
- `w = cos(theta / 2)`

X ve Y bileşenleri sıfırdır.

### 6.11. Dönüşümü yayınlamak

```python
self.tf_broadcaster.sendTransform(t)
```

Hazırlanan dönüşümün TF sistemi üzerinden yayınlanmasını sağlar.

Böylece TF araçları, `odom` referansına göre `base_link` konumunu sorgulayabilir.

---

## 7. Terminal Komutları

### 7.1. Doğrusal hız komutu göndermek

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}}"
```

Bu komut, `/cmd_vel` topic'ine tek bir `Twist` mesajı gönderir.

Doğrusal X hızı `0.2 m/s` olarak belirlenir.

Ancak `--once` yalnızca mesajın bir kez yayınlanmasını sağlar. Mesajın içindeki hızın sıfırlanmasını sağlamaz.

Bizim Python düğümümüz son aldığı hızı sakladığı için yeni bir sıfır hız mesajı gelene kadar bu hızla hesaplama yapmayı sürdürür.

### 7.2. Doğrusal hızı sıfırlamak

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}"
```

Bu komut, doğrusal hızı sıfırlayan bir mesaj gönderir.

Açısal hız da sıfırlanmak isteniyorsa mesajda `angular.z: 0.0` değerinin açıkça belirtilmesi daha güvenlidir.

### 7.3. İleri giderken dönmek

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.5}}"
```

Bu mesajda:

- Doğrusal X hızı: `0.2 m/s`
- Açısal Z hızı: `0.5 rad/s`

olarak ayarlanır.

Düğüm, bu değerleri kullanarak yaklaşık konum ve yönelim hesabı yapar.

### 7.4. TF dönüşümünü kontrol etmek

```bash
ros2 run tf2_ros tf2_echo odom base_link
```

Bu komut, `odom` ile `base_link` arasındaki dönüşümü sorgular.

Bunun çalışması için ilgili dönüşümün TF sisteminde yayınlanıyor olması gerekir. Dolayısıyla odometri düğümümüzün çalışıyor olması önemlidir.

Çıktıda robotun tahmini konumunu ve yönelimini görebiliriz.

### 7.5. Klavyeden hız komutu göndermek

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Bu komut, klavyeden hız komutları gönderen teleoperasyon düğümünü başlatır.

Klavyeden gönderilen komutlar `/cmd_vel` topic'ine ulaşır. Odometri düğümümüz bu mesajları alarak konum tahmini yapabilir.

Ancak mevcut kodumuz yalnızca tahmini TF dönüşümü yayınlar. Robot modelini fiziksel olarak hareket ettirmek için ayrıca bir simülasyon veya hareket kontrol sistemi gerekir.

---


 


