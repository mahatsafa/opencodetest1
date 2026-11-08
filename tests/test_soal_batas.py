import os
import shutil
import tempfile
import unittest

from ujian_agen.batas import MAKS_SOAL, MAKS_WAKTU
from ujian_agen.soal import (
    SoalFormatError,
    SoalValidasiError,
    compile_regex,
    muat_soal,
)


class SoalBatasTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "soal.toml")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def tulis(self, isi: str):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(isi)

    def test_semua_field_valid(self):
        self.tulis(
            """
[[soal]]
id = "lengkap-01"
prompt = "Contoh prompt"
waktu = 45
harus_ada = ["a"]
tidak_boleh = ["b"]
bahasa = "id"
harus_baca = ["x\\\\.md$"]
tidak_boleh_tool = ["shell"]
maks_kata = 100
"""
        )
        soal = muat_soal(self.path)
        self.assertEqual(len(soal), 1)
        self.assertEqual(soal[0]["waktu"], 45)

    def test_id_huruf_besar_ditolak(self):
        self.tulis('[[soal]]\nid = "HurufBesar"\nprompt = "p"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_id_terlalu_panjang(self):
        self.tulis(f'[[soal]]\nid = "{"a" * 65}"\nprompt = "p"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_prompt_wajib(self):
        self.tulis('[[soal]]\nid = "a1"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_prompt_kosong(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "   "\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_waktu_nol(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nwaktu = 0\n')
        with self.assertRaises(SoalValidasiError):
            muat_soal(self.path)

    def test_waktu_melebihi_batas(self):
        self.tulis(
            f'[[soal]]\nid = "a1"\nprompt = "p"\nwaktu = {MAKS_WAKTU + 1}\n'
        )
        with self.assertRaises(SoalValidasiError) as ctx:
            muat_soal(self.path)
        self.assertIn(str(MAKS_WAKTU), str(ctx.exception))

    def test_waktu_bukan_bulat(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nwaktu = "60"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_bahasa_lain_ditolak(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nbahasa = "en"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_regex_bukan_list(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nharus_ada = "x"\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_regex_bukan_string(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nharus_ada = [1]\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_maks_kata_nol(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nmaks_kata = 0\n')
        with self.assertRaises(SoalValidasiError):
            muat_soal(self.path)

    def test_toml_rusak(self):
        self.tulis("[[soal]\nid = 'x'\n")
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_berkas_tidak_ada(self):
        with self.assertRaises(SoalFormatError):
            muat_soal(os.path.join(self.dir, "tidak-ada.toml"))

    def test_tanpa_soal(self):
        self.tulis('x = 1\n')
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_soal_kosong(self):
        self.tulis("soal = []\n")
        with self.assertRaises(SoalFormatError):
            muat_soal(self.path)

    def test_field_tak_dikenal_sebut_berkas_dan_id(self):
        self.tulis('[[soal]]\nid = "a1"\nprompt = "p"\nfoo = 1\n')
        with self.assertRaises(SoalFormatError) as ctx:
            muat_soal(self.path)
        pesan = str(ctx.exception)
        self.assertIn("foo", pesan)
        self.assertIn("a1", pesan)
        self.assertIn(self.path, pesan)

    def test_batas_soal_konstanta(self):
        self.assertEqual(MAKS_SOAL, 200)

    def test_compile_regex_mengembalikan_pattern(self):
        pola = compile_regex("(?i)halo")
        self.assertTrue(pola.search("HALO"))


if __name__ == "__main__":
    unittest.main()
