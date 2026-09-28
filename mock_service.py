"""
Layanan simulasi untuk praktikum uji integrasi (Python 3, tanpa dependensi).

  Client -> Order Service (:8000) -> Inventory Service (:8001)

Jalankan:  python3 mock_service.py
Opsional:  DELAY_MS=30 python3 mock_service.py   (latensi buatan Inventory)

Endpoint Order Service (8000):
  POST /orders            body JSON {"product_id": "P001", "quantity": 2}
                          header opsional: Idempotency-Key
  GET  /orders/{id}
Endpoint Inventory Service (8001):
  GET  /inventory/{product_id}
  POST /inventory/{product_id}/reserve   body {"quantity": n}
  POST /reset             (khusus lingkungan uji lokal: reset stok & pesanan)
"""
import json, os, threading, time, uuid, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DELAY = float(os.environ.get("DELAY_MS", "20")) / 1000.0
INITIAL_STOCK = {"P001": 10, "P002": 0, "P-LOAD": 10_000_000}
stock = dict(INITIAL_STOCK)
orders, idem = {}, {}
lock = threading.Lock()


def send(h, code, obj):
    body = json.dumps(obj).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json")
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


def read_json(h):
    n = int(h.headers.get("Content-Length") or 0)
    try:
        return json.loads(h.rfile.read(n) or b"{}")
    except Exception:
        return None


class Quiet(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Inventory(Quiet):
    def do_GET(self):
        p = self.path.strip("/").split("/")
        if len(p) == 2 and p[0] == "inventory":
            time.sleep(DELAY)
            if p[1] in stock:
                return send(self, 200, {"product_id": p[1], "stock": stock[p[1]]})
            return send(self, 404, {"error": "produk tidak ditemukan"})
        send(self, 404, {"error": "not found"})

    def do_POST(self):
        p = self.path.strip("/").split("/")
        if p == ["reset"]:
            with lock:
                stock.clear(); stock.update(INITIAL_STOCK)
                orders.clear(); idem.clear()
            return send(self, 200, {"status": "reset"})
        if len(p) == 3 and p[0] == "inventory" and p[2] == "reserve":
            time.sleep(DELAY)
            data = read_json(self) or {}
            q = data.get("quantity")
            with lock:
                if p[1] not in stock:
                    return send(self, 404, {"error": "produk tidak ditemukan"})
                if not isinstance(q, int) or q <= 0 or stock[p[1]] < q:
                    return send(self, 409, {"error": "stok tidak cukup"})
                stock[p[1]] -= q
                return send(self, 200, {"product_id": p[1], "stock": stock[p[1]]})
        send(self, 404, {"error": "not found"})


def call_inventory(method, path, payload=None):
    req = urllib.request.Request(
        "http://127.0.0.1:8001" + path, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class Order(Quiet):
    def do_GET(self):
        p = self.path.strip("/").split("/")
        if len(p) == 2 and p[0] == "orders" and p[1] in orders:
            return send(self, 200, orders[p[1]])
        send(self, 404, {"error": "pesanan tidak ditemukan"})

    def do_POST(self):
        if self.path.strip("/") != "orders":
            return send(self, 404, {"error": "not found"})
        data = read_json(self)
        if not isinstance(data, dict) or "product_id" not in data or "quantity" not in data:
            return send(self, 400, {"error": "field wajib: product_id, quantity"})
        pid, q = data["product_id"], data["quantity"]
        if not isinstance(pid, str) or not isinstance(q, int) or isinstance(q, bool) or q <= 0:
            return send(self, 422, {"error": "tipe/nilai data tidak valid"})
        key = self.headers.get("Idempotency-Key")
        if key and key in idem:
            return send(self, 200, orders[idem[key]])
        try:
            code, inv = call_inventory("GET", f"/inventory/{pid}")
            if code == 404:
                return send(self, 404, {"error": "produk tidak ditemukan"})
            if inv["stock"] < q:
                return send(self, 409, {"error": "stok tidak cukup", "stock": inv["stock"]})
            code, res = call_inventory("POST", f"/inventory/{pid}/reserve", {"quantity": q})
            if code != 200:
                return send(self, 409, {"error": "stok tidak cukup"})
        except Exception:
            return send(self, 503, {"error": "inventory service tidak tersedia"})
        oid = uuid.uuid4().hex[:8]
        order = {"order_id": oid, "product_id": pid, "quantity": q,
                 "status": "CREATED", "remaining_stock": res["stock"]}
        with lock:
            orders[oid] = order
            if key:
                idem[key] = oid
        send(self, 201, order)


if __name__ == "__main__":
    for port, cls in ((8001, Inventory), (8000, Order)):
        s = ThreadingHTTPServer(("127.0.0.1", port), cls)
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
    print("Order :8000 | Inventory :8001 | delay", DELAY * 1000, "ms")
    while True:
        time.sleep(3600)
