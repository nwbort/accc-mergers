function NewBadge() {
  return (
    <span
      className="inline-flex items-center px-2 py-1 rounded-md text-xs font-semibold leading-none bg-blue-50 text-blue-700 border border-blue-200/60"
      role="img"
      aria-label="New item since last visit"
    >
      New
    </span>
  );
}

export default NewBadge;
