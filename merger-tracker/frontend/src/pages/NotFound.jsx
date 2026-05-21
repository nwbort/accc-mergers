import { Link, useLocation } from 'react-router-dom';
import { FaFile, FaExclamationCircle } from 'react-icons/fa';
import SEO from '../components/SEO';

function NotFound() {
  const location = useLocation();
  const path = location.pathname;

  // Detect if this is a missing PDF document under /mergers/MN-XXXXX/ or /matters/MN-XXXXX/
  const matterMatch = path.match(/^\/(mergers|matters)\/(MN-\d+)\//i);
  const isPdf = path.toLowerCase().endsWith('.pdf');
  const isDocumentNotFound = matterMatch && isPdf;
  const matterId = matterMatch ? matterMatch[2] : null;

  if (isDocumentNotFound) {
    return (
      <>
        <SEO
          title="Document Not Found"
          description="This ACCC document is not currently available."
        />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 animate-fade-in">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center max-w-lg mx-auto">
            <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
              <FaFile className="w-8 h-8 text-gray-500" aria-hidden="true" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">
              Document not found
            </h1>
            <p className="text-gray-500 mb-6">
              This document isn't currently available. The ACCC may not have made it publicly accessible yet. Try checking on the ACCC website directly.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                to={`/mergers/${matterId}`}
                className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm"
              >
                View merger details
              </Link>
              <a
                href={`https://www.accc.gov.au/public-registers/mergers-and-acquisitions-registers/acquisitions-register?init=1&query=${matterId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-gray-700 bg-white border border-gray-200 hover:bg-gray-50 transition-colors"
              >
                Check ACCC website
              </a>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <SEO
        title="Page Not Found"
        description="The page you're looking for doesn't exist on the Australian Merger Tracker."
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 animate-fade-in">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center max-w-lg mx-auto">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
            <FaExclamationCircle className="w-8 h-8 text-gray-500" aria-hidden="true" />
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
