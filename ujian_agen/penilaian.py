"""Penilaian hasil agen terhadap aturan soal."""

from __future__ import annotations

import re

from .bahasa import heuristik_id

TOOL_BACA = {"read", "grep", "glob"}
KUNCI_PATH = ("path", "filePath", "pattern", "include")


def pemeriksaan(nama: str, lulus: bool, alasan: str) -> dict:
    return {"nama": nama, "lulus": bool(lulus), "alasan": alasan}


def paths_tool(hasil) -> list[tuple[str, str]]:
    """Ambil pasangan (nama tool, path) dari input tool."""
    hasil_path: list[tuple[str, str]] = []
    for tool in getattr(hasil, "tool", []) or []:
        nama = str(tool.get("nama", "")).lower()
        masukan = tool.get("input")
        if not isinstance(masukan, dict):
            continue
        for kunci in KUNCI_PATH:
            if kunci not in masukan:
                continue
            nilai = masukan[kunci]
            if isinstance(nilai, str):
                hasil_path.append((nama, nilai))
            elif isinstance(nilai, list):
                for item in nilai:
                    if isinstance(item, str):
                        hasil_path.append((nama, item))
    return hasil_path


def _cocok(teks: str, pola: str) -> bool:
    return re.search(pola, teks) is not None


def blok_kode(teks: str) -> list[str]:
    """Isi semua blok kode berpagar tiga backtick yang DITUTUP; blok tanpa penutup diabaikan."""
    hasil: list[str] = []
    idx = 0
    while True:
        buka = re.search(r"(^|\n)```[^\n]*\n", teks[idx:])
        if not buka:
            break
        mulai = idx + buka.end()
        tutup = re.search(r"(^|\n)```", teks[mulai:])
        if not tutup:
            break
        akhir = mulai + tutup.start()
        hasil.append(teks[mulai:akhir])
        idx = mulai + tutup.end()
    return hasil


def _periksa_kode(soal: dict, teks: str) -> list[dict]:
    """harus_ada_kode / tidak_boleh_kode hanya pada gabungan isi blok kode."""
    blok = blok_kode(teks)
    isi = "\n".join(blok) if blok else None
    daftar: list[dict] = []
    for indeks, pola in enumerate(soal.get("harus_ada_kode", []) or [], start=1):
        cocok = isi is not None and _cocok(isi, pola)
        daftar.append(pemeriksaan(
            f"harus_ada_kode[{indeks}]", cocok,
            f"regex {pola!r} {'cocok' if cocok else 'tidak cocok'} di blok kode"))
    for indeks, pola in enumerate(soal.get("tidak_boleh_kode", []) or [], start=1):
        cocok = isi is not None and _cocok(isi, pola)
        daftar.append(pemeriksaan(
            f"tidak_boleh_kode[{indeks}]", not cocok,
            f"regex terlarang {pola!r} {'ditemukan' if cocok else 'tidak ditemukan'} di blok kode"))
    return daftar


def nilai(soal: dict, hasil) -> list[dict]:
    """Nilai satu hasil; kembalikan daftar pemeriksaan {nama, lulus, alasan}."""
    daftar: list[dict] = []

    if getattr(hasil, "error", None):
        daftar.append(pemeriksaan("tanpa_error", False, f"error: {hasil.error}"))
    elif getattr(hasil, "kode_keluar", 0) not in (0, None):
        daftar.append(
            pemeriksaan(
                "tanpa_error", False, f"kode keluar {hasil.kode_keluar}"
            )
        )
    else:
        daftar.append(pemeriksaan("tanpa_error", True, "tidak ada error"))

    teks = getattr(hasil, "teks", "") or ""

    for indeks, pola in enumerate(soal.get("harus_ada", []) or [], start=1):
        cocok = _cocok(teks, pola)
        daftar.append(
            pemeriksaan(
                f"harus_ada[{indeks}]",
                cocok,
                f"regex {pola!r} {'cocok' if cocok else 'tidak cocok'} di teks akhir",
            )
        )

    for indeks, pola in enumerate(soal.get("tidak_boleh", []) or [], start=1):
        cocok = _cocok(teks, pola)
        daftar.append(
            pemeriksaan(
                f"tidak_boleh[{indeks}]",
                not cocok,
                f"regex terlarang {pola!r} {'ditemukan' if cocok else 'tidak ditemukan'}",
            )
        )

    daftar.extend(_periksa_kode(soal, teks))

    if soal.get("bahasa") == "id":
        terdeteksi = heuristik_id(teks)
        daftar.append(
            pemeriksaan(
                "bahasa",
                terdeteksi,
                "teks terdeteksi Bahasa Indonesia"
                if terdeteksi
                else "teks tidak terdeteksi Bahasa Indonesia",
            )
        )

    if "harus_baca" in soal:
        path_baca = [p for nama, p in paths_tool(hasil) if nama in TOOL_BACA]
        for indeks, pola in enumerate(soal.get("harus_baca", []) or [], start=1):
            cocok = any(_cocok(path, pola) for path in path_baca)
            daftar.append(
                pemeriksaan(
                    f"harus_baca[{indeks}]",
                    cocok,
                    f"regex path {pola!r} {'cocok' if cocok else 'tidak cocok'} "
                    f"pada {len(path_baca)} path tool baca",
                )
            )

    if "tidak_boleh_tool" in soal:
        terlarang = {str(x).lower() for x in soal.get("tidak_boleh_tool", []) or []}
        dipakai = sorted(
            {str(t.get("nama", "")).lower() for t in getattr(hasil, "tool", []) or []}
            & terlarang
        )
        daftar.append(
            pemeriksaan(
                "tidak_boleh_tool",
                not dipakai,
                "tool terlarang dipakai: " + ", ".join(dipakai)
                if dipakai
                else "tidak ada tool terlarang yang dipakai",
            )
        )

    if "maks_kata" in soal:
        jumlah = len(re.findall(r"\w+", teks))
        batas = soal["maks_kata"]
        daftar.append(
            pemeriksaan(
                "maks_kata",
                jumlah <= batas,
                f"{jumlah} kata, batas {batas}",
            )
        )

    return daftar


def lulus(pemeriksaan_list: list[dict]) -> bool:
    return all(item["lulus"] for item in pemeriksaan_list)
