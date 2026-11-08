"""CLI ujian-agen: jalankan, periksa, laporan."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import __version__
from .bandingkan import BandingkanError, ada_turun, bandingkan, format_teks, muat
from .batas import MAKS_MODEL, MAKS_PARALEL, MAKS_ULANG, MAKS_WAKTU
from .laporan import tabel_ringkas, tulis_markdown
from .penilaian import lulus, nilai, status
from .runner import Hasil, jalankan_opencode
from .soal import SoalError, muat_soal


def _argumen() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ujian_agen",
        description="Harness ujian agen koding CLI (opencode).",
    )
    sub = parser.add_subparsers(dest="perintah", required=True)

    p_jalan = sub.add_parser("jalankan", help="jalankan soal terhadap model")
    p_jalan.add_argument("berkas_soal", metavar="SOAL.toml", help="berkas soal TOML")
    p_jalan.add_argument(
        "-m", "--model", action="append", required=True,
        help="model, boleh berulang (maks %d)" % MAKS_MODEL,
    )
    p_jalan.add_argument("--cwd", default=".", help="direktori kerja agen")
    p_jalan.add_argument("--agen", default=None, help="nama agen opencode")
    p_jalan.add_argument(
        "--standalone", action="store_true",
        help="opencode run --standalone (server pribadi per run; service bersama bisa tertahan)",
    )
    p_jalan.add_argument(
        "--keluaran", default="hasil", help="direktori hasil (default: hasil)"
    )
    p_jalan.add_argument(
        "--ulang", type=int, default=1,
        help="ulangi tiap soal N kali (1..%d)" % MAKS_ULANG,
    )
    p_jalan.add_argument(
        "--paralel", type=int, default=1,
        help="jumlah pekerja paralel (1..%d)" % MAKS_PARALEL,
    )
    p_jalan.add_argument(
        "--soal", dest="pilih_soal", action="append", default=None,
        help="hanya soal dengan ID ini, boleh berulang",
    )

    p_periksa = sub.add_parser("periksa", help="validasi berkas soal")
    p_periksa.add_argument("soal", help="berkas soal TOML")

    p_laporan = sub.add_parser("laporan", help="buat ulang laporan markdown")
    p_laporan.add_argument("hasil", help="berkas hasil JSON")

    p_banding = sub.add_parser(
        "bandingkan", help="bandingkan dua berkas hasil JSON"
    )
    p_banding.add_argument("lama", metavar="LAMA.json", help="hasil lama")
    p_banding.add_argument("baru", metavar="BARU.json", help="hasil baru")
    return parser


def _galat(pesan: str) -> int:
    print(f"error: {pesan}", file=sys.stderr)
    return 2


def _pilih_soal(soal_list: list[dict], diminta: list[str] | None) -> list[dict]:
    if not diminta:
        return soal_list
    dikenal = {s["id"] for s in soal_list}
    tidak_ada = [sid for sid in diminta if sid not in dikenal]
    if tidak_ada:
        raise SoalError("ID soal tidak ditemukan: " + ", ".join(tidak_ada))
    urutan: list[str] = []
    for sid in diminta:
        if sid not in urutan:
            urutan.append(sid)
    peta = {s["id"]: s for s in soal_list}
    return [peta[sid] for sid in urutan]


def _nama_hasil(direktori: Path, saat: datetime) -> Path:
    dasar = f"hasil-{saat:%Y%m%d-%H%M%S}"
    kandidat = direktori / f"{dasar}.json"
    nomor = 2
    while kandidat.exists():
        kandidat = direktori / f"{dasar}-{nomor}.json"
        nomor += 1
    return kandidat


def _satu_hasil(soal: dict, model: str, ulangan: int, args, runner) -> dict:
    waktu = soal.get("waktu", MAKS_WAKTU)
    try:
        hasil = runner(
            soal["prompt"],
            model,
            str(args.cwd),
            waktu,
            agen=args.agen,
            **({"standalone": True} if args.standalone else {}),
        )
    except Exception as exc:  # runner eksternal tidak boleh menjatuhkan seluruh ujian
        hasil = Hasil(error=f"runner gagal: {type(exc).__name__}: {exc}")
    pemeriksaan = nilai(soal, hasil)
    st = status(soal, hasil, pemeriksaan)
    return {
        "model": model,
        "soal": soal["id"],
        "ulangan": ulangan,
        "lulus": lulus(pemeriksaan),
        "status": st,
        "pemeriksaan": pemeriksaan,
        **hasil.ke_dict(),
    }


def _perintah_jalankan(args, runner=None) -> int:
    if len(args.model) > MAKS_MODEL:
        return _galat(
            f"jumlah model {len(args.model)} melebihi MAKS_MODEL {MAKS_MODEL}"
        )
    if not 1 <= args.ulang <= MAKS_ULANG:
        return _galat(f"--ulang harus 1..{MAKS_ULANG}")
    if not 1 <= args.paralel <= MAKS_PARALEL:
        return _galat(f"--paralel harus 1..{MAKS_PARALEL}")

    try:
        soal_list = muat_soal(args.berkas_soal)
        soal_list = _pilih_soal(soal_list, args.pilih_soal)
    except SoalError as exc:
        return _galat(str(exc))

    cwd = Path(args.cwd)
    if not cwd.is_dir():
        return _galat(f"cwd bukan direktori: {args.cwd}")

    direktori = Path(args.keluaran)
    try:
        direktori.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _galat(f"tidak bisa membuat direktori keluaran {direktori}: {exc}")

    runner = runner or jalankan_opencode
    tugas = [
        (soal, model, ulangan)
        for model in args.model
        for soal in soal_list
        for ulangan in range(1, args.ulang + 1)
    ]

    def kerja(tugas_satu):
        soal, model, ulangan = tugas_satu
        return _satu_hasil(soal, model, ulangan, args, runner)

    if args.paralel > 1:
        with ThreadPoolExecutor(max_workers=args.paralel) as eksekutor:
            hasil_list = list(eksekutor.map(kerja, tugas))
    else:
        hasil_list = [kerja(t) for t in tugas]

    saat = datetime.now().astimezone()
    data = {
        "versi": __version__,
        "dibuat": saat.isoformat(timespec="seconds"),
        "berkas_soal": str(args.berkas_soal),
        "cwd": str(cwd),
        "agen": args.agen,
        "standalone": bool(args.standalone),
        "ulang": args.ulang,
        "paralel": args.paralel,
        "model": list(args.model),
        "soal": [{"id": s["id"], "prompt": s["prompt"]} for s in soal_list],
        "hasil": hasil_list,
    }

    path_json = _nama_hasil(direktori, saat)
    path_md = path_json.with_suffix(".md")
    try:
        path_json.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tulis_markdown(data, path_md)
    except (OSError, TypeError, ValueError) as exc:
        return _galat(f"gagal menulis hasil: {exc}")

    print(tabel_ringkas(data))
    print()
    print(f"JSON : {path_json}")
    print(f"MD   : {path_md}")

    semua_ok = all(h.get("status") not in ("gagal", "infra") for h in hasil_list)
    return 0 if semua_ok else 1


def _perintah_periksa(args) -> int:
    try:
        soal_list = muat_soal(args.soal)
    except SoalError as exc:
        return _galat(str(exc))
    print(f"OK: {len(soal_list)} soal valid di {args.soal}")
    return 0


def _perintah_laporan(args) -> int:
    path = Path(args.hasil)
    if not path.is_file():
        return _galat(f"berkas hasil tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _galat(f"gagal membaca {path}: {exc}")
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("hasil"), list)
    ):
        return _galat(f"format hasil tidak dikenal: {path}")

    tujuan = path.with_suffix(".md")
    try:
        tulis_markdown(data, tujuan)
    except OSError as exc:
        return _galat(f"gagal menulis laporan: {exc}")

    print(tabel_ringkas(data))
    print()
    print(f"MD: {tujuan}")
    semua_ok = all(
        (h.get("status") or ("lulus" if h.get("lulus") else "gagal")) not in ("gagal", "infra")
        for h in data.get("hasil", [])
    )
    return 0 if semua_ok else 1


def _perintah_bandingkan(args) -> int:
    try:
        data_lama = muat(args.lama)
        data_baru = muat(args.baru)
    except BandingkanError as exc:
        return _galat(str(exc))
    hasil = bandingkan(data_lama, data_baru)
    print(format_teks(hasil))
    return 1 if ada_turun(hasil) else 0


def main(argv: list[str] | None = None, runner=None) -> int:
    args = _argumen().parse_args(argv)
    if args.perintah == "jalankan":
        return _perintah_jalankan(args, runner=runner)
    if args.perintah == "periksa":
        return _perintah_periksa(args)
    if args.perintah == "laporan":
        return _perintah_laporan(args)
    if args.perintah == "bandingkan":
        return _perintah_bandingkan(args)
    return _galat(f"perintah tidak dikenal: {args.perintah}")
