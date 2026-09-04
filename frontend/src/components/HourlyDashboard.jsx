function formatChange(change) {
  if (change === null || change === undefined) return "--";
  return `${change > 0 ? "+" : ""}${change.toFixed(2)}%`;
}

function DetailedChart({ points, positive }) {
  if (points.length < 2) {
    return <div className="flex h-72 items-center justify-center rounded-lg border border-slate-700 bg-slate-950 text-base text-slate-400">No hourly data available today</div>;
  }

  const prices = points.map((point) => point.price);
  const dataMin = Math.min(...prices);
  const dataMax = Math.max(...prices);
  const dataRange = dataMax - dataMin || Math.max(dataMax * 0.01, 1);
  const padding = dataRange * 0.12;
  const min = dataMin - padding;
  const max = dataMax + padding;
  const range = max - min;
  const width = 920;
  const height = 380;
  const left = 92;
  const right = 28;
  const top = 30;
  const bottom = 64;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const coordinates = points.map((point, index) => {
      const x = left + (index / (points.length - 1)) * chartWidth;
      const y = top + chartHeight - ((point.price - min) / range) * chartHeight;
      return { x, y };
    });
  const coordinateString = coordinates.map(({ x, y }) => `${x},${y}`).join(" ");
  const color = positive ? "#00D09C" : "#EB5B3C";
  const labelIndexes = [0, Math.floor((points.length - 1) / 2), points.length - 1];
  const formatPrice = (value) => value >= 1000 ? value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : value.toFixed(2);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-72 w-full sm:h-80" role="img" aria-label="Hourly price chart">
      {[0, 1, 2, 3, 4].map((line) => {
        const y = top + (chartHeight / 4) * line;
        const value = max - (range / 4) * line;
        return (
          <g key={line}>
            <line x1={left} x2={width - right} y1={y} y2={y} stroke="#334155" strokeDasharray="5 7" />
            <text x={left - 16} y={y + 5} textAnchor="end" fill="#cbd5e1" fontSize="15" fontWeight="600">{formatPrice(value)}</text>
          </g>
        );
      })}
      <line x1={left} x2={left} y1={top} y2={top + chartHeight} stroke="#475569" />
      <line x1={left} x2={width - right} y1={top + chartHeight} y2={top + chartHeight} stroke="#475569" />
      <polyline points={coordinateString} fill="none" stroke={color} strokeWidth="4" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((point, index) => {
        const { x, y } = coordinates[index];
        return <circle key={`${point.timestamp}-${index}`} cx={x} cy={y} r="4.5" fill={color} stroke="#0f172a" strokeWidth="2.5" />;
      })}
      {labelIndexes.map((index) => {
        const { x } = coordinates[index];
        const label = new Date(points[index].timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          timeZone: "UTC",
        });
        return <text key={index} x={x} y={height - 18} textAnchor="middle" fill="#cbd5e1" fontSize="15" fontWeight="600">{label}</text>;
      })}
    </svg>
  );
}

export default function HourlyDashboard({ item, loading, onClose }) {
  const points = item?.points ?? [];
  const positive = item?.change_pct > 0;
  const changeColor = positive ? "text-market-up" : item?.change_pct < 0 ? "text-market-down" : "text-slate-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label={`${item?.symbol} hourly graph`} onClick={onClose}>
      <div className="w-full max-w-5xl rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl sm:p-8" onClick={(event) => event.stopPropagation()}>
        <div className="mb-7 flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-400">Today / hourly movement</p>
            <h2 className="mt-1 text-3xl font-bold text-slate-100">{item?.symbol}</h2>
            <p className={`mt-2 text-base font-semibold ${changeColor}`}>{formatChange(item?.change_pct)} since the first hourly close</p>
          </div>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-3xl leading-none text-slate-400 hover:bg-slate-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-slate-400" aria-label="Close graph">
            ×
          </button>
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-950/60 p-3 sm:p-6">
          {loading ? <div className="flex h-72 items-center justify-center text-base text-slate-400">Loading today&apos;s hourly data...</div> : <DetailedChart points={points} positive={positive} />}
        </div>
        <div className="mt-5 flex flex-wrap justify-between gap-3 text-sm text-slate-400">
          <span>{points.length} hourly data points</span>
          <span>Current day, UTC</span>
        </div>
      </div>
    </div>
  );
}
