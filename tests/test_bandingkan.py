import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from ujian_agen.bandingkan import (
    BandingkanError,
    bandingkan,
    muat,
    status_per_pasangan,
)
from ujian_agen.cli import main


def _data(*hasil):
    return {"hasil": list(hasil)}


def _item(model, soal, status=None, lulus=None, ulangan=1, error=None, teks="", tool=None):
    item = {
        "model": model,
        "soal": soal,
        "ulangan": ulangan,
        "error": error,
        "teks": teks,
        "tool": tool,
    }
    if status is not None:
        item["status"] = status
    if lulus is not None:
        item["lulus"] = lulus
    return item


class StatusPerPasanganTest(unittest.TestCase):
    def test_field_status_dan_fallback_bool(self):
        data = _data(
            _item("m1", "s1", status="lulus"),
            _item("m1", "s2", lulus=False),
            _item("m2", "s1", lulus=True),
        )
        peta = status_per_pasangan(data)
        self.assertEqual(peta[("m1", "s1")], "lulus")
        self.assertEqual(peta[("m1", "s2")], "gagal")
        self.assertEqual(peta[("m2", "s1")], "lulus")

    def test_tanpa_status_error_teks_kosong_jadi_infra(self):
        data = _data(
            _item("m1", "s1", error="ada", teks=""),
            _item("m1", "s2", error="ada", teks="ada"),
            _item("m2", "s1", error="ada", teks="", tool="ada"),
            _item("m2", "s2", error="ada", teks="", tool=""),
        )
        peta = status_per_pasangan(data)
        self.assertEqual(peta[("m1", "s1")], "infra")
        self.assertEqual(peta[("m1", "s2")], "gagal")
        self.assertEqual(peta[("m2", "s1")], "gagal")
        self.assertEqual(peta[("m2", "s2")], "infra")

    def test_ulangan_satu_lulus_satu_gagal_jadi_lulus(self):
        data = _data(
            _item("m1", "s1", status="lulus", ulangan=1),
            _item("m1", "s1", status="gagal", ulangan=2),
        )
        self.assertEqual(status_per_pasangan(data)[("m1", "s1")], "lulus")

    def test_ulangan_dua_gagal_satu_lulus_jadi_gagal(self):
        data = _data(
            _item("m1", "s1", status="gagal", ulangan=1),
            _item("m1", "s1", status="gagal", ulangan=2),
            _item("m1", "s1", status="lulus", ulangan=3),
        )
        self.assertEqual(status_per_pasangan(data)[("m1", "s1")], "gagal")

    def test_infra_diabaikan_lalu_semua_infra(self):
        campur = _data(
            _item("m1", "s1", status="infra", ulangan=1),
            _item("m1", "s1", status="lulus", ulangan=2),
        )
        self.assertEqual(status_per_pasangan(campur)[("m1", "s1")], "lulus")
        semua = _data(
            _item("m1", "s1", status="infra", ulangan=1),
            _item("m1", "s1", status="infra", ulangan=2),
        )
        self.assertEqual(status_per_pasangan(semua)[("m1", "s1")], "infra")

    def test_batas_proporsi_tepat_setengah_dan_di_bawah(self):
        tepat = _data(
            _item("m1", "s1", status="lulus", ulangan=1),
            _item("m1", "s1", status="gagal", ulangan=2),
            _item("m1", "s2", status="lulus", ulangan=1),
            _item("m1", "s2", status="gagal", ulangan=2),
            _item("m1", "s2", status="gagal", ulangan=3),
            _item("m1", "s2", status="infra", ulangan=4),
        )
        peta = status_per_pasangan(tepat)
        self.assertEqual(peta[("m1", "s1")], "lulus")
        self.assertEqual(peta[("m1", "s2")], "gagal")


