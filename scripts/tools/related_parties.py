#!/usr/bin/env python3
"""Web UI to link ACCC merger parties into canonical "related party" groups.

``data/processed/related_parties.json`` records canonical *groups* of party
identities that are really the same real-world entity (e.g. ``COLES GROUP
LIMITED`` and ``COLES SUPERMARKETS AUSTRALIA PTY LTD``). The static-data
pipeline uses those groups to turn each matching party on a merger detail page
into a link to the register filtered by the group's canonical name — see
``scripts/party_matching.py`` for the matching rules.

New groups are normally suggested daily by ``scripts/detect_related_parties.py``
(via a pull request), but this tool lets you build and edit them by hand: it
lists every distinct party across the register, shows which are already grouped,
and lets you select ungrouped parties to form a new group or fold into an
existing one. It writes directly back to ``related_parties.json``.

Run with: python scripts/tools/related_parties.py
          # open http://127.0.0.1:8003
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow imports from the parent scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

from detect_related_parties import (
    DEFAULT_MERGERS,
    DEFAULT_PARTIES,
    _title_case_name,
    collect_party_records,
)
from party_matching import (
    build_group_lookups,
    dedupe_members,
    match_party,
    merge_groups,
    normalise_identifier,
    normalise_name,
)
from slug import slugify

app = FastAPI()


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def load_mergers() -> list[dict]:
    with DEFAULT_MERGERS.open() as fh:
        raw = json.load(fh)
    return raw if isinstance(raw, list) else raw.get("mergers", [])


def load_parties_doc() -> dict:
    """Load related_parties.json, preserving the whole document (incl. _README)."""
    if DEFAULT_PARTIES.exists():
        with DEFAULT_PARTIES.open() as fh:
            doc = json.load(fh)
    else:
        doc = {"groups": []}
    doc.setdefault("groups", [])
    return doc


def save_parties_doc(doc: dict) -> None:
    DEFAULT_PARTIES.parent.mkdir(parents=True, exist_ok=True)
    with DEFAULT_PARTIES.open("w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def _find_group(doc: dict, group_id: str) -> dict:
    group = next((g for g in doc["groups"] if g.get("id") == group_id), None)
    if group is None:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")
    return group


def _new_group_id(canonical_name: str, existing_ids: set[str]) -> str:
    base = slugify(canonical_name) or "party"
    slug = base
    n = 2
    while slug in existing_ids:
        slug = f"{base}-{n}"
        n += 1
    return slug


# ---------------------------------------------------------------------------
# State assembly
# ---------------------------------------------------------------------------

def build_state() -> dict:
    """Assemble the full UI state: grouped + ungrouped parties, with counts."""
    mergers = load_mergers()
    merger_names = {
        m["merger_id"]: m.get("merger_name", "")
        for m in mergers
        if m.get("merger_id")
    }
    records = list(collect_party_records(mergers).values())

    doc = load_parties_doc()
    groups = doc["groups"]
    by_identifier, by_name = build_group_lookups(groups)

    # Accumulate the distinct mergers each group touches, via the same matching
    # the pipeline uses, so the count reflects what the site will actually link.
    group_merger_ids: dict[str, set[str]] = {g.get("id"): set() for g in groups}

    ungrouped: list[dict] = []
    for r in records:
        group = match_party({"name": r.name, "identifier": r.identifier}, by_identifier, by_name)
        if group is not None:
            group_merger_ids[group.get("id")].update(r.merger_ids)
        else:
            ungrouped.append({
                "name": r.name,
                "identifier": r.identifier,
                "merger_count": len(r.merger_ids),
                "merger_ids": sorted(r.merger_ids),
            })

    ungrouped.sort(key=lambda x: (-x["merger_count"], x["name"].lower()))

    groups_out = []
    for g in groups:
        gid = g.get("id")
        groups_out.append({
            "id": gid,
            "canonical_name": g.get("canonical_name", ""),
            "members": g.get("members", []),
            "merger_count": len(group_merger_ids.get(gid, set())),
        })
    groups_out.sort(key=lambda x: (x["canonical_name"] or "").lower())

    return {
        "groups": groups_out,
        "ungrouped": ungrouped,
        "merger_names": merger_names,
        "counts": {
            "groups": len(groups_out),
            "grouped_parties": len(records) - len(ungrouped),
            "ungrouped_parties": len(ungrouped),
            "total_parties": len(records),
        },
    }


# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------

class Member(BaseModel):
    name: str
    identifier: str = ""


class CreateGroup(BaseModel):
    canonical_name: str = ""
    members: list[Member] = []


class AddMembers(BaseModel):
    members: list[Member]


class RenameGroup(BaseModel):
    canonical_name: str


class RemoveMember(BaseModel):
    index: int


class MergeGroups(BaseModel):
    group_ids: list[str]
    canonical_name: str = ""


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML_CONTENT


@app.get("/api/state")
def get_state() -> dict:
    return build_state()


@app.post("/api/groups")
def create_group(req: CreateGroup) -> dict:
    members = dedupe_members([m.model_dump() for m in req.members])
    if not members:
        raise HTTPException(status_code=400, detail="A group needs at least one member.")

    canonical = (req.canonical_name or "").strip()
    if not canonical:
        # Default to a friendly form of the member appearing in the most records
        # (members arrive sorted best-first from the UI selection).
        canonical = _title_case_name(members[0]["name"])

    doc = load_parties_doc()
    existing_ids = {g.get("id") for g in doc["groups"] if g.get("id")}
    group = {
        "id": _new_group_id(canonical, existing_ids),
        "canonical_name": canonical,
        "members": members,
    }
    doc["groups"].append(group)
    save_parties_doc(doc)
    return {"status": "success", "group": group}


@app.post("/api/groups/{group_id}/members")
def add_members(group_id: str, req: AddMembers) -> dict:
    doc = load_parties_doc()
    group = _find_group(doc, group_id)
    combined = list(group.get("members", [])) + [m.model_dump() for m in req.members]
    group["members"] = dedupe_members(combined)
    save_parties_doc(doc)
    return {"status": "success", "group": group}


@app.post("/api/groups/{group_id}/rename")
def rename_group(group_id: str, req: RenameGroup) -> dict:
    canonical = (req.canonical_name or "").strip()
    if not canonical:
        raise HTTPException(status_code=400, detail="Canonical name cannot be empty.")
    doc = load_parties_doc()
    group = _find_group(doc, group_id)
    group["canonical_name"] = canonical
    save_parties_doc(doc)
    return {"status": "success", "group": group}


@app.post("/api/groups/{group_id}/remove-member")
def remove_member(group_id: str, req: RemoveMember) -> dict:
    doc = load_parties_doc()
    group = _find_group(doc, group_id)
    members = group.get("members", [])
    if req.index < 0 or req.index >= len(members):
        raise HTTPException(status_code=400, detail="Invalid member index.")
    del members[req.index]
    if not members:
        # A group with no members links nothing; drop it entirely.
        doc["groups"] = [g for g in doc["groups"] if g.get("id") != group_id]
    save_parties_doc(doc)
    return {"status": "success"}


@app.post("/api/groups/merge")
def merge_groups_endpoint(req: MergeGroups) -> dict:
    if len(set(req.group_ids)) < 2:
        raise HTTPException(status_code=400, detail="Select at least two different groups to merge.")
    doc = load_parties_doc()
    try:
        doc["groups"] = merge_groups(doc["groups"], req.group_ids, req.canonical_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0])
    save_parties_doc(doc)
    kept_id = req.group_ids[0]
    return {"status": "success", "group": _find_group(doc, kept_id)}


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str) -> dict:
    doc = load_parties_doc()
    before = len(doc["groups"])
    doc["groups"] = [g for g in doc["groups"] if g.get("id") != group_id]
    if len(doc["groups"]) == before:
        raise HTTPException(status_code=404, detail=f"Group not found: {group_id}")
    save_parties_doc(doc)
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Link Related Parties</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = { theme: { extend: { colors: { brand: '#335145', accent: '#10b981' } } } }
    </script>
</head>
<body class="bg-gray-50 text-gray-800 font-sans">
<div class="max-w-7xl mx-auto p-6">
    <div class="flex items-center justify-between mb-2">
        <h1 class="text-3xl font-bold text-brand">Link Related Parties</h1>
        <button onclick="load()" class="text-sm bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded transition-colors">Refresh</button>
    </div>
    <p class="text-sm text-gray-500 mb-6">
        Group party identities that are the same real-world entity. Writes directly to
        <code class="bg-gray-100 px-1 rounded">data/processed/related_parties.json</code>.
    </p>

    <div id="stats" class="flex flex-wrap gap-3 mb-6 text-sm"></div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Ungrouped parties -->
        <div>
            <div class="sticky top-0 bg-gray-50 pt-1 pb-3 z-10">
                <h2 class="text-xl font-bold text-gray-900 mb-2">Ungrouped parties</h2>
                <input id="search" oninput="renderUngrouped()" placeholder="Search name or ABN..."
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
                <div id="selection-bar" class="hidden mt-3 flex items-center gap-3 bg-brand text-white px-4 py-2 rounded">
                    <span id="selection-count" class="text-sm font-medium"></span>
                    <button onclick="createGroupFromSelection()" class="text-sm bg-accent hover:bg-emerald-600 px-3 py-1.5 rounded font-medium transition-colors">New group</button>
                    <button onclick="clearSelection()" class="text-sm bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded transition-colors">Clear</button>
                    <span class="text-xs text-white/70 ml-auto">or click "Add" on a group &rarr;</span>
                </div>
            </div>
            <div id="ungrouped" class="space-y-2"></div>
        </div>

        <!-- Existing groups -->
        <div>
            <div class="sticky top-0 bg-gray-50 pt-1 pb-3 z-10">
                <h2 class="text-xl font-bold text-gray-900 mb-2">Canonical groups</h2>
                <input id="group-search" oninput="renderGroups()" placeholder="Search canonical name, member or ABN..."
                    class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
                <div id="group-selection-bar" class="hidden mt-3 flex items-center gap-3 bg-brand text-white px-4 py-2 rounded">
                    <span id="group-selection-count" class="text-sm font-medium"></span>
                    <button onclick="mergeSelectedGroups()" class="text-sm bg-accent hover:bg-emerald-600 px-3 py-1.5 rounded font-medium transition-colors">Merge</button>
                    <button onclick="clearGroupSelection()" class="text-sm bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded transition-colors">Clear</button>
                </div>
            </div>
            <div id="groups" class="space-y-4"></div>
        </div>
    </div>
</div>

<script>
let STATE = { groups: [], ungrouped: [], merger_names: {}, counts: {} };
const selected = new Map();       // key -> { name, identifier }
const selectedGroups = new Map(); // group id -> canonical_name

function partyKey(p) { return p.name + '\\u0000' + (p.identifier || ''); }
function esc(s) { return (s == null ? '' : String(s)).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
// Keys contain a NUL separator, which the browser's HTML parser mangles when it
// round-trips through an inline event-handler attribute (innerHTML -> onchange="..."),
// silently breaking the lookup. Percent-encode so only safe ASCII ever hits the attribute.
function attrKey(key) { return encodeURIComponent(key).replace(/'/g, '%27'); }

async function load() {
    document.getElementById('ungrouped').innerHTML = '<div class="text-gray-400">Loading...</div>';
    const res = await fetch('/api/state');
    STATE = await res.json();
    // Drop any selections that are no longer ungrouped (e.g. just got grouped).
    const valid = new Set(STATE.ungrouped.map(partyKey));
    for (const k of [...selected.keys()]) if (!valid.has(k)) selected.delete(k);
    // Drop any group selections that no longer exist (e.g. just got merged).
    const validGroups = new Set(STATE.groups.map(g => g.id));
    for (const k of [...selectedGroups.keys()]) if (!validGroups.has(k)) selectedGroups.delete(k);
    renderStats();
    renderUngrouped();
    renderGroups();
    renderSelectionBar();
    renderGroupSelectionBar();
}

function renderStats() {
    const c = STATE.counts || {};
    const chip = (label, val, cls) =>
        `<span class="px-3 py-1.5 rounded-full ${cls}"><strong>${val ?? 0}</strong> ${label}</span>`;
    document.getElementById('stats').innerHTML =
        chip('groups', c.groups, 'bg-brand/10 text-brand') +
        chip('grouped parties', c.grouped_parties, 'bg-emerald-100 text-emerald-800') +
        chip('ungrouped parties', c.ungrouped_parties, 'bg-amber-100 text-amber-800') +
        chip('parties total', c.total_parties, 'bg-gray-200 text-gray-700');
}

function mergerTitles(ids) {
    return ids.map(id => `${id}${STATE.merger_names[id] ? ' - ' + STATE.merger_names[id] : ''}`).join('\\n');
}

function renderUngrouped() {
    const q = document.getElementById('search').value.trim().toLowerCase();
    const list = STATE.ungrouped.filter(p =>
        !q || p.name.toLowerCase().includes(q) || (p.identifier || '').toLowerCase().includes(q));
    const container = document.getElementById('ungrouped');
    if (list.length === 0) {
        container.innerHTML = '<div class="p-4 bg-white rounded border border-gray-200 text-gray-400 text-sm">No matching ungrouped parties.</div>';
        return;
    }
    const shown = list.slice(0, 400);
    container.innerHTML = shown.map(p => {
        const key = partyKey(p);
        const isSel = selected.has(key);
        return `<label class="flex items-start gap-3 bg-white p-3 rounded border ${isSel ? 'border-accent ring-1 ring-accent' : 'border-gray-200'} hover:shadow-sm cursor-pointer transition-all">
            <input type="checkbox" ${isSel ? 'checked' : ''} onchange="toggleSelect(this, '${attrKey(key)}')"
                class="mt-1 h-4 w-4 accent-brand" data-key="${attrKey(key)}" />
            <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-gray-900 break-words">${esc(p.name)}</div>
                <div class="text-xs text-gray-500 mt-0.5">
                    <span class="font-mono">${esc(p.identifier || 'no ABN')}</span>
                    <span title="${esc(mergerTitles(p.merger_ids))}" class="ml-2 text-gray-400 cursor-help">${p.merger_count} merger${p.merger_count === 1 ? '' : 's'}</span>
                </div>
            </div>
        </label>`;
    }).join('') + (list.length > shown.length
        ? `<div class="text-xs text-gray-400 p-2">Showing first ${shown.length} of ${list.length}. Refine your search.</div>` : '');
}

function findUngrouped(key) { return STATE.ungrouped.find(p => partyKey(p) === key); }

function toggleSelect(cb, key) {
    key = decodeURIComponent(key);
    const p = findUngrouped(key);
    if (!p) return;
    if (cb.checked) selected.set(key, { name: p.name, identifier: p.identifier });
    else selected.delete(key);
    // Update just this row's styling + the bar.
    cb.closest('label').classList.toggle('border-accent', cb.checked);
    cb.closest('label').classList.toggle('ring-1', cb.checked);
    cb.closest('label').classList.toggle('ring-accent', cb.checked);
    renderSelectionBar();
}

function clearSelection() { selected.clear(); renderUngrouped(); renderSelectionBar(); }

function renderSelectionBar() {
    const bar = document.getElementById('selection-bar');
    if (selected.size === 0) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');
    document.getElementById('selection-count').textContent =
        `${selected.size} party${selected.size === 1 ? '' : 's'} selected`;
}

function selectedMembers() {
    // Preserve merger-count order so the default canonical name uses the biggest.
    return STATE.ungrouped
        .filter(p => selected.has(partyKey(p)))
        .map(p => ({ name: p.name, identifier: p.identifier }));
}

async function createGroupFromSelection() {
    const members = selectedMembers();
    if (members.length === 0) return;
    const def = members[0].name.replace(/\\s+/g, ' ').trim();
    const name = prompt(`Canonical name for this group of ${members.length} party(s):`, titleCase(def));
    if (name === null) return;
    await api('/api/groups', 'POST', { canonical_name: name.trim(), members });
    selected.clear();
    await load();
}

async function addSelectionToGroup(groupId, groupName) {
    const members = selectedMembers();
    if (members.length === 0) { alert('Select one or more ungrouped parties first.'); return; }
    if (!confirm(`Add ${members.length} selected party(s) to "${groupName}"?`)) return;
    await api('/api/groups/' + encodeURIComponent(groupId) + '/members', 'POST', { members });
    selected.clear();
    await load();
}

function titleCase(s) {
    if (s === s.toUpperCase()) return s.toLowerCase().replace(/\\b\\w/g, c => c.toUpperCase());
    return s;
}

function groupMatches(g, q) {
    if (!q) return true;
    if (g.canonical_name.toLowerCase().includes(q)) return true;
    if (g.id.toLowerCase().includes(q)) return true;
    return g.members.some(m =>
        m.name.toLowerCase().includes(q) || (m.identifier || '').toLowerCase().includes(q));
}

function renderGroups() {
    const container = document.getElementById('groups');
    if (STATE.groups.length === 0) {
        container.innerHTML = '<div class="p-4 bg-white rounded border border-gray-200 text-gray-400 text-sm">No groups yet. Select parties on the left to create one.</div>';
        return;
    }
    const q = document.getElementById('group-search').value.trim().toLowerCase();
    const list = STATE.groups.filter(g => groupMatches(g, q));
    if (list.length === 0) {
        container.innerHTML = '<div class="p-4 bg-white rounded border border-gray-200 text-gray-400 text-sm">No matching groups.</div>';
        return;
    }
    container.innerHTML = list.map(g => {
        const isSel = selectedGroups.has(g.id);
        return `
        <div class="bg-white rounded-lg shadow-sm border-t-4 ${isSel ? 'border-accent ring-1 ring-accent' : 'border-brand'} p-4">
            <div class="flex items-start justify-between gap-3 mb-3">
                <label class="flex items-start gap-2 min-w-0 cursor-pointer">
                    <input type="checkbox" ${isSel ? 'checked' : ''} onchange="toggleGroupSelect(this, '${esc(g.id)}', ${JSON.stringify(g.canonical_name).replace(/"/g, '&quot;')})"
                        class="mt-1.5 h-4 w-4 accent-brand shrink-0" />
                    <div class="min-w-0">
                        <div class="text-lg font-bold text-gray-900 break-words">${esc(g.canonical_name)}</div>
                        <div class="text-xs text-gray-400 font-mono">${esc(g.id)} &middot; ${g.merger_count} merger${g.merger_count === 1 ? '' : 's'}</div>
                    </div>
                </label>
                <div class="flex gap-2 shrink-0">
                    <button onclick="renameGroup('${esc(g.id)}', ${JSON.stringify(g.canonical_name).replace(/"/g, '&quot;')})"
                        class="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded transition-colors">Rename</button>
                    <button onclick="deleteGroup('${esc(g.id)}', ${JSON.stringify(g.canonical_name).replace(/"/g, '&quot;')})"
                        class="text-xs bg-red-50 text-red-600 hover:bg-red-600 hover:text-white border border-red-200 px-2 py-1 rounded transition-colors">Delete</button>
                </div>
            </div>
            <div class="space-y-1.5 mb-3">
                ${g.members.map((m, i) => `
                    <div class="flex items-center justify-between gap-2 bg-gray-50 rounded px-3 py-1.5 border border-gray-100">
                        <div class="min-w-0">
                            <div class="text-sm text-gray-800 break-words">${esc(m.name)}</div>
                            <div class="text-xs text-gray-400 font-mono">${esc(m.identifier || 'no ABN')}</div>
                        </div>
                        <button onclick="removeMember('${esc(g.id)}', ${i})" title="Remove member"
                            class="shrink-0 text-gray-300 hover:text-red-600 text-lg leading-none px-1">&times;</button>
                    </div>`).join('')}
            </div>
            <button onclick="addSelectionToGroup('${esc(g.id)}', ${JSON.stringify(g.canonical_name).replace(/"/g, '&quot;')})"
                class="w-full text-sm bg-brand/5 text-brand hover:bg-brand hover:text-white border border-brand/20 px-3 py-1.5 rounded font-medium transition-colors">
                + Add selected party(s)
            </button>
        </div>`;
    }).join('');
}

function toggleGroupSelect(cb, id, name) {
    if (cb.checked) selectedGroups.set(id, name);
    else selectedGroups.delete(id);
    renderGroups();
    renderGroupSelectionBar();
}

function clearGroupSelection() { selectedGroups.clear(); renderGroups(); renderGroupSelectionBar(); }

function renderGroupSelectionBar() {
    const bar = document.getElementById('group-selection-bar');
    if (selectedGroups.size < 2) { bar.classList.add('hidden'); return; }
    bar.classList.remove('hidden');
    document.getElementById('group-selection-count').textContent =
        `${selectedGroups.size} groups selected`;
}

async function mergeSelectedGroups() {
    const ids = [...selectedGroups.keys()];
    if (ids.length < 2) return;
    const names = [...selectedGroups.values()];
    const def = names[0];
    const name = prompt(`Canonical name for the merged group of ${ids.length} (${names.join(', ')}):`, def);
    if (name === null) return;
    if (!confirm(`Merge ${ids.length} groups into "${name.trim() || def}"? This cannot be undone.`)) return;
    await api('/api/groups/merge', 'POST', { group_ids: ids, canonical_name: name.trim() });
    selectedGroups.clear();
    await load();
}

async function renameGroup(id, current) {
    const name = prompt('Canonical name:', current);
    if (name === null || !name.trim()) return;
    await api('/api/groups/' + encodeURIComponent(id) + '/rename', 'POST', { canonical_name: name.trim() });
    await load();
}

async function removeMember(id, index) {
    if (!confirm('Remove this member from the group?\\n(If it is the last member, the group is deleted.)')) return;
    await api('/api/groups/' + encodeURIComponent(id) + '/remove-member', 'POST', { index });
    await load();
}

async function deleteGroup(id, name) {
    if (!confirm(`Delete the group "${name}"? This unlinks its parties.`)) return;
    await api('/api/groups/' + encodeURIComponent(id), 'DELETE');
    await load();
}

async function api(url, method, body) {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail || detail; } catch (e) {}
        alert('Error: ' + detail);
        throw new Error(detail);
    }
    return res.json();
}

load();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    print("Starting related-parties linker UI...")
    print("Open http://127.0.0.1:8003 in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8003, log_level="warning")
