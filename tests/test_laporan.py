import unittest

from ujian_agen.laporan import buat_markdown, ringkas_model, tabel_ringkas, tulis_markdown

DATA = {
    "versi": "0.1.0",
    "dibuat": "2026-11-08T20:00:00+07:00",
    "berkas_soal": "contoh/dasar.toml",
    "cwd": ".",
    "agen": "build",
    "ulang": 2,
    "model": ["m1", "m2"],
    "hasil": [
        {
            "model": "m1",
            "soal": "s1",
            "ulangan": 1,
            "lulus": True,
            "durasi": 1.0,
            "token_in": 100,
            "token_out": 10,
            "pemeriksaan": [{"nama": "tanpa_error", "lulus": True, "alasan": "ok"}],
            "teks": "jawaban",
            "error": None,
        },
        {
            "model": "m1",
            "soal": "s1",
            "ulangan": 2,
            "lulus": False,
            "durasi": 3.0,
            "token_in": 50,
            "token_out": 5,
            "pemeriksaan": [
                {"nama": "harus_ada[1]", "lulus": False, "alasan": "tidak cocok"}
            ],
            "teks": "x" * 400,
            "error": None,
        },
        {
            "model": "m2",
            "soal": "s2",
            "ulangan": 1,
            "lulus": True,
            "durasi": 2.0,
            "token_in": 7,
            "token_out": 3,
            "pemeriksaan": [],
            "teks": "ok",
            "error": None,
        },
    ],
}


class RingkasanTest(unittest.TestCase):
    def test_ringkas_model(self):
        ringkasan = ringkas_model(DATA)
        self.assertEqual([r["model"] for r in ringkasan], ["m1", "m2"])
        m1 = ringkasan[0]
        self.assertEqual(m1["lulus"], 1)
        self.assertEqual(m1["total"], 2)
        self.assertAlmostEqual(m1["persen"], 50.0)
        self.assertAlmostEqual(m1["rata_detik"], 2.0)
        self.assertEqual(m1["token_in"], 150)
        self.assertEqual(m1["token_out"], 15)

        m2 = ringkasan[1]
        self.assertEqual(m2["total"], 1)
        self.assertAlmostEqual(m2["persen"], 100.0)

    def test_ringkas_model_kosong(self):
        self.assertEqual(ringkas_model({"model": ["m"], "hasil": []})[0]["total"], 0)

    def test_model_dari_hasil(self):
        data = {"hasil": [{"model": "baru", "lulus": True}]}
        self.assertEqual(ringkas_model(data)[0]["model"], "baru")


class MarkdownTest(unittest.TestCase):
    def test_isi_laporan(self):
        md = buat_markdown(DATA)
        self.assertIn("# Laporan ujian-agen", md)
        self.assertIn("| Model | Lulus/Total | Infra | % |", md)
        self.assertIn("| `m1` | 1/2 | 0 | 50.0 | 2.00 | 150 | 15 |", md)
        self.assertIn("harus_ada[1]", md)
        self.assertIn("tidak cocok", md)
        self.assertIn("x" * 300, md)
        self.assertNotIn("x" * 301, md)

    def test_tanpa_gagal(self):
        data = {
            "model": ["m"],
            "hasil": [
                {
                    "model": "m",
                    "soal": "s",
                    "lulus": True,
                    "pemeriksaan": [],
                    "teks": "ok",
                }
            ],
        }
        md = buat_markdown(data)
        self.assertIn("Tidak ada kegagalan", md)

    def test_pipe_dan_baris_baru_di_escape(self):
        data = {
            "model": ["m|1"],
            "hasil": [
                {
                    "model": "m|1",
                    "soal": "s",
                    "lulus": False,
                    "pemeriksaan": [
                        {"nama": "a|b", "lulus": False, "alasan": "x\ny"}
                    ],
                    "teks": "z",
                }
            ],
        }
        md = buat_markdown(data)
        self.assertIn("m\\|1", md)
        self.assertIn("a\\|b", md)
        self.assertIn("x y", md)

    def test_tulis_markdown(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            tujuan = Path(d) / "sub" / "laporan.md"
            hasil = tulis_markdown(DATA, tujuan)
            self.assertEqual(hasil, tujuan)
            self.assertTrue(tujuan.is_file())

    def test_tabel_ringkas(self):
        teks = tabel_ringkas(DATA)
        self.assertIn("Model", teks)
        self.assertIn("m1", teks)
        self.assertIn("1/2", teks)


if __name__ == "__main__":
    unittest.main()
