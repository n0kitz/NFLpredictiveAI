// Interactive hero matchup card.
// Tabs: Win Probability | Factors | Trend | H2H
// Clickable sliders that shift the probability in a "what-if" way.

function HeroMatchup({ variant = 'A' }) {
  const m = HERO_MATCHUP;
  const [tab, setTab] = React.useState('win');
  const [adjustments, setAdjustments] = React.useState({ form: 0, injury: 0, weather: 0 });
  const [pulse, setPulse] = React.useState(false);

  // Derived prob — base 58 away, adjust by slider sum
  const adjSum = adjustments.form + adjustments.injury + adjustments.weather;
  const awayPct = Math.max(5, Math.min(95, m.awayPct + adjSum));
  const homePct = 100 - awayPct;
  const winner = awayPct > homePct ? m.away : m.home;
  const edge = Math.abs(awayPct - homePct);
  const conf = edge > 20 ? 'HIGH' : edge > 10 ? 'MEDIUM' : 'LOW';

  React.useEffect(() => {
    setPulse(true);
    const t = setTimeout(() => setPulse(false), 300);
    return () => clearTimeout(t);
  }, [awayPct]);

  const a = TEAMS[m.away], h = TEAMS[m.home];
  const ac = a.primary, hc = h.primary;
  const isA = variant === 'A';

  return (
    <div style={{
      position: 'relative',
      background: isA ? 'var(--surface-2)' : 'var(--surface-1)',
      border: '1px solid var(--border)',
      borderRadius: isA ? 4 : 12,
      overflow: 'hidden',
    }}>
      {/* Top accent edge */}
      <div style={{ display: 'flex', height: 3 }}>
        <div style={{ width: `${awayPct}%`, background: ac, transition: 'width 500ms cubic-bezier(.2,.7,.2,1)' }} />
        <div style={{ width: `${homePct}%`, background: hc, transition: 'width 500ms cubic-bezier(.2,.7,.2,1)' }} />
      </div>

      {/* Header band */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 24px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-3)',
        fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
        letterSpacing: '0.12em', color: 'var(--text-muted)',
      }}>
        <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
          <span style={{ color: 'var(--accent)' }}>● LIVE MODEL</span>
          <span>{m.week.toUpperCase()}</span>
          <span>{m.kickoff.toUpperCase()}</span>
        </div>
        <div style={{ display: 'flex', gap: 20 }}>
          <span>{m.venue.toUpperCase()}</span>
          <span>{m.broadcast.toUpperCase()}</span>
        </div>
      </div>

      {/* Main matchup row */}
      <div style={{ padding: isA ? '28px 32px' : '36px 40px' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr',
          gap: isA ? 24 : 40, alignItems: 'center',
        }}>
          {/* Away */}
          <TeamBlock abbr={m.away} record={m.awayRecord} side="AWAY" align="left" big={!isA} />

          {/* Center probability dial */}
          <div style={{ textAlign: 'center', minWidth: isA ? 160 : 220 }}>
            <div style={{
              fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 600,
              letterSpacing: '0.2em', color: 'var(--text-muted)', marginBottom: 8,
            }}>WIN PROBABILITY</div>

            <div style={{
              fontFamily: 'var(--font-display)', fontWeight: 800,
              fontSize: isA ? 56 : 88, lineHeight: 1,
              letterSpacing: '-0.04em',
              color: winner === m.away ? ac : hc,
              transition: 'color 400ms',
              transform: pulse ? 'scale(1.03)' : 'scale(1)',
              transitionProperty: 'transform, color',
              transitionDuration: '300ms',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {Math.max(awayPct, homePct)}<span style={{ fontSize: '0.5em', opacity: 0.5 }}>%</span>
            </div>
            <div style={{
              fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700,
              letterSpacing: '0.15em',
              color: winner === m.away ? ac : hc,
              marginTop: 6,
            }}>
              {(winner === m.away ? a.name : h.name).toUpperCase()} TO WIN
            </div>

            <div style={{
              display: 'inline-flex', gap: 8, marginTop: 14,
              padding: '6px 12px',
              border: '1px solid var(--border-strong)',
              borderRadius: 2,
              fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 700,
              letterSpacing: '0.15em',
              color: conf === 'HIGH' ? 'var(--pos)' : conf === 'MEDIUM' ? 'var(--accent)' : 'var(--text-muted)',
            }}>
              <Dot color="currentColor" pulse />
              {conf} CONFIDENCE
            </div>
          </div>

          {/* Home */}
          <TeamBlock abbr={m.home} record={m.homeRecord} side="HOME" align="right" big={!isA} />
        </div>

        {/* Full-width probability bar */}
        <div style={{ marginTop: 28 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
            letterSpacing: '0.1em', marginBottom: 8,
          }}>
            <span style={{ color: ac, fontVariantNumeric: 'tabular-nums' }}>{awayPct}% {a.name.toUpperCase()}</span>
            <span style={{ color: hc, fontVariantNumeric: 'tabular-nums' }}>{h.name.toUpperCase()} {homePct}%</span>
          </div>
          <div style={{
            display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden',
            background: 'var(--surface-3)', position: 'relative',
          }}>
            <div style={{
              width: `${awayPct}%`, background: `linear-gradient(90deg, ${ac}ee, ${ac})`,
              transition: 'width 500ms cubic-bezier(.2,.7,.2,1)',
              boxShadow: `0 0 20px ${ac}66`,
            }} />
            <div style={{
              width: `${homePct}%`, background: `linear-gradient(90deg, ${hc}, ${hc}ee)`,
              transition: 'width 500ms cubic-bezier(.2,.7,.2,1)',
              boxShadow: `0 0 20px ${hc}66`,
            }} />
            {/* 50% marker */}
            <div style={{
              position: 'absolute', top: -4, bottom: -4, left: '50%',
              width: 1, background: 'var(--text-muted)', opacity: 0.4,
            }} />
          </div>
        </div>

        {/* Tab strip */}
        <div style={{
          display: 'flex', gap: 0, marginTop: 28,
          borderBottom: '1px solid var(--border)',
        }}>
          {[
            { id: 'win',     label: 'What-If' },
            { id: 'factors', label: 'Factors' },
            { id: 'trend',   label: 'Trend' },
            { id: 'market',  label: 'Market' },
          ].map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding: '12px 18px', background: 'none', border: 'none',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
              letterSpacing: '0.12em', cursor: 'pointer',
              color: tab === t.id ? 'var(--text)' : 'var(--text-muted)',
              transition: 'color 150ms, border-color 150ms',
              marginBottom: -1,
            }}>{t.label.toUpperCase()}</button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ padding: '20px 0 4px', minHeight: 160 }}>
          {tab === 'win' && <WhatIfPanel adjustments={adjustments} setAdjustments={setAdjustments} />}
          {tab === 'factors' && <FactorsPanel factors={m.factors} a={a} h={h} />}
          {tab === 'trend' && <TrendPanel trend={m.trend} a={a} h={h} awayPct={awayPct} />}
          {tab === 'market' && <MarketPanel m={m} />}
        </div>
      </div>
    </div>
  );
}

