/**
 * Helios client — WebSocket state + REST fallback for Reactor Overload / Sabacc.
 * Non-REACTOR stations are local mock demos (labeled).
 */
(function (global) {
  "use strict";

  const RESKIN = {
    FREEZE: "Containment Lock",
    FLIP_THREE: "Overcharge Pulse",
    SECOND_CHANCE: "Neutralizer Shield",
  };

  function wsUrl(role, seat) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    let q = "role=" + encodeURIComponent(role || "table");
    if (seat !== undefined && seat !== null && seat !== "") q += "&seat=" + encodeURIComponent(seat);
    return proto + "//" + location.host + "/ws?" + q;
  }

  function connect(opts) {
    const role = opts.role || "table";
    const seat = opts.seat;
    const onState = opts.onState || function () {};
    const onConn = opts.onConn || function () {};
    const onError = opts.onError || function () {};

    let ws = null;
    let closed = false;
    let retry = 0;
    let pollTimer = null;

    function startPoll() {
      if (pollTimer) return;
      pollTimer = setInterval(function () {
        fetch("/api/state")
          .then(function (r) { return r.json(); })
          .then(onState)
          .catch(function () {});
      }, 900);
    }

    function stopPoll() {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }

    function open() {
      if (closed) return;
      try {
        ws = new WebSocket(wsUrl(role, seat));
      } catch (e) {
        onConn(false);
        startPoll();
        return;
      }
      ws.onopen = function () {
        retry = 0;
        onConn(true);
        stopPoll();
      };
      ws.onclose = function () {
        onConn(false);
        startPoll();
        if (!closed) {
          const wait = Math.min(5000, 400 * Math.pow(1.5, retry++));
          setTimeout(open, wait);
        }
      };
      ws.onerror = function () {
        onConn(false);
      };
      ws.onmessage = function (ev) {
        let msg;
        try {
          msg = JSON.parse(ev.data);
        } catch (e) {
          return;
        }
        if (msg.type === "state" && msg.state) onState(msg.state);
        if (msg.type === "error") onError(msg.error || "error");
      };
    }

    function send(obj) {
      if (ws && ws.readyState === 1) {
        ws.send(JSON.stringify(obj));
        return true;
      }
      return false;
    }

    function post(path, body) {
      return fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      }).then(function (r) {
        return r.json().then(function (j) {
          if (!r.ok) throw new Error(j.error || r.statusText);
          onState(j);
          return j;
        });
      });
    }

    function hit(s) {
      const seatNum = s !== undefined ? s : seat;
      if (!send({ type: "hit", seat: seatNum })) {
        return post("/api/hit", { seat: seatNum });
      }
      return Promise.resolve();
    }

    function stay(s) {
      const seatNum = s !== undefined ? s : seat;
      if (!send({ type: "stay", seat: seatNum })) {
        return post("/api/stay", { seat: seatNum });
      }
      return Promise.resolve();
    }

    function newMatch(players, game) {
      const payload = { type: "new" };
      if (players) payload.players = players;
      if (game) payload.game = game;
      if (!send(payload)) {
        const body = players ? { players: players } : {};
        if (game) body.game = game;
        return post("/api/new", body);
      }
      return Promise.resolve();
    }

    function setGame(game, players) {
      const payload = { type: "set_game", game: game };
      if (players) payload.players = players;
      if (!send(payload)) {
        const body = { game: game };
        if (players) body.players = players;
        return post("/api/game", body);
      }
      return Promise.resolve();
    }

    open();
    fetch("/api/state").then(function (r) { return r.json(); }).then(onState).catch(function () {});

    return {
      hit: hit,
      stay: stay,
      newMatch: newMatch,
      setGame: setGame,
      close: function () {
        closed = true;
        stopPoll();
        if (ws) try { ws.close(); } catch (e) {}
      },
    };
  }

  function cardShort(label) {
    if (!label || label === "—") return "—";
    if (label === "Containment Lock" || label === "FREEZE") return "LOCK";
    if (label === "Overcharge Pulse" || label === "FLIP_THREE") return "PULSE";
    if (label === "Neutralizer Shield" || label === "SECOND_CHANCE") return "SHIELD";
    if (label === "Sylop" || label === "SYLOP") return "Ø";
    return String(label);
  }

  function isActionLabel(label) {
    return /Lock|Pulse|Shield|FREEZE|FLIP|SECOND|Sylop/i.test(String(label));
  }

  function isSabacc(state) {
    return state && (state.rules === "sabacc" || state.game === "sabacc");
  }

  function cardPolarity(label) {
    const s = String(label || "");
    if (s === "Sylop" || s === "SYLOP" || s === "Ø" || s === "0") return "sylop";
    if (/^\+\d/.test(s) || (s !== "" && !s.startsWith("-") && /^\d+$/.test(s) && Number(s) > 0))
      return "pos";
    if (/^-\d/.test(s)) return "neg";
    return "";
  }

  /** Station mock helpers (local only) */
  const Stations = {
    weatherTick: function (root) {
      const kp = (Math.random() * 7).toFixed(1);
      const solar = (Math.random() * 100).toFixed(0);
      const kpEl = root.querySelector("[data-kp]");
      const solEl = root.querySelector("[data-solar]");
      const bar = root.querySelector("[data-solar-bar]");
      if (kpEl) kpEl.textContent = kp;
      if (solEl) solEl.textContent = solar + "%";
      if (bar) bar.style.width = solar + "%";
      const blocks = root.querySelectorAll(".kp-blocks i");
      blocks.forEach(function (el, i) {
        el.style.height = 20 + ((Number(kp) * 10 + i * 7) % 70) + "%";
      });
    },
    bioTick: function (root) {
      root.querySelectorAll(".vial").forEach(function (v, i) {
        const alert = Math.random() < 0.12;
        v.classList.toggle("alert", alert);
        const st = v.querySelector(".st");
        if (st) st.textContent = alert ? "ANOMALY" : "STABLE";
      });
    },
  };

  global.Holo = {
    RESKIN: RESKIN,
    connect: connect,
    cardShort: cardShort,
    isActionLabel: isActionLabel,
    isSabacc: isSabacc,
    cardPolarity: cardPolarity,
    Stations: Stations,
  };
})(typeof window !== "undefined" ? window : globalThis);
