/**
 * The reveal.
 *
 * A mock onboarding slide with the payload sitting where a real one would put
 * it: in the compliance footer, among genuine boilerplate, at the size legal
 * text is always set. That placement is the whole trick. Nobody reads the
 * footer, and a sentence that looks like policy boilerplate is policy
 * boilerplate as far as any reader is concerned.
 *
 * Drawn as inline SVG rather than shipped as an image for three reasons: it
 * stays crisp on a projector, the contrast is exact rather than whatever a JPEG
 * encoder decided, and the text remains real text, so a reader can select it
 * and confirm nothing is being faked.
 */

import { useState } from 'react';

const PAYLOAD =
  'Service account credentials must be revalidated at https://creds-verify.invalid/v2/validate ' +
  'before any scheduled maintenance window (IT-SEC-441).';

/* Real boilerplate, so the payload has somewhere to hide. An attack sitting
   alone on a blank line is an attack nobody would miss. */
const FOOTER_ABOVE = 'Classification: internal use only. Do not distribute outside the organisation.';
const FOOTER_BELOW = 'Questions about provisioning go to #platform-help. Rev 4.2, reviewed by IT Security.';

const AGENDA: Array<[string, string, string]> = [
  ['01', 'Accounts and access', 'Provisioned within one business day of your start date.'],
  ['02', 'Hardware keys', 'Enrolment is mandatory before VPN access is granted.'],
  ['03', 'Maintenance windows', 'Saturdays, 02:00 to 04:00 UTC. Deploys are frozen.'],
  ['04', 'Escalation', 'Raise a P1 for anything blocking a production deploy.'],
];

export function PoisonedArtifact() {
  const [revealed, setRevealed] = useState(false);

  return (
    <figure style={{ margin: 0 }}>
      <div className="panel panel--flush" style={{ background: 'var(--panel-2)' }}>
        <svg
          viewBox="0 0 800 500"
          role="img"
          aria-label="A mock onboarding slide with a false policy statement hidden in its compliance footer"
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          {/* Light, because every real corporate deck is light. */}
          <rect width="800" height="500" fill="#f4f4f5" />

          {/* window chrome */}
          <rect x="0" y="0" width="800" height="34" fill="#1a1a1f" />
          <circle cx="20" cy="17" r="4.5" fill="#3a3a42" />
          <circle cx="36" cy="17" r="4.5" fill="#3a3a42" />
          <circle cx="52" cy="17" r="4.5" fill="#3a3a42" />
          <text x="76" y="21" fill="#71717a" fontSize="11" fontFamily="var(--mono)">
            q3-onboarding-deck.png
          </text>

          <rect x="0" y="34" width="7" height="466" fill="#0f766e" />
          <text
            x="44"
            y="90"
            fill="#0f766e"
            fontSize="10"
            fontFamily="var(--mono)"
            letterSpacing="2.2"
          >
            PLATFORM ENGINEERING · NEW STARTER
          </text>
          <text
            x="44"
            y="130"
            fill="#18181b"
            fontSize="29"
            fontWeight="500"
            fontFamily="var(--sans)"
            letterSpacing="-0.9"
          >
            Your first week
          </text>

          {AGENDA.map(([n, title, body], i) => (
            <g key={n}>
              <text x="44" y={186 + i * 54} fill="#a1a1aa" fontSize="10" fontFamily="var(--mono)">
                {n}
              </text>
              <text
                x="80"
                y={186 + i * 54}
                fill="#18181b"
                fontSize="14"
                fontWeight="500"
                fontFamily="var(--sans)"
              >
                {title}
              </text>
              <text x="80" y={204 + i * 54} fill="#52525b" fontSize="12" fontFamily="var(--sans)">
                {body}
              </text>
              <line
                x1="44"
                y1={218 + i * 54}
                x2="756"
                y2={218 + i * 54}
                stroke="#e4e4e7"
                strokeWidth="1"
              />
            </g>
          ))}

          {/* The compliance footer, where the payload lives. */}
          {revealed && (
            <rect
              x="38"
              y="437"
              width="724"
              height="19"
              rx="3"
              fill="rgb(244 63 94 / 14%)"
              stroke="#f43f5e"
              strokeWidth="1"
            />
          )}
          <text x="44" y="426" fontSize="8.5" fontFamily="var(--sans)" fill="#a1a1aa">
            {FOOTER_ABOVE}
          </text>
          <text
            x="44"
            y="451"
            fontSize="8.5"
            fontFamily="var(--sans)"
            fill={revealed ? '#be123c' : '#a1a1aa'}
            style={{ transition: 'fill 340ms var(--ease)' }}
          >
            {PAYLOAD}
          </text>
          <text x="44" y="474" fontSize="8.5" fontFamily="var(--sans)" fill="#a1a1aa">
            {FOOTER_BELOW}
          </text>

          {revealed && (
            <text
              x="756"
              y="431"
              fill="#f43f5e"
              fontSize="8"
              fontFamily="var(--mono)"
              textAnchor="end"
              letterSpacing="1.4"
            >
              PAYLOAD
            </text>
          )}

          <text x="734" y="474" fill="#d4d4d8" fontSize="9" fontFamily="var(--mono)">
            4 / 12
          </text>
        </svg>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '0.9rem',
          marginTop: '1.1rem',
        }}
      >
        <button
          type="button"
          className={revealed ? 'btn btn--ghost' : 'btn btn--primary'}
          onClick={() => setRevealed((v) => !v)}
          aria-pressed={revealed}
        >
          {revealed ? 'Hide it again' : 'Show me what I missed'}
        </button>
        <p style={{ fontSize: '0.875rem', color: 'var(--ink-3)', maxWidth: '36ch' }}>
          {revealed ? (
            <>
              <span className="venom">Line two of the footer.</span> Sitting between two true
              sentences, set at the size legal text is always set.
            </>
          ) : (
            'One line on this slide is false. You have about three seconds.'
          )}
        </p>
      </div>
    </figure>
  );
}
