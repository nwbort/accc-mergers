function LoadingSpinner() {
  return (
    <div
      className="flex flex-col justify-center items-center py-16 gap-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="relative" aria-hidden="true">
        <div className="h-10 w-10 rounded-full border-[3px] border-gray-200"></div>
        <div className="absolute top-0 left-0 h-10 w-10 rounded-full border-[3px] border-transparent border-t-primary animate-spin"></div>
      </div>
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export default LoadingSpinner;
