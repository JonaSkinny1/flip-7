"""Live Sabacc match for Helios REACTOR station (same hit/stay surface as LiveMatch)."""

from __future__ import annotations

import random
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from .sabacc import (
    SabaccGame,
    SabaccPlayer,
    SabaccTurnController,
    display_sabacc_card,
    hand_total,
)

DEFAULT_CREW = ["Pilot", "Engineer", "Gunner", "Science"]


class SabaccLiveMatch:
    """Thread-safe Sabacc match — API mirrors LiveMatch (hit / stay / new_match / snapshot)."""

    def __init__(
        self,
        player_names: Optional[List[str]] = None,
        rng: random.Random | None = None,
        bot_seats: Optional[Set[int]] = None,
    ):
        names = player_names or DEFAULT_CREW[:2]
        if not 2 <= len(names) <= 4:
            names = (names + DEFAULT_CREW)[: max(2, min(4, len(names) or 2))]
            if len(names) < 2:
                names = DEFAULT_CREW[:2]
        self._lock = threading.RLock()
        self._listeners: List[Callable[[dict], None]] = []
        self.game = SabaccGame(names[:4] if len(names) > 4 else names, rng=rng)
        self.bot_seats: Set[int] = set(bot_seats or ())
        self.turn: Optional[SabaccTurnController] = None
        self.phase = "lobby"
        self.winner: Optional[SabaccPlayer] = None
        self.status = "Helios Sabacc online — Spike toward 0"
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
            if not 2 <= len(names) <= 4:
                raise ValueError("Sabacc needs 2–4 player names")
            rng = random.Random(seed) if seed is not None else random.Random()
            self.game = SabaccGame(names, rng=rng)
            if bot_seats is not None:
                self.bot_seats = set(bot_seats)
            self.turn = None
            self.winner = None
            self.match_id += 1
            self.status = "New Sabacc shuffle"
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
                raise RuntimeError("Cannot stand now")
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
        for _ in range(64):
            if self.winner:
                self.phase = "won"
                return
            self.turn = SabaccTurnController(game=self.game)
            self.phase = "resolving"
            result = self.turn.start()
            if result is None:
                self.phase = "choosing"
                p = self.game.players[self.game.current]
                total = self.turn.hand_sum
                kind = "computer" if self.game.current in self.bot_seats else "crew"
                self.status = f"{p.name}'s turn ({kind}) — sum {total:+d} · Draw or Stand"
                return
            self._settle_result(result)
            if self.winner:
                return
        self.status = "Safety stop: too many auto-resolved turns"
        self.phase = "choosing"

    def _settle_result(self, result) -> None:
        lines = list(result.log[-4:])
        if result.busted:
            tag = "bomb-out"
        elif result.pure:
            tag = "Pure Sabacc"
        else:
            tag = f"sum {result.total:+d}"
        winner = self.game.apply_turn(result)
        self.status = f"+{result.points} ({tag}) · " + " · ".join(lines[-2:])
        self.turn = None
        if winner:
            self.winner = winner
            self.phase = "won"
            self.status = f"{winner.name} wins with {winner.score} — Sabacc complete"
            return
        self.phase = "between"

    def _after_action(self, result) -> None:
        if result is None:
            assert self.turn is not None
            self.phase = "choosing"
            p = self.game.players[self.game.current]
            self.status = (
                f"{p.name}'s turn "
                f"({'computer' if self.game.current in self.bot_seats else 'crew'}) — "
                f"sum {self.turn.hand_sum:+d} · Draw or Stand"
            )
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
            hand_sum = hand_total(hand) if hand else (t.hand_sum if t and not t.done else 0)
            computers = len(self.bot_seats)
            return {
                "station": "REACTOR",
                "title": "Sabacc",
                "rules": "sabacc",
                "game": "sabacc",
                "match_id": self.match_id,
                "phase": self.phase,
                "target": SabaccGame.TARGET,
                "bomb_limit": SabaccGame.BOMB_LIMIT,
                "goal": 0,
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
                "hand": [display_sabacc_card(c) for c in hand],
                "hand_raw": hand,
                "hand_sum": hand_sum,
                "turn_score": t.turn_score if t and not t.done else 0,
                "shield": False,
                "forced_draws": 0,
                "last_flip": display_sabacc_card(last) if last is not None else "—",
                "last_flip_raw": last,
                "log": list(t.log[-8:] if t else []),
                "can_act": self.phase == "choosing" and not self.winner,
                "reskin": {},
                "deck_remaining": len(g.deck),
                "disclaimer": "Fan/home private table — not a licensed Lucasfilm product",
            }
