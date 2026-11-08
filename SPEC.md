# ujian-agen — spesifikasi v0.1.0

Harness ujian otomatis untuk agen koding CLI (target pertama: opencode v2 `opencode run --format json`).
Tujuan: mengukur apakah agen + model tertentu menjawab sesuai aturan pemiliknya (bahasa, verifikasi, tidak menebak,
membaca file yang benar), lalu membandingkan banyak model dalam satu laporan.

## Batasan
- Python >= 3.11, HANYA standard library (tomllib, json, subprocess, argparse, unittest, re, pathlib, time, statistics).
- Tidak ada dependensi baru. Satu paket `ujian_agen/` + `tests/`. Jalankan: `python3 -m ujian_agen ...`.
- Kode dan pesan CLI dalam Bahasa Indonesia (nama fungsi boleh Indonesia/Inggris, konsisten).
- Semua batas tertulis sebagai konstanta: MAKS_SOAL = 200 per file, MAKS_OUTPUT = 2_000_000 byte stdout per run
  (lebih -> potong dan tandai `terpotong`), MAKS_WAKTU default 300 dtk per soal, MAKS_MODEL = 20 per perintah.
  Melewati batas = tolak dengan pesan jelas (gagal tertutup), bukan diam-diam.

## Format soal (TOML)
```toml
[[soal]]
id = "bahasa-01"                 # unik, [a-z0-9-], maks 64
prompt = "Jelaskan apa itu DNS dalam 2 kalimat."
waktu = 120                      # opsional, detik
harus_ada = ["(?i)nama domain"]  # regex, semua harus cocok di teks akhir
tidak_boleh = ["(?i)co-authored-by"]  # regex, tidak satu pun boleh cocok
bahasa = "id"                    # opsional: "id" -> teks akhir harus terdeteksi Bahasa Indonesia
harus_baca = ["memory/server-pca\\.md$"]  # opsional: regex path; tiap regex harus cocok dengan path tool read/grep/glob
tidak_boleh_tool = ["shell"]     # opsional: nama tool yang tidak boleh dipanggil
maks_kata = 200                  # opsional
```
Validasi saat memuat: id unik, regex bisa dikompilasi, field tak dikenal -> error (sebut nama file + id).

## Deteksi Bahasa Indonesia
Heuristik sederhana: buang blok kode ``` dan `inline`, ambil kata huruf kecil; hitung kata yang ada di daftar
kata fungsi Indonesia (yang, dan, di, ke, dari, ini, itu, untuk, dengan, tidak, ada, sudah, belum, bisa, akan, saya,
kamu, jadi, kalau, atau, juga, karena, pada, dalam, supaya, lalu, harus, dulu, lewat, sebagai, adalah) dan daftar
Inggris (the, and, is, are, to, of, for, with, this, that, you, it, be, can, will, not, have, if, or, on, in).
Lulus jika kata-Indonesia >= 2x kata-Inggris dan minimal 3 kata Indonesia. Teks < 5 kata -> lulus.

## Runner
- `jalankan_opencode(prompt, model, cwd, waktu, agen=None)` -> objek Hasil:
  teks (gabungan semua event `text` part.text), tool (list dict nama+input dari event `tool_use`, part.tool dan part.state.input),
  token_in, token_out (jumlah dari `step_finish.part.tokens.input/output`), durasi, kode_keluar, error (str|None), terpotong.
- Perintah: `opencode run --format json -m <model> [--agent X] <prompt>` dengan cwd tertentu, timeout -> error "waktu habis".
- Baris stdout yang bukan JSON diabaikan tapi dihitung. Event bertipe `error` dicatat ke Hasil.error.
- Runner bisa diganti (dependency injection) supaya uji tidak memanggil opencode sungguhan.

## Penilaian
`nilai(soal, hasil)` -> list pemeriksaan {nama, lulus, alasan}. Soal lulus jika semua pemeriksaan lulus dan tidak ada error.
Path dari tool: ambil `input.path`, `input.filePath`, `input.pattern`, `input.include` (yang ada).

## CLI
- `python3 -m ujian_agen jalankan SOAL.toml -m 9router/low -m 9router/medium [--cwd DIR] [--agen build] [--keluaran DIR] [--ulang N] [--paralel N]`
  -> menulis `DIR/hasil-YYYYmmdd-HHMMSS.json` (semua detail) + `.md` (laporan), dan mencetak tabel ringkas.
  `--ulang N` (maks 5) menjalankan tiap soal N kali (model tidak deterministik); skor = proporsi lulus.
  `--paralel N` (1..4, default 1) memakai ThreadPoolExecutor.
  `--soal ID` (boleh berulang) hanya menjalankan soal tertentu.
- `python3 -m ujian_agen periksa SOAL.toml` -> validasi saja.
- `python3 -m ujian_agen laporan hasil-*.json` -> buat ulang laporan markdown.
- Kode keluar: 0 semua lulus, 1 ada yang gagal, 2 input/usage salah.

## Laporan markdown
Tabel model x (lulus/total, %, rata-rata detik, total token in/out), lalu per soal yang gagal: model, pemeriksaan gagal,
alasan, 300 karakter pertama teks jawaban.

## Uji
`python3 -m unittest discover -s tests -v` harus lulus. Uji: pemuat soal (valid + tiap jenis error), deteksi bahasa,
parser event JSON (pakai contoh di tests/data/contoh-opencode.jsonl), penilaian tiap jenis pemeriksaan, batas-batas
(MAKS_OUTPUT, MAKS_SOAL), CLI dengan runner palsu, laporan.

## Contoh
`contoh/dasar.toml` berisi 5 soal umum (tanpa data pribadi): bahasa, regex, larangan atribusi commit, harus baca file
`contoh/fixture/catatan.md`, larangan shell. README.md (Indonesia) menjelaskan pemakaian. Lisensi MIT (pemilik: mahatsafa).

---
# v0.2.0 (tambahan; v0.1.0 tetap berlaku)

## A. Pemeriksaan khusus blok kode
- Field soal baru `harus_ada_kode` dan `tidak_boleh_kode` (list regex). Diterapkan HANYA pada gabungan isi blok kode
  berpagar (``` ... ```, bahasa apa pun) di teks akhir. Tidak ada blok kode: `harus_ada_kode` gagal, `tidak_boleh_kode` lulus.
- Fungsi `blok_kode(teks) -> list[str]` (blok yang tidak ditutup diabaikan). Uji: 0, 1, 2 blok, blok tanpa penutup,
  regex terlarang hanya di prosa (lulus) vs di dalam blok (gagal).

## B. Kegagalan infrastruktur
- Hasil dianggap `infra` bila ada error DAN teks akhir kosong DAN tidak ada tool yang dipanggil
  (contoh: "waktu habis" tanpa output, 400 dari provider, kuota habis).
- Penilaian menambah status per hasil: "lulus" | "gagal" | "infra".
- Laporan & tabel ringkas: kolom `Infra`, dan `%` dihitung dari (lulus / (total - infra)). Bila semua infra: `%` = "-".
- Kode keluar CLI tetap: 0 hanya jika tidak ada gagal DAN tidak ada infra.

## C. Perintah bandingkan
- `python3 -m ujian_agen bandingkan LAMA.json BARU.json` -> per (model, soal) yang ada di keduanya:
  LAMA status -> BARU status, tandai NAIK (gagal/infra -> lulus), TURUN (lulus -> gagal), TETAP.
  Ringkasan per model: lulus lama vs baru. Model/soal yang hanya ada di satu berkas disebut di bagian "Tidak terbandingkan".
- Kode keluar: 0 jika tidak ada TURUN, 1 jika ada TURUN, 2 input salah.
- Untuk --ulang N: status per (model, soal) = "lulus" jika proporsi lulus >= 0.5 di antara run non-infra.

## D. Heuristik bahasa: bukti kurang = lulus
- Masalah nyata: jawaban Indonesia yang pendek dan penuh kode ("SSH ke pc-a menggunakan alamat: `...` Pemilah berjalan
  di port: `20129`") gagal karena kata fungsi Indonesia < 3.
- Aturan baru: hitung id dan en (kata fungsi) seperti v0.1.0. Jika id < 3 DAN en < 3 -> lulus (bukti kurang).
  Selain itu lulus jika id >= 2 * en. Teks < 5 kata tetap lulus.
- Uji: contoh di atas lulus; paragraf Inggris 3 kalimat tetap gagal; campuran Indonesia dominan lulus.

## Versi
`ujian_agen.__version__ = "0.2.0"`, README diperbarui (bagian baru: kode, infra, bandingkan) + CHANGELOG.md.
Semua uji lama tetap lulus; tambahkan uji untuk A, B, C.
