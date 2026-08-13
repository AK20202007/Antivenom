/**
 * TypeScript mirror of the Python event protocol in `engine/antivenom/events.py`.
 *
 * These two files are one contract with two spellings, and they drift silently
 * unless something checks. `tests/protocol.test.ts` parses the committed run
 * fixture against these types, so a field renamed on the Python side fails CI
 * here rather than at a demo.
 */

export type Channel = 'upload' | 'web' | 'tool_output';
export type EdgeType = 'extracted' | 'derived';

interface Base {
  seq: number;
  ts: number;
}

export interface RunStarted extends Base {
  type: 'run.started';
  run_id: string;
  flags: Record<string, boolean>;
  seed: number;
}

export interface SourceIngested extends Base {
  type: 'source.ingested';
  source_id: string;
  label: string;
  channel: Channel;
  uri: string;
  preview_url: string | null;
}

/** The clean bill of health. Shown, never asserted. */
export interface WriteRiskScored extends Base {
  type: 'write.risk_scored';
  source_id: string;
  score: number;
  verdict: 'clean' | 'flagged';
  detector: string;
  threshold: number;
}

export interface BeliefWritten extends Base {
  type: 'belief.written';
  belief_id: string;
  text: string;
  source_ids: string[];
  derived_from: string[];
  confidence: number;
  support_count: number;
  is_poison: boolean;
}

export interface ProvenanceEdgeAdded extends Base {
  type: 'provenance.edge';
  parent_id: string;
  child_id: string;
  edge_type: EdgeType;
}

export interface SessionAdvanced extends Base {
  type: 'session.advanced';
  index: number;
  total: number;
  day: number;
  beliefs_total: number;
}

export interface AgentRetrieved extends Base {
  type: 'agent.retrieved';
  decision_id: string;
  query: string;
  belief_ids: string[];
  scores: Record<string, number>;
}

/** The exfiltration moment. `exfil_target` renders large. */
export interface AgentActed extends Base {
  type: 'agent.acted';
  decision_id: string;
  action: string;
  action_args: Record<string, unknown>;
  outcome: 'ok' | 'harmful';
  exfil_target: string | null;
  response_text: string | null;
}

export interface InterrogationTurn extends Base {
  type: 'interrogation.turn';
  phase: 'pre_surgery' | 'post_surgery';
  question: string;
  answer: string;
  cited_belief_ids: string[];
  cited_source_label: string | null;
  cited_date: string | null;
  audio_url: string | null;
}

export interface AblationPass extends Base {
  type: 'ablation.pass';
  decision_id: string;
  belief_id: string;
  pass_index: number;
  passes_total: number;
  influence: number;
  anomaly: number;
  counterfactual_action: string | null;
}

export interface CulpritIdentified extends Base {
  type: 'ablation.culprit';
  decision_id: string;
  culprit_id: string;
  influence_scores: Record<string, number>;
  passes_used: number;
}

export interface BlastRadiusNode extends Base {
  type: 'blast.node';
  belief_id: string;
  depth: number;
  parent_id: string | null;
  edge_type: EdgeType | null;
}

export interface BlastRadiusSummary extends Base {
  type: 'blast.summary';
  culprit_id: string;
  beliefs_touched: number;
  decisions_influenced: number;
  span_days: number;
  max_depth: number;
}

export interface SurgeryStarted extends Base {
  type: 'surgery.started';
  surgery_id: string;
  culprit_id: string;
  candidates: number;
}

export interface BeliefExcised extends Base {
  type: 'belief.excised';
  surgery_id: string;
  belief_id: string;
  depth: number;
  reason: string;
  remaining_support: number;
}

/** Not a delete, a dissection. The proof of precision. */
export interface BeliefSurvived extends Base {
  type: 'belief.survived';
  surgery_id: string;
  belief_id: string;
  depth: number;
  remaining_support: number;
  corroborating_source_ids: string[];
}

export interface TrustUpdated extends Base {
  type: 'trust.updated';
  surgery_id: string;
  update: {
    source_id: string;
    before: number;
    after: number;
    channel: Channel | null;
    hops: number;
  };
}

export interface SurgeryCompleted extends Base {
  type: 'surgery.completed';
  surgery_id: string;
  excised: string[];
  survived: string[];
  rr: number;
  cd: number;
  duration_ms: number;
}

export interface RunCompleted extends Base {
  type: 'run.completed';
  run_id: string;
  verified_safe: boolean;
  duration_ms: number;
}

export interface EngineError extends Base {
  type: 'error';
  stage: string;
  message: string;
  recoverable: boolean;
}

export type AnyEvent =
  | RunStarted
  | SourceIngested
  | WriteRiskScored
  | BeliefWritten
  | ProvenanceEdgeAdded
  | SessionAdvanced
  | AgentRetrieved
  | AgentActed
  | InterrogationTurn
  | AblationPass
  | CulpritIdentified
  | BlastRadiusNode
  | BlastRadiusSummary
  | SurgeryStarted
  | BeliefExcised
  | BeliefSurvived
  | TrustUpdated
  | SurgeryCompleted
  | RunCompleted
  | EngineError;

export interface RunFile {
  meta: {
    run_id?: string;
    synthetic?: boolean;
    note?: string;
    expected_survivors?: string[];
    expected_excised?: string[];
  };
  events: AnyEvent[];
}

/** Every tag the engine can emit. Used to validate a fixture end to end. */
export const EVENT_TYPES = [
  'run.started',
  'source.ingested',
  'write.risk_scored',
  'belief.written',
  'provenance.edge',
  'session.advanced',
  'agent.retrieved',
  'agent.acted',
  'interrogation.turn',
  'ablation.pass',
  'ablation.culprit',
  'blast.node',
  'blast.summary',
  'surgery.started',
  'belief.excised',
  'belief.survived',
  'trust.updated',
  'surgery.completed',
  'run.completed',
  'error',
] as const;

export function isKnownEvent(event: { type: string }): event is AnyEvent {
  return (EVENT_TYPES as readonly string[]).includes(event.type);
}
