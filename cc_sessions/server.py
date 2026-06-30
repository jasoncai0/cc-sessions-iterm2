"""Local HTTP bridge between the Toolbelt webview and iTerm2."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def envelope(success, code, msg, data=None):
    """Standard API response envelope."""
    return {"success": success, "code": code, "msg": msg, "data": data}


def _json_bytes(payload):
    return json.dumps(payload).encode("utf-8")


def route(method, path, body, *, scan_fn, resume_fn, ui_html):
    """Pure request router. Returns (status, content_type, body_bytes)."""
    if method == "GET" and path == "/":
        return 200, "text/html; charset=utf-8", ui_html.encode("utf-8")

    if method == "GET" and path == "/api/sessions":
        payload = envelope(True, 0, "ok", scan_fn())
        return 200, "application/json", _json_bytes(payload)

    if method == "POST" and path == "/api/resume":
        try:
            parsed = json.loads(body.decode("utf-8")) if body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400, "application/json", _json_bytes(
                envelope(False, 400, "invalid json body"))
        session_id = parsed.get("id")
        cwd = parsed.get("cwd")
        if not isinstance(session_id, str) or not session_id \
                or not isinstance(cwd, str) or not cwd:
            return 400, "application/json", _json_bytes(
                envelope(False, 400, "id and cwd are required"))
        try:
            resume_fn(session_id, cwd)
        except Exception as error:  # never crash the bridge; report to UI
            return 500, "application/json", _json_bytes(
                envelope(False, 500, "resume failed: " + str(error)))
        return 200, "application/json", _json_bytes(envelope(True, 0, "ok"))

    return 404, "application/json", _json_bytes(envelope(False, 404, "not found"))


def make_handler(scan_fn, resume_fn, ui_html):
    """Build a request handler class bound to the given callables."""

    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method):
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            status, content_type, payload = route(
                method, self.path, body,
                scan_fn=scan_fn, resume_fn=resume_fn, ui_html=ui_html)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

        def log_message(self, *args):
            pass  # keep iTerm2's script console quiet

    return Handler


def serve(scan_fn, resume_fn, ui_html, host="127.0.0.1",
          start_port=9223, attempts=20):
    """Bind a ThreadingHTTPServer, trying successive ports. Returns (httpd, port)."""
    handler = make_handler(scan_fn, resume_fn, ui_html)
    last_error = None
    for port in range(start_port, start_port + attempts):
        try:
            httpd = ThreadingHTTPServer((host, port), handler)
            return httpd, port
        except OSError as error:
            last_error = error
            continue
    raise RuntimeError("no free port found") from last_error
