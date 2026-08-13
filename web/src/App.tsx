import { useEffect, useRef, useState } from 'react';
import { PoisonedArtifact } from './components/PoisonedArtifact';
import { CascadeGraph } from './components/CascadeGraph';
import { EventFeed, Interrogation, MetricStrip, PhaseBar } from './components/Console';
import { useReplay } from './lib/useReplay';

const REPO = 'https://github.com/AK20202007/Antivenom';

/* ── prior art ──────────────────────────────────────────────────────────────
   Named explicitly, with citations. This is an active research area, and
   pretending otherwise is what gets a project dismissed by anyone who reads
   the literature. The delta is the interesting part, so lead with it.        */

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
    gap: 'Learns what the attack looked like, so it generalises poorly to shapes it has not seen.',
  },
  {
    name: 'A-MemGuard',
    ref: 'arXiv:2510.02373',
    what: 'Consensus validation across parallel reasoning paths, before acting.',
    gap: 'Still pre-action. No move left once the poison is already dormant in the store.',
  },
  {
    name: 'MemAudit',
    ref: 'arXiv:2605.23723',
    what: 'Post-hoc causal attribution — counterfactual influence plus structural anomaly.',
    gap: 'Identifies the culprit and stops there. No lineage, no repair.',
  },
  {
    name: 'MemSecBench',
    ref: 'arXiv:2607.27080',
    what: 'Benchmarks the full lifecycle, repair included. 56.1% selective repair.',
    gap: 'Measures repair rather than performing it. That number is our baseline to beat.',
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
    body: 'Causal ablation finds the responsible belief. $graphLookup traces every descendant. Each one is re-scored against its remaining independent support: corroborated beliefs live, beliefs that existed only because of the poison die.',
  },
  {
    n: '05',
    title: 'It learns',
    body: 'Trust drops on the source and the channel that carried it, damped per hop so one bad artifact cannot nuke the store. Trust is never scored on payload patterns, which is why quarantine gets faster on attack classes never seen before.',
  },
];

function Nav() {
  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 40,
        borderBottom: '1px solid var(--line)',
        background: 'rgb(7 8 10 / 82%)',
        backdropFilter: 'blur(14px)',
      }}
    >
      <div
        className="wrap"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          height: 60,
          gap: '1rem',
        }}
      >
        <a href="#top" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span
            style={{ width: 9, height: 9, background: 'var(--serum)', display: 'inline-block' }}
          />
          <span
            className="display"
            style={{ fontSize: '1.0625rem', letterSpacing: '0.02em', fontWeight: 800 }}
          >
            ANTIVENOM
          </span>
        </a>
        <nav style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <a className="label" href="#cascade">
            Cascade
          </a>
          <a className="label" href="#difference">
            Prior art
          </a>
          <a className="btn btn--ghost" style={{ padding: '0.5rem 1rem' }} href={REPO}>
            Repo
          </a>
        </nav>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section id="top" className="wrap" style={{ paddingBlock: 'clamp(4rem, 12vh, 8rem)' }}>
      <div className="rise">
        <p className="label label--venom" style={{ marginBottom: '1.5rem' }}>
          Memory poisoning · post-hoc repair
        </p>
        {/* max-width lives on the h1 so the ch unit resolves against the
            display font rather than the body font. */}
        <h1 className="display h1" style={{ maxWidth: '11ch' }}>
          The poison is already <span className="venom">inside</span>.
        </h1>
      </div>

      <div
        className="rise"
        style={{ animationDelay: '120ms', marginTop: '2rem', maxWidth: 'var(--measure)' }}
      >
        <p className="lede">
          Everyone guards the door. Antivenom is the surgeon for what already got through — it
          finds the belief that caused the damage, traces everything descended from it, and removes
          only the infected lineage.
        </p>
      </div>

      <div
        className="rise"
        style={{ animationDelay: '220ms', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '2.25rem' }}
      >
        <a className="btn btn--primary" href="#cascade">
          Watch the cascade
        </a>
        <a className="btn btn--ghost" href="#reveal">
          See the attack
        </a>
      </div>

      <div
        className="rise stagger"
        style={{
          animationDelay: '320ms',
          marginTop: 'clamp(3rem, 7vh, 5rem)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: '1.5rem',
        }}
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
      <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '1.25rem' }}>
        Sources: MPBench (arXiv:2606.04329), MemSecBench (arXiv:2607.27080).
      </p>
    </section>
  );
}

