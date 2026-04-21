// Direction A — "Command Deck"
// Dense sportsbook cockpit: ticker, hero + rails, data grid, value picks strip.

function DashboardA() {
  return (
    <div style={{ background: 'var(--bg)', color: 'var(--text)', minHeight: '100%', fontFamily: 'var(--font-body)' }}>
      <TopBarA />
      <TickerA />
      <div style={{ padding: '20px 24px 40px', display: 'grid', gap: 20 }}>
        <AccuracyStripA />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
          <HeroMatchup variant="A" />
          <SideRailA />
        </div>
        <MatchupGridA />
        <ValuePicksA />
      </div>
    </div>
  );
}

function TopBarA() {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 24px', borderBottom: '1px solid var(--border)',
      background: 'var(--surface-1)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: 18, letterSpacing: '-0.02em',
        }}>
          <span style={{ color: 'var(--accent)' }}>▲</span>{' '}
          GRIDIRON<span style={{ color: 'var(--text-muted)' }}>/</span>OS
        </div>
        <nav style={{ display: 'flex', gap: 2, fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, letterSpacing: '0.08em' }}>
          {['DASHBOARD', 'PREDICT', 'TEAMS', 'FANTASY', 'PLAYOFFS', 'HISTORY'].map((x, i) => (
            <a key={x} href="#" style={{
              padding: '8px 14px',
              color: i === 0 ? 'var(--text)' : 'var(--text-muted)',
              background: i === 0 ? 'var(--surface-3)' : 'transparent',
              borderRadius: 2, textDecoration: 'none',
              transition: 'color 120ms, background 120ms',
            }}>{x}</a>
          ))}
        </nav>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 12px', background: 'var(--surface-3)',
          borderRadius: 2, fontSize: 11, fontFamily: 'var(--font-display)',
          fontWeight: 600, letterSpacing: '0.1em',
        }}>
          <Dot color="var(--pos)" pulse />
          MODEL ONLINE · v4.2.1
        </div>
        <div style={{
          width: 32, height: 32, borderRadius: '50%',
          background: 'var(--surface-3)', border: '1px solid var(--border)',
        }} />
      </div>
    </div>
  );
}

function TickerA() {
  const items = [
    'REBELS WR DARIUS KLINE QUESTIONABLE',
    'VOLTAGE -3.5 SHARP MONEY',
    'TIMBER 7-1 ATS AS ROAD FAV',
    'WEATHER: DEN 28°F WIND 14MPH',
    'MODEL FLIPS ON SNT/WRS',
    'KICKOFF IN 4H 12M',
  ];
  return (
    <div style={{
      position: 'relative', overflow: 'hidden',
      borderBottom: '1px solid var(--border)', background: 'var(--surface-2)',
      fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
      letterSpacing: '0.1em', color: 'var(--text-muted)',
    }}>
      <div style={{
        padding: '8px 0',
        display: 'flex', gap: 40, whiteSpace: 'nowrap',
        animation: 'ticker 40s linear infinite',
        width: 'max-content',
      }}>
        {[...items, ...items, ...items].map((it, i) => (
          <span key={i}>
            <span style={{ color: 'var(--accent)', marginRight: 10 }}>◆</span>
            {it}
          </span>
        ))}
      </div>
    </div>
  );
}

