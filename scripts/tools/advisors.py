#!/usr/bin/env python3
"""
Web UI to record the legal (and other) advisors who worked on each merger.

Writes directly to data/processed/advisors.json. This data is BACKEND-ONLY:
it is deliberately not consumed by generate_static_data.py and is never
published to the front-end. Run with: python scripts/tools/advisors.py
"""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MERGERS_JSON = REPO_ROOT / "data" / "processed" / "mergers.json"
ADVISORS_JSON = REPO_ROOT / "data" / "processed" / "advisors.json"

ADVISOR_TYPES = ["Legal", "Financial", "Economic", "PR", "Other"]

app = FastAPI()


# ── helpers ────────────────────────────────────────────────────────────────

def _load_mergers() -> list:
    with MERGERS_JSON.open() as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("mergers", [])


def _load_advisors() -> dict:
    if not ADVISORS_JSON.exists():
        return {}
    with ADVISORS_JSON.open() as fh:
        return json.load(fh)


def _save_advisors(data: dict) -> None:
    with ADVISORS_JSON.open("w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def _merger_parties(m: dict) -> list:
    """Flatten a merger's parties into [{name, role}] for the UI."""
    parties: list = []
    for role, key in (("acquirer", "acquirers"),
                      ("target", "targets"),
                      ("other", "other_parties")):
        for p in m.get(key) or []:
            name = (p.get("name") or "").strip()
            if name:
                parties.append({"name": name, "role": role})
    return parties


# ── request models ─────────────────────────────────────────────────────────

class PartyRef(BaseModel):
    name: str
    role: str = "other"


class SaveRequest(BaseModel):
    merger_id: str
    index: Optional[int] = None        # None → append new; int → update existing
    firm: str
    type: str = "Legal"
    individuals: List[str] = []
    notes: str = ""
    parties: List[PartyRef] = []
    party_unknown: bool = False


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
    advisors = _load_advisors()
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
            "parties": _merger_parties(m),
            "advisors": advisors.get(mid, {}).get("advisors", []),
        })

    # Append any IDs in advisors.json that aren't in mergers.json
    for key, val in advisors.items():
        if key in _skip or key in seen:
            continue
        result.append({
            "merger_id": key,
            "merger_name": "",
            "status": "",
            "accc_determination": None,
            "parties": [],
            "advisors": val.get("advisors", []),
        })

    return {"mergers": result, "advisor_types": ADVISOR_TYPES}


@app.post("/api/save")
def save_advisor(req: SaveRequest):
    if not req.firm.strip():
        raise HTTPException(400, "Firm/advisor name is required")
    if req.type not in ADVISOR_TYPES:
        raise HTTPException(400, f"Invalid type: {req.type}")

    advisors = _load_advisors()

    entry: dict = {
        "firm": req.firm.strip(),
        "type": req.type,
        "individuals": [n.strip() for n in req.individuals if n.strip()],
        "notes": req.notes.strip(),
        "parties": [] if req.party_unknown
                   else [{"name": p.name, "role": p.role} for p in req.parties],
        "party_unknown": bool(req.party_unknown),
    }

    if req.index is None:
        advisors.setdefault(req.merger_id, {}).setdefault("advisors", []).append(entry)
    else:
        if req.merger_id not in advisors:
            raise HTTPException(404, "Merger not found in advisors")
        items = advisors[req.merger_id].get("advisors", [])
        if not (0 <= req.index < len(items)):
            raise HTTPException(400, "Invalid advisor index")
        items[req.index] = entry

    _save_advisors(advisors)
    return {"status": "success"}


@app.post("/api/delete")
def delete_advisor(req: DeleteRequest):
    advisors = _load_advisors()

    if req.merger_id not in advisors:
        raise HTTPException(404, "Merger not found")
    items = advisors[req.merger_id].get("advisors", [])
    if not (0 <= req.index < len(items)):
        raise HTTPException(400, "Invalid index")

    del items[req.index]
    if not items:
        del advisors[req.merger_id]

    _save_advisors(advisors)
    return {"status": "success"}


