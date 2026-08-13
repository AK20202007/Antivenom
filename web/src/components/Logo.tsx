/**
 * The mark: a ring cut clean through, the two halves drawn apart.
 *
 * It is the product in one glyph. Not a shield and not a lock, because this is
 * not a system that keeps things out. It is an incision, and the two halves
 * still sitting there are the whole point: nothing was destroyed, something was
 * separated.
 *
 * A ring rather than a solid disc, because an annulus reads as a specimen or a
 * cell rather than a dot, and it survives being shrunk to sixteen pixels, which
 * is where most logos with a concept stop working.
 *
 * The wordmark splits on the same idea. ANTI is the cure and VENOM is the
 * poison, so the name already carries both states of the system and only needs
 * the colour to say so. Nothing else on the page has to explain the palette
 * after that.
 */

import { useId } from 'react';

export function Logo({ size = 30, className }: { size?: number; className?: string }) {
  // Gradient ids must be unique per instance or a second copy on the page
  // silently inherits the first one's fill.
  const gid = useId().replace(/:/g, '');

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="Antivenom"
      className={className}
      style={{ display: 'block', flexShrink: 0, overflow: 'visible' }}
    >
      <defs>
        <linearGradient id={`t${gid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7df5e0" />
          <stop offset="55%" stopColor="#5eead4" />
          <stop offset="100%" stopColor="#22bfa8" />
        </linearGradient>
        {/* The incision. Masking rather than drawing a gap keeps the ring's
            stroke geometry intact, so the cut edges stay crisp at any size. */}
        <mask id={`m${gid}`}>
          <rect width="32" height="32" fill="#fff" />
          <rect
            x="-4"
            y="15.05"
            width="40"
            height="1.9"
            fill="#000"
            transform="rotate(-26 16 16)"
          />
        </mask>
      </defs>

      <rect width="32" height="32" rx="9.5" fill={`url(#t${gid})`} />

      <g transform="rotate(-26 16 16)" className="av-mark">
        {/* Upper half, nudged up along the cut's normal. */}
        <g className="av-half av-half--up">
          <circle
            cx="16"
            cy="16"
            r="7.4"
            fill="none"
            stroke="#09090b"
            strokeWidth="3.4"
            mask={`url(#m${gid})`}
            clipPath="inset(0 0 50% 0)"
          />
        </g>
        {/* Lower half, nudged down. */}
        <g className="av-half av-half--down">
          <circle
            cx="16"
            cy="16"
            r="7.4"
            fill="none"
            stroke="#09090b"
            strokeWidth="3.4"
            mask={`url(#m${gid})`}
            clipPath="inset(50% 0 0 0)"
          />
        </g>
      </g>
    </svg>
  );
}

export function Wordmark({ size = 30 }: { size?: number }) {
  return (
    <span className="wordmark">
      <Logo size={size} />
      <span className="wordmark__text">
        <span className="wordmark__anti">ANTI</span>
        <span className="wordmark__venom">VENOM</span>
      </span>
    </span>
  );
}
