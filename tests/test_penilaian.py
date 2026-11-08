import unittest

from ujian_agen.penilaian import lulus, nilai, paths_tool
from ujian_agen.runner import Hasil


def buat_hasil(**kwargs) -> Hasil:
    data = {
        "teks": "",
        "tool": [],
        "token_in": 0,
        "token_out": 0,
        "durasi": 0.0,
        "kode_keluar": 0,
        "error": None,
    }
    data.update(kwargs)
    return Hasil(**data)


def ambil(daftar, nama):
    return next(item for item in daftar if item["nama"] == nama)


class PemeriksaanTest(unittest.TestCase):
    def test_tanpa_error_lulus(self):
        daftar = nilai({"id": "a", "prompt": "p"}, buat_hasil())
        self.assertTrue(lulus(daftar))
        self.assertTrue(ambil(daftar, "tanpa_error")["lulus"])

    def test_error_gagal(self):
        daftar = nilai({}, buat_hasil(error="waktu habis", kode_keluar=None))
        self.assertFalse(ambil(daftar, "tanpa_error")["lulus"])
        self.assertIn("waktu habis", ambil(daftar, "tanpa_error")["alasan"])
        self.assertFalse(lulus(daftar))

    def test_kode_keluar_gagal(self):
        daftar = nilai({}, buat_hasil(kode_keluar=2))
        self.assertFalse(ambil(daftar, "tanpa_error")["lulus"])
        self.assertIn("kode keluar 2", ambil(daftar, "tanpa_error")["alasan"])

    def test_harus_ada(self):
        soal = {"harus_ada": ["(?i)dns", "domain"]}
        daftar = nilai(soal, buat_hasil(teks="DNS adalah nama domain."))
        self.assertTrue(ambil(daftar, "harus_ada[1]")["lulus"])
        self.assertTrue(ambil(daftar, "harus_ada[2]")["lulus"])

        gagal = nilai(soal, buat_hasil(teks="Tidak relevan."))
        self.assertFalse(ambil(gagal, "harus_ada[1]")["lulus"])
        self.assertIn("(?i)dns", ambil(gagal, "harus_ada[1]")["alasan"])

    def test_tidak_boleh(self):
        soal = {"tidak_boleh": ["(?i)co-authored-by"]}
        daftar = nilai(soal, buat_hasil(teks="Pesan biasa."))
        self.assertTrue(ambil(daftar, "tidak_boleh[1]")["lulus"])

        gagal = nilai(soal, buat_hasil(teks="Co-Authored-By: X"))
        self.assertFalse(ambil(gagal, "tidak_boleh[1]")["lulus"])
        self.assertIn("ditemukan", ambil(gagal, "tidak_boleh[1]")["alasan"])

    def test_bahasa(self):
        soal = {"bahasa": "id"}
        daftar = nilai(
            soal, buat_hasil(teks="jawaban ini sudah benar dan jelas")
        )
        self.assertTrue(ambil(daftar, "bahasa")["lulus"])

        gagal = nilai(
            soal,
            buat_hasil(teks="this is a test and you can try with that method"),
        )
        self.assertFalse(ambil(gagal, "bahasa")["lulus"])

    def test_bahasa_tidak_diminta(self):
        daftar = nilai({}, buat_hasil(teks="english only here and there"))
        self.assertFalse(any(p["nama"] == "bahasa" for p in daftar))

    def test_harus_baca(self):
        soal = {"harus_baca": [r"catatan\.md$"]}
        tool = [{"nama": "read", "input": {"path": "contoh/fixture/catatan.md"}}]
        daftar = nilai(soal, buat_hasil(tool=tool))
        self.assertTrue(ambil(daftar, "harus_baca[1]")["lulus"])

        # Tool shell tidak dihitung sebagai pembacaan file.
        tool_shell = [
            {"nama": "shell", "input": {"path": "contoh/fixture/catatan.md"}}
        ]
        gagal = nilai(soal, buat_hasil(tool=tool_shell))
        self.assertFalse(ambil(gagal, "harus_baca[1]")["lulus"])

    def test_harus_baca_grep_pattern(self):
        soal = {"harus_baca": [r"catatan\.md"]}
        tool = [
            {
                "nama": "grep",
                "input": {"pattern": "kode", "include": "contoh/fixture/catatan.md"},
            }
        ]
        daftar = nilai(soal, buat_hasil(tool=tool))
        self.assertTrue(ambil(daftar, "harus_baca[1]")["lulus"])

    def test_paths_tool_semua_kunci(self):
        tool = [
            {"nama": "read", "input": {"path": "/a", "filePath": "/b"}},
            {"nama": "grep", "input": {"pattern": "p", "include": "/c"}},
            {"nama": "glob", "input": {"include": ["/d", "/e"]}},
            {"nama": "shell", "input": {"command": "ls"}},
        ]
        hasil = paths_tool(buat_hasil(tool=tool))
        self.assertEqual(
            hasil,
            [
                ("read", "/a"),
                ("read", "/b"),
                ("grep", "p"),
                ("grep", "/c"),
                ("glob", "/d"),
                ("glob", "/e"),
            ],
        )

    def test_tidak_boleh_tool(self):
        soal = {"tidak_boleh_tool": ["shell", "bash"]}
        daftar = nilai(
            soal, buat_hasil(tool=[{"nama": "read", "input": {"path": "/x"}}])
        )
        self.assertTrue(ambil(daftar, "tidak_boleh_tool")["lulus"])

        gagal = nilai(soal, buat_hasil(tool=[{"nama": "SHELL", "input": {}}]))
        self.assertFalse(ambil(gagal, "tidak_boleh_tool")["lulus"])
        self.assertIn("shell", ambil(gagal, "tidak_boleh_tool")["alasan"])

    def test_maks_kata(self):
        soal = {"maks_kata": 3}
        daftar = nilai(soal, buat_hasil(teks="satu dua tiga"))
        self.assertTrue(ambil(daftar, "maks_kata")["lulus"])

        gagal = nilai(soal, buat_hasil(teks="satu dua tiga empat"))
        self.assertFalse(ambil(gagal, "maks_kata")["lulus"])
        self.assertIn("4 kata", ambil(gagal, "maks_kata")["alasan"])

    def test_semua_pemeriksaan_lulus(self):
        soal = {
            "harus_ada": ["jawaban"],
            "tidak_boleh": ["rahasia"],
            "bahasa": "id",
            "harus_baca": [r"catatan\.md$"],
            "tidak_boleh_tool": ["shell"],
            "maks_kata": 20,
        }
        hasil = buat_hasil(
            teks="jawaban ini sudah benar dan jelas",
            tool=[{"nama": "read", "input": {"path": "/tmp/catatan.md"}}],
        )
        daftar = nilai(soal, hasil)
        self.assertTrue(lulus(daftar), daftar)

    def test_hasil_fake_tanpa_atribut(self):
        class Sederhana:
            teks = "jawaban ini sudah benar dan jelas"
            tool = []
            error = None
            kode_keluar = 0

        daftar = nilai({"harus_ada": ["jawaban"]}, Sederhana())
        self.assertTrue(lulus(daftar))


if __name__ == "__main__":
    unittest.main()
