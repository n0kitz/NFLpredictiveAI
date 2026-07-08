import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CalibrationPanel, { bucketMidpoint, calibrationGap } from './CalibrationPanel';

const CALIBRATION = {
  '50-55%': { total: 113, correct: 65 },
  '55-60%': { total: 105, correct: 62 },
  '60-65%': { total: 84, correct: 55 },
  '65-70%': { total: 82, correct: 64 },
  '70-75%': { total: 58, correct: 43 },
  '75-80%': { total: 40, correct: 28 },
  '80%+': { total: 61, correct: 52 },
};

describe('bucketMidpoint', () => {
  it('returns the midpoint of a range bucket', () => {
    expect(bucketMidpoint('50-55%')).toBeCloseTo(52.5);
    expect(bucketMidpoint('65-70%')).toBeCloseTo(67.5);
  });

  it('uses 85 for the open-ended 80%+ bucket', () => {
    expect(bucketMidpoint('80%+')).toBeCloseTo(85);
  });
});

describe('calibrationGap', () => {
  it('is actual win rate minus predicted midpoint, in points', () => {
    // 65/113 = 57.5% actual vs 52.5% predicted → +5.0
    expect(calibrationGap('50-55%', { total: 113, correct: 65 })).toBeCloseTo(5.0, 1);
  });
});

describe('CalibrationPanel', () => {
  it('renders one row per non-empty bucket', () => {
    render(<CalibrationPanel calibration={CALIBRATION} />);
    for (const label of Object.keys(CALIBRATION)) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('shows actual win rate and sample size per bucket', () => {
    render(<CalibrationPanel calibration={CALIBRATION} />);
    // 55/84 = 65.5%
    expect(screen.getByText('65.5%')).toBeInTheDocument();
    expect(screen.getByText(/84 games/)).toBeInTheDocument();
  });

  it('skips empty buckets', () => {
    render(
      <CalibrationPanel
        calibration={{ '50-55%': { total: 10, correct: 6 }, '80%+': { total: 0, correct: 0 } }}
      />,
    );
    expect(screen.getByText('50-55%')).toBeInTheDocument();
    expect(screen.queryByText('80%+')).toBeNull();
  });

  it('renders nothing when all buckets are empty', () => {
    const { container } = render(
      <CalibrationPanel calibration={{ '50-55%': { total: 0, correct: 0 } }} />,
    );
    expect(container.firstChild).toBeNull();
  });
});
