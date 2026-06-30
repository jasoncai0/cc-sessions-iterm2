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
