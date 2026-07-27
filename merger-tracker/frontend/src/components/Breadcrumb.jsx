import { Link } from 'react-router';
import { FaChevronRight } from 'react-icons/fa';

/**
 * Breadcrumb trail with FaChevronRight separators. `items` is a flat list of
 * `{ label, to }`; every item links to `to` except the last, which renders as
 * the current page (plain text, `aria-current="page"`).
 */
function Breadcrumb({ ariaLabel, items }) {
  const lastIndex = items.length - 1;

  return (
    <nav aria-label={ariaLabel} className="mb-5">
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-gray-500">
        {items.map((item, index) => {
          const isCurrent = index === lastIndex;
          return (
            <li
              key={item.to || item.label}
              className={index === 0 ? undefined : 'flex items-center gap-x-1.5'}
              aria-current={isCurrent ? 'page' : undefined}
            >
              {index > 0 && (
                <FaChevronRight className="w-3 h-3 text-gray-300" aria-hidden="true" />
              )}
              {isCurrent ? (
                <span className="font-medium text-gray-700">{item.label}</span>
              ) : (
                <Link to={item.to} className="hover:text-primary transition-colors">
                  {item.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumb;