function AccuracyStripA() {
  const stats = [
    { label: 'SEASON ACCURACY', value: (ACCURACY.season * 100).toFixed(1) + '%', sub: `${ACCURACY.correct} of ${ACCURACY.total}`, trend: [64,66,67,68,67,69,70,67] },
    { label: 'LAST 5 WEEKS',    value: (ACCURACY.l5 * 100).toFixed(0) + '%',     sub: '+3.8 vs season', trend: [65,68,70,72,71], accent: true },
    { label: 'HIGH CONF HIT',   value: Math.round((ACCURACY.high.correct / ACCURACY.high.total) * 100) + '%', sub: `${ACCURACY.high.correct}/${ACCURACY.high.total} picks` },
    { label: 'MED CONF HIT',    value: Math.round((ACCURACY.medium.correct / ACCURACY.medium.total) * 100) + '%', sub: `${ACCURACY.medium.correct}/${ACCURACY.medium.total} picks` },
    { label: 'ROI VS MARKET',   value: '+12.4%', sub: 'Units: +31.2' },
    { label: 'MODEL EDGE ≥3pt', value: '74%',   sub: '42/57 games' },
  ];
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 1,
      background: 'var(--border)', border: '1px solid var(--border)', borderRadius: 4,
      overflow: 'hidden',
    }}>
      {stats.map((s) => (
        <div key={s.label} style={{
          background: 'var(--surface-2)', padding: '14px 18px',
          display: 'flex', flexDirection: 'column', gap: 4,
          position: 'relative',
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
            {s.label}
          </div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 800,
            letterSpacing: '-0.02em',
            color: s.accent ? 'var(--accent)' : 'var(--text)',
            fontVariantNumeric: 'tabular-nums',
          }}>{s.value}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.sub}</span>
            {s.trend && <Spark values={s.trend} color={s.accent ? 'var(--accent)' : 'var(--text-muted)'} w={48} h={16} />}
          </div>
        </div>
      ))}
    </div>
  );
}

function SideRailA() {
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      {/* Line movement */}
      <RailCardA title="LINE MOVEMENT" sub="Sharp vs public">
        <div style={{ display: 'grid', gap: 8 }}>
          {[
            { tag: 'VLT -3.5', open: '-2.5', now: '-3.5', dir: 'up', pct: '68% sharp' },
            { tag: 'TMB -5.5', open: '-4.0', now: '-5.5', dir: 'up', pct: '72% sharp' },
            { tag: 'SNT +4.5', open: '+3.5', now: '+4.5', dir: 'down', pct: '41% sharp' },
            { tag: 'TDL O 48.5', open: 'O 47', now: 'O 48.5', dir: 'up', pct: '58% public' },
          ].map((x) => (
            <div key={x.tag} style={{
              display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, alignItems: 'center',
            }}>
              <div>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 700 }}>{x.tag}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
                  {x.open.toUpperCase()} → {x.now.toUpperCase()} · {x.pct.toUpperCase()}
                </div>
              </div>
              <div style={{
                fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700,
                color: x.dir === 'up' ? 'var(--pos)' : 'var(--neg)',
              }}>
                <IconArrow dir={x.dir} />
              </div>
            </div>
          ))}
        </div>
      </RailCardA>

      {/* Injuries */}
      <RailCardA title="INJURY WIRE" sub="Model impact">
        <div style={{ display: 'grid', gap: 10 }}>
          {[
            { name: 'D. Kline',   team: 'BLZ', pos: 'WR', status: 'Q',   impact: '-2.1%' },
            { name: 'J. Kowalski', team: 'SNT', pos: 'QB', status: 'OUT', impact: '-8.4%' },
            { name: 'T. Marchetti', team: 'TMB', pos: 'RB', status: 'P',  impact: '-0.8%' },
            { name: 'R. Aldana',  team: 'CRW', pos: 'TE', status: 'Q',   impact: '-1.3%' },
          ].map((p) => (
            <div key={p.name} style={{
              display: 'grid', gridTemplateColumns: 'auto 1fr auto auto', gap: 10, alignItems: 'center',
            }}>
              <TeamMark abbr={p.team} size={26} />
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{p.name}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{p.pos} · {TEAMS[p.team].name}</div>
              </div>
              <span style={{
                padding: '2px 6px', fontSize: 10, fontWeight: 700,
                background: p.status === 'OUT' ? 'var(--neg)' : p.status === 'Q' ? 'var(--accent)' : 'var(--text-muted)',
                color: p.status === 'OUT' || p.status === 'Q' ? '#000' : 'var(--bg)',
                borderRadius: 2, fontFamily: 'var(--font-display)',
              }}>{p.status}</span>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700, color: 'var(--neg)', fontVariantNumeric: 'tabular-nums' }}>{p.impact}</span>
            </div>
          ))}
        </div>
      </RailCardA>

      {/* Standings brief */}
      <RailCardA title="STANDINGS · CONF" sub="Top 6 ranked">
        <div style={{ display: 'grid', gap: 6 }}>
          {STANDINGS_BRIEF.map((s, i) => (
            <div key={s.abbr} style={{
              display: 'grid', gridTemplateColumns: '20px auto 1fr auto auto', gap: 10, alignItems: 'center',
              padding: '4px 0',
            }}>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 11, color: 'var(--text-muted)', fontWeight: 700 }}>{i + 1}</span>
              <TeamMark abbr={s.abbr} size={24} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>{TEAMS[s.abbr].name}</span>
              <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{s.w}-{s.l}</span>
              <span style={{
                fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 700,
                color: s.streak.startsWith('W') ? 'var(--pos)' : 'var(--neg)',
              }}>{s.streak}</span>
            </div>
          ))}
        </div>
      </RailCardA>
    </div>
  );
}

