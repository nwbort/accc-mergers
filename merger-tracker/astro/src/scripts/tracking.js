// Tracking system — vanilla JS island for localStorage-based merger tracking
const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  SEEN_EVENTS: 'merger_tracker_seen_events',
};

function getTrackedIds() {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.TRACKED_MERGERS);
    return stored ? JSON.parse(stored) : [];
  } catch { return []; }
}

function setTrackedIds(ids) {
  localStorage.setItem(STORAGE_KEYS.TRACKED_MERGERS, JSON.stringify(ids));
}

function getSeenEventKeys() {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.SEEN_EVENTS);
    return stored ? new Set(JSON.parse(stored)) : new Set();
  } catch { return new Set(); }
}

function setSeenEventKeys(keys) {
  localStorage.setItem(STORAGE_KEYS.SEEN_EVENTS, JSON.stringify(Array.from(keys)));
}

function getEventKey(event) {
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  return `${event.merger_id}_${event.date}_${title}`;
}

// Track/untrack button handler
function initTrackButtons() {
  document.querySelectorAll('[data-track-merger]').forEach(btn => {
    const mergerId = btn.getAttribute('data-track-merger');
    const ids = getTrackedIds();
    const tracked = ids.includes(mergerId);
    updateTrackButton(btn, tracked);

    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const currentIds = getTrackedIds();
      const isTracked = currentIds.includes(mergerId);

      if (isTracked) {
        setTrackedIds(currentIds.filter(id => id !== mergerId));
      } else {
        setTrackedIds([...currentIds, mergerId]);
        // Mark existing events as seen for newly tracked mergers
        markExistingEventsAsSeen(mergerId);
      }

      updateTrackButton(btn, !isTracked);
      updateNotificationBadge();
    });
  });
}

function updateTrackButton(btn, tracked) {
  const bellSvg = tracked
    ? '<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>'
    : '<svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>';

  btn.innerHTML = bellSvg + (tracked ? ' Tracking' : ' Track');
  btn.setAttribute('aria-pressed', String(tracked));
  btn.setAttribute('aria-label', tracked ? 'Stop tracking this merger' : 'Track this merger for updates');

  if (tracked) {
    btn.className = btn.className.replace(/bg-gray-100 text-gray-600 border-gray-200\/60 hover:bg-gray-200/g, '');
    btn.classList.add('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary-dark', 'shadow-sm');
    btn.classList.remove('bg-gray-100', 'text-gray-600', 'border-gray-200/60', 'hover:bg-gray-200');
  } else {
    btn.classList.remove('bg-primary', 'text-white', 'border-primary', 'hover:bg-primary-dark', 'shadow-sm');
    btn.classList.add('bg-gray-100', 'text-gray-600', 'border-gray-200/60', 'hover:bg-gray-200');
  }
}

async function markExistingEventsAsSeen(mergerId) {
  try {
    const res = await fetch(`/data/mergers/${mergerId}.json`);
    if (!res.ok) return;
    const merger = await res.json();
    if (!merger.events) return;
    const seenKeys = getSeenEventKeys();
    merger.events.forEach(event => {
      seenKeys.add(getEventKey({ ...event, merger_id: mergerId }));
    });
    setSeenEventKeys(seenKeys);
  } catch { /* ignore */ }
}

// Notification bell and badge
async function updateNotificationBadge() {
  const ids = getTrackedIds();
  const badge = document.getElementById('notification-badge');
  const countEl = document.getElementById('notification-count');

  if (ids.length === 0) {
    badge?.classList.add('hidden');
    return;
  }

  // Fetch events for tracked mergers to count unseen
  const seenKeys = getSeenEventKeys();
  let unseenCount = 0;

  for (const id of ids) {
    try {
      const res = await fetch(`/data/mergers/${id}.json`);
      if (!res.ok) continue;
      const merger = await res.json();
      if (!merger.events) continue;
      merger.events.forEach(event => {
        const key = getEventKey({ ...event, merger_id: id });
        if (!seenKeys.has(key)) unseenCount++;
      });
    } catch { /* ignore */ }
  }

  if (unseenCount > 0 && badge && countEl) {
    badge.classList.remove('hidden');
    countEl.textContent = unseenCount > 9 ? '9+' : String(unseenCount);
  } else {
    badge?.classList.add('hidden');
  }
}

// Notification panel toggle
function initNotificationPanel() {
  const bell = document.getElementById('notification-bell');
  const panel = document.getElementById('notification-panel');

  if (!bell || !panel) return;

  bell.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = !panel.classList.contains('hidden');
    panel.classList.toggle('hidden');
    bell.setAttribute('aria-expanded', String(!isOpen));

    if (!isOpen) {
      loadNotificationContent();
      // Mark all events as seen
      markAllTrackedEventsSeen();
    }
  });

  // Close on click outside
  document.addEventListener('mousedown', (e) => {
    if (!panel.contains(e.target) && !bell.contains(e.target)) {
      panel.classList.add('hidden');
      bell.setAttribute('aria-expanded', 'false');
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !panel.classList.contains('hidden')) {
      panel.classList.add('hidden');
      bell.setAttribute('aria-expanded', 'false');
    }
  });
}

