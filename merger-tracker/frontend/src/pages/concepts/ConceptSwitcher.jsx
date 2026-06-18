import { Link } from 'react-router-dom';

// A small pill row that lets a reviewer jump between the three dashboard
// concepts (and back to the index). Rendered at the top of every concept page.
// `dark` flips the palette for the Command Deck's dark hero.

const CONCEPTS = [
  { key: 'pulse', label: 'Pulse', to: '/concepts/pulse' },
  { key: 'command', label: 'Command Deck', to: '/concepts/command' },
  { key: 'clarity', label: 'Clarity', to: '/concepts/clarity' },
  { key: 'bento', label: 'Bento', to: '/concepts/bento' },
  { key: 'atlas', label: 'Atlas', to: '/concepts/atlas' },
  { key: 'agenda', label: 'Agenda', to: '/concepts/agenda' },
];

function ConceptSwitcher({ current, dark = false }) {
  const base = dark
    ? 'text-white/60 hover:text-white hover:bg-white/10'
    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100';
  const active = dark
    ? 'bg-white text-primary-dark'
    : 'bg-primary text-white';

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        to="/concepts"
        className={`text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors ${base}`}
      >
        ← Concepts
      </Link>
      <span className={dark ? 'text-white/20' : 'text-gray-300'}>|</span>
      {CONCEPTS.map((c) => (
        <Link
          key={c.key}
          to={c.to}
          className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors ${
            c.key === current ? active : base
          }`}
        >
          {c.label}
        </Link>
      ))}
    </div>
  );
}

export default ConceptSwitcher;
