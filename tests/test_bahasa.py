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
