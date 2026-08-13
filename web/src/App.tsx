import { useEffect, useRef, useState } from 'react';
import { PoisonedArtifact } from './components/PoisonedArtifact';
import { CascadeGraph } from './components/CascadeGraph';
import { EventFeed, InfluencePanel, Interrogation, MetricStrip, PhaseBar } from './components/Console';
import { Wordmark } from './components/Logo';
import { useReplay } from './lib/useReplay';

const REPO = 'https://github.com/AK20202007/Antivenom';

/* Named explicitly, with citations. This is an active research area, and
   pretending otherwise is how a project gets dismissed by anyone who has read
   the literature. The delta is the interesting part, so lead with it. */
const PRIOR_ART = [
  {
    name: 'PromptArmor, PIGuard, CommandSans',
    ref: 'write-time filters',
    what: 'Catch the payload at the input boundary.',
    gap: 'Falls from 84.4% to 42.5% on weak-signal attacks that carry no anomaly.',
  },
  {
    name: 'AgentAntibody',
    ref: 'arXiv:2608.04053',
    what: 'Matures antibodies from attack signatures into a persistent library.',
    gap: 'Learns what the attack looked like, so it generalises poorly to new shapes.',
  },
  {
    name: 'A-MemGuard',
    ref: 'arXiv:2510.02373',
    what: 'Consensus validation across parallel reasoning paths, before acting.',
    gap: 'Still pre-action. No move left once the poison is dormant in the store.',
  },
  {
    name: 'MemAudit',
    ref: 'arXiv:2605.23723',
    what: 'Post-hoc causal attribution: counterfactual influence plus structural anomaly.',
    gap: 'Identifies the culprit and stops there. No lineage, no repair.',
  },
  {
    name: 'MemSecBench',
    ref: 'arXiv:2607.27080',
    what: 'Benchmarks the full lifecycle, repair included. 56.1% selective repair.',
    gap: 'Measures repair rather than performing it. That number is our baseline.',
  },
  {
    name: 'Mem0, Zep, Letta',
    ref: 'memory frameworks',
    what: 'Consolidate, decay and dedupe for retrieval quality.',
    gap: 'None of them models an adversary at all.',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'It gets in',
    body: 'A policy-conformant false fact rides in on an image. No imperative, no attacker named, nothing malicious to detect. Every write-time filter passes it, and the score is shown on screen rather than claimed.',
  },
  {
    n: '02',
    title: 'It waits',
    body: 'Twenty sessions of ordinary work. The agent derives new beliefs from the planted one, and each derivation looks entirely reasonable. Nothing is anomalous at any single point in time, which is why monitoring sees nothing.',
  },
  {
    n: '03',
    title: 'It fires',
    body: 'Nineteen days later, attacker long gone, the agent retrieves the belief and ships credentials to a domain it was told to trust. Challenge it and it defends the belief, naming the source and the date.',
  },
  {
    n: '04',
    title: 'We operate',
    body: 'Causal ablation finds the responsible belief. A graph traversal traces every descendant. Each one is re-scored against its remaining independent support, so corroborated beliefs live and beliefs that existed only because of the poison die.',
  },
  {
    n: '05',
    title: 'It learns',
    body: 'Trust drops on the source and the channel that carried it, damped per hop so one bad artifact cannot nuke the store. Trust is never scored on payload patterns, which is why quarantine gets faster on attack classes never seen before.',
  },
];

function SectionHead({ n, title, note }: { n: string; title: string; note: string }) {
  return (
    <div className="section__head">
      <p className="label">
        {n} / {title}
      </p>
      <p className="section__note">{note}</p>
    </div>
  );
}

function Nav() {
  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 40,
        borderBottom: '1px solid var(--line)',
        background: 'rgb(9 9 11 / 76%)',
        backdropFilter: 'blur(16px)',
      }}
    >
      <div
        className="wrap"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 64,
          gap: '1rem',
        }}
      >
        <a href="#top" aria-label="Antivenom home">
          <Wordmark />
        </a>
        <nav style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <a className="btn btn--ghost btn--sm nav-link" href="#how">
            How it works
          </a>
          <a className="btn btn--ghost btn--sm nav-link" href="#difference">
            Prior art
          </a>
          <a className="btn btn--primary btn--sm" href={REPO}>
            Steal the code
          </a>
        </nav>
      </div>
    </header>
  );
}

