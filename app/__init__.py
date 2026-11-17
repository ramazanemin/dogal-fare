"""dogal-fare: doğal fare hareketi üreten küçük parametrik sistem.

Katman kuralı:
  models/   ÜRETİM  (saf, Win32 YASAK)
  control/  İCRA    (SendInput, ESC, ekran sınırı, tıklama güvencesi)
  ui/       İNSAN   (kalibrasyon ekranı, önizleme)
  metrics/  ÖLÇÜM   (kinematik + süreç kaynakları)

Bu paket; kullanıcı kendi arayüz işlemlerine yardımcı olması için fare hareketini
insan kinematik modellerine (Fitts yasası, minimum-jerk, submovement) göre üretir.
TESPİT EDİLMEME GARANTİSİ YOKTUR — bkz. docs/gereksinimler_ve_yontem.md §2 (D4, D5).
"""
__version__ = "0.1.0"
