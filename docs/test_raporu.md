# Test Raporu — Yorumlama Rehberi ve Örnek

Son otomatik rapor: `reports/test_raporu_20261115-002123.md` (+ `.json`).
Yeniden üretim: `python scripts/degerlendirme.py --deneme 40`

> **İBARE:** Tüm sonuçlar YEREL kinematik ölçümdür; üçüncü taraf tespit
> sistemleri (ör. Instagram) hakkında KANIT içermez (`docs/gereksinimler_ve_yontem.md` D4, D5).

## Bu raporun verisi neydi?
Teslim anındaki örnek rapor, **sentetik** kayıtlarla (3 oturum x 30 deneme, etiket:
`source:"synthetic"`) pipeline'ı uçtan uca doğrulamak için üretilmiştir — sentetik
veri, insan verisi DEĞİLDİR. Kendi kalibrasyonunu yaptığında
(`scripts/kalibrasyon.py` → `scripts/egitim.py --kaynak human` →
`scripts/degerlendirme.py`) rapor **senin gerçek kinematik verinle** yeniden oluşur;
o zaman karşılaştırma anlamlı hâle gelir.

## Örnek çıktıdan satır bazlı okuma (sentetik veri, 40 hedef)
| Metrik | baseline | rescaler | learned | Yorum |
|---|---|---|---|---|
| isabet (tıklama hedefte) | %100 | %100 | %100 | **güvence**: hedef-dışı tıklama 0 |
| hareket süresi | 540 ms | 732 ms | 760 ms | süreler Fitts'e göre zorlukla artar |
| yol/kiriş | 1.04 | 1.03 | 1.05 | hafif eğrilik; düz çizgi değil |
| tepe hız | 1324 | 1151 | 1394 px/s | 500-2000 px/s insan bandında |
| ivme RMS | 0.009 | 0.009 | 0.015 px/ms² | düzgün ivmelenme |
| toplam duraklama | 0 | 0 | 8.5 ms ort. | yalnız learned duraklama üretir |
| üretim gecikmesi p95 | 2.6 | 3.0 | 3.0 ms | gerçek zamanlı yürütür |

Notlar:
- `baseline` hiç duraklama/düzeltme üretmez (tasarım gereği); bunlar öncelikle
  `rescaler` (örnekten taşır) ve `learned` (öğrenilmiş olasılıklar) kaynaklıdır.
- Hız tepe sayısı, alt-hareket izi proxy'sidir; mikro-tremor'dan etkilenir.
- CPU "tepe %" kısa (5 denemelik) pencere ölçümü olduğundan burst karakter taşır;
  RAM ~44 MB, GPU 0 (tüm model CPU'da ~1-3 KB JSON).

## Yorumlama kuralları
1. **İsabet %100 şart** — güvenlik güvencesi; düşerse hata (kabul edilemez).
2. Süre dağılımı Fitts çizgisine benzer olmalı (D arttıkça / W küçüldükçe süre artar).
3. Yol/kiriş 1.0–1.2 bandı üstünde uçuk sapma = doğal olmayan yörünge sinyali.
4. Bu dört nokta **yerel kalite** ölçütüdür; ötesi (tespit, platform davranışı)
   bu raporun kapsamında DEĞİLDİR.

## Fazlar hatırlatması
- Faz 1 (teslim): kalibrasyon + üç jeneratör + önizleme + rapor + test.
- Faz 2: `canliyardim.py` — önizleme varsayılan, gerçek bayraklar ayrı.
- Faz 3 (canlı platform): **senin kararın**; bu dokümanlar o karar için kanıt sunmaz.
