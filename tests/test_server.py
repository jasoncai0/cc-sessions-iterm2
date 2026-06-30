import json
import threading
import unittest
import urllib.error
import urllib.request

from cc_sessions import server


class RouteTests(unittest.TestCase):
    def _scan(self):
        return {"groups": [{"cwd": "/x", "name": "x", "sessions": [], "latest": 0}]}

    def test_root_serves_html(self):
        status, ctype, body = server.route(
            "GET", "/", b"", scan_fn=self._scan, resume_fn=lambda i, c: None,
            ui_html="<html>hi</html>")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertEqual(body, b"<html>hi</html>")

    def test_sessions_returns_envelope(self):
        status, ctype, body = server.route(
            "GET", "/api/sessions", b"", scan_fn=self._scan,
            resume_fn=lambda i, c: None, ui_html="")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["code"], 0)
        self.assertEqual(len(payload["data"]["groups"]), 1)

    def test_resume_success(self):
        calls = []
        status, _, body = server.route(
            "POST", "/api/resume", json.dumps({"id": "a", "cwd": "/x"}).encode(),
            scan_fn=self._scan, resume_fn=lambda i, c: calls.append((i, c)), ui_html="")
        self.assertEqual(status, 200)
        self.assertEqual(calls, [("a", "/x")])
        self.assertTrue(json.loads(body)["success"])

    def test_resume_validation_error(self):
        status, _, body = server.route(
            "POST", "/api/resume", json.dumps({"id": ""}).encode(),
            scan_fn=self._scan, resume_fn=lambda i, c: None, ui_html="")
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(body)["success"])

    def test_resume_failure_returns_500(self):
        def boom(i, c):
            raise RuntimeError("no window")
        status, _, body = server.route(
            "POST", "/api/resume", json.dumps({"id": "a", "cwd": "/x"}).encode(),
            scan_fn=self._scan, resume_fn=boom, ui_html="")
        self.assertEqual(status, 500)
        self.assertFalse(json.loads(body)["success"])

    def test_unknown_route_404(self):
        status, _, body = server.route(
            "GET", "/nope", b"", scan_fn=self._scan,
            resume_fn=lambda i, c: None, ui_html="")
        self.assertEqual(status, 404)


class ServeTests(unittest.TestCase):
    def test_serve_binds_and_answers_sessions(self):
        scan = lambda: {"groups": []}
        httpd, port = server.serve(scan, lambda i, c: None, "<html>x</html>",
                                   start_port=9300)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/sessions" % port, timeout=5) as resp:
                payload = json.loads(resp.read())
            self.assertTrue(payload["success"])
        finally:
            httpd.shutdown()

    def test_serve_retries_when_port_busy(self):
        first, port = server.serve(lambda: {"groups": []}, lambda i, c: None,
                                   "", start_port=9320)
        try:
            second, port2 = server.serve(lambda: {"groups": []}, lambda i, c: None,
                                         "", start_port=9320)
            try:
                self.assertNotEqual(port, port2)
            finally:
                second.server_close()
        finally:
            first.server_close()


if __name__ == "__main__":
    unittest.main()