# ── frontend ───────────────────────────────────────────────────────────────

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Advisors Tool — ACCC Mergers</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = { theme: { extend: { colors: { brand: '#335145' } } } }
  </script>
  <style>
    .filt-active { background:#335145; color:#fff; }
  </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans min-h-screen">

  <header class="bg-[#335145] text-white px-8 py-4 sticky top-0 z-20 shadow-md">
    <div class="max-w-4xl mx-auto flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold tracking-tight">Advisors Tool</h1>
        <p class="text-xs text-white/60">Backend only — not published to the front-end</p>
      </div>
      <button onclick="load()"
        class="text-sm bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded transition-colors">
        Refresh
      </button>
    </div>
  </header>

  <div class="max-w-4xl mx-auto px-4 py-6">

    <div class="flex flex-col sm:flex-row gap-3 mb-4">
      <input id="search" type="text" placeholder="Search by ID, name or advisor…"
        oninput="render()"
        class="flex-1 border border-gray-200 rounded-lg px-4 py-2.5 shadow-sm text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30 bg-white">
      <div class="flex gap-1.5 shrink-0">
        <button onclick="setFilter('all')" id="filter-all"
          class="filt-active text-sm px-3 py-2 rounded-lg font-medium transition-colors">All</button>
        <button onclick="setFilter('with')" id="filter-with"
          class="text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors">With advisors</button>
        <button onclick="setFilter('without')" id="filter-without"
          class="text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors">No advisors</button>
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
let advisorTypes = ['Legal','Financial','Economic','PR','Other'];
let filter       = 'all';
let expandedId   = null;
let editState    = null;   // { mergerId, index }  — index null = "add new"

const TYPE_COLOURS = {
  'Legal':     'bg-indigo-100 text-indigo-700',
  'Financial': 'bg-green-100 text-green-700',
  'Economic':  'bg-amber-100 text-amber-700',
  'PR':        'bg-pink-100 text-pink-700',
  'Other':     'bg-gray-100 text-gray-600',
};

// ── bootstrap ──────────────────────────────────────────────────────────────
async function load() {
  try {
    const res  = await fetch('/api/data');
    const data = await res.json();
    allMergers   = data.mergers;
    advisorTypes = data.advisor_types || advisorTypes;
    render();
  } catch (e) {
    document.getElementById('merger-list').innerHTML =
      '<p class="text-red-500 text-sm py-4">Failed to load data.</p>';
  }
}

// ── filter + render ────────────────────────────────────────────────────────
function setFilter(f) {
  filter = f;
  ['all','with','without'].forEach(id => {
    const btn = document.getElementById('filter-' + id);
    btn.className = (id === f)
      ? 'filt-active text-sm px-3 py-2 rounded-lg font-medium transition-colors'
      : 'text-sm px-3 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 transition-colors';
  });
  render();
}

function advisorMatchesQuery(a, q) {
  if ((a.firm || '').toLowerCase().includes(q)) return true;
  return (a.individuals || []).some(n => n.toLowerCase().includes(q));
}

function render() {
  const q = document.getElementById('search').value.toLowerCase();
  const shown = allMergers.filter(m => {
    const n = (m.advisors || []).length;
    if (filter === 'with'    && n === 0) return false;
    if (filter === 'without' && n  >  0) return false;
    if (q) return m.merger_id.toLowerCase().includes(q)
                || m.merger_name.toLowerCase().includes(q)
                || (m.advisors || []).some(a => advisorMatchesQuery(a, q));
    return true;
  });

  const withAdv = allMergers.filter(m => (m.advisors || []).length > 0).length;
  document.getElementById('stats').textContent =
    `Showing ${shown.length} of ${allMergers.length} mergers · ${withAdv} have advisors`;

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
  const cnt    = (m.advisors || []).length;
  const countBadge = cnt > 0
    ? `<span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700 whitespace-nowrap">${cnt} advisor${cnt !== 1 ? 's' : ''}</span>`
    : `<span class="text-xs text-gray-300">no advisors</span>`;
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

  if (!(m.advisors || []).length && !addingNew) {
    body += `<p class="text-sm text-gray-400 italic mb-3">No advisors recorded yet.</p>`;
  }

  (m.advisors || []).forEach((a, i) => {
    const editing = editingExist && editState.index === i;
    body += editing ? renderForm(m, i, a) : renderAdvisor(mid, i, a);
  });

  if (addingNew) {
    body += renderForm(m, null, null);
  } else if (!editingExist) {
    body += `
      <button onclick="startAdd('${esc(mid)}')"
        class="mt-1 flex items-center gap-1.5 text-sm text-[#335145] hover:opacity-70 font-medium transition-opacity">
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4"/>
        </svg>
        Add advisor
      </button>`;
  }

  return `<div class="border-t border-gray-100 px-5 py-4 bg-gray-50/50 space-y-3">${body}</div>`;
}

// ── advisor (view mode) ────────────────────────────────────────────────────
function renderAdvisor(mergerId, index, a) {
  const typeCls = TYPE_COLOURS[a.type] || TYPE_COLOURS['Other'];
  const typeBadge = `<span class="text-xs px-1.5 py-0.5 rounded font-medium ${typeCls}">${esc(a.type || 'Other')}</span>`;

  let partyHtml;
  if (a.party_unknown) {
    partyHtml = `<span class="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-700">Party unknown</span>`;
  } else if ((a.parties || []).length) {
    partyHtml = (a.parties || []).map(p =>
      `<span class="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">${esc(p.name)}<span class="text-gray-400"> · ${esc(p.role)}</span></span>`
    ).join(' ');
  } else {
    partyHtml = `<span class="text-xs text-gray-300">no party set</span>`;
  }

  const individuals = (a.individuals || []).length
    ? `<p class="text-xs text-gray-500 mt-1">${(a.individuals || []).map(esc).join(', ')}</p>` : '';
  const notes = a.notes
    ? `<p class="text-xs text-gray-500 italic mt-1">${esc(a.notes)}</p>` : '';

  return `
<div class="bg-white border border-gray-200 rounded-lg p-4 relative group">
  <div class="flex items-center gap-2 flex-wrap pr-20">
    ${typeBadge}
    <span class="text-sm font-semibold text-gray-800">${esc(a.firm)}</span>
  </div>
  <div class="flex items-center gap-1.5 flex-wrap mt-2">${partyHtml}</div>
  ${individuals}
  ${notes}
  <div class="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
    <button onclick="startEdit('${esc(mergerId)}', ${index})"
      class="text-xs text-gray-400 hover:text-[#335145] px-2 py-1 rounded hover:bg-[#335145]/5 transition-colors">Edit</button>
    <button onclick="doDelete('${esc(mergerId)}', ${index})"
      class="text-xs text-gray-400 hover:text-red-600 px-2 py-1 rounded hover:bg-red-50 transition-colors">Delete</button>
  </div>
</div>`;
}

// ── advisor form (add / edit) ──────────────────────────────────────────────
function renderForm(m, index, existing) {
  const mergerId  = m.merger_id;
  const isNew     = (index === null);
  const fid       = 'f_' + mergerId.replace(/[^a-z0-9]/gi, '_') + '_' + (isNew ? 'new' : index);
  const defFirm   = (existing && existing.firm) || '';
  const defType   = (existing && existing.type) || 'Legal';
  const defInd    = ((existing && existing.individuals) || []).join(', ');
  const defNotes  = (existing && existing.notes) || '';
  const defUnknown = !!(existing && existing.party_unknown);
  const selected  = new Set(((existing && existing.parties) || []).map(p => p.name));
  const btnLabel  = isNew ? 'Add advisor' : 'Save changes';

  const typeOpts = advisorTypes.map(t =>
    `<option value="${esc(t)}" ${t === defType ? 'selected' : ''}>${esc(t)}</option>`
  ).join('');

  const partyRows = (m.parties || []).length
    ? (m.parties || []).map((p, i) => `
        <label class="flex items-center gap-2 text-sm py-0.5 ${defUnknown ? 'opacity-40' : ''}">
          <input type="checkbox" class="${fid}_party rounded border-gray-300"
            data-name="${esc(p.name)}" data-role="${esc(p.role)}"
            ${selected.has(p.name) ? 'checked' : ''} ${defUnknown ? 'disabled' : ''}>
          <span class="text-gray-700">${esc(p.name)}</span>
          <span class="text-xs text-gray-400">· ${esc(p.role)}</span>
        </label>`).join('')
    : `<p class="text-xs text-gray-400 italic">No parties listed on this merger — use "party unknown" or add notes.</p>`;

  return `
<div id="${fid}" class="bg-white border-2 border-[#335145]/30 rounded-xl p-4 space-y-3">

  <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
    <div class="sm:col-span-2">
      <label class="block text-xs text-gray-500 mb-1">Firm / advisor name</label>
      <input type="text" id="${fid}_firm" value="${esc(defFirm)}" placeholder="e.g. Allens"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
    <div>
      <label class="block text-xs text-gray-500 mb-1">Type</label>
      <select id="${fid}_type"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">${typeOpts}</select>
    </div>
  </div>

  <div>
    <label class="block text-xs text-gray-500 mb-1">Acted for</label>
    <div class="border border-gray-200 rounded-lg px-3 py-2 bg-gray-50/50">
      <div id="${fid}_parties">${partyRows}</div>
      <label class="flex items-center gap-2 text-sm pt-2 mt-2 border-t border-gray-200">
        <input type="checkbox" id="${fid}_unknown" class="rounded border-gray-300"
          ${defUnknown ? 'checked' : ''}
          onchange="toggleUnknown('${fid}')">
        <span class="text-gray-700">Worked on the deal — party unknown</span>
      </label>
    </div>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
    <div>
      <label class="block text-xs text-gray-500 mb-1">Individuals <span class="text-gray-300">(comma-separated, optional)</span></label>
      <input type="text" id="${fid}_individuals" value="${esc(defInd)}" placeholder="Jane Doe, John Smith"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
    <div>
      <label class="block text-xs text-gray-500 mb-1">Notes <span class="text-gray-300">(optional)</span></label>
      <input type="text" id="${fid}_notes" value="${esc(defNotes)}" placeholder="e.g. lead counsel, source…"
        class="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm
               focus:outline-none focus:ring-2 focus:ring-[#335145]/30">
    </div>
  </div>

  <div class="flex gap-2 pt-1">
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
  if (editState && editState.mergerId === id) return;
  expandedId = (expandedId === id) ? null : id;
  editState  = null;
  render();
}

function startAdd(mergerId) {
  expandedId = mergerId;
  editState  = { mergerId, index: null };
  render();
  setTimeout(() => {
    const el = document.querySelector(`[id$="_new_firm"]`);
    if (el) el.focus();
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

function toggleUnknown(fid) {
  const on = document.getElementById(fid + '_unknown').checked;
  document.querySelectorAll('.' + fid + '_party').forEach(cb => {
    cb.disabled = on;
    cb.closest('label').classList.toggle('opacity-40', on);
  });
}

async function doSave(mergerId, index, fid) {
  const firm  = document.getElementById(fid + '_firm').value.trim();
  if (!firm) { alert('Firm / advisor name is required.'); return; }
  const type  = document.getElementById(fid + '_type').value;
  const notes = document.getElementById(fid + '_notes').value.trim();
  const individuals = document.getElementById(fid + '_individuals').value
    .split(',').map(s => s.trim()).filter(Boolean);
  const partyUnknown = document.getElementById(fid + '_unknown').checked;

  const parties = partyUnknown ? [] : Array.from(
    document.querySelectorAll('.' + fid + '_party'))
    .filter(cb => cb.checked)
    .map(cb => ({ name: cb.dataset.name, role: cb.dataset.role }));

  const payload = {
    merger_id: mergerId, firm, type, notes, individuals,
    parties, party_unknown: partyUnknown,
  };
  if (index !== null) payload.index = index;

  const res = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) { alert('Error saving: ' + (await res.text())); return; }

  // Optimistic local update
  let m = allMergers.find(m => m.merger_id === mergerId);
  if (!m) {
    m = { merger_id: mergerId, merger_name: '', status: '', accc_determination: null, parties: [], advisors: [] };
    allMergers.push(m);
  }
  const entry = { firm, type, individuals, notes, parties, party_unknown: partyUnknown };
  if (index === null) m.advisors.push(entry);
  else                m.advisors[index] = entry;

  editState = null;
  render();
}

async function doDelete(mergerId, index) {
  if (!confirm(`Delete advisor ${index + 1} from ${mergerId}?\nThis writes directly to advisors.json.`)) return;

  const res = await fetch('/api/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ merger_id: mergerId, index }),
  });
  if (!res.ok) { alert('Error deleting'); return; }

  const m = allMergers.find(m => m.merger_id === mergerId);
  if (m) m.advisors.splice(index, 1);
  render();
}

// ── utilities ──────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
    print("Starting advisors tool…")
    print("Open http://127.0.0.1:8002 in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")
