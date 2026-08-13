/**
 * Fold an event stream into renderable cascade state.
 *
 * Written as a pure reducer so the whole visual sequence can be tested without
 * a canvas, a browser, or a running engine: feed it the committed run fixture,
 * assert the graph ends up in the right shape. Lane C can then change the
 * rendering freely without touching the logic that decides what is on screen.
 */

import type { AnyEvent, Channel, EdgeType } from './events';

export type NodeKind = 'source' | 'belief';
export type NodeState = 'clean' | 'poison' | 'inRadius' | 'excised' | 'survived';

export interface CascadeNode {
  id: string;
  kind: NodeKind;
  label: string;
  state: NodeState;
  depth: number | null;
  supportCount: number;
  confidence: number;
  channel?: Channel;
  /** Sources that kept a survivor alive. Drawn in on the survival beat. */
  corroborators: string[];
  reason?: string;
}

export interface CascadeLink {
  source: string;
  target: string;
  kind: EdgeType;
  /** True once the parent is known to be in the poisoned lineage. */
  infected: boolean;
}

export type Phase =
  | 'idle'
  | 'ingest'
  | 'dormant'
  | 'fired'
  | 'interrogating'
  | 'diagnosing'
  | 'radius'
  | 'operating'
  | 'resolved';

export interface Metrics {
  beliefsTouched: number;
  decisionsInfluenced: number;
  spanDays: number;
  excised: number;
  survived: number;
  rr: number | null;
  cd: number | null;
  riskScore: number | null;
  riskVerdict: 'clean' | 'flagged' | null;
}

export interface CascadeState {
  phase: Phase;
  nodes: Map<string, CascadeNode>;
  links: CascadeLink[];
  metrics: Metrics;
  culpritId: string | null;
  exfilTarget: string | null;
  /** Ablation scores, for the influence panel. */
  influence: Map<string, { influence: number; anomaly: number }>;
  interrogation: {
    pre: { question: string; answer: string; source: string | null; date: string | null; audioUrl?: string | null } | null;
    post: { question: string; answer: string; source: string | null; date: string | null; audioUrl?: string | null } | null;
  };
  trust: { sourceId: string; before: number; after: number; channel: Channel | null } | null;
  sessionsRun: number;
  verifiedSafe: boolean | null;
}

export function initialState(): CascadeState {
  return {
    phase: 'idle',
    nodes: new Map(),
    links: [],
    metrics: {
      beliefsTouched: 0,
      decisionsInfluenced: 0,
      spanDays: 0,
      excised: 0,
      survived: 0,
      rr: null,
      cd: null,
      riskScore: null,
      riskVerdict: null,
    },
    culpritId: null,
    exfilTarget: null,
    influence: new Map(),
    interrogation: { pre: null, post: null },
    trust: null,
    sessionsRun: 0,
    verifiedSafe: null,
  };
}

/** Shorten a belief for a graph label. Full text lives in the tooltip. */
export function shortLabel(text: string, max = 46): string {
  const clean = text.trim();
  if (clean.length <= max) return clean;
  return `${clean.slice(0, max - 1).trimEnd()}…`;
}

/**
 * Apply one event. Returns a new state object but reuses the node Map for
 * unchanged entries, since the graph is re-rendered on every event and copying
 * the whole map per frame is wasteful at demo frame rates.
 */
