import { Link } from 'react-router';
import { FaExclamationCircle } from 'react-icons/fa';
import { CARD } from '../utils/classNames';

const PRIMARY_BUTTON =
  'inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm';
const SECONDARY_BUTTON =
  'inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors';

// One action button. `to` is an in-app route, `href` an external page (opened
// in a new tab), and `onClick` a plain button — the error boundary and the
// failed-fetch state use that to reload rather than navigate.
function ActionButton({ action, className }) {
  if (action.to) {
    return (
      <Link to={action.to} className={className}>
        {action.label}
      </Link>
    );
  }
  if (action.href) {
    return (
      <a
        href={action.href}
        target="_blank"
        rel="noopener noreferrer"
        className={className}
        aria-label={action.ariaLabel}
      >
        {action.label}
      </a>
    );
  }
  return (
    <button type="button" onClick={action.onClick} className={className}>
      {action.label}
    </button>
  );
}

/**
 * The centred card every "this page can't be shown" state wears: not found,
 * a missing document, a failed data fetch and the error boundary. They used
 * to be four separate treatments, from a full card down to a bare line of red
 * text; sharing one keeps them reading as the same kind of message, and gives
 * each of them the page's h1.
 *
 * `backTo`/`backLabel` remain as shorthand for an in-app primary action.
 */
function ErrorCard({
  title,
  message,
  icon: Icon = FaExclamationCircle,
  backTo,
  backLabel,
  primaryAction,
  secondaryAction,
  role,
}) {
  const primary = primaryAction || (backTo ? { to: backTo, label: backLabel } : null);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 animate-fade-in" role={role}>
      <div className={`${CARD} p-10 text-center max-w-lg mx-auto`}>
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
          <Icon className="w-8 h-8 text-gray-500" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">{title}</h1>
        <p className="text-gray-500 mb-6">{message}</p>
        {(primary || secondaryAction) && (
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            {primary && <ActionButton action={primary} className={PRIMARY_BUTTON} />}
            {secondaryAction && <ActionButton action={secondaryAction} className={SECONDARY_BUTTON} />}
          </div>
        )}
      </div>
    </div>
  );
}

export default ErrorCard;
