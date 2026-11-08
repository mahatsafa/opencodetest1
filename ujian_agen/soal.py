"""Pemuat dan validator berkas soal TOML.

Aturan mengikuti SPEC.md bagian "Format soal (TOML)": validasi dilakukan saat
memuat, dan setiap error menyebut nama berkas (serta id soal bila ada).
"""

from __future__ import annotations

import re
import tomllib

from .batas import MAKS_SOAL, MAKS_WAKTU, PANJANG_MAKS_ID


class SoalError(Exception):
    """Kesalahan umum saat memuat soal."""


class SoalFormatError(SoalError):
    """Bentuk berkas/field soal tidak valid."""


class SoalValidasiError(SoalError):
    """Nilai soal sah secara bentuk tetapi melewati batas/aturan."""


FIELD_DIIZINKAN = {
    "id",
    "prompt",
    "waktu",
    "harus_ada",
    "tidak_boleh",
    "bahasa",
    "harus_baca",
    "tidak_boleh_tool",
    "maks_kata",
    "harus_ada_kode",
    "tidak_boleh_kode",
}

POLA_ID = re.compile(r"[a-z0-9-]{1,%d}" % PANJANG_MAKS_ID)
DAFTAR_REGEX = ("harus_ada", "tidak_boleh", "harus_baca", "harus_ada_kode", "tidak_boleh_kode")

_regex_cache: dict[str, re.Pattern[str]] = {}


def compile_regex(pola: str) -> re.Pattern[str]:
    """Kompilasi regex dengan cache; error selalu SoalFormatError."""
    if not isinstance(pola, str):
        raise SoalFormatError(f"Regex harus string, bukan {type(pola).__name__}")
    if pola in _regex_cache:
        return _regex_cache[pola]
    try:
        hasil = re.compile(pola)
    except re.error as exc:
        raise SoalFormatError(f"Regex tidak valid: {pola!r}: {exc}") from exc
    _regex_cache[pola] = hasil
    return hasil


def _label(path: str, sid: object) -> str:
    if sid is None:
        return str(path)
    return f"{path} id={sid}"


def _cek_bilangan_bulat(nilai: object, nama: str, label: str, minimal: int = 1) -> None:
    if isinstance(nilai, bool) or not isinstance(nilai, int):
        raise SoalFormatError(f"{nama} harus bilangan bulat di {label}")
    if nilai < minimal:
        raise SoalValidasiError(f"{nama} minimal {minimal} di {label}")


def _cek_daftar_string(nilai: object, nama: str, label: str) -> None:
    if not isinstance(nilai, list):
        raise SoalFormatError(f"{nama} harus list di {label}")
    for item in nilai:
        if not isinstance(item, str):
            raise SoalFormatError(f"{nama} harus berisi string di {label}")
        if not item:
            raise SoalFormatError(f"{nama} tidak boleh berisi string kosong di {label}")


def _validasi_soal(s: object, path: str, ids: set[str]) -> None:
    if not isinstance(s, dict):
        raise SoalFormatError(f"Setiap [[soal]] harus tabel di {path}")

    sid = s.get("id")
    label = _label(path, sid)

    for kunci in s:
        if kunci not in FIELD_DIIZINKAN:
            raise SoalFormatError(f"Field tak dikenal {kunci!r} di {label}")

    if not isinstance(sid, str) or not POLA_ID.fullmatch(sid):
        raise SoalFormatError(
            f"ID tidak valid di {label}; harus [a-z0-9-] maks {PANJANG_MAKS_ID}"
        )
    if sid in ids:
        raise SoalFormatError(f"ID ganda: {sid} di {path}")
    ids.add(sid)

    prompt = s.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SoalFormatError(f"prompt wajib diisi di {label}")

    if "waktu" in s:
        _cek_bilangan_bulat(s["waktu"], "waktu", label)
        if s["waktu"] > MAKS_WAKTU:
            raise SoalValidasiError(
                f"waktu {s['waktu']} melebihi MAKS_WAKTU {MAKS_WAKTU} di {label}"
            )

    for nama in DAFTAR_REGEX:
        if nama in s:
            _cek_daftar_string(s[nama], nama, label)
            for pola in s[nama]:
                try:
                    compile_regex(pola)
                except SoalFormatError as exc:
                    raise SoalFormatError(f"{exc} di {label}") from exc

    if "bahasa" in s:
        if s["bahasa"] != "id":
            raise SoalFormatError(f"bahasa hanya boleh \"id\" di {label}")

    if "tidak_boleh_tool" in s:
        _cek_daftar_string(s["tidak_boleh_tool"], "tidak_boleh_tool", label)

    if "maks_kata" in s:
        _cek_bilangan_bulat(s["maks_kata"], "maks_kata", label)


def muat_soal(path: str) -> list[dict]:
    """Muat dan validasi berkas soal TOML; kembalikan list dict soal."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as exc:
        raise SoalFormatError(f"Berkas soal tidak ditemukan: {path}") from exc
    except OSError as exc:
        raise SoalFormatError(f"Gagal membaca {path}: {exc}") from exc
    except (tomllib.TOMLDecodeError, UnicodeError) as exc:
        raise SoalFormatError(f"TOML tidak valid di {path}: {exc}") from exc

    if "soal" not in data:
        raise SoalFormatError(f"Tidak ada [[soal]] di {path}")
    soal_list = data["soal"]
    if not isinstance(soal_list, list) or not soal_list:
        raise SoalFormatError(f"[[soal]] harus list tidak kosong di {path}")
    if len(soal_list) > MAKS_SOAL:
        raise SoalValidasiError(
            f"Jumlah soal {len(soal_list)} > MAKS_SOAL {MAKS_SOAL} di {path}"
        )

    ids: set[str] = set()
    for s in soal_list:
        _validasi_soal(s, path, ids)
    return soal_list
