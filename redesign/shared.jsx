// Shared UI primitives — team logo, probability bar, icons.

function TeamMark({ abbr, size = 40, mono }) {
  const t = TEAMS[abbr];
  if (!t) return null;
  const bg = mono ? 'transparent' : t.secondary;
  const fg = mono ? 'currentColor' : t.primary;
  const border = mono ? '1.5px solid currentColor' : 'none';
  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.18,
      background: bg, border,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0, position: 'relative', overflow: 'hidden',
    }}>
      <span style={{
        fontFamily: 'var(--font-display)',
        fontWeight: 800, fontSize: size * 0.38,
        letterSpacing: '-0.02em', color: fg,
        lineHeight: 1,
      }}>{abbr}</span>
      {!mono && (
        <span style={{
          position: 'absolute', inset: 0,
          background: `linear-gradient(135deg, ${t.primary}18 0%, transparent 50%)`,
        }} />
      )}
    </div>
  );
}

// Win-probability split bar — configurable height + style
function ProbBar({ awayPct, away, home, height = 6, showLabels }) {
  const homePct = 100 - awayPct;
  const ac = TEAMS[away]?.primary || '#888';
  const hc = TEAMS[home]?.primary || '#444';
  return (
    <div style={{ width: '100%' }}>
      <div style={{
        display: 'flex', height, borderRadius: height / 2,
        overflow: 'hidden', background: 'rgba(255,255,255,0.06)',
      }}>
        <div style={{ width: `${awayPct}%`, background: ac, transition: 'width 700ms cubic-bezier(.2,.7,.2,1)' }} />
        <div style={{ width: `${homePct}%`, background: hc, transition: 'width 700ms cubic-bezier(.2,.7,.2,1)' }} />
      </div>
      {showLabels && (
        <div style={{
          display: 'flex', justifyContent: 'space-between',
          fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600,
          color: 'var(--text-muted)', marginTop: 4, letterSpacing: '0.05em',
        }}>
          <span style={{ color: ac }}>{awayPct}%</span>
          <span style={{ color: hc }}>{homePct}%</span>
        </div>
      )}
    </div>
  );
}

// Tiny sparkline
function Spark({ values, color = 'currentColor', w = 100, h = 24, fill }) {
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 2) - 1;
    return [x, y];
  });
  const d = points.map((p, i) => (i === 0 ? 'M' : 'L') + p[0] + ' ' + p[1]).join(' ');
  const area = d + ` L${w} ${h} L0 ${h} Z`;
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      {fill && <path d={area} fill={fill} />}
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Icon: chevron, dot, arrow
const IconArrow = ({ dir = 'up', size = 10 }) => (
  <svg width={size} height={size} viewBox="0 0 10 10" style={{ display: 'inline-block', verticalAlign: 'middle' }}>
    <path d={dir === 'up' ? 'M5 1L9 8H1z' : 'M5 9L1 2h8z'} fill="currentColor" />
  </svg>
);

const Dot = ({ color = 'currentColor', size = 6, pulse }) => (
  <span style={{
    display: 'inline-block', width: size, height: size, borderRadius: '50%',
    background: color, animation: pulse ? 'pulse 1.8s ease-in-out infinite' : 'none',
    flexShrink: 0,
  }} />
);

Object.assign(window, { TeamMark, ProbBar, Spark, IconArrow, Dot });
