import { formatDate, formatDps } from "../lib/format.js";

const W = 600;
const H = 180;
const PAD = { top: 16, right: 16, bottom: 28, left: 64 };

// Evolução do DPS entre análises do mesmo chefe (RF13). `points` em ordem de data.
export default function EvolutionChart({ points }) {
  const values = points.map((p) => p.dps);
  const min = Math.min(...values) * 0.97;
  const max = Math.max(...values) * 1.03;
  const x = (i) => PAD.left + (i / Math.max(points.length - 1, 1)) * (W - PAD.left - PAD.right);
  const y = (v) => PAD.top + (1 - (v - min) / (max - min || 1)) * (H - PAD.top - PAD.bottom);
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.dps)}`).join(" ");
  const first = points[0];
  const last = points[points.length - 1];

  return (
    <figure className="chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`DPS de ${formatDps(first.dps)} em ${formatDate(first.created_at)} para ${formatDps(last.dps)} em ${formatDate(last.created_at)}`}
      >
        {[min, (min + max) / 2, max].map((v) => (
          <g key={v}>
            <line className="chart-grid" x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} />
            <text className="chart-tick" x={PAD.left - 8} y={y(v) + 4} textAnchor="end">
              {formatDps(v)}
            </text>
          </g>
        ))}
        <path className="chart-line" d={line} />
        {points.map((p, i) => (
          <circle key={p.id} className="chart-dot" cx={x(i)} cy={y(p.dps)} r="5">
            <title>{`${formatDate(p.created_at)}: ${formatDps(p.dps)}`}</title>
          </circle>
        ))}
        <text className="chart-tick" x={x(0)} y={H - 6} textAnchor="start">
          {formatDate(first.created_at)}
        </text>
        <text className="chart-tick" x={x(points.length - 1)} y={H - 6} textAnchor="end">
          {formatDate(last.created_at)}
        </text>
      </svg>
    </figure>
  );
}
