# Heuristik deteksi bahasa Indonesia sesuai SPEC.md
ID_WORDS = {"yang","dan","di","ke","dari","ini","itu","untuk","dengan","tidak","ada","sudah","belum","bisa","akan","saya","kamu","jadi","kalau","atau","juga","karena","pada","dalam","supaya","lalu","harus","dulu","lewat","sebagai","adalah"}
EN_WORDS = {"the","and","is","are","to","of","for","with","this","that","you","it","be","can","will","not","have","if","or","on","in"}
import re

def heuristik_id(teks:str) -> bool:
    teks2 = teks
    # Buang blok kode ```...```
    while True:
        t3 = re.sub(r'```[\s\S]*?```', ' ', teks2)
        if t3 == teks2:
            break
        teks2 = t3
    # Buang `inline`
    teks2 = re.sub(r'`[^`]*`', '', teks2)
    # Normalisasi spasi jamak ke spasi tunggal
    teks2 = re.sub(r'\s+', ' ', teks2)
    # Ambil kata huruf kecil
    kata = re.findall(r'\b[a-z]+\b', teks2.lower())
    if len(kata) <= 5:
        return True
    n_id = sum(1 for w in kata if w in ID_WORDS)
    n_en = sum(1 for w in kata if w in EN_WORDS)
    return n_id >= 3 and n_id >= 2*n_en
