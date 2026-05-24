// Time-Blocking Planner — three redesign variants on a canvas.

const PAL = {
  bg: '#FAF8F4',
  surface: '#FFFFFF',
  ink: '#1B1A17',
  ink2: '#3A3631',
  muted: '#6B655B',
  hairline: '#ECE7DC',
  hairline2: '#E2DBCC',
  accent: '#E07A3B',          // now / active
  accentSoft: '#FBE9D7',
  accentDeep: '#B65C24',
  done: '#4C8A6E',
  doneSoft: '#DDEBE2',
  skip: '#B0A89C',
  skipSoft: '#EFEBE3',
  sans: '"Geist", -apple-system, system-ui, sans-serif',
  mono: '"Geist Mono", ui-monospace, monospace',
};

// Shared data — same 5 blocks across variants, with statuses
const BLOCKS = [
  { id: 'b1', start: '13:00', end: '14:00', dur: 60, title: 'Lunch break',          tag: 'Break', status: 'done' },
  { id: 'b2', start: '14:00', end: '15:00', dur: 60, title: 'Issue #188 — auth bug', tag: 'Deep work', status: 'active' },
  { id: 'b3', start: '15:00', end: '16:00', dur: 60, title: 'P3 ticket triage',      tag: 'Shallow', status: 'upcoming' },
  { id: 'b4', start: '16:00', end: '16:30', dur: 30, title: 'Coffee + walk',         tag: 'Break', status: 'upcoming' },
  { id: 'b5', start: '16:30', end: '17:30', dur: 60, title: 'New tickets sweep',     tag: 'Shallow', status: 'upcoming' },
];

// "Now" anchored at 14:23 (23 minutes into block 2)
const NOW = { h: 14, m: 23 };
const minOf = (hm) => { const [h,m] = hm.split(':').map(Number); return h*60+m; };
const nowMin = NOW.h*60 + NOW.m;

// ─────────────────────────────────────────────────────────────
// Small atoms
// ─────────────────────────────────────────────────────────────
function StatusDot({ status, size = 8 }) {
  const c = status === 'done' ? PAL.done
          : status === 'active' ? PAL.accent
          : status === 'skip' ? PAL.skip
          : '#CFC7B7';
  return (
    <span style={{
      display: 'inline-block', width: size, height: size, borderRadius: 999,
      background: c, flexShrink: 0,
      boxShadow: status === 'active' ? `0 0 0 4px ${PAL.accentSoft}` : 'none',
    }} />
  );
}

