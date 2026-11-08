import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ujian_agen.batas import MAKS_MODEL, MAKS_ULANG, MAKS_WAKTU
from ujian_agen.cli import main
from ujian_agen.runner import Hasil

SOAL_SATU = """
[[soal]]
id = "s1"
prompt = "prompt satu"
harus_ada = ["benar"]
waktu = 45
"""

SOAL_DUA = SOAL_SATU + """
[[soal]]
id = "s2"
prompt = "prompt dua"
harus_ada = ["benar"]
"""


class RunnerPalsu:
    def __init__(self, gagal_model=None):
        self.gagal_model = gagal_model
        self.panggilan = []

    def __call__(self, prompt, model, cwd, waktu, agen=None):
        self.panggilan.append(
            {
                "prompt": prompt,
                "model": model,
                "cwd": cwd,
                "waktu": waktu,
                "agen": agen,
            }
        )
        teks = "jawaban salah" if model == self.gagal_model else "jawaban benar"
        return Hasil(
            teks=teks,
            token_in=10,
            token_out=5,
            durasi=0.25,
            kode_keluar=0,
        )


class RunnerBergantian:
    def __init__(self):
        self.jumlah = 0

    def __call__(self, prompt, model, cwd, waktu, agen=None):
        self.jumlah += 1
        teks = "jawaban benar" if self.jumlah % 2 else "jawaban salah"
        return Hasil(teks=teks, kode_keluar=0, durasi=0.1)


