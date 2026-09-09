"""Stepable turn controller — same rules as Flip7Game.play_turn, for live UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .deck import Card, numeric_score
from .game import Flip7Game, TurnResult


@dataclass
class TurnController:
    """Interactive mid-turn state for one seat."""

    game: Flip7Game
    hand: List[Card] = field(default_factory=list)
    shield: bool = False
    log: List[str] = field(default_factory=list)
    forced_draws: int = 0
    result: Optional[TurnResult] = None
    last_card: Optional[Card] = None
    started: bool = False

    @property
    def done(self) -> bool:
        return self.result is not None

    @property
    def turn_score(self) -> int:
        return numeric_score(self.hand)

    def start(self) -> Optional[TurnResult]:
        """Opening draw (+ drain forced). May finish immediately (freeze/bust/flip7)."""
        if self.started:
            raise RuntimeError("Turn already started")
        self.started = True
        early = self._resolve_draw()
        if early:
            return self._finish(early)
        return self._drain_forced()

    def hit(self) -> Optional[TurnResult]:
        if self.done:
            raise RuntimeError("Turn already finished")
        if not self.started:
            raise RuntimeError("Turn not started")
        if self.forced_draws > 0:
            raise RuntimeError("Forced draws pending")
        early = self._resolve_draw()
        if early:
            return self._finish(early)
        return self._drain_forced()

    def stay(self) -> TurnResult:
        if self.done:
            raise RuntimeError("Turn already finished")
        if not self.started:
            raise RuntimeError("Turn not started")
        if self.forced_draws > 0:
            raise RuntimeError("Cannot stay during Overcharge Pulse")
        pts = numeric_score(self.hand)
        self.log.append(f"Stay — bank {pts}")
        return self._finish(TurnResult(points=pts, hand=list(self.hand), log=list(self.log)))

    def _drain_forced(self) -> Optional[TurnResult]:
        while self.forced_draws > 0 and not self.done:
            self.forced_draws -= 1
            early = self._resolve_draw()
            if early:
                return self._finish(early)
        return None

    def _resolve_draw(self) -> Optional[TurnResult]:
        self.game._ensure_deck()
        card = self.game.deck.pop()
        # mirror draw_card discard tracking: drawn cards that bust/shield-burn go to discard;
        # successful hand cards stay in hand until _end_hand
        self.last_card = card
        self.log.append(f"Drew {card}")

        if isinstance(card, str):
            if card == "SECOND_CHANCE":
                self.shield = True
                self.hand.append(card)
                self.log.append("Shield armed")
                return None
            if card == "FREEZE":
                self.hand.append(card)
                pts = numeric_score(self.hand)
                self.log.append(f"FREEZE — bank {pts}")
                return TurnResult(points=pts, froze=True, hand=list(self.hand), log=list(self.log))
            if card == "FLIP_THREE":
                self.hand.append(card)
                self.forced_draws += 3
                self.log.append("FLIP_THREE — three forced draws")
                return None

        if card != 0 and card in [c for c in self.hand if isinstance(c, int)]:
            if self.shield:
                self.shield = False
                self.log.append(f"Duplicate {card} blocked by SECOND_CHANCE")
                self.game.discard.append(card)
                return None
            self.log.append(f"Bust on duplicate {card}")
            self.game.discard.extend(self.hand)
            self.game.discard.append(card)
            return TurnResult(points=0, busted=True, hand=[], log=list(self.log))

        self.hand.append(card)
        uniques = {c for c in self.hand if isinstance(c, int)}
        if len(uniques) >= 7:
            pts = numeric_score(self.hand) + 15
            self.log.append(f"Flip 7! {pts} points")
            return TurnResult(points=pts, flip7=True, hand=list(self.hand), log=list(self.log))
        return None

    def _finish(self, result: TurnResult) -> TurnResult:
        self.result = result
        self.game._end_hand(self.hand, result)
        return result


def play_turn_with_controller(game: Flip7Game, chooser) -> TurnResult:
    """CLI-compatible path using TurnController (rules parity)."""
    tc = TurnController(game=game)
    early = tc.start()
    if early:
        return early
    while True:
        choice = chooser(list(tc.hand), tc.shield)
        if choice.upper().startswith("S"):
            return tc.stay()
        early = tc.hit()
        if early:
            return early
