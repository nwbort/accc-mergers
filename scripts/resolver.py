#!/usr/bin/env python3
"""
Web UI to resolve ACCC merger duplicate events.
Run with: python scripts/resolver.py
"""

import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Import the logic and paths directly from your existing script
try:
    from detect_duplicates import build_report, DEFAULT_INPUT
except ImportError:
    raise ImportError("Please ensure this script is in the same directory as detect_duplicates.py")

app = FastAPI()

class RemoveRequest(BaseModel):
    merger_id: str
    index: int

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT

@app.get("/api/report")
def get_report():
    """Generate the duplicate report on the fly."""
    with DEFAULT_INPUT.open() as fh:
        raw = json.load(fh)
    mergers = raw if isinstance(raw, list) else raw.get("mergers", [])
    return build_report(mergers)

@app.post("/api/remove")
def remove_event(req: RemoveRequest):
    """Delete a specific event by index and write to disk."""
    with DEFAULT_INPUT.open() as fh:
        raw = json.load(fh)
    
    # Handle both top-level list and wrapped dict
    mergers = raw if isinstance(raw, list) else raw.get("mergers", [])
    
    target = next((m for m in mergers if m.get("merger_id") == req.merger_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Merger not found")
        
    events = target.get("events", [])
    if req.index < 0 or req.index >= len(events):
        raise HTTPException(status_code=400, detail="Invalid event index")
        
    # Delete the event
    del events[req.index]
    
    # Save directly back to mergers.json
    with DEFAULT_INPUT.open("w") as fh:
        json.dump(raw, fh, indent=2)
        
    return {"status": "success"}

# --- Minimal Frontend ---
HTML_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <title>Resolve Duplicates</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: { brand: '#335145' }
                }
            }
        }
    </script>
</head>
<body class="bg-gray-50 text-gray-800 p-8 font-sans">
    <div id="app" class="max-w-5xl mx-auto">
        <div class="flex items-center justify-between mb-8">
            <h1 class="text-3xl font-bold text-brand">Duplicate Event Resolver</h1>
            <button onclick="load()" class="text-sm bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded transition-colors">Refresh Data</button>
        </div>
        <div id="content" class="text-gray-500">Scanning mergers.json...</div>
    </div>

    <script>
    async function load() {
        const container = document.getElementById('content');
        container.innerHTML = 'Loading...';
        
        const res = await fetch('/api/report');
        const data = await res.json();
        
        if (data.findings.length === 0) {
            container.innerHTML = '<div class="p-6 bg-green-50 text-green-800 rounded-lg border border-green-200">No duplicates found! Your JSON is clean.</div>';
            return;
        }
        
        let html = '';
        data.findings.forEach(merger => {
            html += `<div class="bg-white p-6 rounded-lg shadow-sm mb-6 border-t-4 border-brand">
                <h2 class="text-xl font-bold mb-4 text-gray-900">${merger.merger_id} &mdash; ${merger.merger_name}</h2>`;
                
            merger.duplicate_groups.forEach((group) => {
                const isCertain = group.kind === 'certain';
                const badgeClass = isCertain ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800';
                
                html += `<div class="mb-4 bg-gray-50 p-4 rounded-md border border-gray-200">
                    <div class="flex items-center gap-3 mb-4">
                        <span class="${badgeClass} px-2 py-1 rounded text-xs font-bold uppercase tracking-wider">${group.kind}</span>
                        <span class="font-mono text-sm text-gray-600">${group.date}</span>
                    </div>
                    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">`;
                    
                group.events.forEach((ev, i) => {
                    const globalIdx = group.indices[i];
                    html += `<div class="border border-gray-200 p-4 rounded bg-white relative hover:shadow-md transition-shadow">
                        <div class="text-sm font-semibold mb-3 pr-24">${ev.title || '<em>No title</em>'}</div>
                        <div class="text-xs text-gray-600 space-y-1.5 mb-2">
                            <div><span class="text-gray-400 w-20 inline-block">Index</span> <strong>${globalIdx}</strong></div>
                            <div><span class="text-gray-400 w-20 inline-block">Status</span> <code class="bg-gray-100 px-1 rounded">${ev.status || '—'}</code></div>
                            <div><span class="text-gray-400 w-20 inline-block">URL</span> ${ev.url ? `<a href="${ev.url}" target="_blank" class="text-blue-600 hover:underline">View on ACCC &nearr;</a>` : '—'}</div>
                            <div><span class="text-gray-400 w-20 inline-block">GH Link</span> ${ev.url_gh ? 'Yes' : 'No'}</div>
                        </div>
                        <button onclick="removeEvent('${merger.merger_id}', ${globalIdx})" 
                            class="absolute bottom-4 right-4 bg-red-50 text-red-600 hover:bg-red-600 hover:text-white border border-red-200 px-3 py-1.5 rounded text-sm font-medium transition-colors">
                            Remove
                        </button>
                    </div>`;
                });
                
                html += `</div></div>`;
            });
            html += `</div>`;
        });
        container.innerHTML = html;
    }

    async function removeEvent(mergerId, index) {
        if(!confirm('Delete this event? This writes directly to mergers.json.')) return;
        
        await fetch('/api/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ merger_id: mergerId, index: index })
        });
        
        // Immediately reload the data so array indices stay accurate
        load(); 
    }

    // Init
    load();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("Starting duplicate resolver UI...")
    print("Open http://127.0.0.1:8000 in your browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
