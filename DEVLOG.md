# Geliştirme Günlüğü (DEVLOG)

Bu dosya projede yapılan her şeyin, alınan kararların ve sıradaki işlerin özetidir.
Yeni bir çalışma oturumuna başlarken önce bu dosyayı oku; kaldığımız yer en altta.

Son güncelleme: 14 Kasım 2026

---

## 1. Proje özeti

- **Repo:** `kadirakcn00/robotics-journey`
- **Ortam:** Ubuntu 22.04, ROS 2 Humble, Gazebo Fortress (Ignition Gazebo 6), `ros_gz`
- **Amaç:** ROS 2 öğrenme yolculuğu ve dört tekerlekli UGV'yi (insansız kara aracı)
  **TEKNOFEST 2026 İnsansız Kara Aracı Yarışması** parkurunda simüle etmek. Son hedef
  parkuru baştan sona **tam otonom** geçen kod.
- **Şartname:** TEKNOFEST 2026 İKA Türkçe şartnamesi (27 sayfa, V1.3). Özeti 7. bölümde.

### Çalışma kuralları (önemli)

| Kural | Açıklama |
|---|---|
| Çalışma branch'i | `ugv_dev`. Her iş buraya push'lanır, PR ile `main`'e girer. |
| PR birleştirme | **Squash and merge**. Birleştirdikten sonra `ugv_dev` **silinmez**. |
| Commit yazarı | Abdulkadir Akcan, GitHub noreply e-postası. |
| Yapay zekâ izi | Commit'lerde, PR açıklamalarında ve dosyalarda yapay zekâ aracının adı, `Co-Authored-By` ya da oturum linki **olmayacak**. GitHub PR açarken açıklamaya otomatik not ekliyor; PR açıldıktan hemen sonra açıklama düzenlenip not silinmeli. |
| Notlar | `ros2-basics/notes.*.md` ve `ugv-project/notes.*.md` dosyalarını **Kadir yazar**, dokunulmaz. README değiştirilebilir. |
| Test | Kodu yazan ortamda ROS/Gazebo yok (Ubuntu 24.04). Gazebo testi her zaman Kadir'in makinesinde. ROS'tan bağımsız algoritmalar pytest ile önceden test edilir. |

### Yerel makineyi GitHub ile eşitleme

```bash
cd ~/robotics-journey && git fetch origin --prune && git checkout main && git reset --hard origin/main
```
```bash
cd ugv-project && rm -rf build install log && colcon build && source install/setup.bash
```

`~/.bashrc` sonunda `source /opt/ros/humble/setup.bash` ve
`source ~/robotics-journey/ugv-project/install/setup.bash` satırları var.

---

## 2. Paket yapısı (`ugv-project/src`)

```
ugv_description/   Robot modeli (xacro): gövde, tekerlek makrosu, LIDAR, 3 kamera, nişan tareti
ugv_gazebo/        Dünyalar (ugv_world, perception_world), tabela/hedef modelleri, sim.launch.py
ugv_bringup/       Ana launch dosyaları: sim, slam, nav, perception, course + RViz ayarları
ugv_slam/          slam_toolbox ayarları, haritalar, sdf_to_map.py
ugv_navigation/    Nav2 ayarları + navigation.launch.py
ugv_perception/    Tabela okuyucu + atış hedefi bulucu (OpenCV) + testler
ugv_course/        TEKNOFEST parkuru: dünya üretici, su fiziği, kayar engel + testler
ugv_control/       avoid_node (LIDAR ile engelden kaçma)
ugv_odometry/      odom_node (M2 egzersizi; simülasyonla BİRLİKTE çalıştırılmaz)
```

### Çalıştırma komutları

