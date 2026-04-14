#!/usr/bin/env python3
"""
Web UI to add and edit commentary on ACCC merger decisions.
Writes directly to data/processed/commentary.json.
Run with: python scripts/commentary.py
"""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
COMMENTARY_JSON = REPO_ROOT / "data" / "processed" / "commentary.json"

app = FastAPI()


# ── helpers ────────────────────────────────────────────────────────────────

def _load_mergers() -> list:
    with MERGERS_JSON.open() as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("mergers", [])


def _load_commentary() -> dict:
    with COMMENTARY_JSON.open() as fh:
        return json.load(fh)


def _save_commentary(data: dict) -> None:
    with COMMENTARY_JSON.open("w") as fh:
        json.dump(data, fh, indent=2)


# ── request models ─────────────────────────────────────────────────────────

class SaveRequest(BaseModel):
    merger_id: str
    index: Optional[int] = None   # None → append new; int → update existing
    commentary: str = ""
    tags: List[str] = []
    date: Optional[str] = None
    author: Optional[str] = None


class DeleteRequest(BaseModel):
    merger_id: str
    index: int


# ── routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT


@app.get("/api/data")
def get_data():
    mergers = _load_mergers()
    commentary = _load_commentary()
    _skip = {"_README", "_example"}

    seen: set = set()
    result: list = []

    for m in mergers:
        mid = m.get("merger_id")
        if not mid:
            continue
        seen.add(mid)
        result.append({
            "merger_id": mid,
            "merger_name": m.get("merger_name", ""),
            "status": m.get("status", ""),
            "accc_determination": m.get("accc_determination"),
            "comments": commentary.get(mid, {}).get("comments", []),
        })

    # Append any IDs in commentary.json that aren't in mergers.json
    # (e.g. waiver applications or legacy IDs)
    for key, val in commentary.items():
        if key in _skip or key in seen:
            continue
        result.append({
            "merger_id": key,
            "merger_name": "",
            "status": "",
            "accc_determination": None,
            "comments": val.get("comments", []),
        })

    return {"mergers": result}


@app.post("/api/save")
def save_comment(req: SaveRequest):
    commentary = _load_commentary()

    comment: dict = {"commentary": req.commentary, "tags": req.tags}
    if req.date:
        comment["date"] = req.date
    if req.author:
        comment["author"] = req.author

    if req.index is None:
        # Append new comment
        if req.merger_id not in commentary:
            commentary[req.merger_id] = {"comments": []}
        commentary[req.merger_id]["comments"].append(comment)
    else:
        # Update existing
        if req.merger_id not in commentary:
            raise HTTPException(404, "Merger not found in commentary")
        comments = commentary[req.merger_id].get("comments", [])
        if not (0 <= req.index < len(comments)):
            raise HTTPException(400, "Invalid comment index")
        comments[req.index] = comment

    _save_commentary(commentary)
    return {"status": "success"}


@app.post("/api/delete")
def delete_comment(req: DeleteRequest):
    commentary = _load_commentary()

    if req.merger_id not in commentary:
        raise HTTPException(404, "Merger not found")
    comments = commentary[req.merger_id].get("comments", [])
    if not (0 <= req.index < len(comments)):
        raise HTTPException(400, "Invalid index")

    del comments[req.index]
    if not comments:
        del commentary[req.merger_id]

    _save_commentary(commentary)
    return {"status": "success"}