function Pill({ children, tone = 'neutral', mono = false }) {
  const tones = {
    neutral: { bg: '#F2EEE5', fg: PAL.ink2, bd: 'transparent' },
    accent:  { bg: PAL.accentSoft, fg: PAL.accentDeep, bd: 'transparent' },
    done:    { bg: PAL.doneSoft, fg: '#2E5C46', bd: 'transparent' },
    outline: { bg: 'transparent', fg: PAL.muted, bd: PAL.hairline2 },
  };
  const t = tones[tone];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 9px', borderRadius: 999,
      background: t.bg, color: t.fg,
      border: `1px solid ${t.bd}`,
      fontFamily: mono ? PAL.mono : PAL.sans,
      fontSize: 11, fontWeight: 500, letterSpacing: mono ? 0 : 0.2,
      textTransform: mono ? 'none' : 'uppercase',
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function Icon({ name, size = 16, color = 'currentColor', stroke = 1.6 }) {
  const p = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
              stroke: color, strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round' };
  switch (name) {
    case 'check':    return <svg {...p}><path d="M4 12l5 5L20 6"/></svg>;
    case 'x':        return <svg {...p}><path d="M6 6l12 12M18 6L6 18"/></svg>;
    case 'play':     return <svg {...p}><path d="M7 5v14l12-7z" fill={color} stroke="none"/></svg>;
    case 'pause':    return <svg {...p}><rect x="7" y="5" width="3.5" height="14" rx="1" fill={color} stroke="none"/><rect x="13.5" y="5" width="3.5" height="14" rx="1" fill={color} stroke="none"/></svg>;
    case 'chev-l':   return <svg {...p}><path d="M15 6l-6 6 6 6"/></svg>;
    case 'chev-r':   return <svg {...p}><path d="M9 6l6 6-6 6"/></svg>;
    case 'cal':      return <svg {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></svg>;
    case 'plus':     return <svg {...p}><path d="M12 5v14M5 12h14"/></svg>;
    case 'more':     return <svg {...p}><circle cx="6" cy="12" r="1" fill={color}/><circle cx="12" cy="12" r="1" fill={color}/><circle cx="18" cy="12" r="1" fill={color}/></svg>;
    case 'flame':    return <svg {...p}><path d="M12 3c0 4-5 5-5 10a5 5 0 0010 0c0-2-1-3-2-4 0 2-1 3-2 3 0-3 1-5-1-9z"/></svg>;
    case 'coffee':   return <svg {...p}><path d="M4 9h12v6a4 4 0 01-4 4H8a4 4 0 01-4-4V9zM16 11h2a3 3 0 010 6h-2M7 4v2M11 4v2"/></svg>;
    case 'brain':    return <svg {...p}><path d="M9 5a3 3 0 00-3 3v1a3 3 0 00-2 3 3 3 0 002 3v1a3 3 0 003 3M15 5a3 3 0 013 3v1a3 3 0 012 3 3 3 0 01-2 3v1a3 3 0 01-3 3M9 5v14M15 5v14"/></svg>;
    case 'list':     return <svg {...p}><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/></svg>;
    case 'arrow-r':  return <svg {...p}><path d="M5 12h14M13 6l6 6-6 6"/></svg>;
    default: return null;
  }
}

const tagIcon = (tag) => tag === 'Deep work' ? 'brain' : tag === 'Break' ? 'coffee' : 'list';

// ─────────────────────────────────────────────────────────────
// Variant 1 — TIMELINE  (true vertical hour axis)
// ─────────────────────────────────────────────────────────────
function VariantTimeline() {
  const startHour = 9, endHour = 19;
  const hours = endHour - startHour;
  const pxPerHr = 56;
  const trackH = hours * pxPerHr;
  const yOf = (m) => ((m - startHour*60) / 60) * pxPerHr;

  const W = 1080, H = 720;

  return (
    <div style={{
      width: W, height: H, background: PAL.bg, color: PAL.ink,
      fontFamily: PAL.sans, position: 'relative', overflow: 'hidden',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '24px 32px 18px', borderBottom: `1px solid ${PAL.hairline}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.4 }}>Planner</div>
          <div style={{ fontFamily: PAL.mono, fontSize: 12, color: PAL.muted, letterSpacing: 0.4 }}>SUN · MAY 24 · 2026</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SegTabs items={['Day', 'Week', 'Template']} active="Day" />
          <div style={{ width: 1, height: 22, background: PAL.hairline2, margin: '0 6px' }} />
          <IconBtn name="chev-l" />
          <button style={btnTodayStyle}>Today</button>
          <IconBtn name="chev-r" />
          <button style={btnPrimaryStyle}><Icon name="plus" size={14} color="#fff" /><span>Block</span></button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 320px', minHeight: 0 }}>
        {/* Timeline */}
        <div style={{ padding: '24px 12px 24px 32px', overflow: 'hidden', position: 'relative' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: PAL.muted, fontFamily: PAL.mono, letterSpacing: 1, textTransform: 'uppercase' }}>Schedule</div>
            <div style={{ fontSize: 12, color: PAL.muted }}>1 of 5 done · 1 active</div>
          </div>

          <div style={{ position: 'relative', height: trackH, marginLeft: 56 }}>
            {/* hour gridlines + labels */}
            {Array.from({ length: hours + 1 }).map((_, i) => {
              const h = startHour + i;
              return (
                <div key={i} style={{
                  position: 'absolute', left: -56, right: 0, top: i * pxPerHr,
                  height: 1, background: PAL.hairline,
                  display: 'flex', alignItems: 'center',
                }}>
                  <span style={{
                    width: 46, fontFamily: PAL.mono, fontSize: 11, color: PAL.muted,
                    transform: 'translateY(-50%)', background: PAL.bg, paddingRight: 8, textAlign: 'right',
                  }}>{String(h).padStart(2,'0')}:00</span>
                </div>
              );
            })}

            {/* blocks */}
            {BLOCKS.map((b) => {
              const top = yOf(minOf(b.start));
              const h = (b.dur / 60) * pxPerHr;
              const isActive = b.status === 'active';
              const isDone = b.status === 'done';
              const bd = isActive ? PAL.accent : isDone ? PAL.done : PAL.hairline2;
              const bg = isActive ? '#fff' : isDone ? '#fff' : '#fff';
              const stripe = isActive ? PAL.accent : isDone ? PAL.done : PAL.hairline2;
              return (
                <div key={b.id} style={{
                  position: 'absolute', left: 8, right: 8, top, height: h - 4,
                  background: bg, borderRadius: 12,
                  border: `1px solid ${bd}`,
                  boxShadow: isActive
                    ? `0 1px 0 ${PAL.hairline}, 0 12px 28px -16px ${PAL.accent}55`
                    : `0 1px 0 ${PAL.hairline}`,
                  display: 'flex', overflow: 'hidden',
                  opacity: isDone ? 0.78 : 1,
                }}>
                  <div style={{ width: 4, background: stripe, flexShrink: 0 }} />
                  <div style={{ padding: '10px 14px', flex: 1, display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 8, background: isActive ? PAL.accentSoft : '#F2EEE5',
                                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                                  color: isActive ? PAL.accentDeep : PAL.ink2, flexShrink: 0 }}>
                      <Icon name={tagIcon(b.tag)} size={16} />
                    </div>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                        <span style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted }}>{b.start}–{b.end}</span>
                        <Pill tone={isActive ? 'accent' : isDone ? 'done' : 'outline'}>
                          {isActive ? 'Now' : isDone ? 'Done' : b.tag}
                        </Pill>
                      </div>
                      <div style={{ fontSize: 14, fontWeight: 550, color: PAL.ink,
                                    textDecoration: isDone ? 'line-through' : 'none',
                                    textDecorationColor: PAL.muted,
                                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {b.title}
                      </div>
                    </div>
                    {isActive && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <button style={miniBtnStyle('ghost')}><Icon name="check" size={14}/></button>
                        <button style={miniBtnStyle('ghost')}><Icon name="x" size={14}/></button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* NOW line */}
            <div style={{ position: 'absolute', left: -56, right: 0, top: yOf(nowMin), height: 0, zIndex: 5 }}>
              <div style={{ position: 'absolute', left: 0, top: -7, width: 46, textAlign: 'right',
                            fontFamily: PAL.mono, fontSize: 11, fontWeight: 600, color: PAL.accent, paddingRight: 8 }}>
                14:23
              </div>
              <div style={{ position: 'absolute', left: 50, right: 0, top: 0, height: 0,
                            borderTop: `1.5px solid ${PAL.accent}` }} />
              <div style={{ position: 'absolute', left: 46, top: -5, width: 10, height: 10, borderRadius: 999,
                            background: PAL.accent, boxShadow: `0 0 0 4px ${PAL.bg}, 0 0 0 6px ${PAL.accent}33` }} />
            </div>
          </div>
        </div>

        {/* Side: progress + summary */}
        <div style={{ padding: '24px 32px 24px 20px', borderLeft: `1px solid ${PAL.hairline}`,
                      display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Card title="Progress" trailing={<span style={{ fontFamily: PAL.mono, fontSize: 12, color: PAL.muted }}>1 / 5</span>}>
            <DonutProgress value={1} total={5} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 16 }}>
              <Stat label="Focused" value="0h 23m" tone="accent" />
              <Stat label="Remaining" value="3h 07m" />
            </div>
          </Card>

          <Card title="Now" subtitle="14:00–15:00 · Deep work">
            <div style={{ fontSize: 18, fontWeight: 600, color: PAL.ink, lineHeight: 1.25 }}>Issue #188 — auth bug</div>
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ fontFamily: PAL.mono, fontSize: 28, fontWeight: 600, color: PAL.accent, letterSpacing: -0.5 }}>37:00</span>
              <span style={{ fontSize: 12, color: PAL.muted }}>left</span>
            </div>
            <div style={{ height: 4, background: PAL.hairline, borderRadius: 999, marginTop: 8, overflow: 'hidden' }}>
              <div style={{ width: '38%', height: '100%', background: PAL.accent }} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <button style={{ ...btnPrimaryStyle, flex: 1, justifyContent: 'center' }}><Icon name="check" size={14} color="#fff"/>Complete</button>
              <button style={btnGhostStyle}><Icon name="pause" size={14}/></button>
              <button style={btnGhostStyle}><Icon name="more" size={14}/></button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Variant 2 — FOCUS  (hero current block + queue)
// ─────────────────────────────────────────────────────────────
function VariantFocus() {
  const W = 1080, H = 720;
  const remaining = BLOCKS.filter(b => b.status === 'upcoming');
  const done = BLOCKS.filter(b => b.status === 'done');

  return (
    <div style={{
      width: W, height: H, background: PAL.bg, color: PAL.ink,
      fontFamily: PAL.sans, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* slim top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '18px 32px', borderBottom: `1px solid ${PAL.hairline}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Planner</div>
          <div style={{ fontFamily: PAL.mono, fontSize: 12, color: PAL.muted }}>Sun · May 24</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <DayDots blocks={BLOCKS} />
          <span style={{ fontFamily: PAL.mono, fontSize: 12, color: PAL.muted, marginLeft: 6 }}>1 / 5</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SegTabs items={['Day', 'Template']} active="Day" small />
          <IconBtn name="cal" />
          <button style={btnPrimaryStyle}><Icon name="plus" size={14} color="#fff"/><span>Block</span></button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1.35fr 1fr', minHeight: 0 }}>
        {/* HERO — current */}
        <div style={{ padding: '36px 36px 28px', display: 'flex', flexDirection: 'column', gap: 22,
                      borderRight: `1px solid ${PAL.hairline}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: PAL.accent,
                           boxShadow: `0 0 0 5px ${PAL.accentSoft}` }} />
            <span style={{ fontFamily: PAL.mono, fontSize: 11, fontWeight: 600, letterSpacing: 1.4,
                           textTransform: 'uppercase', color: PAL.accentDeep }}>Now · Deep work</span>
          </div>

          <div>
            <div style={{ fontFamily: PAL.mono, fontSize: 13, color: PAL.muted, marginBottom: 8 }}>
              14:00 — 15:00 · 60 min
            </div>
            <div style={{ fontSize: 44, fontWeight: 600, letterSpacing: -1.2, lineHeight: 1.05, color: PAL.ink }}>
              Issue&nbsp;#188
              <span style={{ color: PAL.muted, fontWeight: 400 }}> — auth bug</span>
            </div>
          </div>

          {/* Time-remaining display */}
          <div style={{
            display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between',
            padding: '20px 24px', background: '#fff', borderRadius: 16,
            border: `1px solid ${PAL.hairline}`, gap: 24,
          }}>
            <div>
              <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted, textTransform: 'uppercase', letterSpacing: 1.2 }}>Time remaining</div>
              <div style={{ fontFamily: PAL.mono, fontWeight: 600, fontSize: 64, lineHeight: 1, letterSpacing: -2,
                            color: PAL.accent, marginTop: 6 }}>
                37<span style={{ color: PAL.accentDeep, opacity: 0.5 }}>:</span>00
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
                <div style={{ width: 180, height: 4, background: PAL.hairline, borderRadius: 999, overflow: 'hidden' }}>
                  <div style={{ width: '38%', height: '100%', background: PAL.accent }} />
                </div>
                <span style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted }}>38%</span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
              <div style={{ fontSize: 11, fontFamily: PAL.mono, color: PAL.muted, textTransform: 'uppercase', letterSpacing: 1.2 }}>Up next</div>
              <div style={{ fontSize: 14, fontWeight: 550 }}>P3 ticket triage</div>
              <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted }}>15:00 · 60 min</div>
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button style={{ ...btnPrimaryStyle, padding: '12px 20px', fontSize: 14, flex: '0 0 auto' }}>
              <Icon name="check" size={16} color="#fff"/>Mark complete
            </button>
            <button style={{ ...btnGhostStyle, padding: '12px 16px', fontSize: 14 }}>
              <Icon name="pause" size={14} />Pause
            </button>
            <button style={{ ...btnGhostStyle, padding: '12px 16px', fontSize: 14 }}>
              <Icon name="x" size={14} />Skip
            </button>
            <div style={{ flex: 1 }} />
            <button style={btnGhostStyle}><Icon name="more" size={14}/></button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginTop: 'auto' }}>
            <Stat label="Day focus" value="0h 23m" tone="accent" />
            <Stat label="Day remaining" value="3h 07m" />
            <Stat label="Streak" value="4 days" icon="flame" />
          </div>
        </div>

        {/* Queue */}
        <div style={{ padding: '36px 36px 28px', display: 'flex', flexDirection: 'column', gap: 18, minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted, textTransform: 'uppercase', letterSpacing: 1.4, fontWeight: 600 }}>Up Next</div>
            <span style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted }}>{remaining.length} blocks · 2h 30m</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {remaining.map((b) => <QueueRow key={b.id} block={b} />)}
          </div>

          <div style={{ height: 1, background: PAL.hairline, margin: '8px 0' }} />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted, textTransform: 'uppercase', letterSpacing: 1.4, fontWeight: 600 }}>Completed</div>
            <span style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted }}>1 block · 1h</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {done.map((b) => <QueueRow key={b.id} block={b} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

function QueueRow({ block: b }) {
  const isDone = b.status === 'done';
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 14,
      padding: '12px 14px', background: '#fff', borderRadius: 12,
      border: `1px solid ${PAL.hairline}`, opacity: isDone ? 0.72 : 1,
    }}>
      <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted, width: 86, flexShrink: 0 }}>
        {b.start}<br/>
        <span style={{ opacity: 0.7 }}>—{b.end}</span>
      </div>
      <div style={{ width: 1, height: 28, background: PAL.hairline2, flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 550, color: PAL.ink,
                      textDecoration: isDone ? 'line-through' : 'none', textDecorationColor: PAL.muted,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.title}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
          <Icon name={tagIcon(b.tag)} size={11} color={PAL.muted} />
          <span style={{ fontSize: 11, color: PAL.muted }}>{b.tag} · {b.dur} min</span>
        </div>
      </div>
      {isDone
        ? <span style={{ width: 22, height: 22, borderRadius: 999, background: PAL.doneSoft,
                         display: 'flex', alignItems: 'center', justifyContent: 'center', color: PAL.done }}>
            <Icon name="check" size={13} stroke={2.4} />
          </span>
        : <button style={miniBtnStyle('ghost')}><Icon name="more" size={14}/></button>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Variant 3 — COMPACT  (refined list, denser, status-as-state)
// ─────────────────────────────────────────────────────────────
function VariantCompact() {
  const W = 1080, H = 720;

  return (
    <div style={{
      width: W, height: H, background: PAL.bg, color: PAL.ink,
      fontFamily: PAL.sans, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '28px 40px 0' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <div style={{ fontFamily: PAL.mono, fontSize: 11, color: PAL.muted, letterSpacing: 1.4, textTransform: 'uppercase', marginBottom: 6 }}>
              Sunday · Week 21
            </div>
            <div style={{ fontSize: 40, fontWeight: 600, letterSpacing: -1, lineHeight: 1, color: PAL.ink }}>
              May 24
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <SegTabs items={['Day', 'Template']} active="Day" small />
            <div style={{ width: 1, height: 22, background: PAL.hairline2, margin: '0 4px' }} />
            <IconBtn name="chev-l" />
            <button style={btnTodayStyle}>Today</button>
            <IconBtn name="chev-r" />
            <button style={btnPrimaryStyle}><Icon name="plus" size={14} color="#fff" /><span>New block</span></button>
          </div>
        </div>

        {/* Stat strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto auto auto auto', gap: 28, alignItems: 'center',
                      padding: '18px 24px', background: '#fff', borderRadius: 14, border: `1px solid ${PAL.hairline}` }}>
          <div>
            <div style={{ fontFamily: PAL.mono, fontSize: 10, color: PAL.muted, letterSpacing: 1.2, textTransform: 'uppercase' }}>Progress</div>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2 }}>1<span style={{ color: PAL.muted, fontWeight: 400 }}> / 5</span></div>
          </div>
          <div>
            <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
              {BLOCKS.map((b) => (
                <div key={b.id} style={{
                  flex: b.dur,
                  height: 8, borderRadius: 4,
                  background: b.status === 'done' ? PAL.done
                            : b.status === 'active' ? PAL.accent
                            : PAL.hairline2,
                  position: 'relative', overflow: 'hidden',
                }}>
                  {b.status === 'active' && (
                    <div style={{ position: 'absolute', inset: 0, background: PAL.accentSoft,
                                  width: '62%', right: 0, left: 'auto' }} />
                  )}
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: PAL.mono, fontSize: 10, color: PAL.muted }}>
              <span>13:00</span><span>17:30</span>
            </div>
          </div>
          <Divider />
          <Stat compact label="Focus today" value="0h 23m" tone="accent" />
          <Divider />
          <Stat compact label="Streak" value="4 days" icon="flame" />
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, padding: '20px 40px 32px', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'grid',
                      gridTemplateColumns: '110px 1fr 130px 110px 120px',
                      gap: 16, padding: '6px 18px',
                      fontFamily: PAL.mono, fontSize: 10, color: PAL.muted, letterSpacing: 1.2, textTransform: 'uppercase' }}>
          <span>Time</span><span>Block</span><span>Type</span><span>Duration</span><span style={{ textAlign: 'right' }}>State</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
          {BLOCKS.map((b) => <CompactRow key={b.id} block={b} />)}
        </div>
        <div style={{ marginTop: 10, padding: '12px 18px', border: `1.5px dashed ${PAL.hairline2}`,
                      borderRadius: 12, color: PAL.muted, fontSize: 13, display: 'flex',
                      alignItems: 'center', gap: 10, cursor: 'pointer' }}>
          <Icon name="plus" size={14} color={PAL.muted} /> Add a block after 17:30
        </div>
      </div>
    </div>
  );
}

function CompactRow({ block: b }) {
  const isActive = b.status === 'active';
  const isDone = b.status === 'done';
  const stateColor = isActive ? PAL.accent : isDone ? PAL.done : PAL.hairline2;

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '110px 1fr 130px 110px 120px',
      gap: 16, alignItems: 'center',
      padding: '14px 18px', background: '#fff',
      border: `1px solid ${isActive ? PAL.accent : PAL.hairline}`,
      borderRadius: 12,
      boxShadow: isActive ? `0 1px 0 ${PAL.hairline}, 0 10px 28px -16px ${PAL.accent}55` : 'none',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* leading stripe */}
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 3, background: stateColor }} />

      <div style={{ fontFamily: PAL.mono, fontSize: 13, color: PAL.ink2 }}>
        {b.start}<span style={{ color: PAL.muted }}> → </span>{b.end}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 15, fontWeight: 550,
                      textDecoration: isDone ? 'line-through' : 'none', textDecorationColor: PAL.muted,
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.title}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: PAL.muted, fontSize: 13 }}>
        <Icon name={tagIcon(b.tag)} size={13} color={PAL.muted} /> {b.tag}
      </div>
      <div style={{ fontFamily: PAL.mono, fontSize: 13, color: PAL.ink2 }}>{b.dur} min</div>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        {isActive
          ? <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontFamily: PAL.mono, fontSize: 12, color: PAL.accentDeep, fontWeight: 600 }}>37m left</span>
              <button style={miniBtnStyle('accent')}><Icon name="check" size={13} stroke={2.4} color="#fff"/></button>
            </div>
          : isDone
            ? <Pill tone="done"><Icon name="check" size={11} stroke={2.6} color={PAL.done} />Done · 13:58</Pill>
            : <div style={{ display: 'flex', gap: 6 }}>
                <button style={miniBtnStyle('ghost')}><Icon name="check" size={13}/></button>
                <button style={miniBtnStyle('ghost')}><Icon name="x" size={13}/></button>
              </div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Shared building blocks
// ─────────────────────────────────────────────────────────────
function SegTabs({ items, active, small = false }) {
  return (
    <div style={{
      display: 'inline-flex', padding: 3, background: '#F2EEE5', borderRadius: 10,
      gap: 2,
    }}>
      {items.map((it) => (
        <button key={it} style={{
          padding: small ? '5px 12px' : '6px 14px',
          fontSize: small ? 12 : 13, fontWeight: 550,
          border: 'none', borderRadius: 8, cursor: 'pointer',
          background: it === active ? '#fff' : 'transparent',
          color: it === active ? PAL.ink : PAL.muted,
          boxShadow: it === active ? '0 1px 2px rgba(0,0,0,0.05), 0 0 0 1px rgba(0,0,0,0.04)' : 'none',
          fontFamily: PAL.sans,
        }}>{it}</button>
      ))}
    </div>
  );
}

function IconBtn({ name }) {
  return (
    <button style={{
      width: 32, height: 32, borderRadius: 8, border: `1px solid ${PAL.hairline2}`,
      background: '#fff', cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center', color: PAL.ink2,
    }}><Icon name={name} size={14} /></button>
  );
}

const btnPrimaryStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 7,
  padding: '7px 14px', borderRadius: 9, border: 'none', cursor: 'pointer',
  background: PAL.ink, color: '#fff', fontSize: 13, fontWeight: 550, fontFamily: PAL.sans,
};
const btnTodayStyle = {
  padding: '6px 13px', borderRadius: 8, border: `1px solid ${PAL.hairline2}`,
  background: '#fff', cursor: 'pointer', color: PAL.ink, fontSize: 13, fontWeight: 550, fontFamily: PAL.sans,
};
const btnGhostStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 7,
  padding: '7px 12px', borderRadius: 9, border: `1px solid ${PAL.hairline2}`,
  background: '#fff', color: PAL.ink2, cursor: 'pointer',
  fontSize: 13, fontWeight: 500, fontFamily: PAL.sans,
};

const miniBtnStyle = (variant) => {
  const base = {
    width: 28, height: 28, borderRadius: 7, cursor: 'pointer',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    border: `1px solid ${PAL.hairline2}`, background: '#fff', color: PAL.ink2,
  };
  if (variant === 'accent') return { ...base, background: PAL.accent, color: '#fff', border: 'none' };
  if (variant === 'ghost')  return base;
  return base;
};

function Card({ title, subtitle, trailing, children }) {
  return (
    <div style={{ background: '#fff', borderRadius: 14, padding: 18,
                  border: `1px solid ${PAL.hairline}` }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ fontFamily: PAL.mono, fontSize: 10, color: PAL.muted, letterSpacing: 1.4, textTransform: 'uppercase', fontWeight: 600 }}>{title}</div>
          {subtitle && <div style={{ fontSize: 12, color: PAL.muted, marginTop: 2 }}>{subtitle}</div>}
        </div>
        {trailing}
      </div>
      {children}
    </div>
  );
}

function Stat({ label, value, tone, icon, compact = false }) {
  const color = tone === 'accent' ? PAL.accent : PAL.ink;
  return (
    <div style={{
      padding: compact ? 0 : 12, borderRadius: 10,
      background: compact ? 'transparent' : '#FBF8F2',
      border: compact ? 'none' : `1px solid ${PAL.hairline}`,
    }}>
      <div style={{ fontFamily: PAL.mono, fontSize: 10, color: PAL.muted, letterSpacing: 1.2, textTransform: 'uppercase' }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: compact ? 2 : 4 }}>
        {icon && <Icon name={icon} size={14} color={PAL.accent} />}
        <span style={{ fontFamily: PAL.mono, fontSize: compact ? 18 : 17, fontWeight: 600, color }}>{value}</span>
      </div>
    </div>
  );
}

function Divider() {
  return <div style={{ width: 1, height: 36, background: PAL.hairline2 }} />;
}

function DonutProgress({ value, total }) {
  const size = 96, r = 38, c = 2 * Math.PI * r;
  const pct = value / total;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={PAL.hairline} strokeWidth="8" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={PAL.done} strokeWidth="8"
                strokeDasharray={`${c*pct} ${c}`} strokeLinecap="round"
                transform={`rotate(-90 ${size/2} ${size/2})`} />
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
              fontFamily={PAL.mono} fontSize="20" fontWeight="600" fill={PAL.ink}>
          {Math.round(pct * 100)}%
        </text>
      </svg>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusDot status="done" /><span style={{ fontSize: 12, color: PAL.ink2 }}>1 done</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
          <StatusDot status="active" /><span style={{ fontSize: 12, color: PAL.ink2 }}>1 active</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
          <StatusDot status="upcoming" /><span style={{ fontSize: 12, color: PAL.ink2 }}>3 upcoming</span>
        </div>
      </div>
    </div>
  );
}

function DayDots({ blocks }) {
  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {blocks.map(b => <StatusDot key={b.id} status={b.status} size={9} />)}
    </div>
  );
}

Object.assign(window, { VariantTimeline, VariantFocus, VariantCompact });