async function markAllTrackedEventsSeen() {
  const ids = getTrackedIds();
  const seenKeys = getSeenEventKeys();

  for (const id of ids) {
    try {
      const res = await fetch(`/data/mergers/${id}.json`);
      if (!res.ok) continue;
      const merger = await res.json();
      if (!merger.events) continue;
      merger.events.forEach(event => {
        seenKeys.add(getEventKey({ ...event, merger_id: id }));
      });
    } catch { /* ignore */ }
  }

  setSeenEventKeys(seenKeys);
  const badge = document.getElementById('notification-badge');
  badge?.classList.add('hidden');
}

async function loadNotificationContent() {
  const ids = getTrackedIds();
  const content = document.getElementById('notification-content');
  const footer = document.getElementById('notification-footer');
  const countLabel = document.getElementById('tracked-count-label');

  if (!content) return;

  if (countLabel) {
    countLabel.textContent = ids.length > 0 ? `(${ids.length})` : '';
  }

  if (ids.length === 0) {
    content.innerHTML = `
      <div class="px-5 py-10 text-center">
        <div class="w-12 h-12 rounded-2xl bg-gray-50 flex items-center justify-center mx-auto mb-3">
          <svg class="h-6 w-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
        </div>
        <p class="text-sm font-medium text-gray-500 mb-1">No tracked mergers yet</p>
        <p class="text-xs text-gray-400">Visit a merger's page and click "Track" to receive updates</p>
      </div>`;
    footer?.classList.add('hidden');
    return;
  }

  footer?.classList.remove('hidden');
  content.innerHTML = '<div class="px-5 py-10 text-center"><div class="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-3"></div><p class="text-sm text-gray-500">Loading events...</p></div>';

  const seenKeys = getSeenEventKeys();
  const groups = {};

  for (const id of ids) {
    try {
      const res = await fetch(`/data/mergers/${id}.json`);
      if (!res.ok) continue;
      const merger = await res.json();
      if (!merger.events || merger.events.length === 0) continue;

      groups[id] = {
        merger_id: id,
        merger_name: merger.merger_name,
        events: merger.events.map(e => ({ ...e, merger_id: id, merger_name: merger.merger_name }))
          .sort((a, b) => new Date(b.date) - new Date(a.date)),
      };
    } catch { /* ignore */ }
  }

  const sortedGroups = Object.values(groups).sort((a, b) => {
    const aDate = a.events[0]?.date || '';
    const bDate = b.events[0]?.date || '';
    return bDate.localeCompare(aDate);
  });

  if (sortedGroups.length === 0) {
    content.innerHTML = `
      <div class="px-5 py-10 text-center">
        <p class="text-sm font-medium text-gray-500">No recent events</p>
        <p class="text-xs text-gray-400 mt-1">Events for your tracked mergers will appear here</p>
      </div>`;
    return;
  }

  function formatDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-AU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch { return 'N/A'; }
  }

  content.innerHTML = '<div class="divide-y divide-gray-50">' + sortedGroups.map(group => {
    const eventsHtml = group.events.slice(0, 5).map(event => {
      const key = getEventKey(event);
      const isNew = !seenKeys.has(key);
      return `<li class="text-xs">
        <div class="flex items-start gap-2">
          <span class="mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${isNew ? 'bg-emerald-500' : 'bg-gray-300'}"></span>
          <div class="flex-1 min-w-0">
            <p class="text-gray-700 truncate">${event.display_title || event.title}</p>
            <p class="text-gray-400">${formatDate(event.date)}</p>
          </div>
        </div>
      </li>`;
    }).join('');

    return `<div class="p-4">
      <a href="/mergers/${group.merger_id}" class="block hover:bg-gray-50/80 -mx-4 -mt-4 px-4 pt-4 pb-2 rounded-t-xl transition-colors">
        <h3 class="text-sm font-medium text-gray-900 hover:text-primary transition-colors line-clamp-2">${group.merger_name}</h3>
        <p class="text-xs text-gray-400 mt-0.5">${group.merger_id}</p>
      </a>
      <ul class="mt-2 space-y-2">${eventsHtml}</ul>
    </div>`;
  }).join('') + '</div>';
}

// Initialize on page load
initTrackButtons();
initNotificationPanel();
updateNotificationBadge();

// Also handle tracked star icons in the mergers list
document.querySelectorAll('[data-tracked-star]').forEach(el => {
  const id = el.getAttribute('data-tracked-star');
  const ids = getTrackedIds();
  if (!ids.includes(id)) {
    el.classList.add('hidden');
  }
});