# ── frontend ───────────────────────────────────────────────────────────────

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Commentary Tool — ACCC Mergers</title>
  <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    tailwind.config = { theme: { extend: { colors: { brand: '#335145' } } } }
  </script>
  <style>
    .tab-active  { background:#335145; color:#fff; }
    .filt-active { background:#335145; color:#fff; }
  </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans min-h-screen">

  <!-- Header -->
  <header class="bg-[#335145] text-white px-8 py-4 sticky top-0 z-20 shadow-md">
    <div class="max-w-4xl mx-auto flex items-center justify-between">
      <h1 class="text-xl font-bold tracking-tight">Commentary Tool</h1>
      <button onclick="load()"
        class="text-sm bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded transition-colors">
        Refresh
      </button>
    </div>
  </header>

  <div class="max-w-4xl mx-auto px-4 py-6">

    <!-- Search + filters -->
    <div class="flex flex-col sm:flex-row gap-3 mb-4">
      <input id="search" type="text" placeholder="Search by ID or name…"
        oninput="render()"
        class="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 shadow-sm text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30 bg-white">
      <div class="flex gap-1.5 shrink-0">
        <button onclick="setFilter('all')" id="filter-all"
          class="filt-active text-sm px-3 py-2 rounded-lg font-medium transition-colors">All</button>
        <button onclick="setFilter('commented')" id="filter-commented"
          class="text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors">With comments</button>
        <button onclick="setFilter('uncommented')" id="filter-uncommented"
          class="text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors">No comments</button>
      </div>
    </div>

    <p id="stats" class="text-xs text-gray-400 mb-4"></p>

    <div id="merger-list">
      <div class="text-center py-12 text-gray-400">Loading…</div>
    </div>

  </div>

<script>
// ── state ──────────────────────────────────────────────────────────────────
let allMergers   = [];
let filter       = 'all';
let expandedId   = null;
let editState    = null;   // { mergerId, index }  — index null = "add new"

// ── bootstrap ──────────────────────────────────────────────────────────────
async function load() {
  try {
    const res  = await fetch('/api/data');
    const data = await res.json();
    allMergers = data.mergers;
    render();
  } catch (e) {
    document.getElementById('merger-list').innerHTML =
      '<p class="text-red-500 text-sm py-4">Failed to load data.</p>';
  }
}

// ── filter + render ────────────────────────────────────────────────────────
function setFilter(f) {
  filter = f;
  ['all','commented','uncommented'].forEach(id => {
    const btn = document.getElementById('filter-' + id);
    if (id === f) {
      btn.className = 'filt-active text-sm px-3 py-2 rounded-lg font-medium transition-colors';
    } else {
      btn.className = 'text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors';
    }
  });
  render();
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  const shown = allMergers.filter(m => {
    if (filter === 'commented'   && m.comments.length === 0) return false;
    if (filter === 'uncommented' && m.comments.length  >  0) return false;
    if (q) return m.merger_id.toLowerCase().includes(q)
                || m.merger_name.toLowerCase().includes(q);
    return true;
  });

  const withCmt = allMergers.filter(m => m.comments.length > 0).length;
  document.getElementById('stats').textContent =
    `Showing ${shown.length} of ${allMergers.length} mergers · ${withCmt} have comments`;

  const container = document.getElementById('merger-list');
  if (!shown.length) {
    container.innerHTML = '<p class="text-center text-gray-400 py-10 text-sm">No mergers match.</p>';
    return;
  }
  container.innerHTML = shown.map(renderCard).join('');
}

// ── card ───────────────────────────────────────────────────────────────────
function renderCard(m) {
  const isOpen = (expandedId === m.merger_id);
  const cnt    = m.comments.length;
  const countBadge = cnt > 0
    ? `<span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700 whitespace-nowrap">${cnt} comment${cnt !== 1 ? 's' : ''}</span>`
    : `<span class="text-xs text-gray-300">no comments</span>`;
  const chevron = `<svg class="w-4 h-4 text-gray-400 shrink-0 transition-transform duration-150 ${isOpen ? 'rotate-180' : ''}"
    fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
  </svg>`;

  return `
<div class="bg-white border ${cnt > 0 ? 'border-green-200' : 'border-gray-200'} rounded-xl mb-3 shadow-sm overflow-hidden">
  <div class="px-5 py-3.5 flex items-center gap-4 cursor-pointer hover:bg-gray-50 transition-colors select-none"
       onclick="toggleExpand('${esc(m.merger_id)}')">
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-0.5 flex-wrap">
        <span class="font-mono text-sm font-bold text-[#335145]">${esc(m.merger_id)}</span>
        ${detBadge(m.accc_determination)}
      </div>
      <p class="text-sm text-gray-500 truncate">${m.merger_name ? esc(m.merger_name) : '—'}</p>
    </div>
    <div class="flex items-center gap-2.5 shrink-0">${countBadge}${chevron}</div>
  </div>
  ${isOpen ? renderExpanded(m) : ''}
</div>`;
}

// ── expanded detail ────────────────────────────────────────────────────────
function renderExpanded(m) {
  const mid          = m.merger_id;
  const addingNew    = editState && editState.mergerId === mid && editState.index === null;
  const editingExist = editState && editState.mergerId === mid && editState.index !== null;

  let body = '';

  if (!m.comments.length && !addingNew) {
    body += `<p class="text-sm text-gray-400 italic mb-3">No commentary yet.</p>`;
  }

  m.comments.forEach((c, i) => {
    const editing = editingExist && editState.index === i;
    body += editing ? renderForm(mid, i, c) : renderComment(mid, i, c);
  });

  if (addingNew) {
    body += renderForm(mid, null, null);
  } else if (!editingExist) {
    body += `
      <button onclick="startAdd('${esc(mid)}')"
        class="mt-1 flex items-center gap-1.5 text-sm text-[#335145] hover:opacity-70 font-medium transition-opacity">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"/>
        </svg>
        Add comment
      </button>`;
  }

  return `<div class="border-t border-gray-100 px-5 py-4 bg-gray-50/50 space-y-4">${body}</div>`;
}

// ── comment (view mode) ────────────────────────────────────────────────────
function renderComment(mergerId, index, c) {
  const renderedMd = marked.parse(c.commentary || '');
  const tagHtml = (c.tags || []).map(t =>
    `<span class="bg-gray-100 text-gray-500 text-xs px-2 py-0.5 rounded">${esc(t)}</span>`
  ).join('');
  const meta = [
    c.date   ? `<span class="text-gray-400">${esc(c.date)}</span>` : '',
    c.author ? `<span class="text-gray-600 font-medium">${esc(c.author)}</span>` : '',
    tagHtml,
  ].filter(Boolean).join('');

  return `
<div class="bg-white border border-gray-200 rounded-lg p-4 relative group">
  <div class="prose prose-sm max-w-none text-gray-700 mb-3 pr-20">${renderedMd}</div>
  ${meta ? `<div class="flex items-center gap-2 flex-wrap text-xs">${meta}</div>` : ''}
  <div class="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
    <button onclick="startEdit('${esc(mergerId)}', ${index})"
      class="text-xs text-gray-400 hover:text-[#335145] px-2 py-1 rounded hover:bg-[#335145]/5 transition-colors">Edit</button>
    <button onclick="doDelete('${esc(mergerId)}', ${index})"
      class="text-xs text-gray-400 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50 transition-colors">Delete</button>
  </div>
</div>`;
}

// ── comment form (add / edit) ──────────────────────────────────────────────
function renderForm(mergerId, index, existing) {
  const isNew    = (index === null);
  const fid      = 'f_' + mergerId.replace(/[^a-z0-9]/gi, '_') + '_' + (isNew ? 'new' : index);
  const defDate  = (existing && existing.date)   || todayStr();
  const defTags  = ((existing && existing.tags)  || []).join(', ');
  const defAuth  = (existing && existing.author) || '';
  const defText  = (existing && existing.commentary) || '';
  const btnLabel = isNew ? 'Add comment' : 'Save changes';

  // Encode the default text safely for an HTML textarea
  // (textarea content only needs & and < escaped)
  const safeText = defText.replace(/&/g, '&amp;').replace(/</g, '&lt;');

  return `
<div id="${fid}" class="bg-white border-2 border-[#335145]/30 rounded-xl p-4">

  <div class="flex gap-1 mb-3 pb-2 border-b border-gray-100">
    <button id="${fid}_tw" onclick="showTab('${fid}','write')"
      class="tab-active text-xs px-3 py-1.5 rounded font-medium transition-colors">Write</button>
    <button id="${fid}_tp" onclick="showTab('${fid}','preview')"
      class="text-xs px-3 py-1.5 rounded font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors">Preview</button>
  </div>

  <div id="${fid}_write">
    <textarea id="${fid}_text" rows="7"
      class="w-full border border-gray-200 rounded-lg p-3 text-sm font-mono resize-y
             focus:outline-none focus:ring-2 focus:ring-[#335145]/30"
      placeholder="Write commentary here… (markdown supported)">${safeText}</textarea>
  </div>
  <div id="${fid}_preview" class="hidden">
    <div id="${fid}_previewc"
      class="prose prose-sm max-w-none min-h-28 p-3 bg-gray-50 rounded-lg border border-gray-200 text-gray-700"></div>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
    <div>
      <label class="block text-xs text-gray-500 mb-1">Date</label>
      <input type="date" id="${fid}_date" value="${defDate}"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
    <div>
      <label class="block text-xs text-gray-500 mb-1">Author <span class="text-gray-300">(optional)</span></label>
      <input type="text" id="${fid}_author" value="${esc(defAuth)}" placeholder="Your name"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
    <div>
      <label class="block text-xs text-gray-500 mb-1">Tags <span class="text-gray-300">(comma-separated)</span></label>
      <input type="text" id="${fid}_tags" value="${esc(defTags)}" placeholder="landmark, approved, …"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
  </div>

  <div class="flex gap-2 mt-4">
    <button onclick="doSave('${esc(mergerId)}', ${isNew ? 'null' : index}, '${fid}')"
      class="bg-[#335145] text-white text-sm px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity">
      ${btnLabel}
    </button>
    <button onclick="cancelEdit()"
      class="bg-gray-100 text-gray-600 text-sm px-4 py-2 rounded-lg font-medium hover:bg-gray-200 transition-colors">
      Cancel
    </button>
  </div>
</div>`;
}

// ── interactions ───────────────────────────────────────────────────────────
function toggleExpand(id) {
  // Don't collapse while actively editing this card
  if (editState && editState.mergerId === id) return;
  expandedId = (expandedId === id) ? null : id;
  editState  = null;
  render();
}

function startAdd(mergerId) {
  expandedId = mergerId;
  editState  = { mergerId, index: null };
  render();
  // Small delay to let DOM settle before scrolling/focusing
  setTimeout(() => {
    const textarea = document.querySelector(`[id^="f_"][id$="_new_text"], [id$="_new"] textarea`);
    if (textarea) textarea.focus();
  }, 50);
}

function startEdit(mergerId, index) {
  expandedId = mergerId;
  editState  = { mergerId, index };
  render();
}

function cancelEdit() {
  editState = null;
  render();
}

function showTab(fid, tab) {
  const writeEl   = document.getElementById(fid + '_write');
  const previewEl = document.getElementById(fid + '_preview');
  const twBtn     = document.getElementById(fid + '_tw');
  const tpBtn     = document.getElementById(fid + '_tp');
  const active    = 'tab-active text-xs px-3 py-1.5 rounded font-medium transition-colors';
  const inactive  = 'text-xs px-3 py-1.5 rounded font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors';

  if (tab === 'preview') {
    const txt = document.getElementById(fid + '_text').value;
    document.getElementById(fid + '_previewc').innerHTML = marked.parse(txt);
    writeEl.classList.add('hidden');
    previewEl.classList.remove('hidden');
    twBtn.className = inactive;
    tpBtn.className = active;
  } else {
    previewEl.classList.add('hidden');
    writeEl.classList.remove('hidden');
    twBtn.className = active;
    tpBtn.className = inactive;
  }
}

async function doSave(mergerId, index, fid) {
  const text   = document.getElementById(fid + '_text').value.trim();
  const date   = document.getElementById(fid + '_date').value;
  const author = document.getElementById(fid + '_author').value.trim();
  const rawTags = document.getElementById(fid + '_tags').value;
  const tags   = rawTags.split(',').map(t => t.trim()).filter(Boolean);

  const payload = { merger_id: mergerId, commentary: text, tags };
  if (date)   payload.date   = date;
  if (author) payload.author = author;
  if (index !== null) payload.index = index;

  const res = await fetch('/api/save', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  });
  if (!res.ok) { alert('Error saving: ' + (await res.text())); return; }

  // Optimistic local update
  let m = allMergers.find(m => m.merger_id === mergerId);
  if (!m) {
    m = { merger_id: mergerId, merger_name: '', status: '', accc_determination: null, comments: [] };
    allMergers.push(m);
  }
  const comment = { commentary: text, tags };
  if (date)   comment.date   = date;
  if (author) comment.author = author;

  if (index === null) {
    m.comments.push(comment);
  } else {
    m.comments[index] = comment;
  }

  editState = null;
  render();
}

async function doDelete(mergerId, index) {
  if (!confirm(`Delete comment ${index + 1} from ${mergerId}?\nThis writes directly to commentary.json.`)) return;

  const res = await fetch('/api/delete', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ merger_id: mergerId, index }),
  });
  if (!res.ok) { alert('Error deleting'); return; }

  const m = allMergers.find(m => m.merger_id === mergerId);
  if (m) m.comments.splice(index, 1);
  render();
}

// ── utilities ──────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function detBadge(det) {
  if (!det) return '';
  const colours = {
    'Approved':                  'bg-green-100 text-green-700',
    'Approved with conditions':  'bg-yellow-100 text-yellow-700',
    'Opposed':                   'bg-red-100 text-red-700',
    'Abandoned':                 'bg-gray-100 text-gray-500',
  };
  const cls = colours[det] || 'bg-blue-100 text-blue-700';
  return `<span class="text-xs px-1.5 py-0.5 rounded font-medium ${cls}">${esc(det)}</span>`;
}

// ── init ───────────────────────────────────────────────────────────────────
load();
</script>

</body>
</html>"""


if __name__ == "__main__":
    print("Starting commentary tool…")
    print("Open http://127.0.0.1:8001 in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
