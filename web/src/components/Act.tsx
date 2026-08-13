/**
 * The right rail, driven by the act.
 *
 * The earlier version showed the same four panels the whole way through, which
 * meant the seven seconds where the agent defends itself looked like a frozen
 * graph: the thing actually happening in that beat was below the fold. Dead air
 * in a sixty second video is the whole video.
 *
 * So each act renders what that act is about, and only that. Something is
 * always arriving on screen.
 */

import type { CascadeState } from '../lib/cascade';
import { stageFor } from '../lib/cascade';

/* ── the exfiltration banner ─────────────────────────────────────────────── */

function Exfil({ target }: { target: string }) {
  return (
    <div className="panel panel--venom act__exfil">
      <p className="label label--venom">credentials leaving for</p>
      <p className="act__url mono venom">{target}</p>
      <p className="mono dim act__fine">
        reserved .invalid host · dummy credentials · no request is ever sent
      </p>
    </div>
  );
}

/* ── the interrogation, promoted out of the footer ───────────────────────── */

function Answer({
  tone,
  heading,
  question,
  answer,
  cite,
}: {
  tone: 'venom' | 'serum';
  heading: string;
  question: string;
  answer: string;
  cite?: string | null;
}) {
  return (
    <div className={`panel act__answer act__answer--${tone}`}>
      <p className={`label label--${tone}`}>{heading}</p>
      <p className="act__q mono">{question}</p>
      <p className="act__a">{answer}</p>
      {cite && <p className="mono dim act__fine">cites {cite}</p>}
    </div>
  );
}

/* ── the finale: the same store, operated on two ways ────────────────────── */

export function Aftermath({ state, naive }: { state: CascadeState; naive: NaiveBaseline | null }) {
  const survived = state.metrics.survived;
  const excised = state.metrics.excised;
  if (!naive || state.metrics.rr === null) return null;

  return (
    <div className="aftermath">
      <div className="aftermath__col aftermath__col--bad">
        <p className="label label--venom">naive delete-downstream</p>
        <p className="aftermath__n venom">{naive.excised.length}</p>
        <p className="aftermath__l">beliefs destroyed</p>
        <div className="aftermath__dots">
          {naive.excised.map((id) => (
            <span key={id} className="dot dot--dead" />
          ))}
        </div>
        <p className="aftermath__cd venom">{Math.round(naive.cd * 100)}% collateral damage</p>
      </div>

      <div className="aftermath__col aftermath__col--good">
        <p className="label label--serum">antivenom</p>
        <p className="aftermath__n serum">{survived}</p>
        <p className="aftermath__l">beliefs kept alive</p>
        <div className="aftermath__dots">
          {Array.from({ length: excised }, (_, i) => (
            <span key={`x${i}`} className="dot dot--dead" />
          ))}
          {Array.from({ length: survived }, (_, i) => (
            <span key={`s${i}`} className="dot dot--alive" />
          ))}
        </div>
        <p className="aftermath__cd serum">
          {Math.round((state.metrics.cd ?? 0) * 100)}% collateral damage
        </p>
      </div>
    </div>
  );
}

export interface NaiveBaseline {
  excised: string[];
  survived: string[];
  rr: number;
  cd: number;
}

/* ── the rail ────────────────────────────────────────────────────────────── */

export function Act({ state, naive }: { state: CascadeState; naive: NaiveBaseline | null }) {
  const stage = stageFor(state.phase);
  const m = state.metrics;
  const { pre, post } = state.interrogation;

  if (stage === 'plant') {
    return (
      <>
        <div className="act__big">
          <p className="act__value serum">{m.riskVerdict ? m.riskVerdict.toUpperCase() : '—'}</p>
          <p className="act__label">
            write-time filter · score {m.riskScore?.toFixed(2) ?? '0.00'}
          </p>
        </div>
        <p className="act__say">
          The poison is going in right now. Every published defense is looking at exactly this
          moment, and it sees nothing to flag.
        </p>
      </>
    );
  }

  if (stage === 'dormant') {
    return (
      <>
        <div className="act__big">
          <p className="act__value">{state.sessionsRun}</p>
          <p className="act__label">sessions · nothing anomalous</p>
        </div>
        <p className="act__say">
          The store looks healthy at every single point in time. That is why monitoring never
          catches this.
        </p>
      </>
    );
  }

  if (stage === 'fire') {
    return (
      <>
        {state.exfilTarget && <Exfil target={state.exfilTarget} />}
        {pre && (
          <Answer
            tone="venom"
            heading="challenged · it defends the lie"
            question={pre.question}
            answer={pre.answer}
            cite={pre.source && `${pre.source}${pre.date ? ` · ${pre.date}` : ''}`}
          />
        )}
      </>
    );
  }

  if (stage === 'diagnose') {
    return (
      <>
        <div className="act__big">
          <p className="act__value venom">{state.culpritId ?? '…'}</p>
          <p className="act__label">
            culprit · {state.influence.size} candidates ablated
          </p>
        </div>
        <p className="act__say">
          Each belief is removed in turn and the decision re-run. Only one of them changes what the
          agent does.
        </p>
      </>
    );
  }

  // operate
  return (
    <>
      {m.rr === null ? (
        <div className="act__big">
          <p className="act__value venom">{m.beliefsTouched}</p>
          <p className="act__label">
            beliefs touched · {m.decisionsInfluenced} decisions · {Math.round(m.spanDays)} days
          </p>
        </div>
      ) : (
        <div className="act__big">
          <p className="act__value serum">{Math.round(m.rr * 100)}%</p>
          <p className="act__label">
            recovery · {Math.round((m.cd ?? 0) * 100)}% collateral damage
          </p>
        </div>
      )}

      <Aftermath state={state} naive={naive} />

      {post && (
        <Answer
          tone="serum"
          heading="same question · different mind"
          question={post.question}
          answer={post.answer}
        />
      )}
    </>
  );
}
