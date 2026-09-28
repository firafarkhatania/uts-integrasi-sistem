"""
Menjalankan 6 kasus uji fungsional (FT-01 s.d. FT-06) secara otomatis dan
mencetak tabel hasilnya. Ambil screenshot layar hasilnya sebagai bukti.

Syarat: mock_service.py sedang berjalan di terminal lain.
Jalankan: python uji_fungsional.py
"""
import json, urllib.request, urllib.error

ORDER = "http://127.0.0.1:8000"
INV = "http://127.0.0.1:8001"


def call(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def stock(pid="P001"):
    return call("GET", f"{INV}/inventory/{pid}")[1].get("stock")


call("POST", f"{INV}/reset")  # data uji kembali ke kondisi awal
results = []


def case(id_, nama, expected_codes, body, headers=None, expect_stock_delta=0, repeat=1, pid="P001"):
    before = stock(pid)
    codes, last = [], None
    for _ in range(repeat):
        c, last = call("POST", f"{ORDER}/orders", body, headers)
        codes.append(c)
    after = stock(pid)
    delta = before - after
    ok = codes[0] in expected_codes and delta == expect_stock_delta
    if repeat > 1:
        ok = ok and codes[1] in (200, 201)
    results.append((id_, nama, codes, before, after, "Lulus" if ok else "Gagal"))
    print(f"\n[{id_}] {nama}")
    print(f"  request      : {body} {headers or ''} (dikirim {repeat}x)")
    print(f"  status HTTP  : {codes} (diharapkan {expected_codes})")
    print(f"  respons      : {last}")
    print(f"  stok {pid}   : sebelum={before} sesudah={after} (berkurang {delta}, diharapkan {expect_stock_delta})")
    print(f"  STATUS       : {'Lulus' if ok else 'Gagal'}")


case("FT-01", "Transaksi valid", (200, 201), {"product_id": "P001", "quantity": 2}, expect_stock_delta=2)
case("FT-02", "Stok tidak cukup", (409, 422), {"product_id": "P001", "quantity": 999})
case("FT-03", "Produk tidak ditemukan", (404,), {"product_id": "TIDAK-ADA", "quantity": 1})
case("FT-04", "Field wajib tidak lengkap", (400, 422), {"product_id": "P001"})
case("FT-05", "Tipe data tidak valid", (400, 422), {"product_id": "P001", "quantity": "dua"})
case("FT-06", "Permintaan diulang", (200, 201), {"product_id": "P001", "quantity": 1},
     headers={"Idempotency-Key": "uji-001"}, expect_stock_delta=1, repeat=2)

print("\n=== RINGKASAN ===")
for r in results:
    print(f"{r[0]}  {r[1]:<28} status={r[2]}  stok {r[3]}->{r[4]}  {r[5]}")
