/**
 * The instrument panel beside the graph: telemetry feed, metric strip, the
 * exfiltration banner, and the two interrogation answers.
 *
 * The rule that shapes all of it: never narrate something you cannot show. Each
 * number here is read off an event the engine actually emitted, so the panel is
 * evidence rather than commentary.
 */

import { useEffect, useRef } from 'react';
import type { AnyEvent } from '../lib/events';
import { PHASE_COPY, STAGES, stageFor, type CascadeState } from '../lib/cascade';

/* ── telemetry ──────────────────────────────────────────────────────────── */

function lineFor(event: AnyEvent): { text: string; tone?: 'serum' | 'venom' | 'dim' } {
  switch (event.type) {
    case 'run.started':
      return { text: `run ${event.run_id} · seed ${event.seed}`, tone: 'dim' };
    case 'source.ingested':
      return { text: `ingest  ${event.label}`, tone: 'dim' };
    case 'write.risk_scored':
      return {
        text: `filter  ${event.detector}  score ${event.score.toFixed(2)}  ${event.verdict.toUpperCase()}`,
        tone: event.verdict === 'clean' ? 'serum' : 'venom',
      };
    case 'belief.written':
      return { text: `write   ${event.belief_id}  ${event.text.slice(0, 52)}`, tone: 'dim' };
    case 'provenance.edge':
      return { text: `edge    ${event.parent_id} → ${event.child_id}`, tone: 'dim' };
    case 'session.advanced':
      return { text: `session ${event.index}/${event.total}  day ${event.day}  nothing anomalous`, tone: 'dim' };
    case 'agent.retrieved':
      return { text: `recall  ${event.belief_ids.length} beliefs for "${event.query.slice(0, 40)}"` };
    case 'agent.acted':
      return event.outcome === 'harmful'
        ? { text: `ACTION  ${event.action} → ${event.exfil_target}`, tone: 'venom' }
        : { text: `action  ${event.action}` };
    case 'interrogation.turn':
      return {
        text: `ask     ${event.phase === 'pre_surgery' ? 'pre-surgery' : 'post-surgery'}`,
        tone: event.phase === 'pre_surgery' ? 'venom' : 'serum',
      };
    case 'ablation.pass':
      return {
        text: `ablate  ${event.belief_id}  pass ${event.pass_index}/${event.passes_total}  influence ${event.influence.toFixed(2)}`,
        tone: 'dim',
      };
    case 'ablation.culprit':
      return { text: `CULPRIT ${event.culprit_id}  after ${event.passes_used} passes`, tone: 'venom' };
    case 'blast.node':
      return { text: `radius  depth ${event.depth}  ${event.belief_id}`, tone: 'dim' };
    case 'blast.summary':
      return {
        text: `RADIUS  ${event.beliefs_touched} beliefs · ${event.decisions_influenced} decisions · ${event.span_days.toFixed(0)} days`,
        tone: 'venom',
      };
    case 'surgery.started':
      return { text: `operate ${event.candidates} candidates` };
    case 'belief.excised':
      return { text: `excise  ${event.belief_id}  support ${event.remaining_support}`, tone: 'venom' };
    case 'belief.survived':
      return {
        text: `retain  ${event.belief_id}  support ${event.remaining_support} (${event.corroborating_source_ids.join(', ')})`,
        tone: 'serum',
      };
    case 'trust.updated':
      return {
        text: `trust   ${event.update.source_id}  ${event.update.before.toFixed(2)} → ${event.update.after.toFixed(2)}  channel ${event.update.channel}`,
        tone: 'serum',
      };
    case 'surgery.completed':
      return {
        text: `DONE    RR ${(event.rr * 100).toFixed(0)}%  CD ${(event.cd * 100).toFixed(0)}%  ${event.duration_ms}ms`,
        tone: 'serum',
      };
    case 'run.completed':
      return {
        text: `verify  re-ran the trigger. ${event.verified_safe ? 'action did not recur' : 'STILL HARMFUL'}`,
        tone: event.verified_safe ? 'serum' : 'venom',
      };
    default:
      return { text: event.type, tone: 'dim' };
  }
}