function RailCardA({ title, sub, children }) {
  return (
    <div style={{
      background: 'var(--surface-2)', border: '1px solid var(--border)',
      borderRadius: 4,
    }}>
      <div style={{
        padding: '10px 14px', borderBottom: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        background: 'var(--surface-3)',
      }}>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em' }}>
          {title}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.08em' }}>{sub.toUpperCase()}</span>
      </div>
      <div style={{ padding: '14px' }}>{children}</div>
    </div>
  );
}

function MatchupGridA() {
  return (
    <div style={{
      background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 4,
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 18px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, letterSpacing: '0.12em' }}>WEEK 12 · ALL MATCHUPS</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>8 games · 3 model edges ≥5pt</span>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {['ALL', 'EDGES', 'FADE', 'LOCKS'].map((t, i) => (
            <button key={t} style={{
              padding: '5px 12px', fontSize: 10, fontFamily: 'var(--font-display)',
              fontWeight: 700, letterSpacing: '0.1em',
              background: i === 0 ? 'var(--accent)' : 'transparent',
              color: i === 0 ? '#000' : 'var(--text-muted)',
              border: '1px solid ' + (i === 0 ? 'var(--accent)' : 'var(--border)'),
              borderRadius: 2, cursor: 'pointer',
            }}>{t}</button>
          ))}
        </div>
      </div>
      <div>
        {/* Column headers */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '90px 1fr 80px 1fr 140px 100px 80px 80px',
          padding: '8px 18px', gap: 12,
          fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 700,
          letterSpacing: '0.12em', color: 'var(--text-muted)',
          borderBottom: '1px solid var(--border)',
        }}>
          <span>KICKOFF</span>
          <span>AWAY</span>
          <span style={{ textAlign: 'center' }}>WIN%</span>
          <span style={{ textAlign: 'right' }}>HOME</span>
          <span>WIN PROBABILITY</span>
          <span style={{ textAlign: 'right' }}>SPREAD · O/U</span>
          <span style={{ textAlign: 'right' }}>EDGE</span>
          <span style={{ textAlign: 'right' }}>CONF</span>
        </div>
        {MATCHUPS.map((m, i) => (
          <MatchupRow key={i} m={m} />
        ))}
      </div>
    </div>
  );
}

