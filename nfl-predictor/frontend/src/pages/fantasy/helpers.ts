// Pure (non-component) helpers shared across the Fantasy tabs. Kept separate
// from shared.tsx so that file can export only components (react-refresh rule).

export const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K'] as const;
export type PositionFilter = typeof POSITIONS[number];

export function posColor(pos: string | null): string {
  switch (pos) {
    case 'QB': return '#e74c3c';
    case 'RB': return '#27ae60';
    case 'WR': return '#2980b9';
    case 'TE': return '#8e44ad';
    case 'K':  return '#f39c12';
    default:   return '#888';
  }
}

export function matchupColor(score: number): string {
  if (score >= 1.1) return 'var(--color-win)';
  if (score <= 0.9) return 'var(--color-loss)';
  return 'var(--color-text-muted)';
}
