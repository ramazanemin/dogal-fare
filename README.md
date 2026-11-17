# dogal-fare — Doğal Fare Hareketi için Küçük Parametrik Model

Kullanıcının seçtiği tek bir hedefe, insan motor-control literatürüyle (Fitts yasası,
minimum-jerk, alt-hareket yapısı) uyumlu yörünge üreterek giden ve hedefin **içinde**
tıklayan küçük bir yardımcı. Hedef kullanım: kendi arayüz işlemlerine (ör. kendi
Instagram hesabı) yardımcı olmak.

> ## Dürüst çerçeve (lütfen oku)
> - **Bu araç "tespit edilmeme" garantisi vermez ve bu iddia hiçbir yerde yapılmaz.**
> - Windows, `SendInput` ile verilen girdiyi OS seviyesinde `LLMHF_INJECTED` olarak
>   işaretler; düşük seviye kanca kuran her yazılım sentetik girdiyi görebilir
>   (`docs/gereksinimler_ve_yontem.md` D4).
> - Yayınlanmış araştırma (BeCAPTCHA-Mouse, D5), sinemonöromotor tabanlı dedektörlerin
>   sentetik fare yörüngelerini yüksek oranda ayırt edebildiğini göstermektedir.
> - Otomasyon, hedef platformun kullanım koşullarını ihlal edebilir (D6). Canlı
>   kullanım **senin kararın ve riskin**; bu proje canlı testi kapsam dışı bırakır.
> - Yerel test raporları yalnızca kinematik kalite ölçümüdür; tespit sistemleri
>   hakkında **kanıt içermez**.

