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