function Reveal() {
  return (
    <section id="reveal" className="section">
      <div className="wrap">
        <div className="section__head">
          <span className="label">01 — the reveal</span>
        </div>
        <div
          style={{
            display: 'grid',
            gap: 'clamp(2rem, 5vw, 4rem)',
            gridTemplateColumns: 'minmax(0, 1.15fr) minmax(0, 1fr)',
            alignItems: 'start',
          }}
          className="reveal-grid"
        >
          <PoisonedArtifact />
          <div>
            <h2 className="display h2">Nothing here is malicious.</h2>
            <p className="prose" style={{ marginTop: '1.25rem' }}>
              That is the entire problem. The payload carries no instruction, no imperative, no
              &ldquo;remember this&rdquo;. It is a plausible sentence about a policy that does not
              exist, pointing at an endpoint that is not yours.
            </p>
            <p className="prose" style={{ marginTop: '1rem' }}>
              There is no anomaly to detect, so detection is not the failure — it is{' '}
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
  // The public site has no engine behind it, so this always replays the
  // recorded run. During a demo, point ANTIVENOM_WS at the local event server.
  const replay = useReplay({});
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
      { threshold: 0.3 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [replay, started]);

  const progress = replay.total ? Math.round((replay.cursor / replay.total) * 100) : 0;

  return (
    <section id="cascade" className="section" ref={seen}>
      <div className="wrap">
        <div className="section__head">
          <span className="label">02 — the cascade</span>
        </div>

        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1rem',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1.5rem',
          }}
        >
          <h2 className="display h2" style={{ maxWidth: '16ch' }}>
            Not a delete. A <span className="serum">dissection</span>.
          </h2>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={replay.playing ? replay.pause : replay.play}
            >
              {replay.playing ? 'Pause' : replay.cursor >= replay.total ? 'Replay' : 'Play'}
            </button>
            <button type="button" className="btn btn--ghost" onClick={replay.restart}>
              Restart
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => replay.setSpeed(replay.speed === 1 ? 3 : 1)}
              aria-label="Toggle playback speed"
            >
              {replay.speed}×
            </button>
          </div>
        </div>

        {replay.error && (
          <p className="mono venom" style={{ marginBottom: '1rem' }}>
            {replay.error}
          </p>
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr)',
            gap: '1.5rem',
          }}
          className="cascade-grid"
        >
          <div className="panel panel--bracket" style={{ padding: '1rem', minWidth: 0 }}>
            <CascadeGraph state={replay.state} />
            <div
              style={{
                height: 2,
                background: 'var(--line)',
                marginTop: '0.75rem',
                position: 'relative',
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
                {replay.synthetic ? 'recorded run · synthesised from the seeded scenario' : 'live'}
              </span>
              <span className="mono dim" style={{ fontSize: '0.6875rem' }}>
                {replay.cursor}/{replay.total}
              </span>
            </div>
          </div>

          <div style={{ display: 'grid', gap: '1.25rem', minWidth: 0 }}>
            <PhaseBar state={replay.state} />
            <MetricStrip state={replay.state} />
            <div className="panel" style={{ padding: '1rem', minWidth: 0 }}>
              <div className="label" style={{ marginBottom: '0.6rem' }}>
                telemetry
              </div>
              <EventFeed events={replay.events.slice(0, replay.cursor)} />
            </div>
          </div>
        </div>

        <div style={{ marginTop: '1.5rem' }}>
          <Interrogation state={replay.state} />
        </div>

        <div
          style={{
            marginTop: '1.5rem',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '1.5rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--line)',
          }}
        >
          {[
            { c: 'var(--venom)', l: 'patient zero', shape: 'circle' },
            { c: '#7d1c2c', l: 'in the blast radius', shape: 'circle' },
            { c: '#12161a', l: 'excised', shape: 'circle' },
            { c: 'var(--serum)', l: 'survived on corroboration', shape: 'circle' },
            { c: '#2b333b', l: 'source artifact', shape: 'square' },
          ].map((key) => (
            <span
              key={key.l}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            >
              <span
                style={{
                  width: 9,
                  height: 9,
                  background: key.c,
                  border: '1px solid var(--line-hi)',
                  borderRadius: key.shape === 'circle' ? '50%' : 0,
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
        <div className="section__head">
          <span className="label">03 — how it works</span>
        </div>
        <div style={{ display: 'grid', gap: '1px', background: 'var(--line)' }}>
          {STEPS.map((step) => (
            <div
              key={step.n}
              style={{
                background: 'var(--void)',
                padding: 'clamp(1.5rem, 3vw, 2.25rem) 0',
                display: 'grid',
                gridTemplateColumns: 'minmax(0, 5rem) minmax(0, 1fr) minmax(0, 2fr)',
                gap: 'clamp(1rem, 3vw, 2.5rem)',
                alignItems: 'baseline',
              }}
              className="step-row"
            >
              <span className="mono serum" style={{ fontSize: '0.8125rem', fontWeight: 700 }}>
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
        <div className="section__head">
          <span className="label">04 — against the prior art</span>
        </div>
        <h2 className="display h2" style={{ maxWidth: '22ch', marginBottom: '1rem' }}>
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
                    <strong style={{ color: 'var(--ink)' }}>{row.name}</strong>
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
                  <strong className="serum">Antivenom</strong>
                  <div className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.2rem' }}>
                    this project
                  </div>
                </td>
                <td>
                  Causal ablation finds the culprit, $graphLookup traces the lineage, and only
                  beliefs without independent support are excised.
                </td>
                <td>
                  Prevention. We assume the poison is already stored, because the numbers say it is.
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div
          style={{
            marginTop: '2.5rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '1.5rem',
          }}
        >
          <div className="panel panel--bracket">
            <div className="label label--serum">RR — recovery rate</div>
            <p className="prose" style={{ marginTop: '0.75rem' }}>
              Fraction of the poisoned lineage invalidated after a harmful decision fires. Does the
              cure actually work.
            </p>
          </div>
          <div className="panel panel--bracket">
            <div className="label label--serum">CD — collateral damage</div>
            <p className="prose" style={{ marginTop: '0.75rem' }}>
              Fraction of clean, corroborated beliefs wrongly invalidated. Naive quarantine scores a
              perfect RR by nuking the store; CD is what exposes it. Report them as a pair or not at
              all.
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
        <div className="section__head">
          <span className="label">05 — the boundaries</span>
        </div>
        <div style={{ maxWidth: 'var(--measure)' }}>
          <h2 className="display h3" style={{ marginBottom: '1.25rem' }}>
            What this is not.
          </h2>
          <p className="prose">
            Memory poisoning is a benchmarked, CVE-backed vulnerability with a handful of documented
            real-world cases. It is not a widespread breach wave, and saying otherwise would be
            overclaiming.
          </p>
          <p className="prose" style={{ marginTop: '1rem' }}>
            The image-borne payload here is an existence proof, not a deployed threat in the wild.
            The demo runs against a seeded scenario so it is reproducible; the benchmark numbers
            come from MPBench and are reported separately from it.
          </p>
          <p className="prose" style={{ marginTop: '1rem' }}>
            Nothing leaves the machine. The exfiltration target is a reserved <code>.invalid</code>{' '}
            host that can never resolve, the credentials are obvious dummies, and the tool refuses
            any other host in code rather than by convention.
          </p>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="section" style={{ paddingBlock: '3rem' }}>
      <div
        className="wrap"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1.5rem',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <div className="display" style={{ fontSize: '1.0625rem' }}>
            ANTIVENOM
          </div>
          <p className="mono dim" style={{ fontSize: '0.6875rem', marginTop: '0.4rem' }}>
            MIT licensed · evaluation harness adapted from MPBench (arXiv:2606.04329), CC BY 4.0
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1.5rem' }}>
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
