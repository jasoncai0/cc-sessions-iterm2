"""Pure functions for scanning and grouping Claude Code session files."""

import json
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
