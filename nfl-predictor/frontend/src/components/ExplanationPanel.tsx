import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ReferenceLine, ResponsiveContainer, Cell,
} from 'recharts';
import type { ExplanationEntry } from '../api/types';
import { getTeamColors } from '../theme/teamColors';

interface Props {
  explanation: ExplanationEntry[];
  homeAbbr: string;
  awayAbbr: string;
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

export function ExplanationSkeleton() {
  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      <div className="h-3 w-36 bg-surface-700 rounded animate-pulse mb-4" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="h-3 rounded animate-pulse bg-surface-700" style={{ width: `${80 + (i % 3) * 20}px` }} />
            <div className="h-4 flex-1 rounded animate-pulse bg-surface-700" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Explanation panel ─────────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload, label, chartData }: any) {
  if (!active || !payload?.length) return null;
  const entry = chartData.find((d: { label: string }) => d.label === label);
  return (
    <div className="rounded-md border border-border bg-surface-800 px-3 py-2 text-xs shadow-lg">
      <p className="text-text-primary font-semibold mb-1">{label}</p>
      <p className="text-text-secondary">
        SHAP: {(payload[0].value * 100).toFixed(2)}%
      </p>
      {entry && (
        <p className="text-text-secondary">
          Value: {entry.feature_value.toFixed(3)}
        </p>
      )}
    </div>
  );
}

export default function ExplanationPanel({ explanation, homeAbbr, awayAbbr }: Props) {
  const homeColor = getTeamColors(homeAbbr).primary;
  const awayColor  = getTeamColors(awayAbbr).primary;

  if (explanation.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface-850 p-5">
        <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-3">
          Why this prediction?
        </h2>
        <p className="text-sm text-text-muted italic">
          Train ML model to see feature explanations (python scripts/train_model.py)
        </p>
      </div>
    );
  }

  const chartData = [...explanation]
    .sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
    .map(e => ({
      label:         e.label,
      value:         e.shap_value,
      direction:     e.direction,
      feature_value: e.feature_value,
    }));

  const maxAbs = Math.max(...chartData.map(d => Math.abs(d.value)), 0.01);
  const pad    = Math.max(maxAbs * 1.35, 0.05);
  const domain: [number, number] = [-pad, pad];

  const barHeight = 28;
  const chartHeight = Math.min(320, chartData.length * barHeight + 40);

  return (
    <div className="rounded-lg border border-border bg-surface-850 p-5">
      {/* Title */}
      <h2 className="font-display text-[11px] font-semibold text-text-muted uppercase tracking-[0.2em] mb-1">
        Why this prediction?
      </h2>

      {/* Direction legend */}
      <p className="text-[11px] text-text-muted mb-4 flex items-center gap-2">
        <span style={{ color: awayColor }}>← favors {awayAbbr}</span>
        <span className="opacity-30">|</span>
        <span style={{ color: homeColor }}>favors {homeAbbr} →</span>
      </p>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 0, right: 20, left: 4, bottom: 0 }}
        >
          <XAxis
            type="number"
            domain={domain}
            tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={156}
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={<CustomTooltip chartData={chartData} />}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <ReferenceLine x={0} stroke="var(--color-border)" strokeWidth={1} />
          <Bar dataKey="value" radius={[0, 2, 2, 0]} maxBarSize={20}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={
                  entry.direction === 'home'
                    ? homeColor
                    : entry.direction === 'away'
                      ? awayColor
                      : 'var(--color-text-muted)'
                }
                fillOpacity={0.82}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <p className="text-[10px] text-text-muted mt-1 text-right opacity-60">
        SHAP · ML model (GradientBoosting)
      </p>
    </div>
  );
}
