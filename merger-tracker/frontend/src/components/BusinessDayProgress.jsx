import { getBusinessDayProgress } from '../utils/businessDayProgress';

/**
 * "Business day X of Y" label for the merger detail header. Renders nothing
 * when the merger isn't an in-progress non-waiver assessment (see
 * getBusinessDayProgress).
 */
function BusinessDayProgress({ merger }) {
  const progress = getBusinessDayProgress(merger);
  if (!progress) return null;

  const { elapsed, total, overdue } = progress;

  return (
    <p className={`text-xs font-medium ${overdue ? 'text-amber-700' : 'text-gray-500'}`}>
      {overdue ? 'Determination overdue' : `Business day ${elapsed} of ${total}`}
    </p>
  );
}

export default BusinessDayProgress;
