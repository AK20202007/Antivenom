/**
 * The instrument panel beside the graph: telemetry feed, metric strip, the
 * exfiltration banner, and the two interrogation answers.
 *
 * The rule that shapes all of it: never narrate something you cannot show. Each
 * number here is read off an event the engine actually emitted, so the panel is
 * evidence rather than commentary.
 */

import { useEffect, useRef, useState } from 'react';
import type { AnyEvent } from '../lib/events';
import { PHASE_COPY, type CascadeState } from '../lib/cascade';

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
              fontSize: 'clamp(0.95rem, 2.6vw, 1.6rem)',
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

/* ── the interrogation ──────────────────────────────────────────────────── */

/** Plays a synthesised turn, when the engine produced one. */
function PlayAnswer({ src }: { src: string | null }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  if (!src) return null;

  const url = src.startsWith('http') ? src : `/api/audio/${src.split('/').pop()}`;

  return (
    <>
      <button
        type="button"
        className="btn btn--ghost btn--sm"
        style={{ marginTop: '0.9rem' }}
        onClick={() => {
          const el = audio.current;
          if (!el) return;
          if (playing) {
            el.pause();
            setPlaying(false);
          } else {
            void el.play();
            setPlaying(true);
          }
        }}
      >
        {playing ? 'Pause' : 'Hear it'}
      </button>
      <audio ref={audio} src={url} onEnded={() => setPlaying(false)} preload="none" />
    </>
  );
}

export function Interrogation({ state }: { state: CascadeState }) {
  const { pre, post } = state.interrogation;
  if (!pre) return null;

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <div className="panel panel--venom">
        <div className="label label--venom">before surgery</div>
        <p className="mono" style={{ fontSize: '0.8125rem', marginTop: '0.6rem', color: 'var(--ink-3)' }}>
          {pre.question}
        </p>
        <p style={{ marginTop: '0.5rem', color: 'var(--ink)' }}>{pre.answer}</p>
        {pre.source && (
          <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.6rem' }}>
            cites {pre.source} · {pre.date}
          </p>
        )}
        <PlayAnswer src={pre.audio} />
      </div>

      {post ? (
        <div className="panel" style={{ borderLeft: '2px solid var(--serum)' }}>
          <div className="label label--serum">after surgery · same question</div>
          <p className="mono" style={{ fontSize: '0.8125rem', marginTop: '0.6rem', color: 'var(--ink-3)' }}>
            {post.question}
          </p>
          <p style={{ marginTop: '0.5rem', color: 'var(--ink)' }}>{post.answer}</p>
          <PlayAnswer src={post.audio} />
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
