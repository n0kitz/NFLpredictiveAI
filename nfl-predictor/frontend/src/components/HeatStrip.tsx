interface Cell {
  week: number;
  value: number;        // 0..1 normalized
  rawLabel: string;     // shown inside cell
  tooltip: string;
  isBye?: boolean;
  isMissing?: boolean;
}

interface Props {
  cells: Cell[];
  hue: 'green' | 'blue';
  label: string;
}

function shade(value: number, hue: 'green' | 'blue', missing: boolean, isBye: boolean): string {
  if (isBye) return 'rgba(120,120,140,0.15)';
  if (missing) return 'rgba(60,60,70,0.30)';
  const v = Math.max(0, Math.min(1, value));
  const alpha = 0.18 + v * 0.72;
  return hue === 'green'
    ? `rgba(52, 211, 153, ${alpha.toFixed(2)})`
    : `rgba(96, 165, 250, ${alpha.toFixed(2)})`;
}

export default function HeatStrip({ cells, hue, label }: Props) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-display uppercase tracking-widest text-text-muted">{label}</span>
      </div>
      <div className="flex gap-0.5">
        {cells.map((c) => (
          <div
            key={c.week}
            title={c.tooltip}
            className="flex-1 min-w-[18px] h-7 rounded-sm flex items-center justify-center text-[9px] font-display font-semibold tabular-nums cursor-help select-none"
            style={{
              backgroundColor: shade(c.value, hue, !!c.isMissing, !!c.isBye),
              color: c.isBye ? 'var(--color-text-muted)' : '#0b0d12',
            }}
          >
            {c.isBye ? 'BYE' : c.rawLabel}
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-0.5">
        {cells.map((c) => (
          <span key={c.week} className="flex-1 text-center text-[8px] text-text-muted/60 tabular-nums">
            {c.week}
          </span>
        ))}
      </div>
    </div>
  );
}
