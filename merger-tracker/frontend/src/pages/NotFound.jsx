import { Link } from 'react-router-dom';
import SEO from '../components/SEO';

function NotFound() {
  return (
    <>
      <SEO
        title="Page Not Found"
        description="The page you're looking for doesn't exist on the Australian Merger Tracker."
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 animate-fade-in">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center max-w-lg mx-auto">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">
            Page not found
          </h1>
          <p className="text-gray-500 mb-6">
            The page you're looking for doesn't exist or has been moved.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/"
              className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm"
            >
              Go to dashboard
            </Link>
            <Link
              to="/mergers"
              className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors"
            >
              Browse mergers
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}

export default NotFound;
