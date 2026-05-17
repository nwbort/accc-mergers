import { Link } from 'react-router-dom';

function ConceptSwitcher({ current, dark = false }) {
  const concepts = [
    { id: 1, label: 'The Desk', path: '/dashboard-1' },
    { id: 2, label: 'Terminal', path: '/dashboard-2' },
    { id: 3, label: 'Bento', path: '/dashboard-3' },
  ];
  return (
    <div
      className={`sticky top-16 z-30 backdrop-blur border-b ${
        dark
          ? 'bg-zinc-950/80 border-zinc-800 text-zinc-300'
          : 'bg-white/70 border-slate-200 text-slate-700'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center justify-between gap-4">
        <span className={`text-xs uppercase tracking-widest ${dark ? 'text-zinc-500' : 'text-slate-500'}`}>
          Dashboard concepts
        </span>
        <nav className="flex items-center gap-1.5 text-xs font-medium">
          {concepts.map((c) => {
            const active = c.id === current;
            return (
              <Link
                key={c.id}
                to={c.path}
                className={`px-3 py-1.5 rounded-full transition-all ${
                  active
                    ? dark
                      ? 'bg-emerald-500/20 text-emerald-300'
                      : 'bg-primary text-white'
                    : dark
                    ? 'hover:bg-zinc-800 text-zinc-400'
                    : 'hover:bg-slate-100 text-slate-600'
                }`}
              >
                <span className="opacity-60 mr-1">0{c.id}</span>
                {c.label}
              </Link>
            );
          })}
          <Link
            to="/"
            className={`ml-2 px-3 py-1.5 rounded-full transition-all ${
              dark ? 'hover:bg-zinc-800 text-zinc-500' : 'hover:bg-slate-100 text-slate-500'
            }`}
          >
            ← Current
          </Link>
        </nav>
      </div>
    </div>
  );
}

export default ConceptSwitcher;
