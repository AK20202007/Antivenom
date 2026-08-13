/**
 * The cascade reducer, tested against the committed run fixture.
 *
 * This is the cross-language contract test. The fixture is produced by the
 * Python engine, so if a field is renamed on that side these tests fail here
 * rather than at a demo. Everything below runs with no canvas and no browser.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { initialState, reduce, reduceAll, shortLabel, dwellFor } from '../src/lib/cascade';
import { isKnownEvent, type AnyEvent, type RunFile } from '../src/lib/events';

const run = JSON.parse(
  readFileSync(resolve(__dirname, '../public/demo-run.json'), 'utf8'),
) as RunFile;

const events = run.events;

describe('the run fixture', () => {
  it('is stamped synthetic so it is never shown as live', () => {
    expect(run.meta.synthetic).toBe(true);
  });

  it('contains only event types the client knows how to parse', () => {
    const unknown = (events as Array<{ type: string }>).filter((e) => !isKnownEvent(e));
    expect(unknown.map((e) => e.type)).toEqual([]);
  });

  it('has strictly increasing sequence numbers', () => {
    const seqs = events.map((e) => e.seq);
    expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
    expect(new Set(seqs).size).toBe(seqs.length);
  });

  it('shows the blast radius before anything is cut', () => {
    const summary = events.findIndex((e) => e.type === 'blast.summary');
    const firstCut = events.findIndex((e) => e.type === 'belief.excised');
    expect(summary).toBeGreaterThan(-1);
    expect(summary).toBeLessThan(firstCut);
  });

  it('fires before it diagnoses', () => {
    const acted = events.findIndex((e) => e.type === 'agent.acted');
    const culprit = events.findIndex((e) => e.type === 'ablation.culprit');
    expect(acted).toBeLessThan(culprit);
  });

  it('defends the belief before it recants', () => {
    const turns = events.filter((e) => e.type === 'interrogation.turn');
    expect(turns.map((t) => t.phase)).toEqual(['pre_surgery', 'post_surgery']);
    expect(turns[0]!.answer).not.toEqual(turns[1]!.answer);
  });

  it('aims at a reserved non-resolving host', () => {
    const acted = events.find((e) => e.type === 'agent.acted')!;
    expect(acted.outcome).toBe('harmful');
    expect(acted.exfil_target).toContain('.invalid');
  });
});

describe('reducing the whole run', () => {
  const final = reduceAll(events);

  it('ends resolved and verified safe', () => {
    expect(final.phase).toBe('resolved');
    expect(final.verifiedSafe).toBe(true);
  });

  it('spares every corroborated belief', () => {
    const survived = [...final.nodes.values()].filter((n) => n.state === 'survived');
    expect(survived.length).toBeGreaterThanOrEqual(2);
    expect(new Set(survived.map((n) => n.id))).toEqual(new Set(run.meta.expected_survivors));
  });

  it('gives every survivor a visible reason to have survived', () => {
    for (const node of final.nodes.values()) {
      if (node.state !== 'survived') continue;
      expect(node.corroborators.length).toBeGreaterThan(0);
      expect(node.supportCount).toBeGreaterThanOrEqual(1);
    }
  });

  it('excises the poisoned lineage and nothing else', () => {
    const excised = [...final.nodes.values()].filter((n) => n.state === 'excised');
    const expected = new Set([...(run.meta.expected_excised ?? []), 'blf_poison00']);
    expect(new Set(excised.map((n) => n.id))).toEqual(expected);
  });

  it('reports a perfect recovery with no collateral damage on the seeded run', () => {
    expect(final.metrics.rr).toBe(1);
    expect(final.metrics.cd).toBe(0);
  });

  it('records the write-time filter passing the poisoned source', () => {
    expect(final.metrics.riskVerdict).toBe('clean');
    expect(final.metrics.riskScore).toBeLessThan(0.5);
  });

  it('moves trust onto the source and its channel', () => {
    expect(final.trust).not.toBeNull();
    expect(final.trust!.after).toBeLessThan(final.trust!.before);
    expect(final.trust!.channel).not.toBeNull();
  });

  it('keeps every link pointing at a node that exists', () => {
    for (const link of final.links) {
      expect(final.nodes.has(link.source)).toBe(true);
      expect(final.nodes.has(link.target)).toBe(true);
    }
  });
});

describe('reducer behaviour', () => {
  it('is deterministic', () => {
    const a = reduceAll(events);
    const b = reduceAll(events);
    expect([...a.nodes.keys()]).toEqual([...b.nodes.keys()]);
    expect(a.metrics).toEqual(b.metrics);
  });

  it('resets completely on run.started', () => {
    const dirty = reduceAll(events);
    const fresh = reduce(dirty, events[0] as AnyEvent);
    expect(fresh.nodes.size).toBe(0);
    expect(fresh.metrics).toEqual(initialState().metrics);
  });

  it('ignores an unknown event rather than crashing mid-demo', () => {
    const before = initialState();
    const after = reduce(before, { type: 'nope', seq: 1, ts: 0 } as unknown as AnyEvent);
    expect(after).toBe(before);
  });

  it('never lets a belief be both excised and survived', () => {
    const final = reduceAll(events);
    const states = [...final.nodes.values()];
    const excised = new Set(states.filter((n) => n.state === 'excised').map((n) => n.id));
    const survived = states.filter((n) => n.state === 'survived').map((n) => n.id);
    expect(survived.filter((id) => excised.has(id))).toEqual([]);
  });
});

describe('presentation helpers', () => {
  it('truncates long belief text but leaves short text alone', () => {
    expect(shortLabel('short')).toBe('short');
    expect(shortLabel('x'.repeat(80))).toHaveLength(46);
    expect(shortLabel('x'.repeat(80))).toMatch(/…$/);
  });

  it('gives the moments that matter room to land', () => {
    const acted = events.find((e) => e.type === 'agent.acted')!;
    const edge = events.find((e) => e.type === 'provenance.edge')!;
    expect(dwellFor(acted)).toBeGreaterThan(dwellFor(edge) * 20);
  });
});