## Kurulum
- Windows 10/11, Python 3.10+ (test: 3.12), tek bağımlılık: **numpy** (CPU-only).
- İsteğe bağlı temiz kurulum:
  ```
  cd /d D:\Projeler\dogal-fare
  python -m venv .venv
  .venv\Scripts\pip install numpy
  .venv\Scripts\python -m unittest discover -s tests   # kurulum sağlaması
  ```
  (Sistem Python'da numpy zaten varsa venv şart değil.)

## Hızlı akış (önerilen sıra)
| Adım | Komut / dosya | Ne yapar |
|---|---|---|
| 1 | `Baslat-Onizleme.cmd` veya `python scripts/onizleme.py` | **GERÇEK fare hareketi YOK**: sanal imleçle izle (Boşluk = deneme). |
| 2 | `Baslat-Kalibrasyon.cmd` veya `python scripts/kalibrasyon.py` | Kendi fare hareketini kaydet (40 deneme; ESC = bitir+kaydet). 2 farklı gün/oturum önerilir. |
| 3 | `python scripts/egitim.py --kaynak human` | Kişiye özel modeli eğit → `model/fare_model.json` (~1-3 KB). |
| 4 | `Baslat-Degerlendirme.cmd` veya `python scripts/degerlendirme.py` | Üç yöntemi aynı görülmemiş hedef setinde karşılaştır → `reports/`. |
| 5 | `python scripts/onizleme_smoke.py` | 2 denemelik görsel doğrulama (pencere kendini kapatır). |
| 6 (Faz 2, opsiyonel) | `python scripts/canliyardim.py` | Aşağıdaki güvenlik modeliyle, **önizleme varsayılan**. |

## Faz 2: canlı yardım (kullanıcı-seçimli tek hedef)
```
python scripts/canliyardim.py                              # yalnız önizleme (güvenli)
python scripts/canliyardim.py --hareket-gercek            # imleç gerçekten hareket eder
python scripts/canliyardim.py --hareket-gercek --gercek-tiklama   # + gerçek tıklama
```
Tuşlar: **F8** imleç hedefin merkezindeyken bas → hedef kaydı; sonra imleci hareketin
başlayacağı yere götür; **F9** plan üretir (önizlemede minyatür pencere, gerçek modda
uygular); **ESC** her an anında durdurma/çıkış. Gerçek mod başlarken yazılı onay ister
(`devam` yazman gerekir).

## Güvenlik modeli (zorunlu tasarım)
- **Önizleme varsayılan.** Gerçek imleç hareketi `--hareket-gercek`, gerçek tıklama
  `--gercek-tiklama` **ayrı** bayraklar; tıklama kodu izinsiz çağrılırsa `SafetyAbort`
  ile reddedilir (çifte savunma: `MouseController.allow_click` + `MovementRunner`).
- **ESC = anında duruş.** Yürütme her waypoint'te ESC'yi tarar; ayrıca dış durdurma
  kancası test edilebilir (`tests/test_control.py`).
- **Açık hedef yoksa işlem yok.** F8 ile hedef kaydı gelmeden F9 hiçbir şey yapmaz.
- **Tıklama güvencesi:** son nokta hedefin 0.8·yarıçapı dışındaysa tıklama **asla**
  gönderilmez (plan üretim + doğrulama + yürütme katmanlarında üçlü kontrol).
- **Ekran sınırı:** plan ekran dışına taşarsa yürütme reddi/abort.
- **CAPTCHA/güvenlik bulgusu:** hedef alındığında ve hareket sırasında (200 ms'de bir)
  ön plandaki pencerenin **başlığı** anahtar kelimelerle taranır; bulgu → dur ve
  mesaj: kontrolü sana bırak. Bu bir **buluşsaldır**: ekran içeriğine bakmaz
  (gizlilik) ve bulguların garanti kapsamı yoktur. Şüphede kalırsan ESC ile dur.
- Platform uyarısı: otomasyon hizmet koşullarını ihlal edebilir (D6).

## Veri politikası (kısa; tam metin `docs/gereksinimler_ve_yontem.md` §1)
- Veri **yalnız** kalibrasyon penceresinden: zaman damgası, pencereye göre koordinat,
  hedef yarıçapı, tıklama anı, isabet. Klavye/ekran görüntüsü/çerez/oturum belirteci
  **toplanmaz** (şemada alan yok; `tests/test_storage.py` yapısal denetim).
- Eğitim/test ayrımı **oturum bazlı**; sentetik kayıtlar `source:"synthetic"` +
  `generator` etiketiyle açıkça ayrılır. İnsan kayıtları `.gitignore` ile dışlanır.

## Mimari (tek cümle-de-kural)
`app/models` hareketi **üretir** (saf, Win32 yok); `app/control` **yürütür**
(ctypes `SendInput`, ESC, sınır, tıklama güvencesi); `app/ui` insan ekranları;
`app/metrics` ölçüm. Küçük model: ~30 skaler JSON (`model/fare_model.json`),
GPU/derin öğrenme yok, üretim gecikmesi ~1-3 ms.

## Üç yöntem (docs §3)
1. **baseline** — minimum-jerk + Fitts (veri gerekmez, referans).
2. **rescaler** — kayıtlı gerçek yörünge şekillerini yeni D/W'ye taşır (≥1 oturum).
3. **learned** — kişiye özel parametrik model: Fitts a/b, profil asimetrisi, eğrilik
   tabanları, duraklama olasılığı/süresi, düzeltme alt-hareketi, endpoint dağılımı
   (≥2 oturum önerilir). Otomatik seçim yeterli veriye göre yapılır (`manager.py`).

## Testler ve raporlar
- `Baslat-Testler.cmd` → 45 birim testi (gerçek girdi göndermez; dry-run/sahte
  denetleyici kullanır).
- `Baslat-Degerlendirme.cmd` → `reports/test_raporu_<zaman>.md|.json`
  (isabet, süre, yol/kiriş, hız/ivme/jerk dağılımları, duraklama, üretim gecikmesi,
  CPU/RAM; **ibare her çıktıda**).
- `docs/test_raporu.md` — örnek rapor yorumlaması.
- Yerel sonuçların anlamı **sınırlıdır**: literatürle (D1-D3) tutarlılıktır;
  tespit/tespit-edilmeme hakkında sonuç çıkarılamaz (D4, D5).

## Dosya haritası
```
app/config.py        ayarlar (güvenlik varsayılanları KAPALI)
app/geometry.py      min-jerk, taban fonksiyonlar, hız serisi (saf)
app/features.py     kayıttan öznitelikler (alt-hareket, duraklama, eğrilik)
app/storage.py      JSONL + oturum bazlı train/test ayrımı
app/models/         baseline | rescaler | learned | manager (ÜRETİM)
app/control/         mouse.py (SendInput) | validation.py | runner.py (KONTROL)
app/ui/             calibration.py | preview.py
app/metrics/        kinematics.py | system.py (ctypes CPU/RAM)
app/testgen.py      görülmemiş hedef seti üretici (seed'li)
scripts/            kalibrasyon | sentetik_uret | egitim | onizleme |
                    degerlendirme | onizleme_smoke | canliyardim
tests/              45 birim test (unittest, dış bağımlılık yok)
docs/               gereksinimler_ve_yontem.md | test_raporu.md
model/fare_model.json   küçük model (~1-3 KB JSON)
reports/            otomatik test raporları
```

## Sorun giderme
- "rescaler/learned kullanılamıyor" → önce kalibrasyon, sonra `egitim.py`.
- Konsolda Türkçe bozuk görünürse `python -X utf8 ...` ile çalıştır (Başlat
  dosyaları bunu otomatik yapar).
- Çok monitörde hedef sanal-ekran koordinatlarıyla hesaplanır; negatif koordinatlar
  desteklenir (`MOUSEEVENTF_ABSOLUTE` normalizasyonu).
- Hareket yavaş kalırsa `app/config.py` → `fitts_defaults` ve `waypoint_dt_ms`
  ayarlarına bak (yine de gerçek istatistik için kalibrasyon önerilir).


## Depoyu klonlayarak kurulum

```powershell
git clone https://github.com/ramazanemin/dogal-fare.git
cd dogal-fare
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -X utf8 scripts/onizleme.py
```

CMD baslaticilarini kullanirken once `.venv\Scripts\activate.bat` ile ortami
etkinlestirin. Proje herhangi bir klasorden calisabilir; D: yolu yerel proje
konumunun ornegidir.

### Paylasilan model ve veriler

Depodaki `model/fare_model.json` **sentetik ornek veriden egitilmistir**;
kisisel insan hareketlerinden egitilmis bir model degildir. `data/recordings/sent-*.jsonl`
sentetik orneklerdir. Kisisel kalibrasyon kayitlari, sanal ortam ve gizli ayar
 dosyalari Git disinda tutulur. Kendi verinizle egitimden sonra model dosyasini
herkese acik bir commit'e eklemeden once icerigini kontrol edin.