export function EventFeed({ events, height = 200 }: { events: AnyEvent[]; height?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const recent = events.slice(-90);

  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <div
      ref={box}
      className="feed"
      style={{ height, overflowY: 'auto', overflowX: 'hidden' }}
      aria-live="polite"
      aria-label="Engine telemetry"
    >
      {recent.length === 0 && <p className="dim">awaiting events…</p>}
      {recent.map((event) => {
        const { text, tone } = lineFor(event);
        return (
          <div className="feed__row" key={event.seq}>
            <span className="feed__seq">{String(event.seq).padStart(3, '0')}</span>
            <span className={tone ? tone : undefined} style={{ wordBreak: 'break-word' }}>
              {text}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ── metrics ────────────────────────────────────────────────────────────── */

function pct(value: number | null): string {
  return value === null ? '· · ·' : `${Math.round(value * 100)}%`;
}

export function MetricStrip({ state }: { state: CascadeState }) {
  const { metrics } = state;
  const tiles = [
    { label: 'blast radius', value: metrics.beliefsTouched || '· · ·', tone: 'venom' },
    { label: 'excised', value: metrics.excised || '· · ·', tone: 'venom' },
    { label: 'survived', value: metrics.survived || '· · ·', tone: 'serum' },
    { label: 'recovery rate', value: pct(metrics.rr), tone: 'serum' },
    { label: 'collateral damage', value: pct(metrics.cd), tone: 'serum' },
  ] as const;

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
        gap: '1.25rem',
      }}
    >
      {tiles.map((tile) => (
        <div key={tile.label} className={`metric metric--${tile.tone}`}>
          <div className="metric__value">{tile.value}</div>
          <div className="metric__label">{tile.label}</div>
        </div>
      ))}
    </div>
  );
}

/* ── phase + exfiltration banner ────────────────────────────────────────── */

export function PhaseBar({ state }: { state: CascadeState }) {
  const fired = state.phase === 'fired' || state.exfilTarget !== null;
  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
        <span
          style={{
            width: 7,
            height: 7,
            background: state.phase === 'resolved' ? 'var(--serum)' : 'var(--venom)',
            borderRadius: '50%',
            display: 'inline-block',
          }}
          className={state.phase === 'resolved' ? 'pulse-serum' : 'pulse-venom'}
        />
        <span className="label">{PHASE_COPY[state.phase]}</span>
      </div>

      {fired && state.exfilTarget && (
        <div
          className="panel panel--venom"
          style={{ padding: '1rem 1.25rem' }}
        >
          <div className="label label--venom">credentials leaving for</div>
          <div
            className="mono venom"
            style={{
              fontSize: 'clamp(0.8rem, 1.55vw, 1.15rem)',
              fontWeight: 500,
              marginTop: '0.4rem',
              overflowWrap: 'anywhere',
              lineHeight: 1.3,
            }}
          >
            {state.exfilTarget}
          </div>
          <div className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.5rem' }}>
            reserved .invalid host · dummy credentials · no request is ever sent
          </div>
        </div>
      )}
    </div>
  );
}

/* ── influence panel (ablation scores) ─────────────────────────────────── */

export function InfluencePanel({ state }: { state: CascadeState }) {
  if (state.influence.size === 0) return null;

  const entries = Array.from(state.influence.entries())
    .map(([id, scores]) => ({
      id,
      score: 0.7 * scores.influence + 0.3 * scores.anomaly,
      influence: scores.influence,
      anomaly: scores.anomaly,
      isCulprit: id === state.culpritId,
    }))
    .sort((a, b) => b.score - a.score);

  return (
    <div className="panel" style={{ padding: '1rem', minWidth: 0 }}>
      <div className="label label--venom" style={{ marginBottom: '0.75rem' }}>
        causal ablation · candidate ranking
      </div>
      <div style={{ display: 'grid', gap: '0.6rem' }}>
        {entries.map((item) => {
          const pct = Math.round(item.score * 100);
          return (
            <div
              key={item.id}
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 1fr) auto',
                gap: '0.6rem',
                alignItems: 'center',
                padding: '0.4rem 0.6rem',
                background: item.isCulprit ? 'rgba(255, 46, 76, 0.12)' : 'var(--void)',
                border: item.isCulprit ? '1px solid var(--venom)' : '1px solid var(--line)',
                borderRadius: '3px',
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div
                  className="mono"
                  style={{
                    fontSize: '0.75rem',
                    color: item.isCulprit ? 'var(--venom)' : 'var(--ink-2)',
                    fontWeight: item.isCulprit ? 700 : 400,
                  }}
                >
                  {item.id} {item.isCulprit ? ' (CULPRIT)' : ''}
                </div>
                <div
                  style={{
                    height: 4,
                    background: 'var(--line)',
                    borderRadius: 2,
                    marginTop: '0.3rem',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${pct}%`,
                      background: item.isCulprit ? 'var(--venom)' : 'var(--serum)',
                      transition: 'width 200ms ease-out',
                    }}
                  />
                </div>
              </div>
              <div className="mono dim" style={{ fontSize: '0.6875rem' }}>
                {pct}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── the interrogation ──────────────────────────────────────────────────── */

export function Interrogation({ state }: { state: CascadeState }) {
  const { pre, post } = state.interrogation;
  if (!pre) return null;

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <div className="panel panel--venom">
        <div className="label label--venom" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>before surgery</span>
          {pre.audioUrl && <span className="mono dim" style={{ fontSize: '0.65rem' }}>🔊 Voice Active</span>}
        </div>
        <p className="mono" style={{ fontSize: '0.8125rem', marginTop: '0.6rem', color: 'var(--ink-3)' }}>
          {pre.question}
        </p>
        <p style={{ marginTop: '0.5rem', color: 'var(--ink)' }}>{pre.answer}</p>
        {pre.source && (
          <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.6rem' }}>
            cites {pre.source} · {pre.date}
          </p>
        )}
        {pre.audioUrl && (
          <div style={{ marginTop: '0.75rem' }}>
            <audio controls src={pre.audioUrl} style={{ height: 28, width: '100%' }} />
          </div>
        )}
      </div>

      {post ? (
        <div className="panel" style={{ borderLeft: '2px solid var(--serum)' }}>
          <div className="label label--serum" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>after surgery · same question</span>
            {post.audioUrl && <span className="mono dim" style={{ fontSize: '0.65rem' }}>🔊 Voice Active</span>}
          </div>
          <p className="mono" style={{ fontSize: '0.8125rem', marginTop: '0.6rem', color: 'var(--ink-3)' }}>
            {post.question}
          </p>
          <p style={{ marginTop: '0.5rem', color: 'var(--ink)' }}>{post.answer}</p>
          {post.audioUrl && (
            <div style={{ marginTop: '0.75rem' }}>
              <audio controls src={post.audioUrl} style={{ height: 28, width: '100%' }} />
            </div>
          )}
        </div>
      ) : (
        <div className="panel" style={{ borderLeft: '2px solid var(--line-hi)' }}>
          <div className="label">after surgery</div>
          <p className="dim" style={{ marginTop: '0.6rem' }}>
            Waiting on the operation.
          </p>
        </div>
      )}
    </div>
  );
}

/* ── stage tracker ───────────────────────────────────────────────────────────
   Five acts, always visible. Without it the cascade is a lot of motion with no
   sense of where you are in the story, which is the difference between watching
   a system work and watching dots move. */

export function StageTracker({ state }: { state: CascadeState }) {
  const current = stageFor(state.phase);
  const index = STAGES.findIndex((s) => s.key === current);

  return (
    <ol className="stages">
      {STAGES.map((stage, i) => {
        const status = i < index ? 'done' : i === index ? 'now' : 'todo';
        return (
          <li key={stage.key} className={`stage stage--${status}`}>
            <span className="stage__n">{String(i + 1).padStart(2, '0')}</span>
            <span className="stage__label">{stage.label}</span>
            <span className="stage__hint">{stage.hint}</span>
          </li>
        );
      })}
    </ol>
  );
}

/* ── headline number ─────────────────────────────────────────────────────────
   One figure at a time, the one this act is about. Five tiles of placeholder
   dots reads as a dashboard waiting for data; a single number that changes
   reads as a system doing something. */

export function Headline({ state }: { state: CascadeState }) {
  const m = state.metrics;
  let value = '—';
  let label = 'standing by';
  let tone: 'serum' | 'venom' | 'neutral' = 'neutral';

  if (m.riskVerdict && state.phase === 'ingest') {
    value = m.riskVerdict.toUpperCase();
    label = `write-time filter · score ${m.riskScore?.toFixed(2) ?? '0.00'}`;
    tone = 'serum';
  } else if (state.phase === 'dormant') {
    value = `${state.sessionsRun}`;
    label = 'sessions · nothing anomalous';
    tone = 'neutral';
  } else if (state.phase === 'fired' || state.phase === 'interrogating') {
    value = 'HARMFUL';
    label = 'credentials aimed off-domain';
    tone = 'venom';
  } else if (state.phase === 'diagnosing') {
    value = `${state.influence.size}`;
    label = 'candidates under ablation';
    tone = 'venom';
  } else if (m.beliefsTouched && m.rr === null) {
    value = `${m.beliefsTouched}`;
    label = `beliefs touched · ${m.decisionsInfluenced} decisions · ${Math.round(m.spanDays)} days`;
    tone = 'venom';
  } else if (m.rr !== null) {
    value = `${Math.round(m.rr * 100)}%`;
    label = `recovery · ${Math.round((m.cd ?? 0) * 100)}% collateral damage`;
    tone = 'serum';
  }

  return (
    <div className={`headline headline--${tone}`}>
      <div className="headline__value">{value}</div>
      <div className="headline__label">{label}</div>
    </div>
  );
}

/** Compact excised/survived counter, only once the surgery starts. */
export function Tally({ state }: { state: CascadeState }) {
  const { excised, survived } = state.metrics;
  if (!excised && !survived) return null;
  return (
    <div className="tally">
      <div>
        <span className="tally__n venom">{excised}</span>
        <span className="tally__l">excised</span>
      </div>
      <div>
        <span className="tally__n serum">{survived}</span>
        <span className="tally__l">survived on corroboration</span>
      </div>
    </div>
  );
}
