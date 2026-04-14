import { Link } from 'react-router-dom';

function ErrorCard({ title, message, backTo, backLabel, secondaryAction }) {
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center">
        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
          <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
        </div>
        <h1 className="text-xl font-bold text-gray-900 mb-3">{title}</h1>
        <p className="text-gray-500 mb-6 max-w-md mx-auto">{message}</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to={backTo}
            className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm"
          >
            {backLabel}
          </Link>
          {secondaryAction && (
            <>
              <span className="text-gray-400 text-sm">or</span>
              <a
                href={secondaryAction.href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors"
                aria-label={secondaryAction.ariaLabel}
              >
                {secondaryAction.label}
              </a>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default ErrorCard;
