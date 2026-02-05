function StatCard({ title, value, subtitle, icon }) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card hover:shadow-card-hover transition-all duration-200 overflow-hidden group">
      <div className="p-6">
        <div className="flex items-start gap-4">
          {icon && (
            <div className="flex-shrink-0 w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center text-xl group-hover:scale-105 transition-transform duration-200">
              {icon}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <dl>
              <dt className="text-sm font-medium text-gray-500 mb-1">
                {title}
              </dt>
              <dd>
                <div className="text-xl font-bold text-gray-900 tracking-tight">
                  {value}
                </div>
              </dd>
              {subtitle && (
                <dd className="text-sm text-gray-400 mt-1">{subtitle}</dd>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

export default StatCard;
