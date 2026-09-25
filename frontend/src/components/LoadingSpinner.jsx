// The spinner itself: a grey track with a primary arc running round it. Also
// used on its own where something loads inside a page (an expanded industry
// row, the notification panel), so those match the full-page state.
export function Spinner({ className = '' }) {
  return (
    <div className={`relative h-10 w-10 ${className}`} aria-hidden="true">
      <div className="h-10 w-10 rounded-full border-[3px] border-gray-200"></div>
      <div className="absolute top-0 left-0 h-10 w-10 rounded-full border-[3px] border-transparent border-t-primary animate-spin"></div>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div
      className="flex flex-col justify-center items-center min-h-screen gap-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Spinner />
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export default LoadingSpinner;
