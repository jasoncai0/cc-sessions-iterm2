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
  button.secondary { background: #444; }
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
  .session.open { background: #0b3a5c; }
  .label { display: block; overflow: hidden; text-overflow: ellipsis;
           white-space: nowrap; }
  .meta { color: #888; font-size: 11px; }
  .detail { background: #232323; border-top: 1px solid #333;
            padding: 8px 8px 8px 24px; cursor: default; }
  .detail .row { color: #9cdcfe; font-size: 11px; margin-bottom: 2px;
                 word-break: break-all; }
  .detail .k { color: #888; }
  .detail pre { white-space: pre-wrap; word-break: break-word;
                background: #1b1b1b; border: 1px solid #2f2f2f; border-radius: 4px;
                padding: 6px; margin: 6px 0; max-height: 180px; overflow: auto; }
  .detail .section { color: #888; font-size: 10px; text-transform: uppercase;
                     letter-spacing: .04em; margin-top: 6px; }
  .actions { display: flex; gap: 6px; margin-top: 8px; }
  #toast { position: fixed; bottom: 8px; left: 8px; right: 8px;
           background: #5a1d1d; color: #fff; padding: 6px; border-radius: 4px;
           display: none; }
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
let openPath = null;          // path of the session whose detail is expanded
const detailCache = {};       // path -> detail object

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
function fmtTs(iso) {
  return iso ? iso.slice(0, 16).replace("T", " ") : "";
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
async function openDetail(path) {
  if (openPath === path) { openPath = null; render(); return; }
  openPath = path;
  render();  // show "Loading…"
  if (!detailCache[path]) {
    try {
      const resp = await fetch("/api/session?path=" + encodeURIComponent(path));
      const payload = await resp.json();
      if (payload.success) detailCache[path] = payload.data;
      else { toast(payload.msg); openPath = null; }
    } catch (e) { toast("Detail failed: " + e); openPath = null; }
  }
  render();
}
async function resume(id, cwd) {
  try {
    const resp = await fetch("/api/resume", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, cwd })
    });
    const payload = await resp.json();
    if (payload.success) { openPath = null; render(); }
    else toast(payload.msg);
  } catch (e) { toast("Resume failed: " + e); }
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function buildDetail(session, cwd) {
  const box = el("div", "detail");
  box.onclick = (ev) => ev.stopPropagation();  // don't toggle the row
  const d = detailCache[session.path];
  if (!d) { box.appendChild(el("div", "row", "Loading…")); return box; }

  const meta = el("div");
  function add(k, v) {
    if (!v && v !== 0) return;
    const r = el("div", "row");
    r.appendChild(el("span", "k", k + ": "));
    r.appendChild(document.createTextNode(String(v)));
    meta.appendChild(r);
  }
  add("dir", cwd);
  if (d.branch) add("branch", d.branch);
  add("messages", d.message_count);
  add("started", fmtTs(d.created));
  add("last", fmtTs(d.last_active));
  add("id", d.id);
  box.appendChild(meta);

  box.appendChild(el("div", "section", "First message"));
  box.appendChild(el("pre", null, d.first_message || ""));
  if (d.last_message) {
    box.appendChild(el("div", "section", "Most recent"));
    box.appendChild(el("pre", null, d.last_message));
  }

  const actions = el("div", "actions");
  const resumeBtn = el("button", null, "▶ Resume in new tab");
  resumeBtn.onclick = (ev) => { ev.stopPropagation(); resume(d.id, cwd); };
  const cancelBtn = el("button", "secondary", "Cancel");
  cancelBtn.onclick = (ev) => { ev.stopPropagation(); openPath = null; render(); };
  actions.appendChild(resumeBtn);
  actions.appendChild(cancelBtn);
  box.appendChild(actions);
  return box;
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
    const groupEl = el("div", "group");
    const head = el("div", "group-head");
    head.appendChild(el("span", "caret", isFold ? "▸" : "▾"));
    head.appendChild(el("span", "group-name", g.name));
    head.appendChild(el("span", "count", String(matches.length)));
    head.onclick = () => {
      const f = collapsed(); f[g.cwd] = !f[g.cwd]; setCollapsed(f); render();
    };
    groupEl.appendChild(head);
    if (!isFold) {
      for (const s of matches) {
        const row = el("div", "session" + (openPath === s.path ? " open" : ""));
        row.appendChild(el("span", "label", s.label));
        row.appendChild(el("span", "meta",
          relTime(s.mtime) + (s.branch ? " · " + s.branch : "")));
        row.title = g.cwd + "  (" + s.id + ")";
        row.onclick = () => openDetail(s.path);
        groupEl.appendChild(row);
        if (openPath === s.path) groupEl.appendChild(buildDetail(s, g.cwd));
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
