# ujian-agen

Harness ujian otomatis untuk agen koding CLI, target pertama **opencode v2**
(`opencode run --format json`). Alat ini mengukur apakah agen + model tertentu
menjawab sesuai aturan pemiliknya: bahasa, verifikasi, tidak menebak, membaca
file yang benar, dan mematuhi larangan tool. Banyak model dapat diuji dalam satu
perintah lalu dibandingkan lewat satu laporan.

- Python >= 3.11, **hanya standard library** (tanpa dependensi baru).
- Satu paket `ujian_agen/`, dijalankan dengan `python3 -m ujian_agen ...`.
- Seluruh kode dan pesan CLI dalam Bahasa Indonesia.
- Lisensi MIT (pemilik: mahatsafa).

### Kenapa dibuat

Dibuat untuk "melatih" opencode milik sendiri tanpa menyentuh bobot model: aturan dan ingatan ditulis di
`AGENTS.md`, lalu setiap perubahan aturan diukur dengan ujian yang sama dan dibandingkan (`bandingkan`).
Contoh nyata: setelah aturan "garis merah" dipindah ke atas `AGENTS.md`, satu model naik dari 7/15 ke 14/15.
Soal pribadi (berisi IP/nama layanan) sebaiknya disimpan DI LUAR repo; `contoh/` hanya berisi soal umum.

## Pasang dan jalankan

Tidak ada langkah instalasi paket. Dari root proyek:

```bash
python3 -m ujian_agen periksa contoh/dasar.toml
python3 -m ujian_agen jalankan contoh/dasar.toml -m 9router/low -m 9router/medium
```

`opencode` harus ada di `PATH` dan sudah dikonfigurasi untuk model yang dipakai.
Hasil ditulis ke `hasil/hasil-YYYYmmdd-HHMMSS.json` (detail lengkap) dan
`hasil/hasil-YYYYmmdd-HHMMSS.md` (laporan), lalu tabel ringkas dicetak ke layar.

## Perintah

### `jalankan`

```bash
python3 -m ujian_agen jalankan SOAL.toml -m 9router/low -m 9router/medium \
  --cwd . --agen build --keluaran hasil --ulang 3 --paralel 2 \
  --soal bahasa-01 --soal baca-catatan-04
```

| Opsi | Arti |
|---|---|
| `-m`, `--model` | Model; boleh berulang, maksimal 20 model. Wajib. |
| `--cwd DIR` | Direktori kerja agen (default `.`). |
| `--agen NAMA` | Diteruskan sebagai `opencode run ... --agent NAMA`. |
| `--keluaran DIR` | Direktori hasil (default `hasil`). |
| `--ulang N` | Tiap soal dijalankan N kali (1..5, default 1). Model tidak deterministik; skor = proporsi lulus. |
| `--paralel N` | Jumlah pekerja paralel (1..4, default 1), memakai `ThreadPoolExecutor`. |
| `--soal ID` | Hanya jalankan soal dengan ID tersebut; boleh berulang. |

Tabel ringkas berisi model, lulus/total percobaan, persen, rata-rata detik, dan
total token masuk/keluar. Laporan markdown menambahkan rincian tiap kegagalan.

### `periksa`

```bash
python3 -m ujian_agen periksa contoh/dasar.toml
```

Memvalidasi berkas soal saja (id, regex, tipe field, batas) tanpa memanggil
opencode. Contoh keluaran: `OK: 5 soal valid di contoh/dasar.toml`.

### `bandingkan`

```bash
python3 -m ujian_agen bandingkan hasil/hasil-LAMA.json hasil/hasil-BARU.json
```

Membandingkan status tiap (model, soal): `NAIK` (gagal/infra -> lulus), `TURUN` (lulus -> gagal), `TETAP`.
Dengan `--ulang`, status pasangan = lulus jika >= 50% run non-infra lulus. Model/soal yang hanya ada di salah
satu berkas dicetak di "Tidak terbandingkan". Kode keluar 0 tanpa TURUN, 1 ada TURUN, 2 input salah.

