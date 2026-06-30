# Claude Sessions — iTerm2 Toolbelt Plugin

**Date:** 2026-06-30
**Status:** Approved design

## Goal

A plugin for iTerm2 that shows all CLI Claude Code sessions in the right-hand
Toolbelt sidebar, grouped by project directory. Groups can be expanded and
collapsed. Clicking a session resumes it in a new iTerm2 tab. The plugin is
easy to disable.

## Background / Constraints (verified)

- iTerm2 is installed at `/Applications/iTerm.app`.
- Claude Code sessions are stored as `~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl`.
  The folder name encodes the cwd by replacing `/` with `-` (lossy — cannot
  distinguish a real `-` from a path separator).
- Inside each `.jsonl`, records carry `cwd`, `gitBranch`, `timestamp`. A
  `type: "summary"` record may carry a human-readable `summary`. The first
  real user message is usable as a fallback label, but `<local-command-*>`
  caveat/meta lines must be skipped.
- Resume is `claude --resume <sessionId>`. The user's `claude` is a zsh
  function (wraps `--dangerously-skip-permissions`), so the command must run
  in an interactive login shell, not be exec'd directly.
- The `iterm2` pip package is NOT globally installed; iTerm2 ships and manages
  its own Python runtime for AutoLaunch scripts.
- Decision: **stdlib only** — no third-party Python dependencies, so the script
  runs in iTerm2's basic environment without a custom venv.

## Why build (research summary)

No existing iTerm2 plugin provides a grouped, click-to-resume session browser.
Existing iTerm2 plugins only set tab-title status. The exact feature set exists
only for VS Code (`borball/claude-session-manager`). CLI/TUI pickers exist
(`chronologos/cc-sessions`, `tradchenko/claude-sessions`) but are not embedded
in iTerm2. The clean way to embed a sidebar in iTerm2 is its Python API
"Custom Toolbelt web-view tool".

## Architecture

One self-contained Python AutoLaunch script for iTerm2:

1. Connects to iTerm2 via the Python API (`iterm2.run_forever`) and keeps the
   connection on the asyncio event loop.
2. Starts `http.server.ThreadingHTTPServer` bound to `127.0.0.1:<port>` in a
   background thread (stdlib only). Retries the next port if the chosen one is
   busy.
3. Registers a Custom Toolbelt web-view tool ("Claude Sessions") pointing at
   `http://127.0.0.1:<port>/`.

```
iTerm2 ──registers──► Toolbelt webview (HTML/CSS/JS)
   ▲                        │  fetch /api/sessions  ── GET ──► HTTP server (bg thread)
   │                        │  click resume         ── POST ─►   scans ~/.claude/projects
   └── async_create_tab ◄── run_coroutine_threadsafe ◄── /api/resume schedules coroutine
        + send_text "cd <cwd> && claude --resume <id>\n"  on the iTerm2 asyncio loop
```

The webview is a plain WKWebView, so it cannot call the Python script directly.
The local HTTP server is the bridge: the webview talks HTTP to it, and the
resume handler schedules a coroutine on the iTerm2 loop via
`asyncio.run_coroutine_threadsafe`.

## Components

### scanner (pure, unit-testable)
- Walks `~/.claude/projects/*/*.jsonl`.
- Per session extracts: real `cwd` (read from file content; fall back to
  decoding the folder name if absent), `gitBranch`, last `timestamp`, a label,
  and file `mtime`.
- Label resolution: `summary` record if present → else first real user message
  (skipping `<local-command-*>` caveats and tool/meta lines), truncated → else
  the session id.
- Groups sessions by `cwd`. Groups sorted by most-recent session; sessions
  within a group sorted newest first.
- Pure functions returning new structures; no mutation. Malformed/partial JSON
  lines are skipped, not fatal.

### http server
- `GET /` → serves the SPA (HTML/CSS/JS as static strings or files).
- `GET /api/sessions` → grouped JSON `{ groups: [{ cwd, label, sessions: [...] }] }`.
- `POST /api/resume` with body `{ id, cwd }` → schedules the resume coroutine
  on the iTerm2 loop; returns `{ success, code, msg }`.
- Responses use a standard envelope (`success`/`code`/`msg`/`data`).

### resume coroutine (runs on iTerm2 loop)
- `app = await iterm2.async_get_app(connection)`, current window.
- `tab = await window.async_create_tab()`; get its current session.
- `await session.async_send_text('cd ' + shlex.quote(cwd) + ' && claude --resume ' + shlex.quote(id) + '\n')`.
- On failure (no window, send error) return an error envelope so the UI can
  show a toast.

### webview UI
- Collapsible project groups (▸/▾), collapse state persisted in `localStorage`
  keyed by cwd.
- Session rows: label + relative time + git branch.
- Click a row → POST `/api/resume`.
- Manual ⟳ refresh button + auto-refresh on a timer (default 5s).
- Search/filter box that filters by label, cwd, and branch.
- Minimal dark UI matching iTerm2; no external assets/CDNs.

## Resume / scope / errors

- Click opens a **new tab** in the session's cwd running `claude --resume <id>`.
- Shows **all resumable** sessions, newest project first, newest session first.
- Error handling: unreadable/partial lines skipped; missing cwd falls back to
  folder-name decode; server bind retries next port; resume failures surface a
  toast in the UI; the HTTP server never crashes the iTerm2 connection.

## Easy disable (three levels, documented)

1. Built-in: uncheck the tool in iTerm2's **Toolbelt** menu (instant hide).
2. Stop the script: Scripts menu → stop, or uncheck AutoLaunch.
3. Uninstall: delete the single script folder.

## Testing

- **Unit (scanner):** fixture `.jsonl` files → expected grouped output.
  Cases: summary vs first-message labeling, caveat/meta skipping, cwd content
  vs folder-name fallback, malformed lines, empty dirs, sorting.
- **Integration (http):** request/response tests for `/api/sessions` and
  `/api/resume` (resume mocked — assert the scheduled call payload).
- **Manual (webview):** documented checklist run in the live iTerm2 app
  (panel appears, groups expand/collapse, click resumes in a new tab in the
  right cwd, disable paths work).

## File layout (proposed)

```
cc-sessions-iterm2/
  claude_sessions.py        # AutoLaunch entry: iTerm2 connect + server + tool registration
  cc_sessions/
    scanner.py              # pure session scanning/grouping/labeling
    server.py               # http handler + routes + envelope
    ui.py                   # SPA HTML/CSS/JS as a served string
  tests/
    test_scanner.py
    test_server.py
    fixtures/...
  install.sh                # copies/symlinks into iTerm2 AutoLaunch dir
  README.md                 # install, usage, disable/uninstall
```

## Out of scope (YAGNI)

- Live/running-session badges (chosen scope is "all resumable").
- Status-bar component.
- Session deletion / renaming / creation.
- Multi-agent (Codex/Gemini) sessions.
