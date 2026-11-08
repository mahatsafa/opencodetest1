"""Runner opencode: membangun perintah, mengeksekusi, dan mengurai event JSONL."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field

from .batas import MAKS_OUTPUT, MAKS_WAKTU

BATAS_PESAN_ERROR = 500


@dataclass
class Hasil:
    """Hasil satu kali eksekusi agen."""

    teks: str = ""
    tool: list[dict] = field(default_factory=list)
    token_in: int = 0
    token_out: int = 0
    durasi: float = 0.0
    kode_keluar: int | None = None
    error: str | None = None
    terpotong: bool = False
    baris: int = 0
    baris_bukan_json: int = 0

    def ke_dict(self) -> dict:
        return {
            "teks": self.teks,
            "tool": self.tool,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "durasi": self.durasi,
            "kode_keluar": self.kode_keluar,
            "error": self.error,
            "terpotong": self.terpotong,
            "baris": self.baris,
            "baris_bukan_json": self.baris_bukan_json,
        }


def perintah_opencode(prompt: str, model: str, agen: str | None = None) -> list[str]:
    """Susun argv opencode sesuai SPEC."""
    perintah = ["opencode", "run", "--format", "json", "-m", model]
    if agen:
        perintah.extend(["--agent", agen])
    perintah.append(prompt)
    return perintah


def _ambil_int(nilai: object) -> int:
    if isinstance(nilai, bool) or not isinstance(nilai, int):
        return 0
    return nilai


def _cari_pesan(obj: object) -> str | None:
    if isinstance(obj, str) and obj.strip():
        return obj
    if isinstance(obj, dict):
        for kunci in ("message", "pesan"):
            pesan = obj.get(kunci)
            if isinstance(pesan, str) and pesan.strip():
                return pesan
        data = obj.get("data")
        if isinstance(data, dict):
            pesan = _cari_pesan(data)
            if pesan:
                return pesan
        for kunci in ("error", "name"):
            pesan = _cari_pesan(obj.get(kunci))
            if pesan:
                return pesan
    return None


def _pesan_error(event: dict) -> str:
    part = event.get("part")
    for kandidat in (event.get("error"), part.get("error") if isinstance(part, dict) else None):
        pesan = _cari_pesan(kandidat)
        if pesan:
            return pesan
    pesan = _cari_pesan(event.get("message"))
    if pesan:
        return pesan
    return "error dari opencode"


def _urai_baris(baris: str, hasil: Hasil) -> None:
    """Urai satu baris JSON; baris invalid hanya dihitung."""
    if not baris.strip():
        return
    hasil.baris += 1
    try:
        event = json.loads(baris)
    except (json.JSONDecodeError, ValueError):
        hasil.baris_bukan_json += 1
        return
    if not isinstance(event, dict):
        hasil.baris_bukan_json += 1
        return

    tipe = event.get("type")
    part = event.get("part")
    if not isinstance(part, dict):
        part = {}

    if tipe == "text":
        potongan = part.get("text")
        if isinstance(potongan, str):
            hasil.teks += potongan
    elif tipe == "tool_use":
        nama = part.get("tool")
        state = part.get("state")
        if not isinstance(state, dict):
            state = {}
        masukan = state.get("input")
        if not isinstance(masukan, dict):
            masukan = part.get("input") if isinstance(part.get("input"), dict) else {}
        if isinstance(nama, str) and nama:
            hasil.tool.append({"nama": nama, "input": masukan})
    elif tipe == "step_finish":
        token = part.get("tokens")
        if isinstance(token, dict):
            hasil.token_in += _ambil_int(token.get("input"))
            hasil.token_out += _ambil_int(token.get("output"))
    elif tipe == "error":
        pesan = _pesan_error(event)
        if hasil.error:
            hasil.error = f"{hasil.error}; {pesan}"
        else:
            hasil.error = pesan


def urai_keluaran(teks: str) -> Hasil:
    """Urai seluruh stdout opencode (JSONL) menjadi Hasil."""
    hasil = Hasil()
    for baris in teks.splitlines():
        _urai_baris(baris, hasil)
    return hasil


def _jalankan_proses(perintah: list[str], cwd: str, waktu: int):
    return subprocess.run(perintah, cwd=cwd, capture_output=True, timeout=waktu)


def jalankan_opencode(
    prompt: str,
    model: str,
    cwd: str,
    waktu: int = MAKS_WAKTU,
    agen: str | None = None,
    pelaksana=None,
) -> Hasil:
    """Jalankan opencode sekali.

    `pelaksana` adalah dependency injection: fungsi
    ``pelaksana(perintah, cwd, waktu) -> objek dengan returncode/stdout/stderr``.
    Uji memakai pelaksana palsu sehingga tidak memanggil opencode sungguhan.
    """
    perintah = perintah_opencode(prompt, model, agen)
    pelaksana = pelaksana or _jalankan_proses
    if isinstance(waktu, bool) or not isinstance(waktu, int) or waktu < 1:
        return Hasil(error=f"waktu tidak valid: {waktu!r}")
    if waktu > MAKS_WAKTU:
        return Hasil(
            error=f"waktu {waktu} melebihi MAKS_WAKTU {MAKS_WAKTU}"
        )
    mulai = time.monotonic()
    try:
        proses = pelaksana(perintah, cwd, waktu)
    except subprocess.TimeoutExpired:
        return Hasil(
            durasi=time.monotonic() - mulai,
            kode_keluar=None,
            error="waktu habis",
        )
    except FileNotFoundError:
        return Hasil(
            durasi=time.monotonic() - mulai,
            kode_keluar=None,
            error="opencode tidak ditemukan di PATH",
        )
    except OSError as exc:
        return Hasil(
            durasi=time.monotonic() - mulai,
            kode_keluar=None,
            error=f"gagal menjalankan opencode: {exc}",
        )

    durasi = time.monotonic() - mulai
    keluaran = proses.stdout or b""
    if isinstance(keluaran, str):
        keluaran = keluaran.encode("utf-8", "replace")
    terpotong = len(keluaran) > MAKS_OUTPUT
    if terpotong:
        keluaran = keluaran[:MAKS_OUTPUT]
    teks = keluaran.decode("utf-8", "replace")

    hasil = urai_keluaran(teks)
    hasil.durasi = durasi
    hasil.kode_keluar = proses.returncode
    hasil.terpotong = terpotong

    if proses.returncode not in (0, None) and not hasil.error:
        galat = proses.stderr or b""
        if isinstance(galat, str):
            galat = galat.encode("utf-8", "replace")
        pesan = galat[:BATAS_PESAN_ERROR].decode("utf-8", "replace").strip()
        hasil.error = (
            f"kode keluar {proses.returncode}: {pesan}"
            if pesan
            else f"kode keluar {proses.returncode}"
        )
    return hasil
