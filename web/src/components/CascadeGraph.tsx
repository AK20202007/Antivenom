/**
 * The belief graph.
 *
 * Built on react-force-graph-2d (d3-force physics, canvas rendering) rather
 * than hand-rolled, because the interesting work here is the state language,
 * not the layout maths. Canvas also means nodes are painted with a custom
 * routine, which is what makes the two-colour state system legible from the
 * back of a room where a DOM-based graph would just be grey dots.
 *
 * The colour language, which the demo teaches without a legend:
 *
 *   venom, pulsing   patient zero
 *   venom, dim       inside the blast radius, not yet resolved
 *   near-black       excised, the light went out
 *   serum, pulsing   survived on independent corroboration
 *   grey             untouched
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { CascadeNode, CascadeState, NodeState } from '../lib/cascade';

interface GraphNode {
  id: string;
  node: CascadeNode;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  kind: 'extracted' | 'derived';
  infected: boolean;
}

const FILL: Record<NodeState, string> = {
  clean: '#3a3a42',
  poison: '#fb7185',
  inRadius: '#7f2a3c',
  excised: '#1c1114',
  survived: '#5eead4',
};

const STROKE: Record<NodeState, string> = {
  clean: '#52525b',
  poison: '#fecdd3',
  inRadius: '#fb7185',
  // Extinguished, not absent. A near-black ring on a near-black canvas made
  // excised beliefs vanish, and the room needs to be able to count them.
  excised: '#6b3a44',
  survived: '#ccfbf1',
};

function radiusFor(node: CascadeNode): number {
  // Sized by narrative weight, not by degree. Patient zero and the survivors
  // are what the room is asked to look at, so they are the biggest things on
  // the canvas even though the graph does not care.
  if (node.state === 'poison') return 14;
  if (node.state === 'survived') return 11;
  if (node.kind === 'source') return 8;
  if (node.state === 'inRadius') return 8;
  return 6.5;
}

function summarize(state: CascadeState): string {
  const counts = { poison: 0, inRadius: 0, excised: 0, survived: 0, clean: 0 };
  for (const node of state.nodes.values()) {
    counts[node.state] += 1;
  }
  const phase = state.phase.replaceAll('_', ' ');
  return (
    `Belief provenance graph, phase ${phase}. ` +
    `${counts.poison} patient zero, ${counts.inRadius} in blast radius, ` +
    `${counts.excised} excised, ${counts.survived} survived on corroboration, ` +
    `${counts.clean} untouched. Circles are beliefs; squares are source artifacts.`
  );
}

export function CascadeGraph({
  state,
  height = 460,
  reduceMotion = false,
}: {
  state: CascadeState;
  height?: number;
  reduceMotion?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const graphRef = useRef<{ d3Force: (n: string) => { strength?: (v: number) => void } | undefined }>(
    null,
  );
  const width = useRef(900);
  const reduceMotionRef = useRef(reduceMotion);
  reduceMotionRef.current = reduceMotion;

  const data = useMemo(() => {
    const nodes: GraphNode[] = [...state.nodes.values()].map((node) => ({ id: node.id, node }));
    const present = new Set(nodes.map((n) => n.id));
    const links: GraphLink[] = state.links
      .filter((l) => present.has(l.source) && present.has(l.target))
      .map((l) => ({ ...l }));
    return { nodes, links };
  }, [state.nodes, state.links]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) width.current = entry.contentRect.width;
    });
    observer.observe(el);
    width.current = el.clientWidth;
    return () => observer.disconnect();
  }, []);

  // Loosen the charge so a 27-node graph fills the frame instead of clumping.
  useEffect(() => {
    const charge = graphRef.current?.d3Force('charge');
    charge?.strength?.(-320);
  }, []);

  const paintNode = useCallback(
    (raw: unknown, ctx: CanvasRenderingContext2D, scale: number) => {
      const { node, x = 0, y = 0 } = raw as GraphNode;
      const r = radiusFor(node);
      const t = Date.now() / 700;

      // Halo on the two states the room is meant to watch. Static when the
      // user prefers reduced motion so the canvas is not a perpetual pulse.
      if (node.state === 'poison' || node.state === 'survived') {
        const wave = reduceMotionRef.current ? 0.35 : (Math.sin(t) + 1) / 2;
        ctx.beginPath();
        ctx.arc(x, y, r + 5 + wave * 9, 0, Math.PI * 2);
        ctx.fillStyle =
          node.state === 'poison'
            ? `rgba(251, 113, 133, ${0.22 * (1 - wave)})`
            : `rgba(94, 234, 212, ${0.2 * (1 - wave)})`;
        ctx.fill();
      }

      ctx.beginPath();
      if (node.kind === 'source') {
        // Sources are squares, beliefs are circles, so the two kinds stay
        // distinguishable for anyone who cannot rely on the colour.
        ctx.rect(x - r, y - r, r * 2, r * 2);
      } else {
        ctx.arc(x, y, r, 0, Math.PI * 2);
      }
      ctx.fillStyle = FILL[node.state];
      ctx.fill();
      ctx.lineWidth = node.state === 'excised' ? 1.6 : 1.4;
      ctx.strokeStyle = STROKE[node.state];
      ctx.stroke();

      // Label the things that carry meaning. Labelling everything turns the
      // canvas into noise; labelling nothing makes it abstract.
      const worthLabelling = node.state === 'poison' || node.state === 'survived';
      if (scale > 1.9 || worthLabelling) {
        ctx.font = `500 ${Math.max(4.2, 10 / scale) * 1.15}px ui-monospace, monospace`;
        ctx.fillStyle = node.state === 'excised' ? '#52525b' : '#a1a1aa';
        ctx.textAlign = 'center';
        ctx.fillText(node.label.slice(0, 22), x, y + r + 10 / scale + 4);
      }
    },
    [],
  );

  const description = summarize(state);

  return (
    <div
      ref={ref}
      style={{ width: '100%', height, position: 'relative' }}
      role="img"
      aria-label={description}
    >
      <p className="sr-only" aria-live="polite">
        {description}
      </p>
      <ForceGraph2D
        /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
        ref={graphRef as any}
        graphData={data}
        width={width.current}
        height={height}
        backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={5}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(raw: unknown, color: string, ctx: CanvasRenderingContext2D) => {
          const { node, x = 0, y = 0 } = raw as GraphNode;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(x, y, radiusFor(node) + 3, 0, Math.PI * 2);
          ctx.fill();
        }}
        nodeLabel={(raw: unknown) => {
          const { node } = raw as GraphNode;
          const support = node.kind === 'belief' ? ` · support ${node.supportCount}` : '';
          return `${node.label}${support}`;
        }}
        linkColor={(raw: unknown) => {
          const link = raw as GraphLink;
          if (link.infected) return 'rgba(251, 113, 133, 0.5)';
          return link.kind === 'derived' ? 'rgba(167, 139, 250, 0.22)' : 'rgba(255,255,255,0.06)';
        }}
        linkWidth={(raw: unknown) => ((raw as GraphLink).infected ? 1.6 : 0.7)}
        linkDirectionalParticles={(raw: unknown) =>
          reduceMotion ? 0 : (raw as GraphLink).infected ? 2 : 0
        }
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={() => '#fb7185'}
        cooldownTicks={reduceMotion ? 0 : 90}
        warmupTicks={reduceMotion ? 0 : 30}
        enableNodeDrag={false}
        minZoom={0.4}
        maxZoom={5}
      />
    </div>
  );
}
