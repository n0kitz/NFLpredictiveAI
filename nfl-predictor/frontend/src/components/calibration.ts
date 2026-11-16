// Calibration maths for the reliability panel (kept apart from the component
// so the component file only exports components — required for fast refresh).

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
