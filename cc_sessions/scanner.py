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
    if branch == "HEAD":
        branch = None  # detached checkout — not a meaningful branch label
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
        "path": path,
    }


def _cap(text, limit):
    """Truncate to limit chars (preserving newlines), appending an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def session_detail(path):
    """Rich detail for one session: meta + conversation preview, or None."""
    base = parse_session_file(path)
    if base is None:
        return None
    created = None
    last_active = None
    message_count = 0
    first_message = None
    last_message = None
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
                if record.get("timestamp"):
                    if created is None:
                        created = record["timestamp"]
                    last_active = record["timestamp"]
                if record.get("type") in ("user", "assistant"):
                    message_count += 1
                    text = extract_user_text(record.get("message"))
                    if is_meaningful_text(text):
                        if record["type"] == "user" and first_message is None:
                            first_message = text
                        last_message = text
    except OSError:
        return None
    detail = dict(base)
    detail["created"] = created
    detail["last_active"] = last_active
    detail["message_count"] = message_count
    detail["first_message"] = _cap(first_message, 1500) if first_message else base["label"]
    detail["last_message"] = _cap(last_message, 280) if last_message else None
    return detail


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
