import unittest
from ujian_agen.soal import muat_soal, SoalFormatError, SoalValidasiError
import tempfile, shutil, os

def tulis_toml(isitoml:str):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "uji.toml")
    with open(p,"w") as f: f.write(isitoml)
    return d,p

class SoalTest(unittest.TestCase):
    def test_muat_valid(self):
        t = """
[[soal]]
id="a1"
prompt="Test"
"""
        d,p = tulis_toml(t)
        try:
            soal = muat_soal(p)
            self.assertEqual(soal[0]["id"],"a1")
        finally:
            shutil.rmtree(d)
    def test_field_salah(self):
        t = """
[[soal]]
id="a1"
prompt="test"
FIELDX=1
"""
        d,p = tulis_toml(t)
        try:
            with self.assertRaises(SoalFormatError): muat_soal(p)
        finally: shutil.rmtree(d)
    def test_duplikat_id(self):
        t = """
[[soal]]
id="a1"
prompt="test"
[[soal]]
id="a1"
prompt="test"
"""
        d,p = tulis_toml(t)
        try:
            with self.assertRaises(SoalFormatError): muat_soal(p)
        finally: shutil.rmtree(d)
    def test_regex_tidak_valid(self):
        t = """
[[soal]]
id="a2"
prompt="XX"
harus_ada=["("]
"""
        d,p = tulis_toml(t)
        try:
            with self.assertRaises(SoalFormatError): muat_soal(p)
        finally: shutil.rmtree(d)
    def test_soal_kebanyakan(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "uji.toml")
        with open(p,"w") as f:
            f.write("\n".join([
                "[[soal]]\nid=\"a{}\"\nprompt=\"p\"".format(i) for i in range(201)])
            )
        try:
            with self.assertRaises(SoalValidasiError): muat_soal(p)
        finally: shutil.rmtree(d)