function TeamBlock({ abbr, record, side, align, big }) {
  const t = TEAMS[abbr];
  const size = big ? 64 : 52;
  return (
    <div style={{
      display: 'flex', alignItems: 'center',
      gap: big ? 18 : 14,
      flexDirection: align === 'right' ? 'row-reverse' : 'row',
      textAlign: align,
    }}>
      <TeamMark abbr={abbr} size={size} />
      <div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 600,
          letterSpacing: '0.18em', color: 'var(--text-muted)',
        }}>{side}</div>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 700,
          fontSize: big ? 26 : 22, letterSpacing: '-0.02em',
          color: 'var(--text)', lineHeight: 1.1, marginTop: 2,
        }}>{t.city}</div>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: big ? 18 : 15,
          color: t.primary, letterSpacing: '-0.01em',
        }}>{t.name}</div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
          color: 'var(--text-muted)', marginTop: 4,
          fontVariantNumeric: 'tabular-nums',
        }}>{record} · STREAK W2</div>
      </div>
    </div>
  );
}

function WhatIfPanel({ adjustments, setAdjustments }) {
  const items = [
    { key: 'form',    label: 'Form Momentum',  sub: 'Recent 5-game weighting'  },
    { key: 'injury',  label: 'Injury Impact',  sub: 'Key player availability' },
    { key: 'weather', label: 'Weather Adjust', sub: 'Wind / precipitation'    },
  ];
  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
        Drag sliders to see how the model reacts. Positive values favor <b style={{ color: 'var(--text)' }}>Away</b>.
      </div>
      <div style={{ display: 'grid', gap: 14 }}>
        {items.map((it) => (
          <div key={it.key}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
              marginBottom: 6,
            }}>
              <div>
                <span style={{
                  fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700,
                  color: 'var(--text)', letterSpacing: '0.02em',
                }}>{it.label}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{it.sub}</span>
              </div>
              <span style={{
                fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700,
                color: adjustments[it.key] > 0 ? 'var(--pos)' : adjustments[it.key] < 0 ? 'var(--neg)' : 'var(--text-muted)',
                fontVariantNumeric: 'tabular-nums',
              }}>{adjustments[it.key] > 0 ? '+' : ''}{adjustments[it.key]}%</span>
            </div>
            <input
              type="range" min="-15" max="15" step="1"
              value={adjustments[it.key]}
              onChange={(e) => setAdjustments({ ...adjustments, [it.key]: Number(e.target.value) })}
              className="predictor-range"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function FactorsPanel({ factors, a, h }) {
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {factors.map((f) => {
        const total = f.away + f.home;
        const aw = (f.away / total) * 100;
        return (
          <div key={f.label}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
              marginBottom: 4, letterSpacing: '0.03em',
            }}>
              <span style={{ color: a.primary, fontVariantNumeric: 'tabular-nums' }}>{f.away}</span>
              <span style={{ color: 'var(--text-muted)', letterSpacing: '0.1em' }}>{f.label.toUpperCase()}</span>
              <span style={{ color: h.primary, fontVariantNumeric: 'tabular-nums' }}>{f.home}</span>
            </div>
            <div style={{ display: 'flex', height: 4, borderRadius: 2, overflow: 'hidden', background: 'var(--surface-3)' }}>
              <div style={{ width: `${aw}%`, background: a.primary }} />
              <div style={{ width: `${100 - aw}%`, background: h.primary }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TrendPanel({ trend, a, h, awayPct }) {
  const w = 560, hh = 140;
  const min = 30, max = 70;
  const pts = trend.map((v, i) => {
    const x = (i / (trend.length - 1)) * w;
    const y = hh - ((v - min) / (max - min)) * hh;
    return [x, y];
  });
  const d = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', fontFamily: 'var(--font-display)' }}>12-WEEK MODEL PROBABILITY</div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, color: a.primary, marginTop: 4 }}>
            {a.name} {awayPct}%
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.1em', fontFamily: 'var(--font-display)' }}>TREND (Δ 12w)</div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700, color: 'var(--pos)', marginTop: 4 }}>
            +6.2%
          </div>
        </div>
      </div>
      <svg viewBox={`0 0 ${w} ${hh}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        <defs>
          <linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%"   stopColor={a.primary} stopOpacity="0.35" />
            <stop offset="100%" stopColor={a.primary} stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="0" x2={w} y1={hh / 2} y2={hh / 2} stroke="var(--border)" strokeDasharray="3 4" />
        <path d={d + ` L${w} ${hh} L0 ${hh} Z`} fill="url(#trendFill)" />
        <path d={d} fill="none" stroke={a.primary} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <circle key={i} cx={p[0]} cy={p[1]} r={i === pts.length - 1 ? 5 : 2.5}
            fill={a.primary}
            stroke={i === pts.length - 1 ? 'var(--surface-1)' : 'none'}
            strokeWidth={i === pts.length - 1 ? 3 : 0}
          />
        ))}
      </svg>
    </div>
  );
}

function MarketPanel({ m }) {
  const items = [
    { label: 'Spread',   value: m.spread,   sub: 'Consensus market' },
    { label: 'Total',    value: m.total,    sub: 'Projected pace'   },
    { label: 'Weather',  value: m.weather,  sub: 'Game-time forecast' },
    { label: 'Model Edge', value: '+4.5 pts', sub: 'vs. market spread', positive: true },
  ];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
      {items.map((it) => (
        <div key={it.label} style={{
          padding: '14px 16px', background: 'var(--surface-3)',
          border: '1px solid var(--border)', borderRadius: 4,
        }}>
          <div style={{ fontSize: 10, letterSpacing: '0.14em', color: 'var(--text-muted)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>
            {it.label.toUpperCase()}
          </div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700,
            color: it.positive ? 'var(--accent)' : 'var(--text)', marginTop: 6,
            fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em',
          }}>{it.value}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{it.sub}</div>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { HeroMatchup });
