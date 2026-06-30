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

# Resolve symlinks: the AutoLaunch entry is a symlink into the repo, and the
# cc_sessions package lives next to the REAL file, not next to the symlink.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

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


def _detail_fn(path):
    """Detail for one session, only if path is inside the projects dir."""
    real = os.path.realpath(path)
    root = os.path.realpath(PROJECTS_DIR)
    if not real.startswith(root + os.sep) or not real.endswith(".jsonl"):
        return None
    return scanner.session_detail(real)


async def main(connection):
    global _loop, _connection
    _loop = asyncio.get_event_loop()
    _connection = connection

    httpd, port = server.serve(
        _scan_fn, _resume_fn, ui.index_html(), detail_fn=_detail_fn)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    await iterm2.tool.async_register_web_view_tool(
        connection,
        display_name=TOOL_NAME,
        identifier=TOOL_IDENTIFIER,
        reveal_if_already_registered=True,
        url="http://127.0.0.1:%d/" % port)

    await asyncio.Future()  # keep the script alive


iterm2.run_forever(main)
