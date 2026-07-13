import { CARD } from '../utils/classNames';

function EmptyStateCard({ heading, message }) {
  return (
    <div className={`${CARD} p-6`}>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{heading}</h2>
      <p className="text-gray-500 text-sm">{message}</p>
    </div>
  );
}

export default EmptyStateCard;
