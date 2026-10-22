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