function MatchupRow({ m }) {
  const a = TEAMS[m.away], h = TEAMS[m.home];
  const awayIsWinner = m.awayPct > 50;
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '90px 1fr 80px 1fr 140px 100px 80px 80px',
        padding: '12px 18px', gap: 12, alignItems: 'center',
        borderBottom: '1px solid var(--border)',
        background: hover ? 'var(--surface-3)' : 'transparent',
        cursor: 'pointer', transition: 'background 120ms',
      }}>
      <div>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700, color: 'var(--text)' }}>{m.status.split(' ')[0]}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{m.status.split(' ').slice(1).join(' ')}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <TeamMark abbr={m.away} size={28} />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{a.name}</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{a.city}</div>
        </div>
      </div>
      <div style={{
        textAlign: 'center',
        fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 800,
        color: awayIsWinner ? a.primary : 'var(--text-muted)',
        fontVariantNumeric: 'tabular-nums',
      }}>{m.awayPct}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'flex-end' }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{h.name}</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{h.city}</div>
        </div>
        <TeamMark abbr={m.home} size={28} />
      </div>
      <ProbBar awayPct={m.awayPct} away={m.away} home={m.home} height={6} />
      <div style={{ textAlign: 'right', fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
        <div>{m.spread}</div>
        <div style={{ color: 'var(--text-muted)' }}>{m.ou}</div>
      </div>
      <div style={{
        textAlign: 'right', fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
        color: m.edge.includes('MODEL') ? 'var(--accent)' : m.edge === 'FADE' ? 'var(--neg)' : 'var(--text-muted)',
      }}>{m.edge}</div>
      <div style={{ textAlign: 'right' }}>
        <span style={{
          fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 700,
          padding: '3px 8px', letterSpacing: '0.1em',
          borderRadius: 2,
          background: m.confidence === 'HIGH' ? 'var(--pos)' : m.confidence === 'MEDIUM' ? 'var(--surface-3)' : 'var(--surface-3)',
          color: m.confidence === 'HIGH' ? '#000' : m.confidence === 'MEDIUM' ? 'var(--accent)' : 'var(--text-muted)',
          border: m.confidence === 'MEDIUM' ? '1px solid var(--accent)' : 'none',
        }}>{m.confidence}</span>
      </div>
    </div>
  );
}

function ValuePicksA() {
  return (
    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 4 }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 18px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-3)',
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 700, letterSpacing: '0.12em' }}>FANTASY VALUE PICKS</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Projection vs ownership · edge-ranked</span>
        </div>
        <a href="#" style={{ fontSize: 11, fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--accent)', textDecoration: 'none', letterSpacing: '0.1em' }}>
          FULL FANTASY DASH →
        </a>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1, background: 'var(--border)' }}>
        {VALUE_PICKS.map((p, i) => (
          <ValuePickCard key={i} p={p} />
        ))}
      </div>
    </div>
  );
}

function ValuePickCard({ p }) {
  const t = TEAMS[p.team];
  return (
    <div style={{
      background: 'var(--surface-2)', padding: '14px 16px',
      display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 12,
      alignItems: 'center', cursor: 'pointer',
      transition: 'background 120ms',
    }}
    onMouseEnter={(e) => e.currentTarget.style.background = 'var(--surface-3)'}
    onMouseLeave={(e) => e.currentTarget.style.background = 'var(--surface-2)'}>
      <TeamMark abbr={p.team} size={34} />
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{p.name}</span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-display)', fontWeight: 700, letterSpacing: '0.1em' }}>{p.pos}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>PROJ</span>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{p.proj}</span>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>OWN</span>
          <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{p.own}%</span>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 800,
          color: 'var(--accent)', letterSpacing: '-0.01em',
        }}>{p.edge}</div>
        <div style={{
          display: 'inline-block', marginTop: 3,
          padding: '2px 6px', fontSize: 9, fontWeight: 700,
          fontFamily: 'var(--font-display)', letterSpacing: '0.1em',
          background: p.tag === 'SLEEPER' ? 'var(--accent)' : 'var(--surface-3)',
          color: p.tag === 'SLEEPER' ? '#000' : 'var(--text-muted)',
          border: p.tag === 'CORE' ? '1px solid var(--pos)' : 'none',
          borderRadius: 2,
        }}>{p.tag}</div>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardA });
