import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ujian_agen.cli import main
from ujian_agen.laporan import buat_markdown, ringkas_model, tabel_ringkas
from ujian_agen.penilaian import status
from ujian_agen.runner import Hasil

SOAL = """
[[soal]]
id = "s1"
prompt = "prompt satu"
harus_ada = ["benar"]
"""


class RunnerInfra:
    def __call__(self, prompt, model, cwd, waktu, agen=None):
        return Hasil(
            teks="",
            tool=[],
            error="waktu habis",
            durasi=45.0,
            kode_keluar=None,
        )


class InfraTest(unittest.TestCase):
    def test_status_tiga_kasus(self):
        soal = {"id": "s1", "harus_ada": ["benar"]}

        # 1. infra: error ada, teks kosong, tool kosong
        hasil_infra = Hasil(error="waktu habis", teks="", tool=[])
        pemeriksaan_infra = [{"nama": "tanpa_error", "lulus": False, "alasan": "error"}]
        self.assertEqual(status(soal, hasil_infra, pemeriksaan_infra), "infra")

        # 2. gagal: error ada tapi ada teks
        hasil_gagal = Hasil(error="error x", teks="ada teks", tool=[])
        pemeriksaan_gagal = [{"nama": "tanpa_error", "lulus": False, "alasan": "error"}]
        self.assertEqual(status(soal, hasil_gagal, pemeriksaan_gagal), "gagal")

        # 3. lulus: tanpa error, pemeriksaan lulus semua
        hasil_lulus = Hasil(error=None, teks="jawaban benar", tool=[])
        pemeriksaan_lulus = [
            {"nama": "tanpa_error", "lulus": True, "alasan": "ok"},
            {"nama": "harus_ada[1]", "lulus": True, "alasan": "cocok"},
        ]
        self.assertEqual(status(soal, hasil_lulus, pemeriksaan_lulus), "lulus")

    def test_persen_laporan_dengan_satu_infra(self):
        data = {
            "model": ["m1"],
            "hasil": [
                {
                    "model": "m1",
                    "soal": "s1",
                    "ulangan": 1,
                    "lulus": True,
                    "status": "lulus",
                    "durasi": 1.0,
                    "pemeriksaan": [],
                    "teks": "benar",
                },
                {
                    "model": "m1",
                    "soal": "s1",
                    "ulangan": 2,
                    "lulus": False,
                    "status": "gagal",
                    "durasi": 1.0,
                    "pemeriksaan": [],
                    "teks": "salah",
                },
                {
                    "model": "m1",
                    "soal": "s1",
                    "ulangan": 3,
                    "lulus": False,
                    "status": "infra",
                    "durasi": 45.0,
                    "pemeriksaan": [],
                    "teks": "",
                    "error": "waktu habis",
                },
            ],
        }
        ringkasan = ringkas_model(data)
        self.assertEqual(len(ringkasan), 1)
        r = ringkasan[0]
        self.assertEqual(r["total"], 3)
        self.assertEqual(r["lulus"], 1)
        self.assertEqual(r["infra"], 1)
        # persen = lulus / (total - infra) * 100 = 1 / 2 * 100 = 50.0
        self.assertAlmostEqual(r["persen"], 50.0)

        md = buat_markdown(data)
        self.assertIn("| `m1` | 1/3 | 1 | 50.0 |", md)

        tbl = tabel_ringkas(data)
        self.assertIn("1/3", tbl)
        self.assertIn("50.0", tbl)

    def test_semua_infra_tampilkan_dash(self):
        data = {
            "model": ["m1"],
            "hasil": [
                {
                    "model": "m1",
                    "soal": "s1",
                    "ulangan": 1,
                    "lulus": False,
                    "status": "infra",
                    "durasi": 45.0,
                    "pemeriksaan": [],
                    "teks": "",
                    "error": "waktu habis",
                },
                {
                    "model": "m1",
                    "soal": "s1",
                    "ulangan": 2,
                    "lulus": False,
                    "status": "infra",
                    "durasi": 45.0,
                    "pemeriksaan": [],
                    "teks": "",
                    "error": "waktu habis",
                },
            ],
        }
        ringkasan = ringkas_model(data)
        self.assertEqual(len(ringkasan), 1)
        r = ringkasan[0]
        self.assertEqual(r["total"], 2)
        self.assertEqual(r["infra"], 2)
        self.assertIsNone(r["persen"])

        md = buat_markdown(data)
        self.assertIn("| `m1` | 0/2 | 2 | - |", md)

        tbl = tabel_ringkas(data)
        self.assertIn("-", tbl)

    def test_cli_kode_keluar_satu_jika_ada_infra(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            soal_path = tmp / "soal.toml"
            soal_path.write_text(SOAL, encoding="utf-8")
            keluaran = tmp / "hasil"

            out = io.StringIO()
            err = io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                kode = main(
                    [
                        "jalankan",
                        str(soal_path),
                        "-m",
                        "m1",
                        "--cwd",
                        str(tmp),
                        "--keluaran",
                        str(keluaran),
                    ],
                    runner=RunnerInfra(),
                )
            self.assertEqual(kode, 1)

            berkas = sorted(keluaran.glob("hasil-*.json"))
            self.assertEqual(len(berkas), 1)
            data = json.loads(berkas[0].read_text(encoding="utf-8"))
            self.assertEqual(data["hasil"][0]["status"], "infra")
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
