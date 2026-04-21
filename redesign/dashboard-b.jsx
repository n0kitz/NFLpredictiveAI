// Direction B — "Prime Time"
// Editorial / broadcast: huge type, hero matchup dominant, quieter rails.

function DashboardB() {
  return (
    <div style={{ background: 'var(--bg)', color: 'var(--text)', minHeight: '100%', fontFamily: 'var(--font-body)' }}>
      <TopBarB />
      <div style={{ padding: '32px 48px 48px', display: 'grid', gap: 36, maxWidth: 1600, margin: '0 auto' }}>
        <EditorialHeaderB />
        <HeroMatchup variant="B" />
        <WeekStoryGridB />
        <SleeperColumnB />
      </div>
    </div>
  );
}

function TopBarB() {
  return (
    <div style={{
      padding: '22px 48px', borderBottom: '1px solid var(--border)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 32 }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontWeight: 800,
          fontSize: 22, letterSpacing: '-0.04em',
        }}>
          the <span style={{ color: 'var(--accent)' }}>Edge</span>
        </div>
        <div style={{ fontSize: 11, letterSpacing: '0.18em', color: 'var(--text-muted)', fontFamily: 'var(--font-display)', fontWeight: 600 }}>
          ISSUE 12 · APR 24, 2026
        </div>
      </div>
      <nav style={{ display: 'flex', gap: 24, fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, letterSpacing: '0.08em' }}>
        {['This Week', 'Predict', 'Teams', 'Fantasy', 'Archive'].map((x, i) => (
          <a key={x} href="#" style={{
            color: i === 0 ? 'var(--text)' : 'var(--text-muted)',
            textDecoration: 'none',
            borderBottom: i === 0 ? '1px solid var(--accent)' : '1px solid transparent',
            paddingBottom: 2,
          }}>{x.toUpperCase()}</a>
        ))}
      </nav>
    </div>
  );
}

function EditorialHeaderB() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr auto', gap: 48,
      alignItems: 'end', paddingBottom: 20, borderBottom: '1px solid var(--border)',
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
          letterSpacing: '0.2em', color: 'var(--accent)', marginBottom: 10,
        }}>WEEK 12 · MODEL BRIEFING</div>
        <h1 style={{
          fontFamily: 'var(--font-display)', fontSize: 72, fontWeight: 800,
          letterSpacing: '-0.045em', lineHeight: 0.95, margin: 0,
          textWrap: 'balance', maxWidth: 900,
        }}>
          Voltage open<br />
          as <span style={{ color: 'var(--accent)' }}>narrow</span> favorites<br />
          over the Rebels.
        </h1>
        <p style={{
          marginTop: 18, maxWidth: 600, fontSize: 15, lineHeight: 1.55,
          color: 'var(--text-muted)', textWrap: 'pretty',
        }}>
          The model gives Los Angeles a 58% edge at home, but recent form
          weighting narrows the gap. Below, a full-market scan and this
          week's highest-edge value picks.
        </p>
      </div>
      <div style={{
        display: 'flex', flexDirection: 'column', gap: 4,
        padding: '16px 20px', border: '1px solid var(--border)',
        borderRadius: 8, minWidth: 220,
      }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>
          SEASON ACCURACY
        </div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 44, fontWeight: 800,
          letterSpacing: '-0.03em', lineHeight: 1, fontVariantNumeric: 'tabular-nums',
        }}>67.2<span style={{ fontSize: '0.5em', opacity: 0.5 }}>%</span></div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          139/207 · <span style={{ color: 'var(--pos)', fontWeight: 700 }}>+3.8 L5</span>
        </div>
        <Spark values={[64,66,67,68,67,69,70,67,68,70,71,67]} color="var(--accent)" w={180} h={22} fill="rgba(255,255,255,0.04)" />
      </div>
    </div>
  );
}

function WeekStoryGridB() {
  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'baseline', gap: 16, marginBottom: 22,
      }}>
        <h2 style={{
          fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 800,
          letterSpacing: '-0.03em', margin: 0,
        }}>The Slate</h2>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
          Seven matchups. Three with model edges of 5 points or more.
        </span>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 20,
      }}>
        {MATCHUPS.slice(1, 7).map((m, i) => (
          <StoryCard key={i} m={m} featured={i === 1} />
        ))}
      </div>
    </div>
  );
}

