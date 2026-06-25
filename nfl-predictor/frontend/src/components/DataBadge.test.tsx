import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataBadge from './DataBadge';
import { SEASON_RANGE_LABEL } from '../config';

describe('DataBadge', () => {
  it('renders the label for a known source', () => {
    render(<DataBadge source="ml-model" />);
    expect(screen.getByText('GBM')).toBeInTheDocument();
  });

  it('shows a tooltip with the centralized season range on hover', async () => {
    const user = userEvent.setup();
    render(<DataBadge source="pfr" />);
    // tooltip is hover-gated — not present until mouse enter
    expect(screen.queryByText(new RegExp(SEASON_RANGE_LABEL))).toBeNull();
    await user.hover(screen.getByText('PFR'));
    expect(
      screen.getByText(new RegExp(SEASON_RANGE_LABEL)),
    ).toBeInTheDocument();
  });
});
