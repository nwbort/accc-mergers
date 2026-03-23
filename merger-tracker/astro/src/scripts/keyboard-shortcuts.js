// Keyboard shortcuts for power users
let pendingG = false;
let gTimer = null;

const modal = document.getElementById('keyboard-shortcuts-modal');

function toggleHelp() {
  if (!modal) return;
  modal.classList.toggle('hidden');
}

function closeHelp() {
  if (!modal) return;
  modal.classList.add('hidden');
}

// Close modal on backdrop click or close button
modal?.querySelector('[data-shortcuts-backdrop]')?.addEventListener('click', closeHelp);
modal?.querySelector('[data-shortcuts-close]')?.addEventListener('click', closeHelp);

window.addEventListener('keydown', (e) => {
  const tag = e.target.tagName;
  const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

  // Allow Escape to blur inputs or close modals
  if (e.key === 'Escape') {
    if (isInput) {
      e.target.blur();
      return;
    }
    if (modal && !modal.classList.contains('hidden')) {
      closeHelp();
      return;
    }
    return;
  }

  if (isInput) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  // "g" prefix for navigation
  if (pendingG) {
    pendingG = false;
    clearTimeout(gTimer);

    const routes = {
      d: '/',
      m: '/mergers',
      t: '/timeline',
      i: '/industries',
      c: '/commentary',
      a: '/analysis',
    };

    const route = routes[e.key];
    if (route && window.location.pathname !== route) {
      e.preventDefault();
      window.location.href = route;
    }
    return;
  }

  if (e.key === 'g') {
    pendingG = true;
    gTimer = setTimeout(() => { pendingG = false; }, 2500);
    return;
  }

  // "/" to focus search
  if (e.key === '/') {
    const searchInput = document.getElementById('search');
    if (searchInput) {
      e.preventDefault();
      searchInput.focus();
    }
    return;
  }

  // "?" to toggle help
  if (e.key === '?') {
    e.preventDefault();
    toggleHelp();
    return;
  }
});
