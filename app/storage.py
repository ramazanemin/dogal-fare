"""Kayıt deposu: JSONL yaz/oku + oturum bazlı train/test ayrımı.

VERİ İLKELERİ (yöntem dokümanı §1):
- Yalnız kalibrasyon aracının kendi penceresinden fare hareket/tıklama kaydedilir.
- Zaman damgası (pencereye göre, ms), göreli koordinat, hedef boyutu, tıklama süresi.
- Klavye verisi, ekran görüntüsü, çerez, oturum belirteci YOK (şemada alan bile yok).
- Kaynak etiketi ZORUNLU: "human" (kalibrasyon) veya "synthetic" (sentetik üretici).
- Eğitim/test ayrımı OTURUM bazında yapılır (aynı oturum iki kısma düşmez).
"""
from __future__ import annotations

import json
import os
import random
import time

REQUIRED_TRIAL_FIELDS = (
    "session_id", "source", "target", "radius",
    "presented_ms", "click_ms", "samples",
)
VALID_SOURCES = ("human", "synthetic")


def new_session_id(prefix: str = "oturum") -> str:
    return f"{prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{random.randint(100, 999)}"


def validate_trial(trial: dict) -> None:
    """Şema denetimi: eksik alan veya geçersiz kaynak => ValueError."""
    for field in REQUIRED_TRIAL_FIELDS:
        if field not in trial:
            raise ValueError(f"kayıt eksik alan: {field}")
    if trial["source"] not in VALID_SOURCES:
        raise ValueError(
            f"kayıt kaynak etiketi 'human' veya 'synthetic' olmalı: {trial.get('source')!r}")
    if float(trial["radius"]) <= 0:
        raise ValueError("radius > 0 olmalı")
    if len(trial["samples"]) < 2:
        raise ValueError("samples en az 2 nokta olmalı")
    if trial["source"] == "synthetic" and trial.get("generator", "") == "":
        raise ValueError("sentetik kayıtta 'generator' alanı zorunludur (açık etiket)")


def save_session(out_dir: str, trials: list[dict], meta: dict | None = None) -> str:
    """Deneme listesini <out_dir>/<session_id>.jsonl dosyasına yaz; dosya adı döner."""
    os.makedirs(out_dir, exist_ok=True)
    for tr in trials:
        validate_trial(tr)
    if not trials:
        raise ValueError("kayıt.listesi boş")
    sid = trials[0]["session_id"]
    if any(tr["session_id"] != sid for tr in trials):
        raise ValueError("tek dosyaya yalnız tek oturum yazılır")
    path = os.path.join(out_dir, f"{sid}.jsonl")
    with open(path, "a", encoding="utf-8") as fh:
        if meta is not None:
            fh.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
        for tr in trials:
            fh.write(json.dumps(tr, ensure_ascii=False) + "\n")
    return path


def load_recordings(data_dir: str, sources: tuple[str, ...] = VALID_SOURCES,
                    exclude_sessions: set[str] | None = None) -> list[dict]:
    """Dizindeki tüm *.jsonl'yi oku (yalnız istenen kaynaklar). Bozuk satır => atla."""
    trials: list[dict] = []
    if not os.path.isdir(data_dir):
        return trials
    for fname in sorted(os.listdir(data_dir)):
        if not fname.endswith(".jsonl"):
            continue
        with open(os.path.join(data_dir, fname), "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "_meta" in rec:
                    continue
                if rec.get("source") not in sources:
                    continue
                if exclude_sessions and rec.get("session_id") in exclude_sessions:
                    continue
                try:
                    validate_trial(rec)
                except ValueError:
                    continue
                trials.append(rec)
    return trials


def sessions_of(trials: list[dict]) -> list[str]:
    return sorted({t["session_id"] for t in trials})


def split_train_test(trials: list[dict], test_ratio: float = 0.3,
                     rng: random.Random | None = None) -> tuple[list[dict], list[dict]]:
    """OTURUM bazlı ayrım: (train, test). Aynı oturum iki tarafta YOK (kullanıcı gereksinimi)."""
    rng = rng or random.Random(17)
    sids = sessions_of(trials)
    rng.shuffle(sids)
    n_test = max(1, int(round(len(sids) * test_ratio))) if len(sids) >= 2 else 0
    test_set = set(sids[:n_test])
    train = [t for t in trials if t["session_id"] not in test_set]
    test = [t for t in trials if t["session_id"] in test_set]
    if not train and trials:  # tek oturum: tümü train (uyarı debug amaçlı)
        train = list(trials)
    return train, test
