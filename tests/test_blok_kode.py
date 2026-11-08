import unittest
from ujian_agen import penilaian

class DummyHasil:
    def __init__(self, teks=None, error=None, kode_keluar=None, tool=None):
        self.teks = teks
        self.error = error
        self.kode_keluar = kode_keluar
        self.tool = tool

def with_kode(s: str):
    # Helper untuk blok kode
    return f"""prosa awal
```python
{s}
```
prosa akhir"""

class TestBlokKode(unittest.TestCase):
    def test_blok_kode_0(self):
        # Tanpa blok
        self.assertEqual(penilaian.blok_kode("Ini biasa aja"), [])
    def test_blok_kode_1(self):
        # Satu blok
        src = with_kode("x=1\ny=2")
        result = penilaian.blok_kode(src)
        self.assertEqual(len(result), 1)
        self.assertIn("x=1", result[0])
    def test_blok_kode_2(self):
        # Dua blok
        src = (
            "catatan awal\n" +
            "```py\na=1\n```\n" +
            "bukan\n" +
            "```\nb=2\nc=3\n```"
        )
        result = penilaian.blok_kode(src)
        self.assertEqual(len(result), 2)
        self.assertIn("a=1", result[0])
        self.assertIn("b=2", result[1])
        self.assertIn("c=3", result[1])
    def test_blok_kode_tanpa_penutup_diabaikan(self):
        src = "```py\na=1\nb=2\n"  # tanpa blok tutup
        result = penilaian.blok_kode(src)
        self.assertEqual(result, [])

    def test_harus_ada_kode_tanpa_blok(self):
        soal = {"harus_ada_kode": [r"foo", r"bar"]}
        hasil = DummyHasil("hanya prosa tanpa blok")
        nilai = penilaian.nilai(soal, hasil)
        # Semua harus_ada_kode gagal
        ok = [x for x in nilai if x["nama"].startswith("harus_ada_kode")]
        self.assertTrue(all(not row["lulus"] for row in ok))

    def test_tidak_boleh_kode_tanpa_blok(self):
        soal = {"tidak_boleh_kode": [r"foo"]}
        hasil = DummyHasil("hanya prosa tanpa kode")
        nilai = penilaian.nilai(soal, hasil)
        # Semua tidak_boleh_kode lulus
        ok = [x for x in nilai if x["nama"].startswith("tidak_boleh_kode")]
        self.assertTrue(all(row["lulus"] for row in ok))

    def test_tidak_boleh_kode_hanya_di_prosa_lulus(self):
        # Ada string terlarang di prosa, tidak di kode
        soal = {"tidak_boleh_kode": ["terlarang"]}
        hasil = DummyHasil("terlarang\n```py\naman\n```\ncatatan terlarang")
        nilai = penilaian.nilai(soal, hasil)
        ok = [x for x in nilai if x["nama"].startswith("tidak_boleh_kode")]
        self.assertTrue(all(row["lulus"] for row in ok))

    def test_tidak_boleh_kode_dalam_blok_gagal(self):
        soal = {"tidak_boleh_kode": ["gawat"]}
        hasil = DummyHasil(with_kode("ok1\ngawat\nok2"))
        nilai = penilaian.nilai(soal, hasil)
        ok = [x for x in nilai if x["nama"].startswith("tidak_boleh_kode")]
        self.assertTrue(all(not row["lulus"] for row in ok))

    def test_harus_ada_kode_dalam_blok(self):
        soal = {"harus_ada_kode": ["abc123"]}
        hasil = DummyHasil(with_kode("def\nabc123\nghi"))
        nilai = penilaian.nilai(soal, hasil)
        ok = [x for x in nilai if x["nama"].startswith("harus_ada_kode")]
        self.assertTrue(all(row["lulus"] for row in ok))

    def test_field_baru_diterima(self):
        import tempfile, tomllib, os
        fname = None
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False) as f:
                fname = f.name
                isi = b"""[[soal]]\nid = 'abc'\nprompt = 'x'\nharus_ada_kode = ['z']\ntidak_boleh_kode = ['y']\n"""
                f.write(isi)
            from ujian_agen.soal import muat_soal
            data = muat_soal(fname)
            self.assertIsInstance(data[0]["harus_ada_kode"], list)
            self.assertIsInstance(data[0]["tidak_boleh_kode"], list)
        finally:
            if fname and os.path.exists(fname):
                os.remove(fname)

if __name__ == "__main__":
    unittest.main()
