"""Batas-batas keras harness ujian-agen.

Semua batas ditulis di satu tempat agar mudah diaudit. Melewati batas harus
ditolak dengan pesan jelas (gagal tertutup), bukan dipotong diam-diam.
"""

MAKS_SOAL = 200
MAKS_OUTPUT = 2_000_000
MAKS_WAKTU = 300
MAKS_MODEL = 20
MAKS_ULANG = 5
MAKS_PARALEL = 4
PANJANG_MAKS_ID = 64
