"""Live multiplayer match + Reactor Overload reskin labels for Helios."""

from __future__ import annotations

import random
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from .game import Flip7Game, Player
from .turn import TurnController

# UI chrome only — engine still uses FREEZE / FLIP_THREE / SECOND_CHANCE
RESKIN = {
    "FREEZE": "Containment Lock",
    "FLIP_THREE": "Overcharge Pulse",
    "SECOND_CHANCE": "Neutralizer Shield",
}

DEFAULT_CREW = ["Pilot", "Engineer", "Gunner", "Science"]


def display_card(card: Any) -> str:
    if card is None:
        return "—"
    if isinstance(card, str):
        return RESKIN.get(card, card)
    return str(card)


def display_log_line(line: str) -> str:
    out = line
    for raw, pretty in RESKIN.items():
        out = out.replace(raw, pretty)
    out = out.replace("Flip 7!", "Reactor Overload!")
    out = out.replace("Shield armed", "Neutralizer Shield armed")
    return out


class LiveMatch:
    """Thread-safe Flip 7 match for the Helios REACTOR station."""

    def __init__(
        self,
        player_names: Optional[List[str]] = None,
        rng: random.Random | None = None,
        bot_seats: Optional[Set[int]] = None,
    ):
        names = player_names or DEFAULT_CREW[:2]
        self._lock = threading.RLock()
        self._listeners: List[Callable[[dict], None]] = []
        self.game = Flip7Game(names, rng=rng)
        self.bot_seats: Set[int] = set(bot_seats or ())
        self.turn: Optional[TurnController] = None
        self.phase = "lobby"  # lobby | choosing | resolving | between | won
        self.winner: Optional[Player] = None
        self.status = "Helios REACTOR online — start match"
        self.match_id = 1
        self._begin_turn_unlocked()

    def on_update(self, cb: Callable[[dict], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(cb)

        def off() -> None:
            with self._lock:
                if cb in self._listeners:
                    self._listeners.remove(cb)

        return off

    def _notify(self) -> None:
        snap = self.snapshot()
        for cb in list(self._listeners):
            try:
                cb(snap)
            except Exception:
                pass

    def new_match(
        self,
        player_names: Optional[List[str]] = None,
        seed: Optional[int] = None,
        bot_seats: Optional[Set[int]] = None,
    ) -> dict:
        with self._lock:
            names = player_names or [p.name for p in self.game.players]
            rng = random.Random(seed) if seed is not None else random.Random()
            self.game = Flip7Game(names, rng=rng)
            if bot_seats is not None:
                self.bot_seats = set(bot_seats)
            self.turn = None
            self.winner = None
            self.match_id += 1
            self.status = "New reactor cycle"
            self._begin_turn_unlocked()
            snap = self.snapshot()
        self._notify()
        return snap

    def hit(self, seat: int) -> dict:
        with self._lock:
            self._require_active(seat)
            if self.phase != "choosing" or not self.turn or self.turn.done:
                raise RuntimeError("Cannot draw now")
            result = self.turn.hit()
            self._after_action(result)
            snap = self.snapshot()
        self._notify()
        return snap

    def stay(self, seat: int) -> dict:
        with self._lock:
            self._require_active(seat)
            if self.phase != "choosing" or not self.turn or self.turn.done:
                raise RuntimeError("Cannot bank now")
            result = self.turn.stay()
            self._after_action(result)
            snap = self.snapshot()
        self._notify()
        return snap

    def _require_active(self, seat: int) -> None:
        if self.winner:
            raise RuntimeError("Match over")
        if seat != self.game.current:
            raise RuntimeError("Not your turn")

    def _begin_turn_unlocked(self) -> None:
        """Start turns until someone must choose or the match ends."""
        for _ in range(64):
            if self.winner:
                self.phase = "won"
                return
            self.turn = TurnController(game=self.game)
            self.phase = "resolving"
            result = self.turn.start()
            if result is None:
                self.phase = "choosing"
                p = self.game.players[self.game.current]
                kind = "computer" if self.game.current in self.bot_seats else "crew"
                self.status = f"{p.name}'s turn ({kind}) — Draw Core or Bank Charge"
                return
            self._settle_result(result)
            if self.winner:
                return
        self.status = "Safety stop: too many auto-resolved turns"
        self.phase = "choosing"

    def _settle_result(self, result) -> None:
        lines = [display_log_line(x) for x in result.log[-4:]]
        tag = (
            "bust"
            if result.busted
            else "Containment Lock"
            if result.froze
            else "Reactor Overload"
            if result.flip7
            else "banked"
        )
        winner = self.game.apply_turn(result)
        self.status = f"+{result.points} ({tag}) · " + " · ".join(lines[-2:])
        self.turn = None
        if winner:
            self.winner = winner
            self.phase = "won"
            self.status = f"{winner.name} wins with {winner.score} — Reactor Overload complete"
            return
        self.phase = "between"

    def _after_action(self, result) -> None:
        if result is None:
            assert self.turn is not None
            self.phase = "choosing"
            p = self.game.players[self.game.current]
            kind = "computer" if self.game.current in self.bot_seats else "crew"
            self.status = f"{p.name}'s turn ({kind}) — Draw Core or Bank Charge"
            return
        self._settle_result(result)
        if not self.winner:
            self._begin_turn_unlocked()

    def snapshot(self) -> dict:
        with self._lock:
            g = self.game
            t = self.turn
            hand = list(t.hand) if t and not t.done else []
            last = t.last_card if t else None
            computers = len(self.bot_seats)
            return {
                "station": "REACTOR",
                "title": "Reactor Overload",
                "rules": "flip7",
                "game": "flip7",
                "match_id": self.match_id,
                "phase": self.phase,
                "target": Flip7Game.TARGET,
                "status": self.status,
                "active_seat": g.current,
                "active_name": g.players[g.current].name if g.players else "",
                "active_is_bot": g.current in self.bot_seats,
                "winner": None
                if not self.winner
                else {
                    "seat": next(i for i, p in enumerate(g.players) if p is self.winner),
                    "name": self.winner.name,
                    "score": self.winner.score,
                },
                "players": [
                    {
                        "seat": i,
                        "name": p.name,
                        "score": p.score,
                        "active": i == g.current,
                        "is_bot": i in self.bot_seats,
                        "kind": "computer" if i in self.bot_seats else "human",
                    }
                    for i, p in enumerate(g.players)
                ],
                "computers": computers,
                "hand": [display_card(c) for c in hand],
                "hand_raw": hand,
                "turn_score": t.turn_score if t and not t.done else 0,
                "shield": bool(t.shield) if t and not t.done else False,
                "forced_draws": t.forced_draws if t and not t.done else 0,
                "last_flip": display_card(last),
                "last_flip_raw": last,
                "log": [display_log_line(x) for x in (t.log[-8:] if t else [])],
                "can_act": self.phase == "choosing" and not self.winner,
                "reskin": dict(RESKIN),
                "deck_remaining": len(g.deck),
            }
