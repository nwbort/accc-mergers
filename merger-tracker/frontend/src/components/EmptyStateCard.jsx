function EmptyStateCard({ heading, message }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{heading}</h2>
      <p className="text-gray-500 text-sm">{message}</p>
    </div>
  );
}

export default EmptyStateCard;