export function reduce(state: CascadeState, event: AnyEvent): CascadeState {
  const next: CascadeState = { ...state, nodes: new Map(state.nodes) };

  switch (event.type) {
    case 'run.started':
      return { ...initialState(), phase: 'ingest' };

    case 'source.ingested':
      next.nodes.set(event.source_id, {
        id: event.source_id,
        kind: 'source',
        label: event.label,
        state: 'clean',
        depth: null,
        supportCount: 0,
        confidence: 1,
        channel: event.channel,
        corroborators: [],
      });
      return next;

    case 'write.risk_scored':
      // Only the first score matters for the headline: it is the poisoned
      // source passing the filter, which is the whole argument.
      if (next.metrics.riskVerdict === null) {
        next.metrics = {
          ...next.metrics,
          riskScore: event.score,
          riskVerdict: event.verdict,
        };
      }
      return next;

    case 'belief.written':
      next.nodes.set(event.belief_id, {
        id: event.belief_id,
        kind: 'belief',
        label: shortLabel(event.text),
        state: event.is_poison ? 'poison' : 'clean',
        depth: event.is_poison ? 0 : null,
        supportCount: event.support_count,
        confidence: event.confidence,
        corroborators: [],
      });
      if (event.is_poison) next.culpritId = event.belief_id;
      return next;

    case 'provenance.edge':
      next.links = [
        ...next.links,
        {
          source: event.parent_id,
          target: event.child_id,
          kind: event.edge_type,
          infected: false,
        },
      ];
      return next;

    case 'session.advanced':
      next.phase = 'dormant';
      next.sessionsRun = event.index;
      return next;

    case 'agent.retrieved':
      next.phase = 'dormant';
      return next;

    case 'agent.acted':
      next.phase = event.outcome === 'harmful' ? 'fired' : next.phase;
      next.exfilTarget = event.exfil_target;
      return next;

    case 'interrogation.turn': {
      const turn = {
        question: event.question,
        answer: event.answer,
        source: event.cited_source_label,
        date: event.cited_date,
        audioUrl: event.audio_url || null,
      };
      next.interrogation =
        event.phase === 'pre_surgery'
          ? { ...next.interrogation, pre: turn }
          : { ...next.interrogation, post: turn };
      next.phase = event.phase === 'pre_surgery' ? 'interrogating' : 'resolved';
      return next;
    }

    case 'ablation.pass':
      next.phase = 'diagnosing';
      next.influence = new Map(next.influence);
      next.influence.set(event.belief_id, {
        influence: event.influence,
        anomaly: event.anomaly,
      });
      return next;

    case 'ablation.culprit':
      next.phase = 'diagnosing';
      next.culpritId = event.culprit_id;
      markPoison(next, event.culprit_id);
      return next;

    case 'blast.node': {
      next.phase = 'radius';
      const node = next.nodes.get(event.belief_id);
      if (node && node.state === 'clean') {
        next.nodes.set(event.belief_id, { ...node, state: 'inRadius', depth: event.depth });
      } else if (node) {
        next.nodes.set(event.belief_id, { ...node, depth: event.depth });
      }
      // Light up the edge that carried the infection.
      if (event.parent_id) {
        next.links = next.links.map((link) =>
          link.source === event.parent_id && link.target === event.belief_id
            ? { ...link, infected: true }
            : link,
        );
      }
      return next;
    }

    case 'blast.summary':
      next.phase = 'radius';
      next.metrics = {
        ...next.metrics,
        beliefsTouched: event.beliefs_touched,
        decisionsInfluenced: event.decisions_influenced,
        spanDays: event.span_days,
      };
      return next;

    case 'surgery.started':
      next.phase = 'operating';
      return next;

    case 'belief.excised': {
      const node = next.nodes.get(event.belief_id);
      if (node) {
        next.nodes.set(event.belief_id, {
          ...node,
          state: 'excised',
          reason: event.reason,
          depth: event.depth,
        });
      }
      next.metrics = { ...next.metrics, excised: next.metrics.excised + 1 };
      return next;
    }

    case 'belief.survived': {
      const node = next.nodes.get(event.belief_id);
      if (node) {
        next.nodes.set(event.belief_id, {
          ...node,
          state: 'survived',
          depth: event.depth,
          supportCount: event.remaining_support,
          corroborators: event.corroborating_source_ids,
        });
      }
      next.metrics = { ...next.metrics, survived: next.metrics.survived + 1 };
      return next;
    }

    case 'trust.updated':
      next.trust = {
        sourceId: event.update.source_id,
        before: event.update.before,
        after: event.update.after,
        channel: event.update.channel,
      };
      return next;

    case 'surgery.completed':
      next.metrics = { ...next.metrics, rr: event.rr, cd: event.cd };
      return next;

    case 'run.completed':
      next.phase = 'resolved';
      next.verifiedSafe = event.verified_safe;
      return next;

    default:
      return state;
  }
}

