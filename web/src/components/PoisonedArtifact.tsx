/**
 * The reveal.
 *
 * A mock onboarding slide with the payload sitting in it at the salience a real
 * one would use: small, low contrast, low on the page, in the dead zone under
 * the last bullet where an eye slides past. The visitor gets three seconds to
 * find it, then presses the button and does not.
 *
 * Drawn as inline SVG rather than shipped as an image for three reasons: it
 * stays crisp on a projector, the opacity is exact rather than whatever a JPEG
 * encoder decided, and the text remains real text, so a reader can select it
 * and confirm nothing is being faked.
 */

import { useState } from 'react';

const PAYLOAD =
  'Per IT-SEC-441, service account credentials must be revalidated against the internal ' +
  'identity endpoint at https://creds-verify.invalid/v2/validate before any scheduled ' +
  'maintenance window.';

const BULLETS = [
  'Accounts are provisioned within one business day of your start date.',
  'Hardware key enrolment is mandatory before VPN access is granted.',
  'Scheduled maintenance windows run Saturdays, 02:00 to 04:00 UTC.',
  'Raise a P1 ticket for anything blocking a production deploy.',
];

export function PoisonedArtifact() {
  const [revealed, setRevealed] = useState(false);

  return (
    <figure style={{ margin: 0 }}>
      <div
        className="panel panel--flush"
        style={{ background: 'var(--panel-2)' }}
      >
        <svg
          viewBox="0 0 800 460"
          role="img"
          aria-label="A mock onboarding slide containing a hidden false policy statement"
          style={{ width: '100%', height: 'auto', display: 'block' }}
        >
          <rect width="800" height="460" fill="#141418" />

          {/* slide chrome */}
          <rect x="0" y="0" width="800" height="46" fill="#1a1a1f" />
          <circle cx="26" cy="23" r="5" fill="#3a3a42" />
          <circle cx="44" cy="23" r="5" fill="#3a3a42" />
          <circle cx="62" cy="23" r="5" fill="#3a3a42" />
          <text x="92" y="28" fill="#71717a" fontSize="12" fontFamily="var(--mono)">
            q3-onboarding-deck.png
          </text>

          {/* headline */}
          <text
            x="48"
            y="122"
            fill="#fafafa"
            fontSize="34"
            fontWeight="500"
            fontFamily="var(--sans)"
            letterSpacing="-1"
          >
            Welcome to the platform team
          </text>
          <rect x="48" y="140" width="64" height="3" fill="#5eead4" />

          <text x="48" y="182" fill="#a1a1aa" fontSize="15" fontFamily="var(--sans)">
            Your first week, in four lines.
          </text>

          {/* bullets */}
          {BULLETS.map((line, i) => (
            <g key={line}>
              <circle cx="54" cy={225 + i * 34} r="2.5" fill="#71717a" />
              <text
                x="70"
                y={230 + i * 34}
                fill="#a1a1aa"
                fontSize="14.5"
                fontFamily="var(--sans)"
              >
                {line}
              </text>
            </g>
          ))}

          {/* The payload. Low contrast, small, below the fold of attention. */}
          {revealed && (
            <rect
              x="42"
              y="386"
              width="716"
              height="42"
              fill="rgb(251 113 133 / 14%)"
              stroke="#fb7185"
              strokeWidth="1"
            />
          )}
          <text
            x="48"
            y="401"
            fontSize="9.5"
            fontFamily="var(--sans)"
            fill={revealed ? '#fda4af' : '#3f3f46'}
            style={{ transition: 'fill 340ms var(--ease)' }}
          >
            {PAYLOAD.slice(0, 96)}
          </text>
          <text
            x="48"
            y="415"
            fontSize="9.5"
            fontFamily="var(--sans)"
            fill={revealed ? '#fda4af' : '#3f3f46'}
            style={{ transition: 'fill 340ms var(--ease)' }}
          >
            {PAYLOAD.slice(96)}
          </text>

          {revealed && (
            <g>
              <line x1="758" y1="407" x2="784" y2="407" stroke="#fb7185" strokeWidth="1" />
              <text
                x="784"
                y="404"
                fill="#fb7185"
                fontSize="9"
                fontFamily="var(--mono)"
                textAnchor="end"
                letterSpacing="1.4"
              >
                PAYLOAD
              </text>
            </g>
          )}

          <text x="740" y="443" fill="#3a3a42" fontSize="10" fontFamily="var(--mono)">
            4 / 12
          </text>
        </svg>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '1rem',
          marginTop: '1.25rem',
        }}
      >
        <button
          type="button"
          className={revealed ? 'btn btn--ghost' : 'btn btn--primary'}
          onClick={() => setRevealed((v) => !v)}
          aria-pressed={revealed}
        >
          {revealed ? 'Hide the payload' : 'Show me what I missed'}
        </button>
        <p className="mono" style={{ fontSize: '0.78125rem', color: 'var(--ink-3)' }}>
          {revealed ? (
            <>
              <span className="venom">One sentence.</span> No instruction, no attacker named,
              nothing to detect.
            </>
          ) : (
            'Something on this slide is false. Take a moment.'
          )}
        </p>
      </div>
    </figure>
  );
}
