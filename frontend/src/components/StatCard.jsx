import { Link } from 'react-router';
import { CARD } from '../utils/classNames';
import MaterialShape from './MaterialShape';

function StatCard({ title, value, subtitle, icon, href, reserveTitleLines = true }) {
  const Wrapper = href ? Link : 'div';
  const wrapperProps = href ? { to: href } : {};
  // Only a card that goes somewhere lifts on hover: on a plain one the lift
  // promises a click that does nothing.

  return (
    <Wrapper
      {...wrapperProps}
      className={`block ${CARD} overflow-hidden group ${
        href ? 'press-morph hover:shadow-card-hover hover:rounded-3xl' : ''
      }`}
    >
      <div className="p-6">
        <div className="flex items-start gap-4">
          {icon && (
            // The icon sits in one of the app's Material shapes, which turns
            // on hover.
            <div className="relative flex-shrink-0 w-12 h-12 flex items-center justify-center text-xl text-on-primary-container">
              <MaterialShape
                shape="cookie9"
                className={`absolute inset-0 w-12 h-12 text-primary-container${
                  href ? ' transition-transform duration-500 ease-spring group-hover:rotate-[40deg] group-hover:scale-110' : ''
                }`}
              />
              <span className="relative">{icon}</span>
            </div>
          )}
          <div className="flex-1 min-w-0">
            {/* The label reserves two lines so the value below it starts at
                the same height in every card of a row, whether or not that
                card's label wraps. Without it, a one-line label lifts its
                number 20px above its neighbours'. A row whose labels all fit on
                one line doesn't need the reserve and reads as a gap under the
                label, so it can be turned off (reserveTitleLines={false}). It
                only applies from `sm` up: every grid using StatCard is a
                single column below that, with no neighbour to line up with. */}
            <dl>
              <dt
                className={`text-sm font-medium text-gray-500 leading-5 mb-1 ${
                  reserveTitleLines ? 'sm:min-h-10' : ''
                }`}
              >
                {title}
              </dt>
              <dd>
                <div className="text-2xl type-emphasized text-gray-900">
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
