# Accessibility

Target: **WCAG 2.2 Level AA** for the marketing site in `web/`.

## What was tested

- Automated: axe-core (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440×900, 390×844, and 320×800 on the default page and reachable states (reveal toggle, cascade play/pause, integration tabs, full scroll).
- Manual: keyboard order and focus visibility, skip link, landmarks/headings, reduced-motion behaviour for cascade autoplay and graph pulse, form-less controls (playback, tabs), live regions for telemetry and phase, canvas graph text alternative.

## Known limitations

- The cascade belief graph is a canvas visualisation. Shape (circle vs square) and an off-screen live summary carry state; fine-grained per-node exploration for screen readers is not offered beyond that summary and the telemetry log.
- The prior-art table scrolls horizontally below ~640px width; the scroll region is keyboard-focusable.

## Reporting a barrier

Open an issue on [AK20202007/Antivenom](https://github.com/AK20202007/Antivenom) describing the page, assistive technology, and what blocked you.