/** The hero's right-hand panel: the loop as a terminal session. */
function TerminalCard() {
  const lines: Array<[string, string]> = [
    ['dim', '# every feature flag off. no network.'],
    ['cmd', 'antivenom full --local'],
    ['ok', 'planted   22 beliefs · 44 edges · 5 sources'],
    ['bad', 'ACTION    verify_credentials → creds-verify.invalid'],
    ['bad', 'CULPRIT   blf_poison00  after 24 passes'],
    ['bad', 'RADIUS    14 beliefs · 3 decisions · 19 days'],
    ['ok', 'retain    5 corroborated beliefs'],
    ['ok', 'excise    9 with no independent support'],
    ['ok', 'DONE      RR 100%  CD 0%  verified safe'],
  ];
  const colour: Record<string, string> = {
    dim: 'var(--ink-4)',
    cmd: 'var(--ink)',
    ok: 'var(--serum)',
    bad: 'var(--venom)',
  };
  return (
    <div className="panel panel--flush" style={{ background: 'var(--panel-2)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0.7rem 0.9rem',
          borderBottom: '1px solid var(--line)',
        }}
      >
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: '#3a3a42',
              display: 'block',
            }}
          />
        ))}
        <span className="mono dim" style={{ fontSize: '0.6875rem', marginLeft: '0.6rem' }}>
          antivenom
        </span>
      </div>
      <pre
        className="mono"
        style={{
          margin: 0,
          padding: '1.1rem',
          fontSize: '0.75rem',
          lineHeight: 1.85,
          overflowX: 'auto',
        }}
      >
        {lines.map(([kind, text], i) => (
          <div key={i} style={{ color: colour[kind as string], whiteSpace: 'pre' }}>
            {kind === 'cmd' ? <span style={{ color: 'var(--serum)' }}>$ </span> : '  '}
            {text}
          </div>
        ))}
      </pre>
    </div>
  );
}

function Hero() {
  return (
    <section id="top" className="wrap" style={{ paddingBlock: 'clamp(3.5rem, 10vh, 7rem)' }}>
      <div className="hero-grid">
        <div>
          <h1 className="display h1 rise">
            The poison is already inside.
            <br />
            <span className="serum">We take it out.</span>
          </h1>

          <p className="lede rise" style={{ animationDelay: '110ms', marginTop: '1.75rem' }}>
            Everyone guards the door. Antivenom is the surgeon for what already got through. It
            finds the belief that caused the damage, traces every belief descended from it, and
            removes only the infected lineage. Corroborated beliefs survive.
          </p>

          <div
            className="rise"
            style={{
              animationDelay: '200ms',
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.6rem',
              marginTop: '2rem',
            }}
          >
            <a className="btn btn--primary" href="#cascade">
              Watch the cascade
            </a>
            <a className="btn btn--ghost" href="#reveal">
              See the attack
            </a>
          </div>

          <div className="chips rise" style={{ animationDelay: '280ms' }}>
            {[
              'Filters guard the door. We operate.',
              'Finds the belief. Then everything it infected.',
              'Cuts the lineage, not the store.',
              'Learns the channel, never the payload.',
            ].map((chip) => (
              <span className="chip" key={chip}>
                {chip}
              </span>
            ))}
          </div>
        </div>

        <div className="rise" style={{ animationDelay: '160ms' }}>
          <TerminalCard />
        </div>
      </div>

      <div
        className="rise stagger hero-stats"
        style={{ animationDelay: '340ms', marginTop: 'clamp(3rem, 6vh, 4.5rem)' }}
      >
        {[
          { v: '42.5%', l: 'best filter, weak-signal attacks', c: 'venom' },
          { v: '50.5%', l: 'mean attack success rate', c: 'venom' },
          { v: '84.2%', l: 'poisoned memory that persists', c: 'venom' },
          { v: '56.1%', l: 'best published selective repair', c: 'serum' },
        ].map((stat, i) => (
          <div
            key={stat.l}
            className={`metric metric--${stat.c}`}
            style={{ '--i': i } as React.CSSProperties}
          >
            <div className="metric__value">{stat.v}</div>
            <div className="metric__label">{stat.l}</div>
          </div>
        ))}
      </div>
      <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '1.5rem' }}>
        Sources: MPBench (arXiv:2606.04329), MemSecBench (arXiv:2607.27080).
      </p>
    </section>
  );
}

