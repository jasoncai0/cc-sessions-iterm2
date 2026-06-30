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
