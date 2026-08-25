import { Link } from 'react-router';
import { FaEnvelope, FaArrowRight } from 'react-icons/fa6';
import { CARD } from '../utils/classNames';

function DigestPromoCard() {
  return (
    <Link
      to="/digest"
      className={`flex items-center gap-4 p-6 mb-8 ${CARD} hover:shadow-card-hover transition-all duration-200 group`}
    >
      <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center text-xl text-primary group-hover:scale-105 transition-transform duration-200">
        <FaEnvelope />
      </div>
      <div className="flex-1 min-w-0">
        <h2 className="text-base font-semibold text-gray-900">
          Want a weekly round-up of ACCC merger activity?
        </h2>
        <p className="text-sm text-gray-500 mt-0.5">
          Get the week's notifications, determinations and upcoming deadlines in one email.
        </p>
      </div>
      <FaArrowRight className="flex-shrink-0 text-gray-400 group-hover:text-primary group-hover:translate-x-0.5 transition-all duration-200" />
    </Link>
  );
}

export default DigestPromoCard;