class BandingkanTest(unittest.TestCase):
    def test_naik_turun_tetap_dan_infra_ke_lulus(self):
        lama = _data(
            _item("m1", "s1", status="gagal"),
            _item("m1", "s2", status="lulus"),
            _item("m1", "s3", status="lulus"),
            _item("m2", "s1", status="infra"),
            _item("m2", "s2", status="gagal"),
        )
        baru = _data(
            _item("m1", "s1", status="lulus"),
            _item("m1", "s2", status="gagal"),
            _item("m1", "s3", status="lulus"),
            _item("m2", "s1", status="lulus"),
            _item("m2", "s2", status="gagal"),
        )
        hasil = bandingkan(lama, baru)
        tanda = {(b["model"], b["soal"]): b["tanda"] for b in hasil["baris"]}
        self.assertEqual(tanda[("m1", "s1")], "NAIK")
        self.assertEqual(tanda[("m1", "s2")], "TURUN")
        self.assertEqual(tanda[("m1", "s3")], "TETAP")
        self.assertEqual(tanda[("m2", "s1")], "NAIK")
        self.assertEqual(tanda[("m2", "s2")], "TETAP")

        status = {
            (b["model"], b["soal"]): (b["status_lama"], b["status_baru"])
            for b in hasil["baris"]
        }
        self.assertEqual(status[("m2", "s1")], ("infra", "lulus"))
        self.assertEqual(hasil["tidak_terbandingkan"], [])

    def test_lulus_ke_infra_tetap_bukan_turun(self):
        lama = _data(_item("m1", "s1", status="lulus"), _item("m1", "s2", status="infra"))
        baru = _data(_item("m1", "s1", status="infra"), _item("m1", "s2", status="gagal"))
        tanda = {
            b["soal"]: b["tanda"] for b in bandingkan(lama, baru)["baris"]
        }
        self.assertEqual(tanda["s1"], "TETAP")
        self.assertEqual(tanda["s2"], "TETAP")

    def test_ringkasan_dua_model(self):
        lama = _data(
            _item("m1", "s1", status="gagal"),
            _item("m1", "s2", status="lulus"),
            _item("m2", "s1", status="lulus"),
        )
        baru = _data(
            _item("m1", "s1", status="lulus"),
            _item("m1", "s2", status="lulus"),
            _item("m2", "s1", status="gagal"),
        )
        ringkas = {r["model"]: r for r in bandingkan(lama, baru)["ringkasan"]}
        self.assertEqual(ringkas["m1"]["lulus_lama"], 1)
        self.assertEqual(ringkas["m1"]["lulus_baru"], 2)
        self.assertEqual(ringkas["m2"]["lulus_lama"], 1)
        self.assertEqual(ringkas["m2"]["lulus_baru"], 0)

    def test_hanya_di_satu_berkas_tidak_terbandingkan(self):
        lama = _data(
            _item("m1", "s1", status="lulus"),
            _item("m1", "s2", status="gagal"),
            _item("m3", "s9", status="lulus"),
        )
        baru = _data(
            _item("m1", "s1", status="gagal"),
            _item("m2", "s1", status="lulus"),
            _item("m2", "s2", status="lulus"),
        )
        hasil = bandingkan(lama, baru)
        self.assertEqual(
            [(b["model"], b["soal"]) for b in hasil["baris"]], [("m1", "s1")]
        )
        self.assertEqual(hasil["baris"][0]["tanda"], "TURUN")
        tidak = {(t["model"], t["sisi"]) for t in hasil["tidak_terbandingkan"]}
        self.assertEqual(
            tidak,
            {("m1", "lama"), ("m3", "lama"), ("m2", "baru")}
        )
        self.assertEqual([r["model"] for r in hasil["ringkasan"]], ["m1"])

    def test_ulangan_digabung_sebelum_dibandingkan(self):
        lama = _data(
            _item("m1", "s1", status="lulus", ulangan=1),
            _item("m1", "s1", status="gagal", ulangan=2),
        )
        baru = _data(
            _item("m1", "s1", status="gagal", ulangan=1),
            _item("m1", "s1", status="gagal", ulangan=2),
        )
        baris = bandingkan(lama, baru)["baris"]
        self.assertEqual(len(baris), 1)
        self.assertEqual(baris[0]["status_lama"], "lulus")
        self.assertEqual(baris[0]["status_baru"], "gagal")
        self.assertEqual(baris[0]["tanda"], "TURUN")


class MuatTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_berkas_tidak_ada_dan_json_rusak(self):
        with self.assertRaises(BandingkanError):
            muat(self.dir / "hilang.json")
        rusak = self.dir / "rusak.json"
        rusak.write_text("{bukan json", encoding="utf-8")
        with self.assertRaises(BandingkanError):
            muat(rusak)

    def test_format_tanpa_hasil_ditolak_dan_valid_lolos(self):
        salah = self.dir / "salah.json"
        salah.write_text(json.dumps({"model": []}), encoding="utf-8")
        with self.assertRaises(BandingkanError):
            muat(salah)
        benar = self.dir / "benar.json"
        benar.write_text(
            json.dumps(_data(_item("m1", "s1", status="lulus"))), encoding="utf-8"
        )
        data = muat(benar)
        self.assertEqual(len(data["hasil"]), 1)


class CliBandingkanTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir)

    def tulis(self, nama, *hasil):
        path = self.dir / nama
        path.write_text(json.dumps(_data(*hasil)), encoding="utf-8")
        return path

    def jalankan(self, argumen):
        keluaran = io.StringIO()
        galat = io.StringIO()
        with redirect_stdout(keluaran), redirect_stderr(galat):
            kode = main(argumen)
        return kode, keluaran.getvalue(), galat.getvalue()

    def test_kode_keluar_nol_tanpa_turun(self):
        lama = self.tulis("lama.json", _item("m1", "s1", status="gagal"), _item("m1", "s2", status="lulus"))
        baru = self.tulis("baru.json", _item("m1", "s1", status="lulus"), _item("m1", "s2", status="lulus"))
        kode, stdout, stderr = self.jalankan(
            ["bandingkan", str(lama), str(baru)]
        )
        self.assertEqual(kode, 0)
        self.assertEqual(stderr, "")
        self.assertIn("NAIK", stdout)
        self.assertIn("TETAP", stdout)
        self.assertIn("Ringkasan per model", stdout)
        self.assertIn("Tidak terbandingkan", stdout)
        self.assertNotIn("TURUN", stdout)

    def test_kode_keluar_satu_ada_turun(self):
        lama = self.tulis(
            "lama.json",
            _item("m1", "s1", status="lulus"),
            _item("m2", "s1", status="gagal"),
        )
        baru = self.tulis(
            "baru.json",
            _item("m1", "s1", status="gagal"),
            _item("m2", "s1", status="lulus"),
            _item("m2", "s9", status="lulus"),
        )
        kode, stdout, _ = self.jalankan(["bandingkan", str(lama), str(baru)])
        self.assertEqual(kode, 1)
        self.assertIn("TURUN", stdout)
        self.assertIn("NAIK", stdout)
        self.assertIn("m2 / s9 (hanya di baru)", stdout)

    def test_kode_keluar_dua_input_salah(self):
        lama = self.tulis("lama.json", _item("m1", "s1", status="lulus"))
        kode, _, stderr = self.jalankan(
            ["bandingkan", str(lama), str(self.dir / "hilang.json")]
        )
        self.assertEqual(kode, 2)
        self.assertIn("tidak ditemukan", stderr)

        rusak = self.dir / "rusak.json"
        rusak.write_text("[1, 2,", encoding="utf-8")
        kode, _, stderr = self.jalankan(["bandingkan", str(rusak), str(lama)])
        self.assertEqual(kode, 2)
        self.assertIn("JSON rusak", stderr)

        bukan_hasil = self.dir / "bukan.json"
        bukan_hasil.write_text("{}", encoding="utf-8")
        kode, _, stderr = self.jalankan(["bandingkan", str(bukan_hasil), str(lama)])
        self.assertEqual(kode, 2)
        self.assertIn("format hasil", stderr)


if __name__ == "__main__":
    unittest.main()
