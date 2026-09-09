"""Turn and match logic."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from .deck import Card, create_deck, numeric_score, shuffle_deck


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
        from .turn import play_turn_with_controller

        return play_turn_with_controller(self, chooser)

    def _end_hand(self, hand: List[Card], result: TurnResult) -> None:
        if not result.busted:
            self.discard.extend(hand)

    def apply_turn(self, result: TurnResult) -> Optional[Player]:
        player = self.players[self.current]
        player.score += result.points
        winner = player if player.score >= self.TARGET else None
        self.current = (self.current + 1) % len(self.players)
        return winner
