# Gereksinim ve Yöntem Karşılaştırması — "dogal-fare"

Doğal fare hareket motoru: kullanıcının seçtiği hedeflere, insan kinematiğiyle uyumlu hareketle
ulaşan ve tıklayan küçük model. Hedef: kullanıcının kendi arayüz işlemlerine (ör. kendi Instagram
hesabı) yardımcı olmak. **Tespit edilmeme garantisi yoktur ve iddia edilmemektedir** (bkz. §2, D4).

---

## 1. Gereksinimler (özet)

- **Amaç:** Hareket kalitesi + tıklama doğruluğu ile ölçülen yardımcı tıklama aracı.
- **Veri:** Yalnızca kullanıcı tarafından başlatılan yerel kalibrasyon ekranında toplanır:
  zaman damgası, pencereye göre göreli koordinatlar, hedef boyutu, tıklama süresi.
  Klavye girdisi, ekran görüntüsü, çerez, oturum belirteci, ağ trafiği **toplanmaz**.
  Eğitim/test ayrımı **oturum bazlı**; sentetik veri `source:"synthetic"` ile açıkça etiketlenir.
- **Hareket:** Süre mesafe (D) ve hedef genişliğine (W) göre ayarlanır (Fitts);
  yumuşak hızlanma/yavaşlanma; eğrilik, duraklama ve düzeltme alt-hareketleri öğrenilen örneklerden modellenir;
  tıklama hedefin içinde garanti edilir (sert kontrol). Üretim, fare kontrolünden **ayrı modüldedir**.
- **Çalıştırma:** Önizleme varsayılan. Gerçek imleç hareketi ve gerçek tıklama **ayrı bayraklarla**.
  ESC = anında durdurma; ekran sınırı ve hedef-dışı tıklamayı reddetme. Açık hedef yoksa işlem yok.
  CAPTCHA/güvenlik uyarısı bulgusunda dur ve kullanıcıya devret (sadece başlık-bulgusu; garanti değil).
- **Test:** Yerel test ekranında algoritmik taban çizgiyle karşılaştırma; isabet, süre, yol uzunluğu,
  hız/ivme dağılımı, CPU/RAM raporu; görülmemiş hedef konum/boyutlarıyla değerlendirme.
  **Yerel sonuçlar Instagram'da tespit edilmeme kanıtı DEĞİLDİR.** Canlı hesap testi ayrı aşamadır.

## 2. Doğrulanmış / Varsayım / Bilinmeyen

### Doğrulanmış (ataflar ve birincil kaynaklar)
- **D1 Fitts yasası:** MT = a + b·log₂(D/W + 1) (Fitts 1954; MacKenzie 1992 Shannon formu).
  İnsan tıklama süresi D ve W üzerinden logaritmik zorlukla doğrusaldır; kişisel a,b eğitilebilir.
- **D2 Minimum-jerk modeli:** Noktadan noktaya hızlı hareketler çan biçimli hız profili üretir;
  s(t)=10s³−15s⁴+6s⁵ yörüngesi bu profille deneysel olarak uyumludur (Flash & Hogan 1985).
- **D3 Alt-hareket yapısı:** Gerçek hedefe yönelim birincil hareket + düzeltme alt-hareketlerine
  ayrışır; hız arttıkça endpoint dağılımı genişler (Meyer vd. 1988; Woodworth 1899).
  Yön/duraklamalar, iki-üçlü güç yasası ve Sigma-Lognormal modeli hızlı hareketleri dar
  parametre kümeleriyle açıklar (Plamondon 1995; Viviani & Flash 1995).
- **D4 Windows enjeksiyon bayrağı (kritik):** `SendInput` ile verilen girdi OS seviyesinde
  "injected" işaretlenir; düşük seviye kanca kuran her uygulama `LLMHF_INJECTED` bayrağını
  görebilir (Microsoft Win32 dokümantasyonu: MSLLHOOKSTRUCT, LLMHF_INJECTED 0x01).
  → **"Tespit edilemez" iddiası teknik olarak yanlıştır.** Bu araç bu iddiayı hiçbir yerde içermez.
