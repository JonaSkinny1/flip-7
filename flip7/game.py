"""Turn and match logic."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .deck import Card, create_deck, draw_card, numeric_score, shuffle_deck


@dataclass
class Player:
    name: str
    score: int = 0


@dataclass
class TurnResult:
    points: int
    busted: bool = False
    froze: bool = False
    flip7: bool = False
    hand: List[Card] = field(default_factory=list)
    log: List[str] = field(default_factory=list)


class Flip7Game:
    TARGET = 200

    def __init__(self, player_names: List[str], rng: random.Random | None = None):
        if not 1 <= len(player_names) <= 6:
            raise ValueError("Need 1–6 players")
        self.rng = rng or random.Random()
        self.players = [Player(n) for n in player_names]
        self.deck: List[Card] = create_deck()
        self.discard: List[Card] = []
        shuffle_deck(self.deck, self.rng)
        self.current = 0

    def _ensure_deck(self, min_cards: int = 1) -> None:
        if len(self.deck) < min_cards:
            self.deck.extend(self.discard)
            self.discard.clear()
            shuffle_deck(self.deck, self.rng)

    def play_turn(self, chooser) -> TurnResult:
        """chooser(hand, has_shield) -> 'H' or 'S'."""
        hand: List[Card] = []
        shield = False
        log: List[str] = []
        forced_draws = 0

        def resolve_draw() -> Optional[TurnResult]:
            nonlocal shield, forced_draws
            self._ensure_deck()
            card = draw_card(self.deck, self.discard)
            log.append(f"Drew {card}")

            if isinstance(card, str):
                if card == "SECOND_CHANCE":
                    shield = True
                    hand.append(card)
                    log.append("Shield armed")
                    return None
                if card == "FREEZE":
                    hand.append(card)
                    pts = numeric_score(hand)
                    log.append(f"FREEZE — bank {pts}")
                    return TurnResult(points=pts, froze=True, hand=list(hand), log=list(log))
                if card == "FLIP_THREE":
                    hand.append(card)
                    forced_draws += 3
                    log.append("FLIP_THREE — three forced draws")
                    return None

            # number card
            if card != 0 and card in [c for c in hand if isinstance(c, int)]:
                if shield:
                    shield = False
                    log.append(f"Duplicate {card} blocked by SECOND_CHANCE")
                    # burn the duplicate into discard, keep hand
                    self.discard.append(card)
                    return None
                log.append(f"Bust on duplicate {card}")
                self.discard.extend(hand)
                self.discard.append(card)
                return TurnResult(points=0, busted=True, hand=[], log=list(log))

            hand.append(card)
            uniques = {c for c in hand if isinstance(c, int)}
            if len(uniques) >= 7:
                pts = numeric_score(hand) + 15
                log.append(f"Flip 7! {pts} points")
                return TurnResult(points=pts, flip7=True, hand=list(hand), log=list(log))
            return None

        # opening draw
        early = resolve_draw()
        if early:
            self._end_hand(hand, early)
            return early

        while True:
            while forced_draws > 0:
                forced_draws -= 1
                early = resolve_draw()
                if early:
                    self._end_hand(hand, early)
                    return early

            choice = chooser(list(hand), shield)
            if choice.upper().startswith("S"):
                pts = numeric_score(hand)
                log.append(f"Stay — bank {pts}")
                result = TurnResult(points=pts, hand=list(hand), log=list(log))
                self._end_hand(hand, result)
                return result

            early = resolve_draw()
            if early:
                self._end_hand(hand, early)
                return early

    def _end_hand(self, hand: List[Card], result: TurnResult) -> None:
        if not result.busted:
            self.discard.extend(hand)

    def apply_turn(self, result: TurnResult) -> Optional[Player]:
        player = self.players[self.current]
        player.score += result.points
        winner = player if player.score >= self.TARGET else None
        self.current = (self.current + 1) % len(self.players)
        return winner
