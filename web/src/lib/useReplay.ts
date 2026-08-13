/**
 * Replay a recorded run on a timeline, or stream a live one over WebSocket.
 *
 * The dashboard talks to a local event server during a real demo, and falls
 * back to the committed run fixture when there is no engine listening — which
 * is every visit to the public site, and also the honest fallback if the engine
 * dies on stage. Both paths produce the same state, because both consume the
 * same protocol.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import type { AnyEvent, RunFile } from './events';
import { dwellFor, initialState, reduce, type CascadeState } from './cascade';

export type Source = 'fixture' | 'live';

interface Replay {
  state: CascadeState;
  events: AnyEvent[];
  cursor: number;
  total: number;
  playing: boolean;
  source: Source;
  synthetic: boolean;
  ready: boolean;
  error: string | null;
  play: () => void;
  pause: () => void;
  restart: () => void;
  seek: (index: number) => void;
  speed: number;
  setSpeed: (n: number) => void;
}

const RUN_URL = '/demo-run.json';

export function useReplay(options: { autoplay?: boolean; wsUrl?: string } = {}): Replay {
  const { autoplay = false, wsUrl } = options;

  const [events, setEvents] = useState<AnyEvent[]>([]);
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<Source>('fixture');
  const [synthetic, setSynthetic] = useState(true);
  const [speed, setSpeed] = useState(1);

  const [state, dispatch] = useReducer(reduce, undefined, initialState);
  const timer = useRef<number | null>(null);

  // ── load the fixture ────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    fetch(RUN_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`run fixture unavailable (${res.status})`);
        return res.json() as Promise<RunFile>;
      })
      .then((run) => {
        if (cancelled) return;
        setEvents(run.events);
        setSynthetic(run.meta?.synthetic !== false);
        setReady(true);
        if (autoplay) setPlaying(true);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err.message);
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [autoplay]);

  // ── prefer a live engine when one is listening ──────────────────────────
  useEffect(() => {
    if (!wsUrl) return;
    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
    } catch {
      return; // No engine running. The fixture already covers this.
    }
    socket.onopen = () => {
      setSource('live');
      setSynthetic(false);
      setPlaying(false);
    };
    socket.onmessage = (message) => {
      try {
        dispatch(JSON.parse(message.data as string) as AnyEvent);
      } catch {
        // A malformed frame must not take down the cascade mid-demo.
      }
    };
    socket.onerror = () => setSource('fixture');
    return () => socket?.close();
  }, [wsUrl]);

  // ── drive the timeline ──────────────────────────────────────────────────
  useEffect(() => {
    if (!playing || source === 'live' || cursor >= events.length) {
      if (cursor >= events.length && playing) setPlaying(false);
      return;
    }
    const event = events[cursor];
    if (!event) return;

    dispatch(event);
    const delay = Math.max(8, dwellFor(event) / speed);
    timer.current = window.setTimeout(() => setCursor((c) => c + 1), delay);

    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [playing, cursor, events, speed, source]);

  const play = useCallback(() => {
    if (cursor >= events.length) {
      dispatch({ type: 'run.started', seq: 0, ts: 0, run_id: 'replay', flags: {}, seed: 0 });
      setCursor(0);
    }
    setPlaying(true);
  }, [cursor, events.length]);

  const pause = useCallback(() => setPlaying(false), []);

  const restart = useCallback(() => {
    setPlaying(false);
    setCursor(0);
    dispatch({ type: 'run.started', seq: 0, ts: 0, run_id: 'replay', flags: {}, seed: 0 });
    setPlaying(true);
  }, []);

  /** Jump to an index by replaying from the start — the reducer is cheap and
   *  this keeps seek exact rather than approximating intermediate state. */
  const seek = useCallback(
    (index: number) => {
      setPlaying(false);
      dispatch({ type: 'run.started', seq: 0, ts: 0, run_id: 'replay', flags: {}, seed: 0 });
      for (let i = 0; i < index && i < events.length; i += 1) {
        const event = events[i];
        if (event) dispatch(event);
      }
      setCursor(index);
    },
    [events],
  );

  return {
    state,
    events,
    cursor,
    total: events.length,
    playing,
    source,
    synthetic,
    ready,
    error,
    play,
    pause,
    restart,
    seek,
    speed,
    setSpeed,
  };
}
