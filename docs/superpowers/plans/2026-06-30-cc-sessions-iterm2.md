# Claude Sessions iTerm2 Toolbelt Plugin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an iTerm2 Toolbelt sidebar that lists all Claude Code sessions grouped by project directory, with collapsible groups and click-to-resume in a new tab.

**Architecture:** A single iTerm2 AutoLaunch Python script connects to iTerm2, starts a stdlib `http.server` in a background thread, and registers a Custom Toolbelt web-view tool pointing at that local server. The webview (HTML/JS) fetches grouped session JSON and POSTs resume requests; resume requests are bridged onto the iTerm2 asyncio loop to open a new tab running `claude --resume <id>`.

**Tech Stack:** Python 3 standard library only (`http.server`, `json`, `asyncio`, `threading`, `shlex`); iTerm2 Python API (`iterm2`, provided by iTerm2's runtime); vanilla HTML/CSS/JS for the webview. Tests use stdlib `unittest`.

## Global Constraints

- **Stdlib only at runtime** — no third-party Python packages (so the script runs in iTerm2's basic environment). `iterm2` is the sole exception and is provided by iTerm2.
- **No mutation** — scanner functions return new structures; never mutate inputs.
- **Immutable/pure scanner** — all functions in `cc_sessions/scanner.py` are pure and side-effect-free except file reads.
- **API envelope** — every JSON API response is `{"success": bool, "code": int, "msg": str, "data": any}`; success sentinel `code == 0`.
- **No external assets** — the webview must not load any CDN/remote resource; all HTML/CSS/JS is inline.
- **Panel title** — the Toolbelt tool display name is exactly `Claude Sessions`; identifier `com.cc.sessions.toolbelt`.
- **Sessions source** — `~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl`.
- **Resume command** — run in an interactive shell: `cd <quoted cwd> && claude --resume <quoted id>` (relies on the user's `claude` shell function).
- **Tests are stdlib `unittest`**, run from the project root with `python3 -m unittest ...`.

---

### Task 1: Scanner helpers — path decoding and user-text extraction

**Files:**
- Create: `cc_sessions/__init__.py` (empty)
- Create: `cc_sessions/scanner.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_scanner.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `decode_cwd(folder_name: str) -> str`
  - `extract_user_text(message) -> str | None`
  - `is_meaningful_text(text) -> bool`
  - `truncate_label(text: str, limit: int = 80) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_scanner.py`:
```python
import unittest

from cc_sessions import scanner


class DecodeCwdTests(unittest.TestCase):
    def test_decodes_dashed_folder_to_absolute_path(self):
        self.assertEqual(scanner.decode_cwd("-Users-mac-workspace"), "/Users/mac/workspace")

    def test_decodes_private_tmp(self):
        self.assertEqual(scanner.decode_cwd("-private-tmp"), "/private/tmp")


class ExtractUserTextTests(unittest.TestCase):
    def test_returns_string_content_directly(self):
        self.assertEqual(scanner.extract_user_text({"content": "hello"}), "hello")

    def test_returns_first_text_block_from_list_content(self):
        msg = {"content": [{"type": "text", "text": "hi there"}]}
        self.assertEqual(scanner.extract_user_text(msg), "hi there")

    def test_returns_none_for_non_dict(self):
        self.assertIsNone(scanner.extract_user_text(None))


class MeaningfulTextTests(unittest.TestCase):
    def test_rejects_empty_and_whitespace(self):
        self.assertFalse(scanner.is_meaningful_text(""))
        self.assertFalse(scanner.is_meaningful_text("   "))

    def test_rejects_meta_tag_text(self):
        self.assertFalse(scanner.is_meaningful_text("<local-command-caveat>blah"))

    def test_accepts_normal_text(self):
        self.assertTrue(scanner.is_meaningful_text("fix the bug"))


class TruncateLabelTests(unittest.TestCase):
    def test_collapses_whitespace(self):
        self.assertEqual(scanner.truncate_label("a\n  b   c"), "a b c")

    def test_truncates_with_ellipsis(self):
        self.assertEqual(scanner.truncate_label("x" * 100, limit=10), "x" * 9 + "…")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cc_sessions'`.

- [ ] **Step 3: Write minimal implementation**

Create `cc_sessions/__init__.py` (empty) and `tests/__init__.py` (empty).

`cc_sessions/scanner.py`:
```python
"""Pure functions for scanning and grouping Claude Code session files."""

import os


def decode_cwd(folder_name):
    """Decode an encoded project folder name back to an absolute path.

    '-Users-mac-workspace' -> '/Users/mac/workspace'. Lossy fallback only:
    a literal '-' in a path is indistinguishable from a separator.
    """
    name = folder_name[1:] if folder_name.startswith("-") else folder_name
    return "/" + name.replace("-", "/")


def extract_user_text(message):
    """Return the text of a user message, or None."""
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                return item.get("text")
    return None


def is_meaningful_text(text):
    """True when text is real user prose, not a CLI meta/caveat tag."""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("<"):
        return False
    return True


def truncate_label(text, limit=80):
    """Collapse whitespace to a single line and truncate with an ellipsis."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner -v`
Expected: PASS (all tests in the four test classes).

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/__init__.py cc_sessions/scanner.py tests/__init__.py tests/test_scanner.py
git commit -m "feat: scanner path-decode and user-text helpers

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Scanner — parse a single session file

**Files:**
- Modify: `cc_sessions/scanner.py`
- Modify: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `extract_user_text`, `is_meaningful_text`, `truncate_label`, `decode_cwd` (Task 1).
- Produces:
  - `parse_session_file(path: str) -> dict | None` returning
    `{"id": str, "cwd": str, "branch": str | None, "timestamp": str | None, "mtime": float, "label": str}`,
    or `None` if the file cannot be opened.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scanner.py` (and add `import json`, `import os`, `import tempfile` at top):
```python
class ParseSessionFileTests(unittest.TestCase):
    def _write(self, lines):
        d = tempfile.mkdtemp(prefix="-Users-demo-proj")
        path = os.path.join(d, "abc123.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for obj in lines:
                f.write(json.dumps(obj) + "\n")
        return path

    def test_uses_summary_when_present(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj", "gitBranch": "main",
             "timestamp": "2026-06-01T10:00:00Z",
             "message": {"content": "do the thing"}},
            {"type": "summary", "summary": "Refactor the parser"},
        ])
        result = scanner.parse_session_file(path)
        self.assertEqual(result["id"], "abc123")
        self.assertEqual(result["cwd"], "/Users/demo/proj")
        self.assertEqual(result["branch"], "main")
        self.assertEqual(result["label"], "Refactor the parser")

    def test_falls_back_to_first_meaningful_user_message(self):
        path = self._write([
            {"type": "user", "cwd": "/Users/demo/proj",
             "message": {"content": "<local-command-caveat>skip me"}},
            {"type": "user", "message": {"content": "real request here"}},
        ])
        result = scanner.parse_session_file(path)
        self.assertEqual(result["label"], "real request here")

    def test_skips_malformed_lines_and_decodes_cwd_fallback(self):
        d = tempfile.mkdtemp(prefix="-Users-demo-fallback")
        path = os.path.join(d, "s1.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            f.write("not json\n")
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        result = scanner.parse_session_file(path)
        # cwd not in records -> decoded from the temp folder name (starts with '/')
        self.assertTrue(result["cwd"].startswith("/"))
        self.assertEqual(result["label"], "hi")

    def test_returns_none_for_missing_file(self):
        self.assertIsNone(scanner.parse_session_file("/no/such/file.jsonl"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner.ParseSessionFileTests -v`
Expected: FAIL — `AttributeError: module 'cc_sessions.scanner' has no attribute 'parse_session_file'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top of `cc_sessions/scanner.py` (after `import os`):
```python
import json
```

Add to `cc_sessions/scanner.py`:
```python
def parse_session_file(path):
    """Parse one session .jsonl into a session dict, or None if unreadable."""
    cwd = None
    branch = None
    last_ts = None
    summary = None
    first_user = None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get("cwd"):
                    cwd = record["cwd"]
                if record.get("gitBranch"):
                    branch = record["gitBranch"]
                if record.get("timestamp"):
                    last_ts = record["timestamp"]
                if record.get("type") == "summary" and record.get("summary"):
                    summary = record["summary"]
                if first_user is None and record.get("type") == "user":
                    text = extract_user_text(record.get("message"))
                    if is_meaningful_text(text):
                        first_user = text
    except OSError:
        return None

    session_id = os.path.splitext(os.path.basename(path))[0]
    if cwd is None:
        cwd = decode_cwd(os.path.basename(os.path.dirname(path)))
    label = summary or first_user or session_id
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    return {
        "id": session_id,
        "cwd": cwd,
        "branch": branch,
        "timestamp": last_ts,
        "mtime": mtime,
        "label": truncate_label(label),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner -v`
Expected: PASS (all scanner tests).

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/scanner.py tests/test_scanner.py
git commit -m "feat: parse a single Claude session file

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Scanner — scan a directory, group, and build payload

**Files:**
- Modify: `cc_sessions/scanner.py`
- Modify: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `parse_session_file` (Task 2).
- Produces:
  - `scan_sessions(projects_dir: str) -> list[dict]`
  - `group_sessions(sessions: list[dict]) -> list[dict]` where each group is
    `{"cwd": str, "name": str, "sessions": list[dict], "latest": float}`,
    groups sorted by `latest` desc, sessions within a group by `mtime` desc.
  - `build_payload(projects_dir: str) -> dict` returning `{"groups": [...]}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scanner.py`:
```python
class ScanAndGroupTests(unittest.TestCase):
    def _make_projects(self):
        root = tempfile.mkdtemp()
        proj_a = os.path.join(root, "-Users-demo-a")
        proj_b = os.path.join(root, "-Users-demo-b")
        os.makedirs(proj_a)
        os.makedirs(proj_b)
        for name, cwd in [("s1.jsonl", "/Users/demo/a"),
                          ("s2.jsonl", "/Users/demo/a")]:
            with open(os.path.join(proj_a, name), "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "user", "cwd": cwd,
                                    "message": {"content": name}}) + "\n")
        with open(os.path.join(proj_b, "s3.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "cwd": "/Users/demo/b",
                                "message": {"content": "b work"}}) + "\n")
        # Make proj_b's session the most recently modified.
        os.utime(os.path.join(proj_b, "s3.jsonl"), (10 ** 9 + 100, 10 ** 9 + 100))
        return root

    def test_scan_finds_all_sessions(self):
        root = self._make_projects()
        sessions = scanner.scan_sessions(root)
        self.assertEqual(len(sessions), 3)

    def test_scan_returns_empty_for_missing_dir(self):
        self.assertEqual(scanner.scan_sessions("/no/such/dir"), [])

    def test_group_orders_groups_by_latest_session(self):
        root = self._make_projects()
        groups = scanner.group_sessions(scanner.scan_sessions(root))
        self.assertEqual(groups[0]["cwd"], "/Users/demo/b")
        names = {g["cwd"]: g for g in groups}
        self.assertEqual(len(names["/Users/demo/a"]["sessions"]), 2)
        self.assertEqual(names["/Users/demo/a"]["name"], "a")

    def test_build_payload_shape(self):
        root = self._make_projects()
        payload = scanner.build_payload(root)
        self.assertIn("groups", payload)
        self.assertEqual(len(payload["groups"]), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner.ScanAndGroupTests -v`
Expected: FAIL — `AttributeError: ... has no attribute 'scan_sessions'`.

- [ ] **Step 3: Write minimal implementation**

Add to `cc_sessions/scanner.py`:
```python
def scan_sessions(projects_dir):
    """Scan all *.jsonl session files under projects_dir into session dicts."""
    sessions = []
    if not os.path.isdir(projects_dir):
        return sessions
    for entry in os.listdir(projects_dir):
        project_dir = os.path.join(projects_dir, entry)
        if not os.path.isdir(project_dir):
            continue
        for fname in os.listdir(project_dir):
            if not fname.endswith(".jsonl"):
                continue
            session = parse_session_file(os.path.join(project_dir, fname))
            if session is not None:
                sessions.append(session)
    return sessions


def group_sessions(sessions):
    """Group sessions by cwd, newest session first, newest group first."""
    by_cwd = {}
    for session in sessions:
        by_cwd.setdefault(session["cwd"], []).append(session)
    groups = []
    for cwd, items in by_cwd.items():
        ordered = sorted(items, key=lambda s: s["mtime"], reverse=True)
        groups.append({
            "cwd": cwd,
            "name": os.path.basename(cwd.rstrip("/")) or cwd,
            "sessions": ordered,
            "latest": ordered[0]["mtime"] if ordered else 0.0,
        })
    groups.sort(key=lambda g: g["latest"], reverse=True)
    return groups


def build_payload(projects_dir):
    """Convenience: scan + group into the API payload shape."""
    return {"groups": group_sessions(scan_sessions(projects_dir))}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_scanner -v`
Expected: PASS (all scanner tests).

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/scanner.py tests/test_scanner.py
git commit -m "feat: scan, group, and build session payload

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: HTTP routing and response envelope (pure)

**Files:**
- Create: `cc_sessions/server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: nothing (scan/resume passed in as callables).
- Produces:
  - `envelope(success: bool, code: int, msg: str, data=None) -> dict`
  - `route(method: str, path: str, body: bytes, *, scan_fn, resume_fn, ui_html: str) -> tuple[int, str, bytes]`
    where `scan_fn() -> dict` and `resume_fn(session_id: str, cwd: str) -> None` (may raise).

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
import json
import unittest

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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_server -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cc_sessions.server'`.

- [ ] **Step 3: Write minimal implementation**

`cc_sessions/server.py`:
```python
"""Local HTTP bridge between the Toolbelt webview and iTerm2."""

import json


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_server -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/server.py tests/test_server.py
git commit -m "feat: pure HTTP router with response envelope

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: HTTP handler and server with port retry (integration)

**Files:**
- Modify: `cc_sessions/server.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Consumes: `route`, `make_handler` (this task).
- Produces:
  - `make_handler(scan_fn, resume_fn, ui_html) -> type` (a `BaseHTTPRequestHandler` subclass).
  - `serve(scan_fn, resume_fn, ui_html, host="127.0.0.1", start_port=9223, attempts=20) -> tuple[ThreadingHTTPServer, int]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server.py` (add `import threading`, `import urllib.request`, `import urllib.error` at top):
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_server.ServeTests -v`
Expected: FAIL — `AttributeError: ... has no attribute 'serve'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top of `cc_sessions/server.py` (after `import json`):
```python
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
```

Add to `cc_sessions/server.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_server -v`
Expected: PASS (route + serve tests).

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/server.py tests/test_server.py
git commit -m "feat: threading HTTP server with port retry

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Webview UI (HTML/CSS/JS)

**Files:**
- Create: `cc_sessions/ui.py`
- Create: `tests/test_ui.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `index_html() -> str` — a complete self-contained HTML document
  with inline CSS/JS that calls `GET /api/sessions` and `POST /api/resume`.

- [ ] **Step 1: Write the failing test**

`tests/test_ui.py`:
```python
import unittest

from cc_sessions import ui


class IndexHtmlTests(unittest.TestCase):
    def test_returns_self_contained_document(self):
        html = ui.index_html()
        self.assertIn("Claude Sessions", html)
        self.assertIn("/api/sessions", html)
        self.assertIn("/api/resume", html)
        # No external resources allowed.
        self.assertNotIn("http://", html.replace("http://127.0.0.1", ""))
        self.assertNotIn("https://", html)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_ui -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cc_sessions.ui'`.

- [ ] **Step 3: Write minimal implementation**

`cc_sessions/ui.py`:
```python
"""Self-contained webview UI served at GET /."""

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Claude Sessions</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font: 12px -apple-system, sans-serif;
         background: #1e1e1e; color: #d4d4d4; }
  header { position: sticky; top: 0; background: #252526; padding: 6px;
           display: flex; gap: 6px; align-items: center;
           border-bottom: 1px solid #333; }
  #search { flex: 1; background: #3c3c3c; border: 1px solid #444;
            color: #ddd; padding: 4px 6px; border-radius: 4px; }
  button { background: #0e639c; color: #fff; border: 0; border-radius: 4px;
           padding: 4px 8px; cursor: pointer; }
  .group { border-bottom: 1px solid #2a2a2a; }
  .group-head { display: flex; gap: 6px; padding: 6px 8px; cursor: pointer;
                user-select: none; background: #2d2d2d; }
  .group-head:hover { background: #333; }
  .caret { width: 10px; }
  .group-name { font-weight: 600; flex: 1; overflow: hidden;
                text-overflow: ellipsis; white-space: nowrap; }
  .count { color: #888; }
  .session { padding: 5px 8px 5px 24px; cursor: pointer;
             border-top: 1px solid #262626; }
  .session:hover { background: #094771; }
  .label { display: block; overflow: hidden; text-overflow: ellipsis;
           white-space: nowrap; }
  .meta { color: #888; font-size: 11px; }
  #toast { position: fixed; bottom: 8px; left: 8px; right: 8px;
           background: #5a1d1d; color: #fff; padding: 6px; border-radius: 4px;
           display: none; }
  .hidden { display: none; }
</style>
</head>
<body>
<header>
  <input id="search" placeholder="Filter Claude Sessions…" autocomplete="off">
  <button id="refresh">&#x21bb;</button>
</header>
<div id="list"></div>
<div id="toast"></div>
<script>
const COLLAPSE_KEY = "ccSessionsCollapsed";
let groups = [];

function collapsed() {
  try { return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "{}"); }
  catch (e) { return {}; }
}
function setCollapsed(map) {
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify(map));
}
function relTime(mtime) {
  if (!mtime) return "";
  const secs = Date.now() / 1000 - mtime;
  if (secs < 60) return "just now";
  if (secs < 3600) return Math.floor(secs / 60) + "m ago";
  if (secs < 86400) return Math.floor(secs / 3600) + "h ago";
  return Math.floor(secs / 86400) + "d ago";
}
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg; t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 4000);
}
async function load() {
  try {
    const resp = await fetch("/api/sessions");
    const payload = await resp.json();
    if (!payload.success) { toast(payload.msg); return; }
    groups = payload.data.groups || [];
    render();
  } catch (e) { toast("Failed to load sessions: " + e); }
}
async function resume(id, cwd) {
  try {
    const resp = await fetch("/api/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, cwd })
    });
    const payload = await resp.json();
    if (!payload.success) toast(payload.msg);
  } catch (e) { toast("Resume failed: " + e); }
}
function render() {
  const q = document.getElementById("search").value.toLowerCase();
  const fold = collapsed();
  const list = document.getElementById("list");
  list.textContent = "";
  for (const g of groups) {
    const matches = g.sessions.filter(s =>
      !q || (s.label + " " + g.cwd + " " + (s.branch || "")).toLowerCase().includes(q));
    if (q && matches.length === 0) continue;
    const isFold = !!fold[g.cwd];
    const groupEl = document.createElement("div");
    groupEl.className = "group";
    const head = document.createElement("div");
    head.className = "group-head";
    head.innerHTML =
      '<span class="caret">' + (isFold ? "&#9656;" : "&#9662;") + "</span>" +
      '<span class="group-name"></span>' +
      '<span class="count"></span>';
    head.querySelector(".group-name").textContent = g.name;
    head.querySelector(".count").textContent = matches.length;
    head.onclick = () => {
      const f = collapsed(); f[g.cwd] = !f[g.cwd]; setCollapsed(f); render();
    };
    groupEl.appendChild(head);
    if (!isFold) {
      for (const s of matches) {
        const row = document.createElement("div");
        row.className = "session";
        const label = document.createElement("span");
        label.className = "label"; label.textContent = s.label;
        const meta = document.createElement("span");
        meta.className = "meta";
        meta.textContent = relTime(s.mtime) +
          (s.branch ? " · " + s.branch : "");
        row.appendChild(label); row.appendChild(meta);
        row.title = g.cwd + "  (" + s.id + ")";
        row.onclick = () => resume(s.id, g.cwd);
        groupEl.appendChild(row);
      }
    }
    list.appendChild(groupEl);
  }
}
document.getElementById("refresh").onclick = load;
document.getElementById("search").oninput = render;
load();
setInterval(load, 5000);
</script>
</body>
</html>"""


def index_html():
    """Return the complete, self-contained Toolbelt webview document."""
    return _HTML
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest tests.test_ui -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
git add cc_sessions/ui.py tests/test_ui.py
git commit -m "feat: self-contained Toolbelt webview UI

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: iTerm2 AutoLaunch entry, installer, and docs (manual verification)

**Files:**
- Create: `claude_sessions.py` (iTerm2 AutoLaunch entry)
- Create: `install.sh`
- Create: `README.md`
- Modify: `docs/superpowers/plans/2026-06-30-cc-sessions-iterm2.md` (check off manual checklist as you verify)

**Interfaces:**
- Consumes: `cc_sessions.scanner.build_payload`, `cc_sessions.server.serve`, `cc_sessions.ui.index_html`.
- Produces: a runnable AutoLaunch script. Not unit-tested (needs the live iTerm2 app); verified via the manual checklist below.

- [ ] **Step 1: Write the entry script**

`claude_sessions.py`:
```python
#!/usr/bin/env python3
"""iTerm2 AutoLaunch: Claude Sessions Toolbelt.

Starts a local HTTP server that serves the session browser webview and
registers it as a Custom Toolbelt tool. Clicking a session opens a new tab
running `claude --resume <id>` in that session's cwd.
"""

import asyncio
import os
import shlex
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import iterm2  # provided by iTerm2's Python runtime

from cc_sessions import scanner, server, ui

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
TOOL_NAME = "Claude Sessions"
TOOL_IDENTIFIER = "com.cc.sessions.toolbelt"

_loop = None
_connection = None


async def _do_resume(session_id, cwd):
    app = await iterm2.async_get_app(_connection)
    window = app.current_terminal_window
    if window is None:
        window = await iterm2.Window.async_create(_connection)
    tab = await window.async_create_tab()
    target = tab.current_session
    command = "cd %s && claude --resume %s\n" % (
        shlex.quote(cwd), shlex.quote(session_id))
    await target.async_send_text(command)


def _resume_fn(session_id, cwd):
    """Called from the HTTP server thread; bridges onto the iTerm2 loop."""
    future = asyncio.run_coroutine_threadsafe(
        _do_resume(session_id, cwd), _loop)
    future.result(timeout=15)


def _scan_fn():
    return scanner.build_payload(PROJECTS_DIR)


async def main(connection):
    global _loop, _connection
    _loop = asyncio.get_event_loop()
    _connection = connection

    httpd, port = server.serve(_scan_fn, _resume_fn, ui.index_html())
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    await iterm2.tool.async_register_web_view_tool(
        connection,
        display_name=TOOL_NAME,
        identifier=TOOL_IDENTIFIER,
        reveal_if_already_registered=True,
        url="http://127.0.0.1:%d/" % port)

    await asyncio.Future()  # keep the script alive


iterm2.run_forever(main)
```

- [ ] **Step 2: Write the installer**

`install.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOLAUNCH="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch"

mkdir -p "$AUTOLAUNCH"
ln -sf "$SRC/claude_sessions.py" "$AUTOLAUNCH/claude_sessions.py"
ln -sf "$SRC/cc_sessions" "$AUTOLAUNCH/cc_sessions"

echo "Installed. In iTerm2:"
echo "  1. Enable the Python API: Settings > General > Magic > Enable Python API."
echo "  2. Scripts menu will auto-launch 'claude_sessions.py' (or run it once)."
echo "  3. Open the Toolbelt (View > Toolbelt > Show Toolbelt, or Cmd+B)."
echo "  4. Toolbelt menu > check 'Claude Sessions'."
```

- [ ] **Step 3: Write the README**

`README.md`:
```markdown
# Claude Sessions — iTerm2 Toolbelt

Lists all Claude Code sessions in the iTerm2 Toolbelt, grouped by project
directory. Collapsible groups; click a session to resume it in a new tab.

## Install

```bash
./install.sh
```

Then in iTerm2: enable **Settings > General > Magic > Enable Python API**,
open the Toolbelt with **Cmd+B**, and check **Claude Sessions** in the
**Toolbelt** menu. The script auto-launches on iTerm2 start.

## Disable / Uninstall

- **Hide instantly:** uncheck **Claude Sessions** in the Toolbelt menu.
- **Stop the script:** Scripts menu > stop, or remove it from AutoLaunch.
- **Uninstall:** delete the symlinks:
  ```bash
  rm "$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch/claude_sessions.py"
  rm "$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch/cc_sessions"
  ```

## How it works

A stdlib HTTP server serves the webview and a JSON API reading
`~/.claude/projects`. Clicking a session POSTs to the server, which opens a
new iTerm2 tab and runs `claude --resume <id>` in the session's directory.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
```

- [ ] **Step 4: Run the full test suite (regression)**

Run: `cd ~/workspace/cc-sessions-iterm2 && python3 -m unittest discover -s tests -v`
Expected: PASS — all scanner, server, and ui tests green.

- [ ] **Step 5: Verify the entry script imports cleanly without iTerm2**

Run:
```bash
cd ~/workspace/cc-sessions-iterm2
python3 -c "import ast; ast.parse(open('claude_sessions.py').read()); print('syntax ok')"
```
Expected: `syntax ok` (full import needs the iTerm2 runtime; this only checks syntax).

- [ ] **Step 6: Manual verification checklist (in the live iTerm2 app)**

Run `./install.sh`, restart iTerm2, then confirm each:
- [ ] "Claude Sessions" appears in the Toolbelt menu and panel.
- [ ] Projects are listed as groups, newest first, with session counts.
- [ ] Clicking a group caret collapses/expands it; state survives a refresh.
- [ ] The filter box narrows groups/sessions by label, cwd, and branch.
- [ ] Clicking a session opens a NEW tab in the correct cwd running `claude --resume <id>`.
- [ ] Unchecking the tool in the Toolbelt menu hides it (disable path works).

- [ ] **Step 7: Commit**

```bash
cd ~/workspace/cc-sessions-iterm2
chmod +x install.sh
git add claude_sessions.py install.sh README.md docs/superpowers/plans/2026-06-30-cc-sessions-iterm2.md
git commit -m "feat: iTerm2 AutoLaunch entry, installer, and docs

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Notes for the implementer

- Run every command from the project root `~/workspace/cc-sessions-iterm2`.
- `cc_sessions/` is a package (`__init__.py` present); `tests/` likewise. The
  entry script adds its own directory to `sys.path` so AutoLaunch can import
  the package regardless of iTerm2's working directory.
- Do not add third-party dependencies. If a step seems to need one, re-read the
  Global Constraints — there is always a stdlib path here.
- The `except Exception` in `route`'s resume branch is deliberate: the bridge
  must never crash the iTerm2 connection; it converts any failure into a
  user-visible toast.
