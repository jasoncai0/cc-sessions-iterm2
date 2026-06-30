#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOLAUNCH="$HOME/Library/Application Support/iTerm2/Scripts/AutoLaunch"

mkdir -p "$AUTOLAUNCH"

# Symlink ONLY the entry script. Do NOT symlink the cc_sessions package into
# AutoLaunch: iTerm2 scans AutoLaunch entries and would scaffold a Python
# environment into the package, clobbering it. The entry resolves its own real
# path and imports cc_sessions from the repo via sys.path.
ln -sf "$SRC/claude_sessions.py" "$AUTOLAUNCH/claude_sessions.py"

# Clean up a package symlink left by older installs, if present.
rm -f "$AUTOLAUNCH/cc_sessions"

echo "Installed entry: $AUTOLAUNCH/claude_sessions.py -> $SRC/claude_sessions.py"
echo
echo "In iTerm2:"
echo "  1. Enable the Python API: Settings > General > Magic > Enable Python API."
echo "  2. Run the script: Scripts > AutoLaunch > claude_sessions.py"
echo "     (or restart iTerm2 — it auto-launches). Allow the runtime download"
echo "     and the API-access prompt on first run."
echo "  3. Open the Toolbelt (Cmd+B), then Toolbelt menu > check 'Claude Sessions'."
