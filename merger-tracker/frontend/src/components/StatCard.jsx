import { Link } from 'react-router';
import { CARD } from '../utils/classNames';

function StatCard({ title, value, subtitle, icon, href }) {
  const Wrapper = href ? Link : 'div';
  const wrapperProps = href ? { to: href } : {};

  return (
    <Wrapper
      {...wrapperProps}
      className={`block ${CARD} hover:shadow-card-hover transition-all duration-200 overflow-hidden group`}
    >
      <div className="p-6">
        <div className="flex items-start gap-4">
          {icon && (
            <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center text-xl text-primary group-hover:scale-105 transition-transform duration-200">
              {icon}
            </div>
          )}
          <div className="flex-1 min-w-0">
            {/* The label reserves two lines so the value below it starts at the
                same height in every card of a row, whether or not that card's
                label wraps. Without it, a one-line label lifts its number 20px
                above its neighbours'. */}
            <dl>
              <dt className="text-sm font-medium text-gray-500 leading-5 min-h-10 mb-1">
                {title}
              </dt>
              <dd>
                <div className="text-xl font-bold text-gray-900 tracking-tight">
                  {value}
                </div>
              </dd>
              {subtitle && (
                <dd className="text-sm text-gray-500 leading-5 mt-1">{subtitle}</dd>
              )}
            </dl>
          </div>
        </div>
      </div>
    </Wrapper>
  );
}

export default StatCard;
