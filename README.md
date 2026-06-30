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
