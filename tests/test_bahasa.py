import unittest
from ujian_agen.bahasa import heuristik_id

class BahasaTest(unittest.TestCase):
    def test_teks_pendek(self):
        self.assertTrue(heuristik_id('ini test'))
    def test_id_dominan(self):
        t = 'kamu bisa menulis dengan baik dan juga harus belajar'
        self.assertTrue(heuristik_id(t))
    def test_en_dominan(self):
        t = 'this is a test and you can try with that method'
        self.assertFalse(heuristik_id(t))
    def test_campur(self):
        t = 'kamu bisa the car dan meja in house juga pada itu'
        self.assertTrue(heuristik_id(t))
    def test_blok_kode(self):
        t = 'ini teks sebelum ```\nkode python\nini bukan\n``` dan setelah'
        # Teks sisa: "ini teks sebelum  dan setelah" -> <5 kata, lulus
        self.assertTrue(heuristik_id(t))
    def test_bukti_kurang_lolos(self):
        # Sesuai SPEC.md v0.2.0 D: id < 3 dan en < 3 harus lulus (bukti kurang)
        t = 'SSH ke server-a menggunakan alamat: `100.64.0.10` Proxy berjalan di port: `8080`'
        # Kata id: di, menggunakan (tidak masuk ID_WORDS), port, berjalan (tidak), ke, alamat, pemilah, pc-a (hanya "di" yg cocok)
        # Kata en: - (tidak ada, selain "port"?)
        # len(kata) > 5, n_id=1, n_en=0 < 3 --> lulus
        self.assertTrue(heuristik_id(t))
    def test_inggris_3_kalimat_gagal(self):
        t = 'This is a test. You must answer in English. Please explain the result.'
        self.assertFalse(heuristik_id(t))
    def test_id_en_kurang_tidak_lulus_kalau_salah_satu_3_atau_lebih(self):
        # id = 2, en = 3 (en >=3) -> HARUS GAGAL
        t = 'ini adalah the test and you'
        self.assertFalse(heuristik_id(t))
        # id = 3, en = 1 (id >=3, id>=2*en) -> id=3, en=1  >=2*1 -> 3>=2, LULUS
        t2 = 'saya adalah manusia dan'
        self.assertTrue(heuristik_id(t2))
