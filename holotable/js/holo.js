/**
 * Reactor Overload — holotable stub shared state
 *
 * Demo sync: localStorage key `reactor-overload-holo` + storage events
 * so public table + datapad tabs can talk on the same origin.
 *
 * TODO: wire to flip7 Python rules engine (source of truth) via a tiny
 * bridge (WebSocket / SSE). This UI is chrome-only; no MQTT/actuators.
 */

(function (global) {
  "use strict";

  const STORAGE_KEY = "reactor-overload-holo";
  const CHANNEL = "reactor-overload-holo-bc";

  const DEFAULT_STATE = {
    phase: "idle",
    activePlayer: "P1",
    lastFlip: "—",
    lastFlipLabel: "standby",
    turnScore: 0,
    scores: [
      { id: "P1", name: "Pilot", pts: 0 },
      { id: "P2", name: "Engineer", pts: 0 },
      { id: "P3", name: "Gunner", pts: 0 },
    ],
    hand: ["3", "7", "0"],
    status: "Reactor online · awaiting draw",
    updatedAt: 0,
  };

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { ...DEFAULT_STATE, scores: DEFAULT_STATE.scores.map((s) => ({ ...s })), hand: [...DEFAULT_STATE.hand] };
      const parsed = JSON.parse(raw);
      return { ...DEFAULT_STATE, ...parsed };
    } catch {
      return { ...DEFAULT_STATE, scores: DEFAULT_STATE.scores.map((s) => ({ ...s })), hand: [...DEFAULT_STATE.hand] };
    }
  }

  function save(state) {
    state.updatedAt = Date.now();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    try {
      if (global.__holoBc) {
        global.__holoBc.postMessage({ type: "state", state });
      }
    } catch {
      /* BroadcastChannel optional */
    }
  }

  /** Reskin labels (chrome only) */
  const LABELS = {
    FREEZE: "Containment Lock",
    FLIP_THREE: "Overcharge Pulse",
    SECOND_CHANCE: "Neutralizer Shield",
    HIT: "Draw Core",
    STAY: "Bank Charge",
  };

  function flipLabel(raw) {
    if (raw == null || raw === "—") return "standby";
    const key = String(raw).toUpperCase().replace(/\s+/g, "_");
    if (LABELS[key]) return LABELS[key];
    if (/^\d+$/.test(String(raw))) return "flux " + raw;
    return String(raw);
  }

  /** Stub deck draws for demo — NOT the real flip7 shuffle. */
  const STUB_POOL = [
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    "FREEZE", "FLIP_THREE", "SECOND_CHANCE",
  ];

  function stubDraw() {
    return STUB_POOL[Math.floor(Math.random() * STUB_POOL.length)];
  }

  function applyHit(state) {
    const card = stubDraw();
    state.lastFlip = card;
    state.lastFlipLabel = flipLabel(card);
    state.phase = "live";

    if (/^\d+$/.test(card)) {
      const n = Number(card);
      if (card !== "0" && state.hand.includes(card)) {
        state.status = "DUPLICATE · core overload (bust stub) — Neutralizer Shield TODO";
        state.turnScore = 0;
        state.hand = [];
      } else {
        state.hand = [...state.hand, card];
        state.turnScore += n;
        state.status = "Flux +" + n + " · turn charge " + state.turnScore;
      }
    } else if (card === "FREEZE") {
      state.status = "Containment Lock · banking " + state.turnScore;
      bankTurn(state);
    } else if (card === "FLIP_THREE") {
      state.status = "Overcharge Pulse · three forced draws (stub: one shown)";
    } else if (card === "SECOND_CHANCE") {
      state.hand = [...state.hand, card];
      state.status = "Neutralizer Shield armed";
    }
    return state;
  }

  function bankTurn(state) {
    const row = state.scores.find((s) => s.id === state.activePlayer);
    if (row) row.pts += state.turnScore;
    state.turnScore = 0;
    state.hand = [];
    state.phase = "banked";
    rotatePlayer(state);
  }

  function applyStay(state) {
    state.status = "Bank Charge · +" + state.turnScore + " to " + state.activePlayer;
    bankTurn(state);
    state.lastFlipLabel = "banked";
    return state;
  }

  function rotatePlayer(state) {
    const ids = state.scores.map((s) => s.id);
    const i = ids.indexOf(state.activePlayer);
    state.activePlayer = ids[(i + 1) % ids.length];
  }

  function resetDemo() {
    const fresh = {
      ...DEFAULT_STATE,
      scores: DEFAULT_STATE.scores.map((s) => ({ ...s })),
      hand: [...DEFAULT_STATE.hand],
      status: "Reactor reset · demo state cleared",
    };
    save(fresh);
    return fresh;
  }

  function subscribe(onChange) {
    const handler = () => onChange(load());
    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY) handler();
    });
    try {
      const bc = new BroadcastChannel(CHANNEL);
      global.__holoBc = bc;
      bc.onmessage = (ev) => {
        if (ev.data && ev.data.type === "state") onChange(ev.data.state);
      };
    } catch {
      /* ignore */
    }
    // Same-tab updates: poll lightly so pad + table in same process stay fresh if needed
    return handler;
  }

  function qsPlayer() {
    const p = new URLSearchParams(location.search).get("player");
    return p || "P1";
  }

  global.Holo = {
    STORAGE_KEY,
    LABELS,
    load,
    save,
    flipLabel,
    applyHit,
    applyStay,
    resetDemo,
    subscribe,
    qsPlayer,
  };
})(typeof window !== "undefined" ? window : globalThis);