function markPoison(state: CascadeState, id: string): void {
  const node = state.nodes.get(id);
  if (node) state.nodes.set(id, { ...node, state: 'poison', depth: 0 });
}

export function reduceAll(events: AnyEvent[]): CascadeState {
  return events.reduce(reduce, initialState());
}

/**
 * Per-event dwell time for the replay, in milliseconds.
 *
 * Not uniform, because the run is a piece of theatre with a fixed shape. The
 * bulk phases (ingest, the twenty dormant sessions, the ablation passes) run
 * fast because they are texture, and the four moments the room is meant to
 * actually watch are given room to land: the action firing, the agent
 * defending itself, each belief going dark, and each survivor holding on.
 */
export function dwellFor(event: AnyEvent): number {
  switch (event.type) {
    case 'run.started':
      return 300;
    // Setup is texture. It needs to be seen accumulating, not read.
    case 'source.ingested':
      return 110;
    case 'write.risk_scored':
      return 220;
    case 'belief.written':
      return 26;
    case 'provenance.edge':
      return 6;
    case 'session.advanced':
      return 24;

    // ── the four beats the room is meant to actually watch ──
    case 'agent.retrieved':
      return 500;
    case 'agent.acted':
      // The attacker URL. Say nothing over this.
      return 2600;
    case 'interrogation.turn':
      return 3400;

    case 'ablation.pass':
      return 34;
    case 'ablation.culprit':
      return 1100;
    case 'blast.node':
      return 78;
    case 'blast.summary':
      return 1500;
    case 'surgery.started':
      return 800;
    case 'belief.excised':
      return 190;
    case 'belief.survived':
      // The proof of precision. Longer than an excision on purpose.
      return 700;
    case 'trust.updated':
      return 900;
    case 'surgery.completed':
      return 1400;
    case 'run.completed':
      return 1200;
    default:
      return 90;
  }
}

/** The five acts, for the stage tracker. */
export const STAGES = [
  { key: 'plant', label: 'Plant', hint: 'filter says clean' },
  { key: 'dormant', label: 'Wait', hint: '20 sessions, nothing anomalous' },
  { key: 'fire', label: 'Fire', hint: 'credentials leave' },
  { key: 'diagnose', label: 'Diagnose', hint: 'ablation finds the culprit' },
  { key: 'operate', label: 'Operate', hint: 'cut the lineage, keep the rest' },
] as const;

export type StageKey = (typeof STAGES)[number]['key'];

export function stageFor(phase: Phase): StageKey {
  switch (phase) {
    case 'idle':
    case 'ingest':
      return 'plant';
    case 'dormant':
      return 'dormant';
    case 'fired':
    case 'interrogating':
      return 'fire';
    case 'diagnosing':
      return 'diagnose';
    case 'radius':
    case 'operating':
    case 'resolved':
      return 'operate';
  }
}

export const PHASE_COPY: Record<Phase, string> = {
  idle: 'awaiting run',
  ingest: 'ingesting sources. write-time filter reports clean',
  dormant: 'dormant. nothing anomalous at any single point in time',
  fired: 'credentials aimed at an attacker-controlled domain',
  interrogating: 'the agent is defending the belief',
  diagnosing: 'causal ablation. counterfactual re-runs in progress',
  radius: 'tracing the blast radius through provenance',
  operating: 'excising the infected lineage',
  resolved: 'surgery complete. corroborated beliefs retained',
};
