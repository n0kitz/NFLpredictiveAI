interface Props {
  boomPct: number | null | undefined;
  bustPct: number | null | undefined;
  size?: 'sm' | 'md';
}

export default function BoomBustBadge({ boomPct, bustPct, size = 'sm' }: Props) {
  if (boomPct == null && bustPct == null) return null;

  const px = size === 'md' ? 'px-2 py-0.5 text-[10px]' : 'px-1.5 py-0.5 text-[9px]';

  return (
    <span className="inline-flex items-center gap-1">
      {boomPct != null && (
        <span
          title={`Boom = % of weeks ≥1.5× season avg PPR`}
          className={`inline-flex items-center rounded-full font-display font-semibold uppercase tracking-wider bg-win/15 text-win ${px}`}
        >
          ▲ {Math.round(boomPct)}%
        </span>
      )}
      {bustPct != null && (
        <span
          title={`Bust = % of weeks ≤0.5× season avg PPR`}
          className={`inline-flex items-center rounded-full font-display font-semibold uppercase tracking-wider bg-loss/15 text-loss ${px}`}
        >
          ▼ {Math.round(bustPct)}%
        </span>
      )}
    </span>
  );
}
