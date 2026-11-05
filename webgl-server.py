import http.server
import os
import socketserver
import urllib.error
import urllib.request

UPSTREAM = "http://lymdm8.com:3000"
ROOT = os.path.dirname(os.path.abspath(__file__))
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".wasm": "application/wasm",
    ".data": "application/octet-stream",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".css": "text/css",
    ".ico": "image/x-icon",
}
PROXY_PREFIXES = ("/playerLogin", "/playerOp", "/player", "/hall")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _serve_file(self, send_body):
        path = self.path.split("?")[0].lstrip("/") or "index.html"
        full = os.path.join(ROOT, path.replace("%20", " "))
        if not os.path.isfile(full):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        size = os.path.getsize(full)
        ext = os.path.splitext(full)[1].lower()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            with open(full, "rb") as fp:
                while True:
                    chunk = fp.read(1024 * 256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    def _proxy(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in ("host", "connection", "content-length", "origin", "referer")
        }
        req = urllib.request.Request(UPSTREAM + self.path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection", "content-length", "access-control-allow-origin"):
                        self.send_header(k, v)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as exc:
            data = exc.read()
            self.send_response(exc.code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc).encode("utf-8")
            self.send_response(502)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        if self.path.startswith(PROXY_PREFIXES):
            self._proxy("GET")
        else:
            self._serve_file(True)

    def do_HEAD(self):
        if self.path.startswith(PROXY_PREFIXES):
            self._proxy("HEAD")
        else:
            self._serve_file(False)

    def do_POST(self):
        self._proxy("POST")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", self.headers.get("Access-Control-Request-Headers", "*"))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        print("[web] " + fmt % args, flush=True)


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print("[web] root=" + ROOT, flush=True)
    ThreadingServer(("0.0.0.0", 8080), Handler).serve_forever()
