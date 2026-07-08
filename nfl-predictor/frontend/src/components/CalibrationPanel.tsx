// Reliability display for the game model: for each predicted-probability bucket,
// how often did the predicted winner actually win? Perfect calibration means
// actual ≈ the bucket's predicted range. Data comes from /api/accuracy (backtester).

type CalibrationBuckets = Record<string, { total: number; correct: number }>;

/** Midpoint of a bucket label like "60-65%"; the open-ended "80%+" maps to 85. */
export function bucketMidpoint(label: string): number {
  const range = label.match(/^(\d+)-(\d+)%$/);
  if (range) return (Number(range[1]) + Number(range[2])) / 2;
  const open = label.match(/^(\d+)%\+$/);
  if (open) return (Number(open[1]) + 100) / 2 - 5; // "80%+" → 85
  return NaN;
}

/** Actual win rate minus predicted midpoint, in percentage points. */
export function calibrationGap(label: string, bucket: { total: number; correct: number }): number {
  return (100 * bucket.correct) / bucket.total - bucketMidpoint(label);
}

function gapColor(gap: number): string {
  const abs = Math.abs(gap);
  if (abs <= 5) return 'text-win';
  if (abs <= 10) return 'text-accent';
  return 'text-loss';
}

export default function CalibrationPanel({ calibration }: { calibration: CalibrationBuckets }) {
  const rows = Object.entries(calibration).filter(([, b]) => b.total > 0);
  if (rows.length === 0) return null;

  return (
    <section aria-label="Model calibration" className="animate-fade-in">
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-display text-xl tracking-wide text-text-primary">Calibration</h2>
        <span className="text-xs text-text-secondary">
          predicted confidence vs. actual win rate
        </span>
      </div>
      <div className="rounded-lg border border-border bg-surface-800 divide-y divide-border">
        {rows.map(([label, bucket]) => {
          const actual = (100 * bucket.correct) / bucket.total;
          const gap = calibrationGap(label, bucket);
          return (
            <div key={label} className="flex items-center gap-4 px-5 py-2.5 text-sm">
              <span className="w-16 shrink-0 font-mono text-text-secondary">{label}</span>
              <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${Math.min(actual, 100).toFixed(1)}%` }}
                />
              </div>
              <span className="w-14 shrink-0 text-right font-mono text-text-primary">
                {actual.toFixed(1)}%
              </span>
              <span className={`w-14 shrink-0 text-right font-mono ${gapColor(gap)}`}>
                {gap >= 0 ? '+' : ''}{gap.toFixed(1)}
              </span>
              <span className="w-20 shrink-0 text-right text-xs text-text-secondary">
                {bucket.total} games
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-text-secondary">
        Gap = actual − predicted (midpoint). Near zero is well calibrated; positive means the
        model is underconfident in that range.
      </p>
    </section>
  );
}
