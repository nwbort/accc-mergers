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

$('btn-load').addEventListener('click', load);

if (savedUrl && savedSecret) load();
