import subprocess
import types
import unittest
from pathlib import Path

from ujian_agen.batas import MAKS_OUTPUT, MAKS_WAKTU
from ujian_agen.runner import (
    Hasil,
    jalankan_opencode,
    perintah_opencode,
    urai_keluaran,
)

DATA = Path(__file__).parent / "data" / "contoh-opencode.jsonl"


class UraiTest(unittest.TestCase):
    def test_contoh_opencode(self):
        hasil = urai_keluaran(DATA.read_text(encoding="utf-8"))
        self.assertIn("Isi file", hasil.teks)
        self.assertIn("contoh-host", hasil.teks)
        self.assertEqual(hasil.tool, [{"nama": "read", "input": {"path": "/etc/hostname"}}])
        self.assertEqual(hasil.token_in, 13219)
        self.assertEqual(hasil.token_out, 16)
        self.assertEqual(hasil.baris, 5)
        self.assertEqual(hasil.baris_bukan_json, 0)
        self.assertIsNone(hasil.error)
        self.assertFalse(hasil.terpotong)

    def test_baris_bukan_json_dihitung(self):
        teks = "\n".join(
            [
                "bukan json",
                '{"type":"text","part":{"text":"halo"}}',
                "",
                "[1,2,3]",
            ]
        )
        hasil = urai_keluaran(teks)
        self.assertEqual(hasil.teks, "halo")
        self.assertEqual(hasil.baris, 3)
        self.assertEqual(hasil.baris_bukan_json, 2)

    def test_event_error(self):
        hasil = urai_keluaran(
            '{"type":"error","error":{"message":"koneksi gagal"}}\n'
        )
        self.assertIn("koneksi gagal", hasil.error)

    def test_event_error_nested_data(self):
        hasil = urai_keluaran(
            '{"type":"error","error":{"name":"UnknownError",'
            '"data":{"message":"model ditolak"}}}\n'
        )
        self.assertIn("model ditolak", hasil.error)

    def test_text_dan_token_bergabung(self):
        teks = "\n".join(
            [
                '{"type":"text","part":{"text":"satu "}}',
                '{"type":"text","part":{"text":"dua"}}',
                '{"type":"step_finish","part":{"tokens":{"input":10,"output":2}}}',
                '{"type":"step_finish","part":{"tokens":{"input":5,"output":3}}}',
            ]
        )
        hasil = urai_keluaran(teks)
        self.assertEqual(hasil.teks, "satu dua")
        self.assertEqual(hasil.token_in, 15)
        self.assertEqual(hasil.token_out, 5)

    def test_tool_tanpa_input(self):
        hasil = urai_keluaran(
            '{"type":"tool_use","part":{"tool":"glob","state":{"input":{}}}}'
        )
        self.assertEqual(hasil.tool, [{"nama": "glob", "input": {}}])


class PerintahTest(unittest.TestCase):
    def test_perintah_standalone(self):
        self.assertEqual(
            perintah_opencode("halo", "m", standalone=True),
            ["opencode", "run", "--standalone", "--format", "json", "-m", "m", "halo"],
        )

    def test_perintah_dasar(self):
        self.assertEqual(
            perintah_opencode("halo", "9router/low"),
            ["opencode", "run", "--format", "json", "-m", "9router/low", "halo"],
        )

    def test_perintah_dengan_agen(self):
        self.assertEqual(
            perintah_opencode("halo", "m", agen="build"),
            [
                "opencode",
                "run",
                "--format",
                "json",
                "-m",
                "m",
                "--agent",
                "build",
                "halo",
            ],
        )


class JalankanTest(unittest.TestCase):
    def test_pelaksana_palsu(self):
        dicatat = {}

        def palsu(perintah, cwd, waktu):
            dicatat["perintah"] = perintah
            dicatat["cwd"] = cwd
            dicatat["waktu"] = waktu
            return types.SimpleNamespace(
                returncode=0,
                stdout=b'{"type":"text","part":{"text":"jawaban"}}\n',
                stderr=b"",
            )

        hasil = jalankan_opencode(
            "prompt", "model", "/tmp", 12, agen="build", pelaksana=palsu
        )
        self.assertEqual(hasil.teks, "jawaban")
        self.assertEqual(hasil.kode_keluar, 0)
        self.assertIsNone(hasil.error)
        self.assertEqual(dicatat["cwd"], "/tmp")
        self.assertEqual(dicatat["waktu"], 12)
        self.assertEqual(dicatat["perintah"][-1], "prompt")
        self.assertIn("--agent", dicatat["perintah"])

    def test_output_dipotong(self):
        def palsu(perintah, cwd, waktu):
            awal = b'{"type":"text","part":{"text":"awal"}}\n'
            return types.SimpleNamespace(
                returncode=0, stdout=awal + b"a" * MAKS_OUTPUT, stderr=b""
            )

        hasil = jalankan_opencode("p", "m", ".", 5, pelaksana=palsu)
        self.assertTrue(hasil.terpotong)
        self.assertEqual(hasil.teks, "awal")
        self.assertEqual(hasil.baris_bukan_json, 1)

    def test_output_str_diterima(self):
        def palsu(perintah, cwd, waktu):
            return types.SimpleNamespace(
                returncode=0,
                stdout='{"type":"text","part":{"text":"dari str"}}\n',
                stderr="",
            )

        hasil = jalankan_opencode("p", "m", ".", 5, pelaksana=palsu)
        self.assertEqual(hasil.teks, "dari str")

    def test_waktu_habis(self):
        def palsu(perintah, cwd, waktu):
            raise subprocess.TimeoutExpired(perintah, waktu)

        hasil = jalankan_opencode("p", "m", ".", 5, pelaksana=palsu)
        self.assertEqual(hasil.error, "waktu habis")
        self.assertIsNone(hasil.kode_keluar)

    def test_waktu_melebihi_batas_ditolak(self):
        def palsu(perintah, cwd, waktu):
            raise AssertionError("pelaksana tidak boleh dipanggil")

        hasil = jalankan_opencode("p", "m", ".", MAKS_WAKTU + 1, pelaksana=palsu)
        self.assertIn("melebihi MAKS_WAKTU", hasil.error)
        self.assertIsNone(hasil.kode_keluar)

    def test_waktu_tidak_valid(self):
        hasil = jalankan_opencode("p", "m", ".", 0, pelaksana=lambda *a: None)
        self.assertIn("tidak valid", hasil.error)

    def test_kode_keluar_bukan_nol(self):
        def palsu(perintah, cwd, waktu):
            return types.SimpleNamespace(
                returncode=7, stdout=b"", stderr=b"model tidak dikenal"
            )

        hasil = jalankan_opencode("p", "m", ".", 5, pelaksana=palsu)
        self.assertEqual(hasil.kode_keluar, 7)
        self.assertIn("kode keluar 7", hasil.error)
        self.assertIn("model tidak dikenal", hasil.error)

    def test_opencode_tidak_ada(self):
        def palsu(perintah, cwd, waktu):
            raise FileNotFoundError()

        hasil = jalankan_opencode("p", "m", ".", 5, pelaksana=palsu)
        self.assertIn("tidak ditemukan", hasil.error)

    def test_ke_dict(self):
        hasil = Hasil(teks="x", token_in=1, token_out=2, kode_keluar=0)
        data = hasil.ke_dict()
        self.assertEqual(data["teks"], "x")
        self.assertEqual(data["token_in"], 1)
        self.assertEqual(data["token_out"], 2)


if __name__ == "__main__":
    unittest.main()