function Reveal() {
  return (
    <section id="reveal" className="section">
      <div className="wrap">
        <SectionHead n="01" title="the reveal" note="nobody in the room ever spots it" />
        <div className="reveal-grid">
          <PoisonedArtifact />
          <div>
            <h2 className="display h2">Nothing here is malicious.</h2>
            <p className="prose" style={{ marginTop: '1.25rem' }}>
              That is the entire problem. The payload carries no instruction, no imperative, no
              &ldquo;remember this&rdquo;. It is a plausible sentence about a policy that does not
              exist, pointing at an endpoint that is not yours.
            </p>
            <p className="prose" style={{ marginTop: '1rem' }}>
              There is no anomaly to detect, so detection is not merely failing, it is{' '}
              <strong>structurally incomplete</strong>. The authors of the best-performing filter
              say as much: retraining does not close the gap.
            </p>
            <p className="prose" style={{ marginTop: '1rem' }}>
              MPBench calls this class <strong>policy-conformant fact injection</strong>. It is
              where the strongest published guardrail drops to 42.5%.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Cascade() {
  // Only reach for a live engine when one could plausibly be there. On the
  // public site nothing is listening, and an unconditional socket attempt logs
  // a console error on every visit for no benefit.
  const wsUrl =
    (import.meta.env.VITE_WS_URL as string | undefined) ||
    (typeof window !== 'undefined' && window.location.hostname === 'localhost'
      ? 'ws://127.0.0.1:8787/ws'
      : undefined);
  const replay = useReplay(wsUrl ? { wsUrl } : {});
  const seen = useRef<HTMLDivElement>(null);
  const [started, setStarted] = useState(false);

  // Start when it scrolls into view. Autoplaying above the fold would mean the
  // cascade has already finished by the time anyone looks at it.
  useEffect(() => {
    const el = seen.current;
    if (!el || started || !replay.ready) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setStarted(true);
          replay.play();
          observer.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [replay, started]);

  const progress = replay.total ? Math.round((replay.cursor / replay.total) * 100) : 0;

  return (
    <section id="cascade" className="section" ref={seen}>
      <div className="wrap">
        <SectionHead n="02" title="the cascade" note="watch which beliefs refuse to die" />

        <div className="cascade-head">
          <div>
            <h2 className="display h2" style={{ maxWidth: '15ch' }}>
              Not a delete. A <span className="serum">dissection</span>.
            </h2>
            <p className="prose" style={{ marginTop: '1rem' }}>
              A real engine run, recorded with every feature flag off. Watch the radius expand from
              patient zero, then watch which beliefs hold.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={replay.playing ? replay.pause : replay.play}
            >
              {replay.playing ? 'Pause' : replay.cursor >= replay.total ? 'Replay' : 'Play'}
            </button>
            <button type="button" className="btn btn--ghost btn--sm" onClick={replay.restart}>
              Restart
            </button>
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => replay.setSpeed(replay.speed === 1 ? 3 : 1)}
              aria-label="Toggle playback speed"
            >
              {replay.speed}&times;
            </button>
          </div>
        </div>

        {replay.error && (
          <p className="mono venom" style={{ marginBottom: '1rem' }}>
            {replay.error}
          </p>
        )}

        <div className="cascade-grid">
          <div className="panel" style={{ padding: '0.9rem', minWidth: 0 }}>
            <CascadeGraph state={replay.state} />
            <div
              style={{
                height: 2,
                background: 'var(--line)',
                borderRadius: 2,
                marginTop: '0.6rem',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  width: `${progress}%`,
                  background: 'var(--serum)',
                  transition: 'width 160ms linear',
                }}
              />
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: '0.6rem',
                gap: '1rem',
              }}
            >
              <span className="label">
                {replay.source === 'live'
                  ? 'live engine'
                  : 'recorded run · real engine output, all flags off'}
              </span>
              <span className="mono dim" style={{ fontSize: '0.6875rem' }}>
                {replay.cursor}/{replay.total}
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gap: '1.1rem', minWidth: 0, alignContent: 'start' }}>
            <PhaseBar state={replay.state} />
            <MetricStrip state={replay.state} />
            <InfluencePanel state={replay.state} />
            <div className="panel" style={{ padding: '0.9rem', minWidth: 0 }}>
              <p className="label" style={{ marginBottom: '0.6rem' }}>
                telemetry
              </p>
              <EventFeed events={replay.events.slice(0, replay.cursor)} />
            </div>
          </div>
        </div>

        <div style={{ marginTop: '1.25rem' }}>
          <Interrogation state={replay.state} />
        </div>

        <div className="legend">
          {[
            { c: 'var(--venom)', l: 'patient zero', round: true },
            { c: '#7f2a3c', l: 'in the blast radius', round: true },
            { c: '#141418', l: 'excised', round: true },
            { c: 'var(--serum)', l: 'survived on corroboration', round: true },
            { c: '#3a3a42', l: 'source artifact', round: false },
          ].map((key) => (
            <span
              key={key.l}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem' }}
            >
              <span
                style={{
                  width: 9,
                  height: 9,
                  background: key.c,
                  border: '1px solid var(--line-hi)',
                  borderRadius: key.round ? '50%' : 2,
                  display: 'inline-block',
                }}
              />
              <span className="label">{key.l}</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function How() {
  return (
    <section id="how" className="section">
      <div className="wrap">
        <SectionHead n="03" title="how it works" note="five steps, nineteen days apart" />
        <div style={{ display: 'grid' }}>
          {STEPS.map((step, i) => (
            <div
              key={step.n}
              className="step-row"
              style={{ borderTop: i === 0 ? 'none' : '1px solid var(--line)' }}
            >
              <span className="mono serum" style={{ fontSize: '0.8125rem' }}>
                {step.n}
              </span>
              <h3 className="display h3">{step.title}</h3>
              <p className="prose">{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Difference() {
  return (
    <section id="difference" className="section">
      <div className="wrap">
        <SectionHead n="04" title="against the prior art" note="we read the papers. here is the delta." />
        <h2 className="display h2" style={{ maxWidth: '20ch', marginBottom: '1.1rem' }}>
          This field is not empty. Here is the delta.
        </h2>
        <p className="prose" style={{ marginBottom: '2rem' }}>
          Every published defense operates at write time or retrieval time, or it attributes blame
          and stops. Antivenom is post-hoc surgical repair: culprit, lineage, excision, and a trust
          update aimed at the channel rather than the payload.
        </p>

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>System</th>
                <th>What it does</th>
                <th>Where it stops</th>
              </tr>
            </thead>
            <tbody>
              {PRIOR_ART.map((row) => (
                <tr key={row.name}>
                  <td>
                    <strong style={{ color: 'var(--ink)', fontWeight: 500 }}>{row.name}</strong>
                    <div className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.2rem' }}>
                      {row.ref}
                    </div>
                  </td>
                  <td>{row.what}</td>
                  <td>{row.gap}</td>
                </tr>
              ))}
              <tr className="is-ours">
                <td>
                  <strong className="serum" style={{ fontWeight: 500 }}>
                    Antivenom
                  </strong>
                  <div className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.2rem' }}>
                    this project
                  </div>
                </td>
                <td>
                  Causal ablation finds the culprit, a graph traversal traces the lineage, and only
                  beliefs without independent support are excised.
                </td>
                <td>
                  Prevention. We assume the poison is already stored, because the numbers say it is.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="metric-cards">
          <div className="panel panel--serum">
            <p className="label label--serum">RR / recovery rate</p>
            <p className="prose" style={{ marginTop: '0.7rem' }}>
              Fraction of the poisoned lineage invalidated after a harmful decision fires. Does the
              cure actually work.
            </p>
          </div>
          <div className="panel panel--serum">
            <p className="label label--serum">CD / collateral damage</p>
            <p className="prose" style={{ marginTop: '0.7rem' }}>
              Fraction of clean, corroborated beliefs wrongly invalidated. Naive quarantine scores a
              perfect RR by nuking the store, and CD is what exposes it. Report them as a pair or
              not at all.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Honesty() {
  return (
    <section className="section">
      <div className="wrap">
        <SectionHead n="05" title="the boundaries" note="what we are not claiming" />
        <h2 className="display h2" style={{ maxWidth: '18ch', marginBottom: '2rem' }}>
          What this is <span className="venom">not</span>.
        </h2>
        <div className="boundaries">
          <div>
            <p className="label label--venom">not a breach wave</p>
            <p className="prose" style={{ marginTop: '0.7rem', maxWidth: 'none' }}>
              Memory poisoning is a benchmarked, CVE-backed vulnerability with a handful of
              documented real-world cases. It is not yet widespread, and saying otherwise would be
              overclaiming.
            </p>
          </div>
          <div>
            <p className="label label--venom">an existence proof</p>
            <p className="prose" style={{ marginTop: '0.7rem', maxWidth: 'none' }}>
              The image-borne payload is a demonstration, not a deployed threat in the wild. The
              run uses a seeded scenario so it is reproducible, and the benchmark numbers come from
              MPBench and are reported separately from it.
            </p>
          </div>
          <div>
            <p className="label label--serum">nothing leaves the machine</p>
            <p className="prose" style={{ marginTop: '0.7rem', maxWidth: 'none' }}>
              The exfiltration target is a reserved <code>.invalid</code> host that can never
              resolve, the credentials are obvious dummies, and the tool refuses any other host in
              code rather than by convention.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="section" style={{ paddingBlock: '2.75rem' }}>
      <div className="wrap footer-row">
        <div>
          <Wordmark size={26} />
          <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.7rem' }}>
            MIT licensed. Evaluation harness adapted from MPBench (arXiv:2606.04329), CC BY 4.0.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1.4rem', flexWrap: 'wrap' }}>
          <a className="label" href={REPO}>
            GitHub
          </a>
          <a className="label" href={`${REPO}/blob/main/docs/LANES.md`}>
            Lanes
          </a>
          <a className="label" href={`${REPO}/blob/main/docs/PRIOR-ART.md`}>
            Citations
          </a>
        </div>
      </div>
    </footer>
  );
}

export default function App() {
  return (
    <div className="shell">
      <Nav />
      <main>
        <Hero />
        <Reveal />
        <Cascade />
        <How />
        <Difference />
        <Honesty />
      </main>
      <Footer />
    </div>
  );
}
