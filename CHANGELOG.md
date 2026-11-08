# Changelog

## 0.2.0 — 2026-11-09
Lahir dari ujian nyata opencode 2026-11-08 (15 soal x 5 model).
- `harus_ada_kode` / `tidak_boleh_kode`: regex hanya di isi blok kode (prosa larangan tidak lagi dihukum).
- Status `infra` (error + teks kosong + tanpa tool); persen laporan tanpa infra; kolom Infra.
- Perintah `bandingkan LAMA.json BARU.json` (NAIK/TURUN/TETAP, ringkasan per model).
- Heuristik bahasa: bukti kurang (kata fungsi id < 3 dan en < 3) = lulus.
- Diketahui: kode keluar `jalankan` kini 1 juga bila hanya ada infra.

## 0.1.0 — 2026-11-08
- Soal TOML, runner `opencode run --format json`, penilaian, CLI jalankan/periksa/laporan, laporan JSON + Markdown.
