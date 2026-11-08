"""Pembuatan laporan markdown dan ringkasan dari data hasil JSON."""

from __future__ import annotations

from pathlib import Path


def _sel(nilai: object) -> str:
    return str(nilai).replace("|", "\\|").replace("\n", " ")


def _status_hasil(h: dict) -> str:
    st = h.get("status")
    if st in ("lulus", "gagal", "infra"):
        return st
    return "lulus" if h.get("lulus") else "gagal"


def ringkas_model(data: dict) -> list[dict]:
    """Agregasi per model: lulus/total, infra, persen, rata-rata detik, token."""
    urutan = list(data.get("model", []) or [])
    hasil = data.get("hasil", []) or []
    for item in hasil:
        model = item.get("model")
        if model not in urutan:
            urutan.append(model)

    ringkasan = []
    for model in urutan:
        milik = [h for h in hasil if h.get("model") == model]
        total = len(milik)
        st_list = [_status_hasil(h) for h in milik]
        lulus = sum(1 for st in st_list if st == "lulus")
        infra = sum(1 for st in st_list if st == "infra")
        efektif = total - infra
        persen = (100.0 * lulus / efektif) if efektif > 0 else None
        detik = sum(float(h.get("durasi") or 0.0) for h in milik)
        ringkasan.append(
            {
                "model": model,
                "lulus": lulus,
                "total": total,
                "infra": infra,
                "persen": persen,
                "rata_detik": (detik / total) if total else 0.0,
                "token_in": sum(int(h.get("token_in") or 0) for h in milik),
                "token_out": sum(int(h.get("token_out") or 0) for h in milik),
            }
        )
    return ringkasan


def tabel_ringkas(data: dict) -> str:
    """Tabel teks polos untuk dicetak ke terminal."""
    baris = [
        f"{'Model':<28} {'Lulus/Total':>12} {'Infra':>6} {'%':>7} {'Rata2 dtk':>10} "
        f"{'Token in':>12} {'Token out':>12}"
    ]
    baris.append("-" * 93)
    for r in ringkas_model(data):
        persen_str = (
            f"{r['persen']:>7.1f}" if r["persen"] is not None else f"{'-':>7}"
        )
        baris.append(
            f"{str(r['model']):<28} "
            f"{str(r['lulus']) + '/' + str(r['total']):>12} "
            f"{r['infra']:>6} "
            f"{persen_str} "
            f"{r['rata_detik']:>10.2f} "
            f"{r['token_in']:>12} "
            f"{r['token_out']:>12}"
        )
    return "\n".join(baris)


def _blok_teks(teks: str) -> str:
    potongan = (teks or "")[:300]
    return "````text\n" + potongan + "\n````"


def buat_markdown(data: dict) -> str:
    """Susun laporan markdown sesuai SPEC."""
    hasil = data.get("hasil", []) or []
    gagal = [h for h in hasil if not h.get("lulus")]

    baris: list[str] = ["# Laporan ujian-agen", ""]
    baris.append(f"- Dibuat: `{_sel(data.get('dibuat', '-'))}`")
    baris.append(f"- Berkas soal: `{_sel(data.get('berkas_soal', '-'))}`")
    baris.append(f"- CWD: `{_sel(data.get('cwd', '-'))}`")
    agen = data.get("agen") or "-"
    baris.append(f"- Agen: `{_sel(agen)}`")
    baris.append(f"- Ulangan: {data.get('ulang', 1)}")
    model = ", ".join(f"`{_sel(m)}`" for m in data.get("model", []) or [])
    baris.append(f"- Model: {model or '-'}")
    baris.append("")

    baris.append("## Ringkasan model")
    baris.append("")
    baris.append(
        "| Model | Lulus/Total | Infra | % | Rata-rata detik | Token masuk | Token keluar |"
    )
    baris.append("|---|---:|---:|---:|---:|---:|---:|")
    for r in ringkas_model(data):
        persen_str = (
            f"{r['persen']:.1f}" if r["persen"] is not None else "-"
        )
        baris.append(
            f"| `{_sel(r['model'])}` | {r['lulus']}/{r['total']} | "
            f"{r['infra']} | {persen_str} | {r['rata_detik']:.2f} | "
            f"{r['token_in']} | {r['token_out']} |"
        )
    baris.append("")

    baris.append("## Soal gagal")
    baris.append("")
    if not gagal:
        baris.append("Tidak ada kegagalan. Semua pemeriksaan lulus.")
        baris.append("")
    else:
        for item in gagal:
            ulangan = item.get("ulangan", 1)
            baris.append(
                f"### `{_sel(item.get('model', '-'))}` — "
                f"`{_sel(item.get('soal', '-'))}` (ulangan {ulangan})"
            )
            baris.append("")
            baris.append("Pemeriksaan gagal:")
            baris.append("")
            pemeriksaan_gagal = [
                p for p in item.get("pemeriksaan", []) or [] if not p.get("lulus")
            ]
            if not pemeriksaan_gagal and item.get("status") != "infra":
                baris.append("- `lulus` bernilai salah (tanpa rincian pemeriksaan)")
            for p in pemeriksaan_gagal:
                baris.append(
                    f"- **{_sel(p.get('nama', '-'))}**: "
                    f"{_sel(p.get('alasan', '-'))}"
                )
            if item.get("error"):
                baris.append(f"- **error runner**: {_sel(item['error'])}")
            baris.append("")
            baris.append("Jawaban (300 karakter pertama):")
            baris.append("")
            baris.append(_blok_teks(item.get("teks", "")))
            baris.append("")
    return "\n".join(baris).rstrip() + "\n"


def tulis_markdown(data: dict, path: str | Path) -> Path:
    tujuan = Path(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    tujuan.write_text(buat_markdown(data), encoding="utf-8")
    return tujuan