- **D5 Sentetik yörüngeler ayırt edilebiliyor:** BeCAPTCHA-Mouse (Acien vd., 2020/2022,
  arXiv:2005.00890; doi:10.1016/j.patcog.2022.108643) sinemonöromotor tabanlı dedektörlerin
  fonksiyon-tabanlı ve GAN ile üretilmiş sentetik fare yörüngelerini tek yörüngede ~%93'e varan
  doğrulukla ayırt edebildiğini raporlar. → Doğal görünen üretim, tespit karşıtı garanti değildir.
- **D6 Platform politikası:** Instagram/Meta kullanım koşulları yetkisiz otomasyonu yasaklar
  (birincil sayfa bu oturumda doğrulanamadı; Meta AB 587 politika raporu: otomasyon, scraping
  ve yetkisiz veri toplama yasak kapsamındadır). Canlı kullanım **kullanıcının sorumluluğu ve
  ayrı kararıdır**; bu proje canlı testi kapsam dışı bırakır.

### Varsayım (makul, ölçülebilir, kanıtlanmamış)
- Kullanıcının kalibrasyon ekranındaki kinematiği, aynı kullanıcının gerçek arayüz kullanımına yaklaşık benzer.
- Birkaç oturumluk kalibrasyon (~2 oturum, ≥40 deneme) kişiye özel a,b ve şekil parametreleri için yeterli olur.
- Eklenen eğrilik/duraklama/düzeltme bileşenleri çıktıyı literatürdeki insan kinematik istatistiklerine yaklaştırır.

### Bilinmeyen (açıkça)
- Instagram'ın tespit mekanizmaları, öznitelikleri ve eşikleri (özel/kapalı).
- Tarayıcı/web sayfasının OS-seviyesi enjeksiyon bayrağını görüp görmediği (yayınlanmış teknik detay yok).
- Yerel metriklerin canlı platformda nasıl karşılanacağı — **yalnızca kullanıcı fazında ölçülebilir**.

## 3. Yöntem karşılaştırması

Üç jeneratör aynı arayüzün arkasında: `generate(start, target, radius, rng) -> TrajectoryPlan`.

| Boyut | (a) Algoritmik taban çizgi | (b) Örnek yeniden ölçekleme | (c) Küçük öğrenilmiş model |
|---|---|---|---|
| Fiziksel temel | Min-jerk + Fitts (D1,D2) | Gerçek/hedef örnek yörünge şekli | D1-D3'ten parametrik kurgu |
| Veri ihtiyacı | 0 | ≥1 oturum, ≥15 deneme | ≥2 oturum, ≥40 deneme |
| Süre modeli | Varsayılan a,b (D1) | Fitts katsayıları (aynı) | Kişiye özel a,b + artık gürültü |
| Eğrilik | Sabit hafif yay | Örneğinki birebir taşınır | Taban fonksiyonu katsayı dağılımı |
| Duraklama | Yok | Örneğinki taşınır | Olasılık + lognormal süre (öğrenilir) |
| Düzeltme alt-hareketi | Yok | Örneğinkiler taşınır | Olasılık + büyüklük (öğrenilir) |
| Endpoint dağılımı | Tek nokta (merkez) | Örneğinki (kırpılır) | sigma(W) ile prova + kırpma |
| Genelleme (görülmemiş D,W) | Her yere (ama şekil yavan) | Yakın ID'lerde iyi | ID ayrıntılarına kadar |
| Boyut/karmaşıklık | ~100 satır | Kayıt arşivi boyutu | ~30 skaler → ~2-3 KB JSON |
| Aşırı uyum riski | — | Az (ham veri) | Orta (az parametre, oturum split) |
| Çalıştırma maliyeti | µs | µs + en yakın komşu | µs |

**Karar (en küçük uygulanabilir çözüm):** Üç yöntem birden teslim edilir ve **aynı yerel test
ekranında karşılaştırılır**. Otomatik seçim: veri yeterliyse (c), eksikse (b), o da yoksa (a).
GPU/derin öğrenme **kullanılmaz**: fayda ölçülebilir olsaydı bile bu problem için parametrik
model (≤50 parametre) literatürün açıkladığın neredeyse tamamını zaten kapsar (D1-D3);
BeCAPTCHA sonuçları (D5) büyük modelle de "tespit garantisi" olmadığını gösteriyor.

