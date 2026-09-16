"""Helios holotable server — static UI + REST + WebSocket broadcast.

Software only (no actuators / MQTT). Serves the five-station Helios shell;
REACTOR station runs Flip 7 / Reactor Overload or Sabacc via a game picker.
Computer opponents auto-act server-side (no datapad required).
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .bots import BOT_NAMES, build_roster, decide_from_snapshot
from .live import DEFAULT_CREW, LiveMatch
from .sabacc_live import SabaccLiveMatch
from . import wsutil

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "holotable"

MatchType = Union[LiveMatch, SabaccLiveMatch]

_state_lock = threading.Lock()
_game_id = "flip7"
_computers = 0
_match: MatchType = LiveMatch(DEFAULT_CREW[:2])
_clients: Set["WsClient"] = set()
_clients_lock = threading.Lock()
_bot_timer: Optional[threading.Timer] = None
_bot_timer_lock = threading.Lock()
_bot_delay_sec = float(os.environ.get("HELIOS_BOT_DELAY", "0.75"))  # default; overridden at schedule


def get_match() -> MatchType:
    with _state_lock:
        return _match


def get_game_id() -> str:
    with _state_lock:
        return _game_id


def get_computers() -> int:
    with _state_lock:
        return _computers


def set_match(m: MatchType, game_id: Optional[str] = None, computers: Optional[int] = None) -> None:
    global _match, _game_id, _computers
    with _state_lock:
        _match = m
        if game_id is not None:
            _game_id = game_id
        elif isinstance(m, SabaccLiveMatch):
            _game_id = "sabacc"
        else:
            _game_id = "flip7"
        if computers is not None:
            _computers = int(computers)
        else:
            _computers = len(getattr(m, "bot_seats", ()) or ())
    m.on_update(_on_match_update)
    _on_match_update(m.snapshot())


def _parse_computers(body: dict, default: Optional[int] = None) -> Optional[int]:
    if "computers" in body:
        return int(body["computers"])
    if "bots" in body:
        return int(body["bots"])
    if "computer_opponents" in body:
        return int(body["computer_opponents"])
    return default


def _human_names_from_body(body: dict) -> Optional[List[str]]:
    names = body.get("players") or body.get("names") or body.get("human_names")
    if names is None:
        return None
    if isinstance(names, str):
        return [names]
    return list(names)


def _roster_for(
    game: str,
    computers: int,
    human_names: Optional[List[str]] = None,
) -> tuple:
    return build_roster(computers=computers, human_names=human_names, game=game)


def switch_game(
    game: str,
    player_names: Optional[List[str]] = None,
    seed: Optional[int] = None,
    computers: Optional[int] = None,
) -> dict:
    """Start a new match of flip7 or sabacc on the REACTOR table."""
    g = (game or "").strip().lower()
    if g in ("flip7", "reactor", "reactor_overload", "flip"):
        g = "flip7"
    elif g in ("sabacc", "spike", "corellian"):
        g = "sabacc"
    else:
        raise ValueError("Unknown game — use flip7 or sabacc")

    n_comp = get_computers() if computers is None else max(0, min(3, int(computers)))

    import random

    rng = random.Random(seed) if seed is not None else random.Random()

    # Explicit players list without a computers key → all-human (API compat).
    # When computers is set/preserved, rebuild Pilot + bot roster.
    if player_names is not None and computers is None:
        names = list(player_names)
        bot_seats: Set[int] = set()
        if g == "sabacc":
            if len(names) > 4:
                names = names[:4]
            if len(names) < 2:
                names = DEFAULT_CREW[:2]
            m: MatchType = SabaccLiveMatch(names, rng=rng, bot_seats=bot_seats)
        else:
            if not (2 <= len(names) <= 6):
                names = DEFAULT_CREW[: max(2, min(4, len(names) or 2))]
            m = LiveMatch(names, rng=rng, bot_seats=bot_seats)
        set_match(m, game_id=g, computers=0)
        return m.snapshot()

    humans = player_names
    if humans is not None:
        bot_set = set(BOT_NAMES)
        filtered = [n for n in humans if n not in bot_set]
        humans = filtered or ["Pilot"]

    names, bot_seats = _roster_for(g, n_comp, humans)
    if g == "sabacc":
        m = SabaccLiveMatch(names, rng=rng, bot_seats=bot_seats)
    else:
        m = LiveMatch(names, rng=rng, bot_seats=bot_seats)
    set_match(m, game_id=g, computers=n_comp)
    return m.snapshot()


def apply_computers(
    computers: int,
    human_names: Optional[List[str]] = None,
    seed: Optional[int] = None,
    game: Optional[str] = None,
) -> dict:
    """Rebuild current (or specified) game with N computer opponents."""
    g = game or get_game_id()
    n = max(0, min(3, int(computers)))
    return switch_game(g, player_names=human_names, seed=seed, computers=n)


def new_match_with_options(
    match: MatchType,
    names: Optional[List[str]],
    seed: Optional[int],
    computers: Optional[int],
) -> dict:
    if computers is not None:
        return apply_computers(computers, human_names=names, seed=seed)
    if names is not None:
        # Preserve existing bot seats if names length matches and bots present
        bot_seats = set(getattr(match, "bot_seats", ()) or ())
        snap = match.new_match(player_names=names, seed=seed, bot_seats=bot_seats)
        return snap
    return match.new_match(seed=seed)


class WsClient:
    def __init__(self, sock, role: str, seat: Optional[int]):
        self.sock = sock
        self.role = role
        self.seat = seat
        self.lock = threading.Lock()

    def send_json(self, obj: dict) -> None:
        data = wsutil.encode_text(json.dumps(obj, default=str))
        with self.lock:
            self.sock.sendall(data)


def broadcast(state: dict) -> None:
    dead: List[WsClient] = []
    with _clients_lock:
        clients = list(_clients)
    for c in clients:
        try:
            c.send_json({"type": "state", "state": state})
        except Exception:
            dead.append(c)
    if dead:
        with _clients_lock:
            for c in dead:
                _clients.discard(c)


def _cancel_bot_timer() -> None:
    global _bot_timer
    with _bot_timer_lock:
        if _bot_timer is not None:
            try:
                _bot_timer.cancel()
            except Exception:
                pass
            _bot_timer = None


def _run_bot_turn(expected_match_id: int, expected_seat: int) -> None:
    match = get_match()
    try:
        state = match.snapshot()
    except Exception:
        return
    if state.get("match_id") != expected_match_id:
        return
    if state.get("phase") != "choosing" or not state.get("can_act"):
        return
    if state.get("active_seat") != expected_seat:
        return
    decision = decide_from_snapshot(state)
    if decision is None:
        return
    try:
        if decision == "hit":
            match.hit(expected_seat)
        else:
            match.stay(expected_seat)
    except (RuntimeError, ValueError, TypeError):
        pass


def _schedule_bot_if_needed(state: dict) -> None:
    _cancel_bot_timer()
    if not state or state.get("phase") != "choosing" or not state.get("can_act"):
        return
    if state.get("winner"):
        return
    seat = state.get("active_seat")
    players = state.get("players") or []
    if seat is None or seat < 0 or seat >= len(players):
        return
    if not players[seat].get("is_bot"):
        return
    mid = state.get("match_id")
    try:
        delay = float(os.environ.get("HELIOS_BOT_DELAY", str(_bot_delay_sec)))
    except ValueError:
        delay = _bot_delay_sec
    timer = threading.Timer(delay, _run_bot_turn, args=(mid, seat))
    timer.daemon = True
    with _bot_timer_lock:
        global _bot_timer
        _bot_timer = timer
        timer.start()


def _on_match_update(state: dict) -> None:
    broadcast(state)
    _schedule_bot_if_needed(state)


_match.on_update(_on_match_update)


def json_bytes(obj: Any, code: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(obj, default=str).encode("utf-8")
    return code, body, "application/json; charset=utf-8"


class HeliosHandler(BaseHTTPRequestHandler):
    server_version = "HeliosFlip7/0.4"

    def log_message(self, fmt: str, *args) -> None:
        if os.environ.get("HELIOS_VERBOSE"):
            super().log_message(fmt, *args)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/ws":
            self._websocket(qs)
            return
        if path in ("/api/state", "/api/reactor/state"):
            self._send(*json_bytes(get_match().snapshot()))
            return
        if path == "/api/health":
            self._send(
                *json_bytes(
                    {
                        "ok": True,
                        "shell": "HELIOS",
                        "outpost": "Ohio Outpost // Sol-3",
                        "reactor": "Reactor Overload",
                        "games": ["flip7", "sabacc"],
                        "active_game": get_game_id(),
                        "computers": get_computers(),
                        "bot_names": list(BOT_NAMES[:3]),
                    }
                )
            )
            return
        if path == "/api/games":
            self._send(
                *json_bytes(
                    {
                        "games": [
                            {"id": "flip7", "title": "Reactor Overload (Flip 7)"},
                            {"id": "sabacc", "title": "Sabacc (Spike house rules)"},
                        ],
                        "active": get_game_id(),
                        "computers": get_computers(),
                    }
                )
            )
            return

        self._static(path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(*json_bytes({"error": "invalid JSON"}, 400))
            return

        match = get_match()
        try:
            if path in ("/api/computers", "/api/reactor/computers", "/api/bots"):
                n = _parse_computers(body)
                if n is None:
                    raise ValueError("Need computers (0–3)")
                humans = _human_names_from_body(body)
                snap = apply_computers(n, human_names=humans, seed=body.get("seed"), game=body.get("game"))
                self._send(*json_bytes(snap))
                return
            if path in ("/api/game", "/api/reactor/game"):
                names = _human_names_from_body(body)
                seed = body.get("seed")
                game = body.get("game") or body.get("rules") or body.get("id")
                computers = _parse_computers(body)
                snap = switch_game(str(game), player_names=names, seed=seed, computers=computers)
                self._send(*json_bytes(snap))
                return
            if path in ("/api/new", "/api/reactor/new"):
                names = _human_names_from_body(body)
                seed = body.get("seed")
                computers = _parse_computers(body)
                if body.get("game") or body.get("rules"):
                    snap = switch_game(
                        str(body.get("game") or body.get("rules")),
                        player_names=names,
                        seed=seed,
                        computers=computers if computers is not None else get_computers(),
                    )
                    self._send(*json_bytes(snap))
                    return
                snap = new_match_with_options(match, names, seed, computers)
                self._send(*json_bytes(snap))
                return
            if path in ("/api/hit", "/api/reactor/hit"):
                seat = int(body.get("seat", 0))
                snap = match.hit(seat)
                self._send(*json_bytes(snap))
                return
            if path in ("/api/stay", "/api/reactor/stay"):
                seat = int(body.get("seat", 0))
                snap = match.stay(seat)
                self._send(*json_bytes(snap))
                return
        except (RuntimeError, ValueError, TypeError) as exc:
            self._send(*json_bytes({"error": str(exc)}, 400))
            return

        self._send(*json_bytes({"error": "not found"}, 404))

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str) -> None:
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        if ".." in rel.split("/"):
            self._send(*json_bytes({"error": "bad path"}, 400))
            return
        file_path = (STATIC_DIR / rel).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())):
            self._send(*json_bytes({"error": "bad path"}, 400))
            return
        if not file_path.is_file():
            self.send_response(404)
            self._cors()
            self.end_headers()
            self.wfile.write(b"not found")
            return
        ctype, _ = mimetypes.guess_type(str(file_path))
        data = file_path.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _websocket(self, qs: Dict[str, List[str]]) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key or self.headers.get("Upgrade", "").lower() != "websocket":
            self._send(*json_bytes({"error": "expected websocket"}, 400))
            return
        role = (qs.get("role") or ["table"])[0]
        seat_raw = (qs.get("seat") or [None])[0]
        seat = int(seat_raw) if seat_raw is not None and str(seat_raw).isdigit() else None
        _handle_ws(self, key, role, seat)


def _handle_ws(handler: HeliosHandler, key: str, role: str, seat: Optional[int]) -> None:
    sock = handler.request
    sock.sendall(wsutil.handshake_response(key))
    client = WsClient(sock, role, seat)
    with _clients_lock:
        _clients.add(client)
    try:
        client.send_json({"type": "hello", "role": role, "seat": seat})
        client.send_json({"type": "state", "state": get_match().snapshot()})
        while True:
            opcode, data = wsutil.read_frame(sock.recv)
            if opcode == 0x8:
                break
            if opcode == 0x9:
                sock.sendall(wsutil.encode_pong(data))
                continue
            if opcode != 0x1:
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            _dispatch_ws(client, msg)
    except Exception:
        pass
    finally:
        with _clients_lock:
            _clients.discard(client)
        try:
            sock.close()
        except Exception:
            pass


def _dispatch_ws(client: WsClient, msg: dict) -> None:
    mtype = msg.get("type")
    match = get_match()
    try:
        if mtype == "hit":
            seat = int(msg.get("seat", client.seat if client.seat is not None else 0))
            match.hit(seat)
        elif mtype == "stay":
            seat = int(msg.get("seat", client.seat if client.seat is not None else 0))
            match.stay(seat)
        elif mtype == "new":
            computers = _parse_computers(msg)
            if msg.get("game") or msg.get("rules"):
                switch_game(
                    str(msg.get("game") or msg.get("rules")),
                    player_names=msg.get("players") or msg.get("human_names"),
                    seed=msg.get("seed"),
                    computers=computers if computers is not None else get_computers(),
                )
            else:
                new_match_with_options(
                    match,
                    msg.get("players") or msg.get("human_names"),
                    msg.get("seed"),
                    computers,
                )
        elif mtype == "set_game":
            switch_game(
                str(msg.get("game") or msg.get("rules") or ""),
                player_names=msg.get("players") or msg.get("human_names"),
                seed=msg.get("seed"),
                computers=_parse_computers(msg),
            )
        elif mtype in ("set_computers", "computers", "bots"):
            n = _parse_computers(msg)
            if n is None:
                raise ValueError("Need computers (0–3)")
            apply_computers(
                n,
                human_names=msg.get("players") or msg.get("human_names"),
                seed=msg.get("seed"),
                game=msg.get("game"),
            )
        elif mtype == "ping":
            client.send_json({"type": "pong"})
        elif mtype == "get_state":
            client.send_json({"type": "state", "state": match.snapshot()})
    except (RuntimeError, ValueError, TypeError) as exc:
        try:
            client.send_json({"type": "error", "error": str(exc)})
        except Exception:
            pass


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Helios holotable — Flip 7 / Sabacc server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--players", type=int, default=2, help="2–4 crew seats at boot (ignored if --computers set)")
    parser.add_argument(
        "--computers",
        type=int,
        default=0,
        help="Computer opponents at boot (0–3). Seat 0 = Pilot (human pad).",
    )
    parser.add_argument(
        "--game",
        default="flip7",
        choices=("flip7", "sabacc"),
        help="Boot game on REACTOR (default flip7)",
    )
    args = parser.parse_args(argv)

    n_comp = max(0, min(3, args.computers))
    if n_comp > 0:
        names, bot_seats = build_roster(computers=n_comp, game=args.game)
    else:
        n = max(2, min(4, args.players))
        names = DEFAULT_CREW[:n] if n <= len(DEFAULT_CREW) else [f"Crew {i+1}" for i in range(n)]
        bot_seats = set()

    if args.game == "sabacc":
        set_match(SabaccLiveMatch(names, bot_seats=bot_seats), game_id="sabacc", computers=n_comp)
    else:
        set_match(LiveMatch(names, bot_seats=bot_seats), game_id="flip7", computers=n_comp)

    httpd = ThreadingHTTPServer((args.host, args.port), HeliosHandler)
    httpd.daemon_threads = True
    httpd.allow_reuse_address = True
    print(f"Helios listening on http://{args.host}:{args.port}/")
    print(f"  public table:  http://{args.host}:{args.port}/")
    print(f"  datapad seat0: http://{args.host}:{args.port}/pad.html?seat=0")
    print(f"  datapad seat1: http://{args.host}:{args.port}/pad.html?seat=1")
    print(f"  websocket:     ws://{args.host}:{args.port}/ws?role=table")
    print(f"  active game:   {args.game}")
    print(f"  computers:     {n_comp}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown")
    finally:
        _cancel_bot_timer()
        httpd.server_close()


if __name__ == "__main__":
    main()
