const REPO = 'nwbort/accc-mergers';
const MAX = 80;

const $ = id => document.getElementById(id);

const savedUrl = localStorage.getItem('fb_worker_url');
const savedSecret = localStorage.getItem('fb_secret');
if (savedUrl) $('url').value = savedUrl;
if (savedSecret) $('secret').value = savedSecret;

function truncate(s) { return s.length <= MAX ? s : s.slice(0, MAX - 1) + '…'; }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function fmt(raw) {
  const d = new Date(raw.replace(' ', 'T') + (raw.includes('Z') ? '' : 'Z'));
  return d.toLocaleString('en-AU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

function issueUrl(row) {
  const title = truncate(row.message);
  const body = ['**From:** ' + row.email, '**Submitted:** ' + row.created_at, '**Feedback ID:** ' + row.id, '', '---', '', row.message].join('\n');
  return 'https://github.com/' + REPO + '/issues/new?' + new URLSearchParams({ title, body, labels: 'feedback' });
}

async function load() {
  const base = $('url').value.trim().replace(/\/$/, '');
  const secret = $('secret').value.trim();
  if (!base || !secret) return;
  localStorage.setItem('fb_worker_url', base);
  localStorage.setItem('fb_secret', secret);

  $('btn-load').disabled = true;
  $('btn-load').textContent = 'Loading…';
  $('err').style.display = 'none';
  $('content').innerHTML = '';

  try {
    const res = await fetch(base + '/feedback', {
      headers: { 'x-secret': secret }
    });
    if (res.status === 403) throw new Error('Forbidden — check your secret');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const rows = await res.json();

    if (!rows.length) {
      $('content').innerHTML = '<p class="msg">No feedback yet.</p>';
      return;
    }

    $('content').innerHTML = `
      <table>
        <thead><tr>
          <th style="width:36px">#</th>
          <th>Message</th>
          <th style="width:180px">Email</th>
          <th style="width:150px">Submitted</th>
          <th style="width:90px;text-align:right">Issue</th>
        </tr></thead>
        <tbody>${rows.map(r => `
          <tr>
            <td class="muted mono">${escapeHtml(r.id)}</td>
            <td>${escapeHtml(r.message)}</td>
            <td class="muted">${escapeHtml(r.email)}</td>
            <td class="muted mono">${escapeHtml(fmt(r.created_at))}</td>
            <td style="text-align:right"><a class="issue" href="${escapeHtml(issueUrl(r))}" target="_blank">New issue ↗</a></td>
          </tr>`).join('')}
        </tbody>
      </table>
      <p class="count">${rows.length} ${rows.length === 1 ? 'entry' : 'entries'}</p>`;
  } catch (e) {
    $('err').textContent = 'Error: ' + e.message;
    $('err').style.display = '';
  } finally {
    $('btn-load').disabled = false;
    $('btn-load').textContent = 'Fetch';
  }
}

async function loadEvents() {
  const base = $('url').value.trim().replace(/\/$/, '');
  const secret = $('secret').value.trim();
  if (!base || !secret) return;

  $('events-err').style.display = 'none';
  $('events-content').innerHTML = '';

  try {
    const res = await fetch(base + '/events', {
      headers: { 'x-secret': secret }
    });
    if (res.status === 403) throw new Error('Forbidden — check your secret');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const rows = await res.json();

    if (!rows.length) {
      $('events-content').innerHTML = '<p class="msg">No feature-usage events recorded yet.</p>';
      return;
    }

    $('events-content').innerHTML = `
      <table>
        <thead><tr>
          <th>Event</th>
          <th style="width:120px">Day</th>
          <th style="width:90px;text-align:right">Count</th>
        </tr></thead>
        <tbody>${rows.map(r => `
          <tr>
            <td>${escapeHtml(r.event_type)}</td>
            <td class="muted mono">${escapeHtml(r.day)}</td>
            <td class="mono" style="text-align:right">${escapeHtml(r.count)}</td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  } catch (e) {
    $('events-err').textContent = 'Error: ' + e.message;
    $('events-err').style.display = '';
  }
}

async function loadApiUsage() {
  const base = $('url').value.trim().replace(/\/$/, '');
  const secret = $('secret').value.trim();
  if (!base || !secret) return;

  $('api-err').style.display = 'none';
  $('api-content').innerHTML = '';

  try {
    const res = await fetch(base + '/api-usage', {
      headers: { 'x-secret': secret }
    });
    if (res.status === 403) throw new Error('Forbidden — check your secret');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const { keys, usage } = await res.json();

    // Totals and last-seen day per client over the 90 days returned.
    const totals = {};
    for (const r of usage) {
      const t = totals[r.label] || (totals[r.label] = { count: 0, last: '' });
      t.count += r.count;
      if (r.day > t.last) t.last = r.day;
    }

    const keyRows = keys.length ? `
      <table>
        <thead><tr>
          <th>Client</th>
          <th style="width:170px">Key</th>
          <th style="width:150px">Created</th>
          <th style="width:150px">Revoked</th>
          <th style="width:110px;text-align:right">Requests (90d)</th>
          <th style="width:110px">Last used</th>
        </tr></thead>
        <tbody>${keys.map(k => `
          <tr>
            <td>${escapeHtml(k.label)}</td>
            <td class="muted mono">${escapeHtml(k.key_hint)}…</td>
            <td class="muted mono">${escapeHtml(fmt(k.created_at))}</td>
            <td class="muted mono">${k.revoked_at ? escapeHtml(fmt(k.revoked_at)) : '—'}</td>
            <td class="mono" style="text-align:right">${escapeHtml((totals[k.label] || {}).count || 0)}</td>
            <td class="muted mono">${escapeHtml((totals[k.label] || {}).last || '—')}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="msg">No API keys issued yet.</p>';

    const usageRows = usage.length ? `
      <table style="margin-top:1rem">
        <thead><tr>
          <th>Client</th>
          <th style="width:120px">Day</th>
          <th style="width:90px;text-align:right">Requests</th>
        </tr></thead>
        <tbody>${usage.map(r => `
          <tr>
            <td>${escapeHtml(r.label)}</td>
            <td class="muted mono">${escapeHtml(r.day)}</td>
            <td class="mono" style="text-align:right">${escapeHtml(r.count)}</td>
          </tr>`).join('')}
        </tbody>
      </table>` : '<p class="msg">No API requests in the last 90 days.</p>';

    $('api-content').innerHTML = keyRows + usageRows;
  } catch (e) {
    $('api-err').textContent = 'Error: ' + e.message;
    $('api-err').style.display = '';
  }
}

$('btn-load').addEventListener('click', () => {
  load();
  loadEvents();
  loadApiUsage();
});

if (savedUrl && savedSecret) {
  load();
  loadEvents();
  loadApiUsage();
}
