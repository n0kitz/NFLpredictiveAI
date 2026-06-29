import { describe, it, expect } from 'vitest';
import { gradeColor, posColor, matchupColor, POSITIONS } from './helpers';

describe('fantasy helpers', () => {
  it('maps every letter grade to a distinct colour (A best → F worst)', () => {
    const grades = ['A', 'B', 'C', 'D', 'F'] as const;
    const colors = grades.map(gradeColor);
    // all defined, none falls through to the grey default
    colors.forEach((c) => expect(c).not.toBe('#888'));
    // distinct per grade
    expect(new Set(colors).size).toBe(grades.length);
  });

  it('returns the grey fallback for an unknown grade', () => {
    // @ts-expect-error — exercising the default branch with an invalid grade
    expect(gradeColor('Z')).toBe('#888');
  });

  it('colours known positions and falls back to grey otherwise', () => {
    expect(posColor('QB')).toBe('#e74c3c');
    expect(posColor('K')).toBe('#f39c12');
    expect(posColor(null)).toBe('#888');
    expect(posColor('LB')).toBe('#888');
  });

  it('classifies matchup scores by win/loss/neutral thresholds', () => {
    expect(matchupColor(1.2)).toBe('var(--color-win)');
    expect(matchupColor(0.8)).toBe('var(--color-loss)');
    expect(matchupColor(1.0)).toBe('var(--color-text-muted)');
  });

  it('exposes the canonical position filter list with ALL first', () => {
    expect(POSITIONS[0]).toBe('ALL');
    expect(POSITIONS).toContain('QB');
  });
});