## 4. Mimari

```
app/
  config.py     ayarlar (güvenlik varsayılanları KAPALI)
  geometry.py   saf hesap (min-jerk, taban fonksiyonlar, hız serisi)
  features.py   kayıttan öznitelik çıkarma (segmentasyon, eğrilik, duraklama)
  storage.py    JSONL kayıt/okuma + oturum bazlı train/test ayrımı
  models/       baseline.py | rescaler.py | learned.py | manager.py   ← ÜRETİM (saf)
  control/      mouse.py (ctypes SendInput) | validation.py | runner.py ← KONTROL (donanım)
  ui/           calibration.py (kalibrasyon ekranı) | preview.py (önizleme + test ekranı)
  metrics/      kinematics.py (isabet/süre/yol/hız/ivme) | system.py (CPU/RAM, ctypes)
scripts/        kalibrasyon | sentetik_uret | egitim | onizleme | degerlendirme | canliyardim
```

Kesin kural: `models/` hiçbir Win32 çağrısı içermez; `control/` hareket üretmez.
`canliyardim.py` farkında olmaksızın başlatılamaz ve oturum başına metinli onay ister.

## 5. Ölçüm planı (yerel test, önizleme; gerçek tıklama istenmez)
- **Görülmemiş hedefler:** seed'li üretici; eğitim kayıtlarında bulunmayan konum/boyut karması
  (D: 150–900 px; W: 16–128 px; 40+ deneme).
- **Metrikler:** isabet oranı (son nokta ve tıklama noktası hedef içinde), hareket süresi,
  yol uzunluğu/kiriş oranı, tepe/ortalama hız, ivme & jerk dağılım istatistikleri, hız tepe sayısı
  (alt-hareket sayısı proxy'si), duraklama toplamı, üretim gecikmesi p50/p95, süreç CPU% ve RAM.
- **Karşılaştırma:** (a) vs (b) vs (c) aynı hedef setinde, aynı RNG tohum düzeninde.
- **Sorumluluk ibaresi:** raporun her çıktısında "yerel kinematik ölçümüdür; üçüncü taraf
  tespit sistemleri hakkında kanıt içermez" ibaresi bulunur (D4, D5).

## 6. Fazlar ve sorumluluk sınırları
- **Faz 1 (bu teslim):** kalibrasyon aracı, üç jeneratör, önizleme + yerel test ekranı,
  otomatik rapor, birim testler. **Gerçek tıklama bayrağı açılabilir ama bu fazda zorunlu değil.**
- **Faz 2 (kullanıcı kararı):** `canliyardim.py` ile kullanıcı-seçimli tek tıklama yardımı
  (F8 hedef al → F9 uygula → ESC durdur; önizleme varsayılan).
- **Faz 3 (kullanıcı kararı, bu işin kapsamı dışında):** canlı platform denemesi.
  Bu doküman ve araçlar o karar için **kanıt sunmaz**; riskler D4-D6'da listelenmiştir.

## 7. Kaynaklar
- MSLLHOOKSTRUCT / LLMHF_INJECTED — learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-msllhookstruct (D4)
- SendInput — learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput (D4)
- Fitts, P. M. (1954). JEP 47(6):389-396, doi:10.1037/h0045386 (D1)
- Flash, T. & Hogan, N. (1985). J. Neuroscience 5(11):3273-3280 (D2)
- Meyer, D. E. et al. (1988). Psych. Review 95(3):340-370 — optimized submovements (D3)
- Plamondon, R. (1995). Biological Cybernetics 72:295-307 — kinematik teori / lognormal (D3)
- Acien, A. et al. (2020). BeCAPTCHA-Mouse, arXiv:2005.00890; doi:10.1016/j.patcog.2022.108643 (D5)
- Crawlex (2026). "Why a real mouse path is hard to fake" — özellik sentezi ve tespit pratiği özeti (D5)
- Meta Platforms AB 587 policy report (media.ca.gov) + Instagram Terms of Use (D6)
