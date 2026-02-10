function NewBadge() {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200/60"
      role="status"
      aria-label="New item since last visit"
    >
      New
    </span>
  );
}

export default NewBadge;
