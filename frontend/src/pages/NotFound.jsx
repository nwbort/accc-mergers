import { useLocation } from 'react-router';
import { FaFile } from 'react-icons/fa';
import SEO from '../components/SEO';
import ErrorCard from '../components/ErrorCard';

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
        <ErrorCard
          icon={FaFile}
          title="Document not found"
          message="This document isn't currently available. The ACCC may not have made it publicly accessible yet. Try checking on the ACCC website directly."
          backTo={`/mergers/${matterId}`}
          backLabel="View merger details"
          secondaryAction={{
            href: `https://www.accc.gov.au/public-registers/acquisitions-and-mergers-registers/acquisitions-register?init=1&query=${matterId}`,
            label: 'Check ACCC website',
            ariaLabel: `Search for ${matterId} on ACCC website (opens in new tab)`,
          }}
        />
      </>
    );
  }

  return (
    <>
      <SEO
        title="Page Not Found"
        description="The page you're looking for doesn't exist on the Australian Merger Tracker."
      />
      <ErrorCard
        title="Page not found"
        message="The page you're looking for doesn't exist or has been moved."
        backTo="/"
        backLabel="Go to dashboard"
        secondaryAction={{ to: '/mergers', label: 'Browse mergers' }}
      />
    </>
  );
}

export default NotFound;
