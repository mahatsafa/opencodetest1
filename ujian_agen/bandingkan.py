"""Bandingkan dua berkas hasil ujian (LAMA vs BARU)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


class BandingkanError(Exception):
    """Berkas tidak ada, JSON rusak, atau format hasil tidak dikenal."""


def muat(path) -> dict:
    """Muat JSON hasil ujian. Error jelas bila berkas tidak ada atau rusak."""
    berkas = Path(path)
    if not berkas.is_file():
        raise BandingkanError(f"berkas tidak ditemukan: {berkas}")
    try:
        teks = berkas.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise BandingkanError(f"gagal membaca {berkas}: {exc}") from exc
    try:
        data = json.loads(teks)
    except json.JSONDecodeError as exc:
        raise BandingkanError(f"JSON rusak di {berkas}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("hasil"), list):
        raise BandingkanError(f"format hasil tidak dikenal: {berkas}")
    return data


def _status_satu(item: dict) -> str:
    st = item.get("status")
    if st in ("lulus", "gagal", "infra"):
        return st
    error = item.get("error")
    teks = item.get("teks", "").strip()
    tool = item.get("tool")
    if error and not teks and not tool:
        return "infra"
    return "lulus" if item.get("lulus") else "gagal"


def status_per_pasangan(data: dict) -> dict:
    """Status gabungan per (model, soal).

    Beberapa ulangan: "lulus" jika proporsi lulus >= 0.5 di antara run non-infra.
    Semua infra -> "infra". Field "status" tidak ada -> pakai bool "lulus".
    """
    kelompok: dict[tuple[str, str], list[str]] = defaultdict(list)
    for item in data.get("hasil", []):
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        soal = item.get("soal")
        if model is None or soal is None:
            continue
        kelompok[(str(model), str(soal))].append(_status_satu(item))

    hasil: dict[tuple[str, str], str] = {}
    for kunci, daftar in kelompok.items():
        non_infra = [st for st in daftar if st != "infra"]
        if not non_infra:
            hasil[kunci] = "infra"
            continue
        lulus = sum(1 for st in non_infra if st == "lulus")
        hasil[kunci] = "lulus" if (lulus / len(non_infra)) >= 0.5 else "gagal"
    return hasil


def _tanda(lama: str, baru: str) -> str:
    if lama in ("gagal", "infra") and baru == "lulus":
        return "NAIK"
    if lama == "lulus" and baru == "gagal":
        return "TURUN"
    return "TETAP"


def bandingkan(lama: dict, baru: dict) -> dict:
    """Bandingkan dua data hasil.

    Kembalian:
      baris: list dict (model, soal, status_lama, status_baru, tanda)
      ringkasan: list dict (model, lulus_lama, lulus_baru) — dihitung dari
        pasangan yang terbandingkan saja
      tidak_terbandingkan: list dict (model, soal, sisi) dengan sisi "lama"|"baru"
    """
    peta_lama = status_per_pasangan(lama)
    peta_baru = status_per_pasangan(baru)
    kunci_bersama = sorted(set(peta_lama) & set(peta_baru))

    baris = []
    for kunci in kunci_bersama:
        model, soal = kunci
        status_lama = peta_lama[kunci]
        status_baru = peta_baru[kunci]
        baris.append(
            {
                "model": model,
                "soal": soal,
                "status_lama": status_lama,
                "status_baru": status_baru,
                "tanda": _tanda(status_lama, status_baru),
            }
        )

    per_model: dict[str, dict[str, int]] = {}
    for item in baris:
        rekap = per_model.setdefault(
            item["model"], {"lulus_lama": 0, "lulus_baru": 0}
        )
        if item["status_lama"] == "lulus":
            rekap["lulus_lama"] += 1
        if item["status_baru"] == "lulus":
            rekap["lulus_baru"] += 1

    ringkasan = [
        {"model": model, "lulus_lama": rekap["lulus_lama"], "lulus_baru": rekap["lulus_baru"]}
        for model, rekap in sorted(per_model.items())
    ]

    tidak = []
    for model, soal in sorted(set(peta_lama) - set(peta_baru)):
        tidak.append({"model": model, "soal": soal, "sisi": "lama"})
    for model, soal in sorted(set(peta_baru) - set(peta_lama)):
        tidak.append({"model": model, "soal": soal, "sisi": "baru"})

    return {
        "baris": baris,
        "ringkasan": ringkasan,
        "tidak_terbandingkan": tidak,
    }


def ada_turun(hasil: dict) -> bool:
    return any(item["tanda"] == "TURUN" for item in hasil["baris"])


def format_teks(hasil: dict) -> str:
    """Tabel teks: perbandingan, ringkasan per model, tidak terbandingkan."""
    baris = hasil["baris"]
    lebar_model = max([8] + [len(item["model"]) for item in baris])
    lebar_soal = max([8] + [len(item["soal"]) for item in baris])
    baris_tabel = [
        f"{'Model':<{lebar_model}} {'Soal':<{lebar_soal}} {'Lama':<8} {'Baru':<8} Tanda",
        f"{'-' * lebar_model} {'-' * lebar_soal} {'-' * 8} {'-' * 8} -----",
    ]
    for item in baris:
        baris_tabel.append(
            f"{item['model']:<{lebar_model}} {item['soal']:<{lebar_soal}} "
            f"{item['status_lama']:<8} {item['status_baru']:<8} {item['tanda']}"
        )
    if not baris:
        baris_tabel.append("(tidak ada pasangan yang sama)")

    lebar_ringkas = max([16] + [len(item["model"]) for item in hasil["ringkasan"]])
    ringkas = [
        "",
        "Ringkasan per model",
        f"{'Model':<{lebar_ringkas}} {'Lulus lama':>10} {'Lulus baru':>10}",
        f"{'-' * lebar_ringkas} {'-' * 10} {'-' * 10}",
    ]
    for item in hasil["ringkasan"]:
        ringkas.append(
            f"{item['model']:<{lebar_ringkas}} {item['lulus_lama']:>10} {item['lulus_baru']:>10}"
        )
    if not hasil["ringkasan"]:
        ringkas.append("(kosong)")

    # Model tanpa satu pun pasangan terbandingkan dan semua soalnya di satu sisi -> satu baris ringkas.
    model_terbanding = {item["model"] for item in baris}
    per_model: dict[str, list[dict]] = defaultdict(list)
    for item in hasil.get("tidak_terbandingkan", []):
        per_model[item["model"]].append(item)
    tidak = ["", "Tidak terbandingkan"]
    for model, items in per_model.items():
        sisi = {item["sisi"] for item in items}
        if model not in model_terbanding and len(sisi) == 1:
            tidak.append(f"- {model}: {len(items)} soal hanya di {items[0]['sisi']}")
        else:
            for item in items:
                tidak.append(f"- {model} / {item['soal']} (hanya di {item['sisi']})")
    if not per_model:
        tidak.append("(tidak ada)")

    return "\n".join(baris_tabel + ringkas + tidak)
