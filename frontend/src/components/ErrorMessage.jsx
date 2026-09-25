import ErrorCard from './ErrorCard';

// A page whose data fetch failed. Rendered in place of the whole page, so it
// wears the same card as not-found and carries the page's h1.
function ErrorMessage({ error }) {
  return (
    <ErrorCard
      role="alert"
      title="Couldn't load this page"
      message={`Something went wrong fetching the data (${error}). Refreshing the page usually fixes it.`}
      primaryAction={{ label: 'Refresh page', onClick: () => window.location.reload() }}
      secondaryAction={{ to: '/', label: 'Go to dashboard' }}
    />
  );
}

export default ErrorMessage;
