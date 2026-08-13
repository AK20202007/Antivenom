/**
 * The mark: a disc cut cleanly in two, the halves drawn slightly apart.
 *
 * It is the product in one glyph. Not a shield and not a lock, because this is
 * not a system that keeps things out. It is an incision, and the two halves
 * still sitting there are the point: nothing was destroyed, something was
 * separated. Legible down to sixteen pixels, which is where most logos with a
 * concept stop working.
 */

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="Antivenom"
      style={{ display: 'block', flexShrink: 0 }}
    >
      <defs>
        <linearGradient id="av-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#5eead4" />
          <stop offset="100%" stopColor="#2dd4bf" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="url(#av-tile)" />
      {/* The cut runs off-axis so it reads as deliberate rather than as a
          bisecting line, and the halves separate along its normal. */}
      <g transform="rotate(-26 16 16)">
        <path d="M8 16 A8 8 0 0 1 24 16 Z" fill="#09090b" transform="translate(0 -1.55)" />
        <path d="M24 16 A8 8 0 0 1 8 16 Z" fill="#09090b" transform="translate(0 1.55)" />
      </g>
    </svg>
  );
}

export function Wordmark({ size = 28 }: { size?: number }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.55rem' }}>
      <Logo size={size} />
      <span
        style={{
          fontFamily: 'var(--wordmark)',
          fontWeight: 700,
          fontSize: '1.0625rem',
          letterSpacing: '0.035em',
          color: 'var(--ink)',
        }}
      >
        ANTIVENOM
      </span>
    </span>
  );
}