| Komut | Ne açar |
|---|---|
| `ros2 launch ugv_description display.launch.py` | Sadece RViz'de model + eklem kaydırıcıları |
| `ros2 launch ugv_bringup sim.launch.py` | Gazebo + ugv_world + köprüler + RViz (`rviz:=false`) |
| `ros2 launch ugv_bringup slam.launch.py` | Simülasyon + slam_toolbox (harita çıkarma) |
| `ros2 launch ugv_bringup nav.launch.py` | Simülasyon + Nav2 (RViz'de **Nav2 Goal** ile hedef) |
| `ros2 launch ugv_bringup perception.launch.py` | Kamera test dünyası + tabela/hedef tespiti |
| `ros2 launch ugv_bringup course.launch.py` | TEKNOFEST parkuru (`start:=main` ya da `start:=accel`) |
| `ros2 run teleop_twist_keyboard teleop_twist_keyboard` | Klavyeyle sürüş |

Harita kaydetme (SLAM açıkken, `nav.launch.py` KAPALIYKEN):

```bash
cd ~/robotics-journey/ugv-project/src/ugv_slam/maps && ros2 run nav2_map_server map_saver_cli -f ugv_world
```

### Testler (ROS gerektirmez)

```bash
cd ugv-project/src/ugv_perception && python3 -m pytest test/test_detection.py     # 53 test
```
```bash
cd ugv-project/src/ugv_course && python3 -m pytest test/test_course_logic.py      # 13 test
```

### Üretici script'ler

| Script | Ürettiği |
|---|---|
| `ugv_gazebo/scripts/make_course_models.py` | Aşama tabelaları 1–11 ve atış hedefi modelleri (×0.4) |
| `ugv_course/scripts/make_teknofest_course.py` | Parkur dünyası, yan eğim mesh'i, koni + kayar engel modelleri, `water_zones.yaml`, `docs/course_top_view.png` |
| `ugv_slam/scripts/sdf_to_map.py` | Bir `.sdf` dünyasındaki kutu/silindirlerden Nav2 haritası |

Parkurda bir ölçü değişirse `make_teknofest_course.py` düzenlenip tekrar çalıştırılır;
`teknofest_course.sdf` elle düzenlenmez.

---

## 3. Robotun güncel hali

| Parça | Değer |
|---|---|
| Gövde | 0.5 × 0.3 × 0.2 m, 5 kg, merkezi `base_z = 0.20` (yerden yükseklik 10 cm) |
| Tekerlekler | 4 adet, yarıçap **0.12 m**, genişlik 0.04, konum x ±0.16 / y ±0.17, sürtünme 1.2 |
| Sürüş | Gazebo `DiffDrive` (4 tekerlek, skid-steer), `wheel_separation 0.34` |
| LIDAR | **Ön tampon** (0.30, 0, 0.20), `gpu_lidar`, **±90°**, 181 ışın, 0.12–10 m, `/scan` |
| Ön kamera | Gövde üstü önde, 69° FOV, 640×480, `/camera/front/image_raw` |
| Arka kamera | Arka yüz, 69° FOV, `/camera/rear/image_raw` |
| Nişan tareti | Arkada direk + pan (±162°) + tilt (±34°), dar açılı nişan kamerası (14°) + lazer linki |
| Taret komutu | `/aim/pan_cmd`, `/aim/tilt_cmd` (std_msgs/Float64, radyan) |
| Gerçek konum | Gazebo `OdometryPublisher` → `/ground_truth/odom` |
| Nav2 footprint | `[[0.35, 0.21], [0.35, -0.21], [-0.30, -0.21], [-0.30, 0.21]]` |

Hız komutu topic'i xacro/launch argümanı: `cmd_vel_topic` (varsayılan `/cmd_vel`).
Parkurda `/cmd_vel → water_physics → /cmd_vel_gz → Gazebo`.

### Köprüler (`ugv_gazebo/launch/sim.launch.py`)

Üç ayrı `parameter_bridge` var; biri çökerse diğerleri çalışır:

- `bridge_core`: `/clock`, hız komutu, `/odom`, `/ground_truth/odom`, `/tf`, `/scan`, `/joint_states`
- `bridge_cameras`: 3 kameranın `image_raw` + `camera_info`
- `bridge_turret`: `/aim/pan_cmd`, `/aim/tilt_cmd`
- Parkurda ayrıca `bridge_course`: `/course/slider_cmd`

---

## 4. Yapılanlar (PR'lar)

| PR | Konu | Sonuç |
|---|---|---|
| #1 | Gazebo Classic 11 → Gazebo Fortress geçişi | Çalıştı (Gazebo + RViz birlikte açıldı) |
| #2 | Paket düzeni + URDF→xacro + SLAM (slam_toolbox) | Çalıştı (harita çıkarma) |
| #3 | Nav2 (AMCL, NavFn, Regulated Pure Pursuit) + referans harita | Çalıştı (#7 sonrası) |
| #4 | M5 kameralar | Branch yeniden adlandırılınca kapandı, #5 olarak açıldı |
| #5 | 3 kamera + nişan tareti + tabela/hedef tespiti | Çalıştı (#7 sonrası) |
| #6 | `main` → `ugv_dev` birleştirmesi (Kadir açtı) | Gereksizdi, zararsız |
| #7 | Köprü çökmesi düzeltmesi + köprüyü üçe bölme | Çalıştı |
| #8 | TEKNOFEST parkuru (M6) | Rampada takıldı, havuz görünmedi |
| #9 | Parkur fiziği düzeltmesi (tekerlek, eğimler, havuz, LIDAR) | Birleştirildi, README'de M6 "Completed" |

Ayrıca: `main` geçmişi yeniden yazıldı (eski commit'lerin yazarı Kadir yapıldı, yapay zekâ
satırları silindi), çalışma branch'i `ugv_dev` olarak yeniden adlandırıldı.

### Doğrulanan test sonuçları (Kadir'in makinesi)

- SLAM ile harita çıkarma çalışıyor.
- Nav2: verilen hedefe gidiyor.
- Kamera: ön kamera `stage_sign = 4`, arka kamera `11`, hedef sapması x = −0.001, y = −0.018,
  yarıçap 19.2 px (beklenen ≈19.5). Taret `pan_cmd` ile dönüyor.
- Tabela dokuları Gazebo'da düz görünüyor (ters/aynalı değil).

### Tespit algoritmalarının sentetik test sonuçları

- Tabela okuyucu: 600 rastgele sahnede **0 yanlış okuma**. ≥70 px: 370/370, 40–70 px: 160/163,
  <40 px: 52/67 (emin olmadığında atlıyor). Atış hedefi: 200/200.

---

## 5. Karşılaşılan hatalar ve dersler

| Sorun | Sebep | Çözüm / ders |
|---|---|---|
| `git push` 403 | GitHub şifre kabul etmiyor; fine-grained token'ın yazma izni yoktu | Token'da `robotics-journey` seçili + Contents: Read and write |
| Nav2 "unknown", `map` frame yok, `/clock` boş | Köprü çökmüştü: `/model/ugv/joint/aim_pan_joint/0/cmd_pos` adındaki `0` ROS isim kuralına aykırı, remap geçersiz | Topic adlarını SDF'te `<topic>` ile ver; ROS'ta topic parçası rakamla başlayamaz. Köprüleri böl. |
| Kaydedilen "SLAM haritası" referans haritayla aynı | `map_saver_cli` `nav.launch.py` açıkken çalıştırıldı (map_server'ın haritası kaydedildi) | Kaydetmeden önce sadece `slam.launch.py` açık olmalı |
| Tabela okuyucu ilk denemede 21/53 test kaldı | Numara küçük bulanık leke gibi kalıyordu; gri tonda kırmızı halka koyu görünüyordu | Numarayı kendi sınırına göre kırp, en-boy oranını koru; HSV V kanalı + Otsu eşiği |
| Havuz Gazebo'da görünmüyordu | Yol yüzeyi görseli havuzun üstünü örtüyordu | Yol çizimini havuzda kes |
| Robot %45 rampada takıldı | Rampalar OBJ mesh'ti (tekerlek–mesh teması güvenilmez) + 7 cm tekerlek küçüktü | Eğimler döndürülmüş kutu, tümsekler gömülü silindir; tekerlek 12 cm |
| 6 cm dik engel aşılamıyordu | Tekerlek pratikte yarıçapının ~yarısı kadar basamak aşar | Tekerlek yarıçapı ≥ 2 × engel yüksekliği |
| Üstteki LIDAR konileri görmüyordu | Gövde yükselince tarama düzlemi 32 cm'ye çıktı, koniler 31 cm | LIDAR ön tampona, 20 cm'ye |
| Eğimli kutu doğrulamasında hata | −x yönünde yükselen eğimde kutu açısı ±90° dışına çıkıyordu | Açı her zaman ±90° içinde; üretilen pozlardan yüzeyi geri hesaplayıp kontrol et |

Zararsız uyarılar: `libEGL warning: failed to create dri2 screen`,
`KDL does not support a root link with an inertia`.

GitHub'da hâlâ görünebilecek eski izler: kapalı PR #1–#4 sayfalarında eski branch adı ve
eski commit kopyaları, PR zaman çizelgesindeki "pushed" kayıtları. Repo geçmişinde ve
Contributors API'sinde iz yok (sadece `kadirakcn00`).

---

## 6. TEKNOFEST parkuru (simülasyon)

Ölçek: tüm uzunluklar **×0.4** (robot küçük kaldı, parkur küçültüldü). Eğimler aynı.
Üstten görünüş: `ugv-project/src/ugv_course/docs/course_top_view.png`

Yerleşim (metre, robot x ekseni boyunca ilerler):

| Sıra | y | Yön | İçerik |
|---|---|---|---|
| A | 0 | −x | Start (7.5, 0) → 1 havuz [5.2–6.6] → 2 çakıl [3.6–4.8] → 3 yan eğim [0.8–2.8] |
| — | — | — | Sol U dönüşü (yarıçap 1.5) |
| B | 3 | +x | 4 dik engel [1.0–1.4] → 5 koniler (x 2.2…5.0, y ±0.3) → 6 kayar engel (x 6.6) |
| — | — | — | Sağ U dönüşü |
| C | 6 | −x | 7 tümsekler [6.0–7.6] → 8 rampa [5.4→4.87] → 9 platform [4.87–3.27, h 0.24] → 10 rampa [3.27→2.73] → bitiş x 1.2 |
| Hedef | 6 | — | (−2.6, 6), platform ortasından 6.7 m |
| D | 9.5 | +x | 11 hızlanma: start (−0.3, 9.5), 12 m + 4 m durma |

| Aşama | Şartname | Simülasyon |
|---|---|---|
| Yol | 3 m, bariyer 80 cm, düzlük 20 m | 1.2 m, 32 cm, 8 m |
| 1 Su + yağmur | 40 cm | 16 cm, giriş/çıkış 20°, yağmur parçacıkları |
| 2 Çakıl | ≤5 cm | ≤2 cm, 90 taş |
| 3 Yan eğim | %20 | %20, yumuşak geçişli mesh |
| 4 Dik engel | 15 cm | 6 cm |
| 5 Koniler | 40×40 taban, 75 cm | 16×16, 31 cm |
| 6 Kayar engel | 1 m, 20 cm/s | 0.4 m, 8 cm/s, ±0.8 m (yolun dışına çıkar) |
| 7 Tümsek | 20×5 cm | 8×2 cm |
| 8/10 Dik eğim | %45, stop'ta 2 sn bekle | %45, stop çizgileri |
| 9 Atış | hedef ≥10 m | 6.7 m |
| 11 Hızlanma | 30 m + 10 m | 12 m + 4 m |

**Su fiziği** (`ugv_course/water.py`, `water_physics` node'u): batma oranı
s = derinlik / 0.30 m. En yüksek hız −%60·s, dönüş −%50·s, ivme limiti 1.0 → 0.3 m/s²,
küçük rastgele yön sapması. Konum `/ground_truth/odom`'dan, gelmezse `/odom` + başlangıç
konumu. Derinlik: `/course/water_depth`.

**Kayar engel** (`sliding_obstacle` node'u): üçgen dalga ±0.8 m, 8 cm/s →
`/course/slider_cmd` → prismatic eklem.

---

## 7. Şartname özeti (TEKNOFEST 2026 İKA)

- 2 koşu: **1) Uzaktan kontrollü (manuel)**, **2) Tam otonom** (otonom sürüş + otonom atış).
  Puanlar toplanır. Her koşu en fazla **15 dakika**.
- Puanlama: KTR %20, Teknik Sunum %10, Final %70.
- Araç: boy 1.2–2.0 m, en 0.75–1.2 m, yükseklik ≥0.4 m ve < 1.25 × en, ≥4 tekerlek,
  %45 eğim, 15 cm dik engel (20 cm için tork), 3 m koridorda dönüş, far, acil durdurma,
  haberleşme kesilince acil durma. En az **3 kamera** (ileri, geri, nişan) + lazer
  (10 m'de nokta çapı ≤1.5 cm).
- Aşama tabelası: kırmızı çember, Arial Black, dış çap 60 cm. Otonomda tabela tanınarak
  aşama anlaşılır.
- Atış: A3 hedef ≥10 m, nişan lazer kapalıyken kamerayla alınır, lazer en az 1 sn hedefte
  kalır, lazer açıkken araç/lazer hareket ederse −10. En fazla 3 deneme, en iyisi sayılır.
  İç daire 50, orta halka 25, dış halka 15 puan.
- Dik eğim: çıkışta ve inişte stop yerlerinde tam durup ≥2 sn bekle (yoksa aşama puanı yok).
- Puanlar: su 10, çakıl 5, yan eğim 5, dik engel 5, koniler 50 (her temas −5),
  kayar engel 50 (temassız), engebeli 5 (hatalı çıkış −5), dik eğim 15 (beklemeden 10),
  otonomda hedefi tespit 10, atış 50/25/15, bariyere her temas −5,
  süre sıralaması en fazla 100, hızlanma en fazla 25.
- Pas hakkı: koşu başına 1 aşama (o aşamanın puanı kadar ceza). Hızlanma ve **otonomda
  koniler** pas geçilemez.

---

## 8. Kaldığımız yer ve sıradaki işler

1. **Parkuru elle sürme testi (PR #9 sonrası):** Kadir README'de M6'yı "Completed" yaptı ama
   elle sürüşün sonucunu (havuz görünüyor mu, dik engel/rampa geçiliyor mu) yazılı olarak
   bildirmedi. Otonoma başlamadan önce sorulmalı.
2. **Otonom görev node'u (`mission_node`, sıradaki büyük iş).** Plan:

   | Aşama | Davranış |
   |---|---|
   | Genel | Ön kamerayla tabela okuyup aşamayı anlama, yolun ortasını takip |
   | 1–3, 7 | Aşamaya göre hız: suda yavaş, tümseklerde ortadan |
   | 4 | Engele dik açıyla, sabit hızla yaklaşıp tırmanma |
   | 5 | LIDAR ile konileri görüp slalom (temas −5) |
   | 6 | LIDAR ile kayar engelin konumunu/yönünü izleyip boşlukta geçme |
   | 8 / 10 | Stop çizgisinde tam durup 2 sn bekleme |
   | 9 | Tareti çevirip hedefi ortalama, ≥1 sn "lazer atışı", isabeti kaydetme |
   | Bitiş | Durma, süre ve puanı yazdırma |

   Not: LIDAR yatay, rampa yüzeyini engel olarak görür; rampa aşamasında engel algısı
   görev mantığında ele alınmalı.
3. **Hakem node'u (cevap bekliyor):** Süre, koni/bariyer temasları, stop beklemeleri, atış
   isabeti → şartnamedeki puan tablosuna göre puan. Kadir'e soruldu, henüz cevap yok.
4. Lazer atışının simülasyonu (lazer ışınının hedefe değdiği noktayı hesaplama).
5. İsteğe bağlı: `images/` klasöründeki Gazebo Classic ekran görüntülerini Fortress'tan
   yenileriyle değiştirmek (Kadir).