class RunnerRusak:
    def __call__(self, prompt, model, cwd, waktu, agen=None):
        raise RuntimeError("meledak")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.soal = self.dir / "soal.toml"
        self.soal.write_text(SOAL_SATU, encoding="utf-8")
        self.keluaran = self.dir / "hasil"

    def tearDown(self):
        shutil.rmtree(self.dir)

    def jalankan(self, argumen, runner):
        keluaran = io.StringIO()
        galat = io.StringIO()
        with redirect_stdout(keluaran), redirect_stderr(galat):
            kode = main(argumen, runner=runner)
        return kode, keluaran.getvalue(), galat.getvalue()

    def baca_json(self):
        berkas = sorted(self.keluaran.glob("hasil-*.json"))
        self.assertEqual(len(berkas), 1, berkas)
        return json.loads(berkas[0].read_text(encoding="utf-8")), berkas[0]

    def test_jalankan_lulus(self):
        palsu = RunnerPalsu()
        kode, stdout, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
                "--agen",
                "build",
            ],
            palsu,
        )
        self.assertEqual(kode, 0)
        self.assertIn("Lulus/Total", stdout)
        data, path = self.baca_json()
        self.assertEqual(data["model"], ["m1"])
        self.assertEqual(data["ulang"], 1)
        self.assertEqual(len(data["hasil"]), 1)
        self.assertTrue(data["hasil"][0]["lulus"])
        self.assertEqual(data["hasil"][0]["teks"], "jawaban benar")
        self.assertTrue(path.with_suffix(".md").is_file())
        self.assertEqual(palsu.panggilan[0]["waktu"], 45)
        self.assertEqual(palsu.panggilan[0]["agen"], "build")
        self.assertEqual(palsu.panggilan[0]["cwd"], str(self.dir))

    def test_jalankan_gagal_kode_1(self):
        palsu = RunnerPalsu(gagal_model="m1")
        kode, stdout, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            palsu,
        )
        self.assertEqual(kode, 1)
        data, path = self.baca_json()
        self.assertFalse(data["hasil"][0]["lulus"])
        md = path.with_suffix(".md").read_text(encoding="utf-8")
        self.assertIn("Soal gagal", md)
        self.assertIn("harus_ada[1]", md)
        self.assertIn("jawaban salah", md)

    def test_waktu_default(self):
        palsu = RunnerPalsu()
        self.soal.write_text(
            '[[soal]]\nid = "s1"\nprompt = "p"\nharus_ada = ["benar"]\n',
            encoding="utf-8",
        )
        kode, _, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            palsu,
        )
        self.assertEqual(kode, 0)
        self.assertEqual(palsu.panggilan[0]["waktu"], MAKS_WAKTU)

    def test_ulang_dan_skor_proporsi(self):
        palsu = RunnerBergantian()
        kode, stdout, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
                "--ulang",
                "3",
            ],
            palsu,
        )
        self.assertEqual(kode, 1)
        self.assertEqual(palsu.jumlah, 3)
        data, _ = self.baca_json()
        self.assertEqual(len(data["hasil"]), 3)
        self.assertEqual(sum(1 for h in data["hasil"] if h["lulus"]), 2)
        self.assertIn("2/3", stdout)

    def test_soal_dipilih(self):
        self.soal.write_text(SOAL_DUA, encoding="utf-8")
        palsu = RunnerPalsu()
        kode, _, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
                "--soal",
                "s2",
            ],
            palsu,
        )
        self.assertEqual(kode, 0)
        self.assertEqual([p["prompt"] for p in palsu.panggilan], ["prompt dua"])

    def test_soal_tidak_dikenal(self):
        palsu = RunnerPalsu()
        kode, _, galat = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
                "--soal",
                "tidak-ada",
            ],
            palsu,
        )
        self.assertEqual(kode, 2)
        self.assertIn("tidak ditemukan", galat)
        self.assertEqual(palsu.panggilan, [])

    def test_paralel(self):
        self.soal.write_text(SOAL_DUA, encoding="utf-8")
        palsu = RunnerPalsu()
        kode, _, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "-m",
                "m2",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
                "--ulang",
                "2",
                "--paralel",
                "2",
            ],
            palsu,
        )
        self.assertEqual(kode, 0)
        self.assertEqual(len(palsu.panggilan), 8)
        data, _ = self.baca_json()
        self.assertEqual(len(data["hasil"]), 8)

    def test_batas_model(self):
        palsu = RunnerPalsu()
        argumen = ["jalankan", str(self.soal)]
        for i in range(MAKS_MODEL + 1):
            argumen.extend(["-m", f"m{i}"])
        argumen.extend(["--cwd", str(self.dir), "--keluaran", str(self.keluaran)])
        kode, _, galat = self.jalankan(argumen, palsu)
        self.assertEqual(kode, 2)
        self.assertIn("MAKS_MODEL", galat)
        self.assertEqual(palsu.panggilan, [])

    def test_batas_ulang(self):
        kode, _, galat = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--ulang",
                str(MAKS_ULANG + 1),
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            RunnerPalsu(),
        )
        self.assertEqual(kode, 2)
        self.assertIn("--ulang", galat)

    def test_batas_paralel(self):
        kode, _, galat = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--paralel",
                "5",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            RunnerPalsu(),
        )
        self.assertEqual(kode, 2)
        self.assertIn("--paralel", galat)

    def test_cwd_tidak_ada(self):
        kode, _, galat = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir / "tidak-ada"),
                "--keluaran",
                str(self.keluaran),
            ],
            RunnerPalsu(),
        )
        self.assertEqual(kode, 2)
        self.assertIn("cwd", galat)

    def test_runner_melempar_exception(self):
        kode, _, _ = self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            RunnerRusak(),
        )
        self.assertEqual(kode, 1)
        data, _ = self.baca_json()
        self.assertIn("runner gagal", data["hasil"][0]["error"])
        self.assertFalse(data["hasil"][0]["lulus"])

    def test_periksa_valid(self):
        kode, stdout, _ = self.jalankan(["periksa", str(self.soal)], RunnerPalsu())
        self.assertEqual(kode, 0)
        self.assertIn("OK: 1 soal", stdout)

    def test_periksa_contoh(self):
        contoh = Path(__file__).resolve().parent.parent / "contoh" / "dasar.toml"
        kode, stdout, _ = self.jalankan(["periksa", str(contoh)], RunnerPalsu())
        self.assertEqual(kode, 0)
        self.assertIn("OK: 5 soal", stdout)

    def test_periksa_salah(self):
        self.soal.write_text('[[soal]]\nid = "X"\nprompt = "p"\n', encoding="utf-8")
        kode, _, galat = self.jalankan(["periksa", str(self.soal)], RunnerPalsu())
        self.assertEqual(kode, 2)
        self.assertIn("ID tidak valid", galat)

    def test_laporan_cetak_ulang(self):
        self.jalankan(
            [
                "jalankan",
                str(self.soal),
                "-m",
                "m1",
                "--cwd",
                str(self.dir),
                "--keluaran",
                str(self.keluaran),
            ],
            RunnerPalsu(gagal_model="m1"),
        )
        _, path = self.baca_json()
        path.with_suffix(".md").unlink()
        kode, stdout, _ = self.jalankan(["laporan", str(path)], RunnerPalsu())
        self.assertEqual(kode, 1)
        self.assertTrue(path.with_suffix(".md").is_file())
        self.assertIn("Soal gagal", path.with_suffix(".md").read_text(encoding="utf-8"))
        self.assertIn("MD:", stdout)

    def test_laporan_file_tidak_ada(self):
        kode, _, galat = self.jalankan(
            ["laporan", str(self.dir / "tidak.json")], RunnerPalsu()
        )
        self.assertEqual(kode, 2)
        self.assertIn("tidak ditemukan", galat)

    def test_laporan_json_rusak(self):
        path = self.dir / "rusak.json"
        path.write_text("{bukan json", encoding="utf-8")
        kode, _, galat = self.jalankan(["laporan", str(path)], RunnerPalsu())
        self.assertEqual(kode, 2)
        self.assertIn("gagal membaca", galat)


if __name__ == "__main__":
    unittest.main()