function StoryCard({ m, featured }) {
  const a = TEAMS[m.away], h = TEAMS[m.home];
  const pct = Math.max(m.awayPct, 100 - m.awayPct);
  const winner = m.awayPct > 50 ? m.away : m.home;
  const wc = TEAMS[winner];
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        padding: '22px 24px',
        background: featured ? 'var(--surface-2)' : 'transparent',
        border: '1px solid var(--border)',
        borderRadius: 10, cursor: 'pointer',
        transform: hover ? 'translateY(-2px)' : 'translateY(0)',
        transition: 'transform 180ms, border-color 180ms',
        borderColor: hover ? 'var(--accent)' : 'var(--border)',
      }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontFamily: 'var(--font-display)', fontSize: 10, fontWeight: 700,
        letterSpacing: '0.14em', color: 'var(--text-muted)', marginBottom: 16,
      }}>
        <span>{m.status.toUpperCase()}</span>
        <span style={{ color: m.edge.includes('MODEL') ? 'var(--accent)' : m.edge === 'FADE' ? 'var(--neg)' : 'var(--text-muted)' }}>
          {m.edge}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <TeamMark abbr={m.away} size={36} />
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em' }}>{a.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{m.awayPct}%</div>
          </div>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>AT</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexDirection: 'row-reverse' }}>
          <TeamMark abbr={m.home} size={36} />
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em' }}>{h.name}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{100 - m.awayPct}%</div>
          </div>
        </div>
      </div>
      <ProbBar awayPct={m.awayPct} away={m.away} home={m.home} height={4} />
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
        marginTop: 18,
      }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.12em', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
            MODEL PICK
          </div>
          <div style={{
            fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800,
            color: wc.primary, letterSpacing: '-0.02em', marginTop: 2,
          }}>
            {wc.name} {pct}%
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.12em', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
            SPREAD
          </div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 700, fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>
            {m.spread}
          </div>
        </div>
      </div>
    </div>
  );
}

function SleeperColumnB() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 48,
      paddingTop: 24, borderTop: '1px solid var(--border)',
    }}>
      <div>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 11, fontWeight: 700,
          letterSpacing: '0.2em', color: 'var(--accent)', marginBottom: 10,
        }}>FANTASY · VALUE PICKS</div>
        <h2 style={{
          fontFamily: 'var(--font-display)', fontSize: 44, fontWeight: 800,
          letterSpacing: '-0.04em', lineHeight: 1, margin: 0, textWrap: 'balance',
        }}>
          Eight names to <em style={{ color: 'var(--accent)', fontStyle: 'normal' }}>beat the chalk</em> this week.
        </h2>
        <p style={{
          marginTop: 16, fontSize: 14, lineHeight: 1.6, color: 'var(--text-muted)',
          textWrap: 'pretty', maxWidth: 340,
        }}>
          Ranked by projected points minus ownership-adjusted baseline.
          Positive edge = the model thinks the market is under-pricing them.
        </p>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 0,
        borderTop: '1px solid var(--border)',
      }}>
        {VALUE_PICKS.map((p, i) => (
          <SleeperRow key={i} p={p} rank={i + 1} />
        ))}
      </div>
    </div>
  );
}

function SleeperRow({ p, rank }) {
  const t = TEAMS[p.team];
  const [hover, setHover] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: 'grid', gridTemplateColumns: '32px auto 1fr auto auto', gap: 14,
        alignItems: 'center', padding: '16px 14px',
        borderBottom: '1px solid var(--border)',
        borderRight: rank % 2 === 1 ? '1px solid var(--border)' : 'none',
        background: hover ? 'var(--surface-2)' : 'transparent',
        transition: 'background 120ms', cursor: 'pointer',
      }}>
      <span style={{
        fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 800,
        color: 'var(--text-muted)', letterSpacing: '-0.02em',
        fontVariantNumeric: 'tabular-nums',
      }}>{String(rank).padStart(2, '0')}</span>
      <TeamMark abbr={p.team} size={32} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 700, letterSpacing: '-0.01em' }}>{p.name}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {p.pos} · {t.name} · {p.own}% owned
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 14, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{p.proj}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em', fontFamily: 'var(--font-display)', fontWeight: 700 }}>PROJ</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{
          fontFamily: 'var(--font-display)', fontSize: 16, fontWeight: 800,
          color: 'var(--accent)', letterSpacing: '-0.01em',
        }}>{p.edge}</div>
        <div style={{
          fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.12em',
          fontFamily: 'var(--font-display)', fontWeight: 700, marginTop: 2,
        }}>{p.tag}</div>
      </div>
    </div>
  );
}

Object.assign(window, { DashboardB });