### `laporan`

```bash
python3 -m ujian_agen laporan hasil/hasil-20261108-210000.json
```

Membuat ulang berkas `.md` di sebelah JSON tanpa menjalankan model.

## Format soal TOML

```toml
[[soal]]
id = "bahasa-01"                 # wajib, unik, [a-z0-9-], maks 64 karakter
prompt = "Jelaskan apa itu DNS dalam 2 kalimat."  # wajib
waktu = 120                      # opsional, detik, maks 300
harus_ada = ["(?i)nama domain"]  # regex, semua harus cocok di teks akhir
tidak_boleh = ["(?i)co-authored-by"]  # regex, tidak satu pun boleh cocok
bahasa = "id"                    # opsional, satu-satunya nilai: "id"
harus_baca = ["contoh/fixture/catatan\\.md$"]  # regex path tool baca
tidak_boleh_tool = ["shell"]     # nama tool yang tidak boleh dipanggil
maks_kata = 200                  # opsional, jumlah kata teks akhir
harus_ada_kode = ["systemctl restart"]   # regex, dicari HANYA di isi blok kode berpagar
tidak_boleh_kode = ["npm uninstall"]     # regex terlarang HANYA di blok kode (prosa "jangan npm uninstall" tetap lulus)
```

Validasi dilakukan saat memuat:

- `id` wajib unik, cocok `[a-z0-9-]{1,64}`.
- `prompt` wajib string tidak kosong.
- `waktu` bilangan bulat 1..300; `maks_kata` bilangan bulat >= 1.
- Semua regex (`harus_ada`, `tidak_boleh`, `harus_baca`, `harus_ada_kode`, `tidak_boleh_kode`) harus bisa dikompilasi.
- Field tak dikenal ditolak; pesan menyebut nama berkas dan id soal.
- Maksimal 200 soal per berkas.

## Aturan penilaian

`nilai(soal, hasil)` menghasilkan daftar pemeriksaan `{nama, lulus, alasan}`.
Soal dinyatakan lulus hanya jika **semua** pemeriksaan lulus dan runner tidak
melaporkan error.

| Pemeriksaan | Lulus jika |
|---|---|
| `tanpa_error` | Tidak ada error runner dan kode keluar 0. |
| `harus_ada[n]` | Regex ke-n cocok di teks akhir. |
| `tidak_boleh[n]` | Regex terlarang ke-n tidak cocok di teks akhir. |
| `bahasa` | Teks akhir terdeteksi Bahasa Indonesia. |
| `harus_baca[n]` | Regex ke-n cocok dengan path dari tool `read`, `grep`, atau `glob`. |
| `tidak_boleh_tool` | Tidak ada tool terlarang yang dipanggil (tidak peka huruf besar/kecil). |
| `maks_kata` | Jumlah kata teks akhir <= batas. |
| `harus_ada_kode[n]` | Regex ke-n cocok di gabungan isi blok kode (tanpa blok = gagal). |
| `tidak_boleh_kode[n]` | Regex ke-n tidak cocok di isi blok kode (tanpa blok = lulus). |

Setiap percobaan juga diberi `status`: `lulus`, `gagal`, atau `infra`. **infra** = ada error, teks akhir kosong,
dan tidak ada tool dipanggil (contoh: provider "Model is unavailable", kuota habis, waktu habis tanpa output).
Infra tidak dihitung sebagai jawaban buruk: persen di laporan = lulus / (total - infra).

Path tool diambil dari `input.path`, `input.filePath`, `input.pattern`, dan
`input.include` yang ada. Deteksi Bahasa Indonesia memakai heuristik: buang blok
kode berpagar dan teks `inline`, lalu hitung kata fungsi Indonesia vs Inggris.
Jika kata fungsi Indonesia < 3 DAN Inggris < 3, bukti dianggap kurang dan lulus (jawaban pendek berisi kode).
Selain itu lulus jika kata Indonesia >= 2x kata Inggris. Teks 5 kata atau kurang dianggap lulus.

## Runner dan parser event

`jalankan_opencode(prompt, model, cwd, waktu, agen=None)` menjalankan:

```text
opencode run --format json -m MODEL [--agent AGEN] PROMPT
```

Parser membaca stdout JSONL:

- event `text` -> `part.text` digabung ke `Hasil.teks`;
- event `tool_use` -> `{"nama": part.tool, "input": part.state.input}`;
- event `step_finish` -> token `part.tokens.input/output` dijumlahkan;
- event `error` -> dicatat ke `Hasil.error`;
- baris bukan JSON diabaikan tetapi dihitung di `baris_bukan_json`.

`Hasil` berisi `teks`, `tool`, `token_in`, `token_out`, `durasi`, `kode_keluar`,
`error`, `terpotong`, `baris`, dan `baris_bukan_json`. Timeout menghasilkan
`error = "waktu habis"`. Keluaran lebih dari 2.000.000 byte dipotong dan ditandai
`terpotong`.

Untuk pengujian, runner dapat diganti (dependency injection): fungsi
`jalankan_opencode` menerima parameter `pelaksana`, dan `main` menerima parameter
`runner`. Uji tidak pernah memanggil opencode sungguhan.

## Batas keras

Semua konstanta ada di `ujian_agen/batas.py`:

| Konstanta | Nilai | Perilaku saat dilewati |
|---|---:|---|
| `MAKS_SOAL` | 200 | berkas ditolak saat dimuat |
| `MAKS_OUTPUT` | 2.000.000 byte | stdout dipotong, `terpotong = true` |
| `MAKS_WAKTU` | 300 detik | `waktu` soal di atas 300 ditolak |
| `MAKS_MODEL` | 20 | perintah ditolak |
| `MAKS_ULANG` | 5 | perintah ditolak |
| `MAKS_PARALEL` | 4 | perintah ditolak |

Batas yang dilanggar pada input CLI menghasilkan kode keluar 2 dengan pesan
jelas, bukan pemotongan diam-diam.

## Kode keluar

| Kode | Arti |
|---:|---|
| 0 | Semua percobaan lulus (tidak ada gagal maupun infra). |
| 1 | Ada percobaan gagal atau infra (`bandingkan`: ada TURUN). |
| 2 | Input, berkas soal, opsi CLI, atau usage salah. |

## Struktur hasil

JSON memuat versi, waktu, berkas soal, cwd, agen, jumlah ulangan, daftar model,
daftar soal, dan seluruh percobaan. Tiap percobaan menyimpan model, id soal,
nomor ulangan, status lulus, daftar pemeriksaan, teks jawaban, tool yang dipakai,
token, durasi, kode keluar, error, dan penanda terpotong.

Laporan markdown berisi:

1. tabel model x (lulus/total, infra, %, rata-rata detik, total token masuk/keluar);
2. untuk setiap percobaan gagal: model, soal, nomor ulangan, pemeriksaan yang
   gagal beserta alasannya, dan 300 karakter pertama teks jawaban.

## Contoh

- `contoh/dasar.toml` berisi 5 soal umum tanpa data pribadi: bahasa Indonesia,
  regex, larangan atribusi commit, keharusan membaca file, dan larangan shell.
- `contoh/fixture/catatan.md` adalah file yang harus dibaca pada soal terkait.

## Uji

```bash
python3 -m unittest discover -s tests -v
```

Cakupan uji: pemuat soal (valid dan tiap jenis error), batas soal/waktu,
deteksi bahasa, parser event JSONL dengan `tests/data/contoh-opencode.jsonl`,
seluruh jenis pemeriksaan, pemotongan output dan timeout runner, CLI dengan
runner palsu (`--ulang`, `--paralel`, `--soal`, batas model), serta pembuatan
laporan markdown/JSON.

## Lisensi

MIT. Lihat `LICENSE` (pemilik: mahatsafa).
