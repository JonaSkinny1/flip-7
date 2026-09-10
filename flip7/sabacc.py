"""Simplified Corellian Spike–inspired Sabacc for Helios private tables.

Fan/home private table rules — NOT a licensed Lucasfilm product.
See README for full house rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Union

SabaccCard = Union[int, str]  # int values; "SYLOP" is 0

BOMB_LIMIT = 23  # bust if abs(total) > 23
TARGET = 100  # first to this match score wins
OPENING_CARDS = 2


def create_sabacc_deck() -> List[SabaccCard]:
    """−10..−1 and +1..+10 (two each) + two Sylops (0)."""
    deck: List[SabaccCard] = []
    for n in range(1, 11):
        deck.extend([n, n, -n, -n])
    deck.extend(["SYLOP", "SYLOP"])
    return deck


def shuffle_sabacc(deck: List[SabaccCard], rng: random.Random | None = None) -> None:
    (rng or random).shuffle(deck)


def card_value(card: SabaccCard) -> int:
    if card == "SYLOP":
        return 0
    return int(card)


def hand_total(hand: List[SabaccCard]) -> int:
    return sum(card_value(c) for c in hand)


def is_bomb(hand: List[SabaccCard]) -> bool:
    return abs(hand_total(hand)) > BOMB_LIMIT


def stand_points(hand: List[SabaccCard]) -> int:
    """Score for a non-bust stand: 24 − |total| (exact 0 / Pure Sabacc = 24)."""
    total = hand_total(hand)
    return 24 - abs(total)


def display_sabacc_card(card: SabaccCard) -> str:
    if card == "SYLOP":
        return "Sylop"
    if isinstance(card, int):
        return f"{card:+d}" if card != 0 else "0"
    return str(card)


@dataclass
class SabaccPlayer:
    name: str
    score: int = 0


@dataclass
class SabaccTurnResult:
    points: int
    busted: bool = False
    pure: bool = False  # exact 0
    hand: List[SabaccCard] = field(default_factory=list)
    total: int = 0
    log: List[str] = field(default_factory=list)


class SabaccGame:
    """Match state: deck, seats, race to TARGET."""

    TARGET = TARGET
    BOMB_LIMIT = BOMB_LIMIT

    def __init__(self, player_names: List[str], rng: random.Random | None = None):
        if not 2 <= len(player_names) <= 4:
            raise ValueError("Sabacc needs 2–4 players")
        self.rng = rng or random.Random()
        self.players = [SabaccPlayer(n) for n in player_names]
        self.deck: List[SabaccCard] = create_sabacc_deck()
        self.discard: List[SabaccCard] = []
        shuffle_sabacc(self.deck, self.rng)
        self.current = 0

    def _ensure_deck(self, min_cards: int = 1) -> None:
        if len(self.deck) < min_cards:
            self.deck.extend(self.discard)
            self.discard.clear()
            shuffle_sabacc(self.deck, self.rng)

    def draw(self) -> SabaccCard:
        self._ensure_deck()
        return self.deck.pop()

    def _end_hand(self, hand: List[SabaccCard], result: SabaccTurnResult) -> None:
        self.discard.extend(hand)

    def apply_turn(self, result: SabaccTurnResult) -> Optional[SabaccPlayer]:
        player = self.players[self.current]
        player.score += result.points
        winner = player if player.score >= self.TARGET else None
        self.current = (self.current + 1) % len(self.players)
        return winner


@dataclass
class SabaccTurnController:
    """Interactive mid-turn state: opening deal of 2, then hit / stay."""

    game: SabaccGame
    hand: List[SabaccCard] = field(default_factory=list)
    log: List[str] = field(default_factory=list)
    result: Optional[SabaccTurnResult] = None
    last_card: Optional[SabaccCard] = None
    started: bool = False

    @property
    def done(self) -> bool:
        return self.result is not None

    @property
    def turn_score(self) -> int:
        """Potential stand points if not busted; 0 if bomb."""
        if is_bomb(self.hand):
            return 0
        return stand_points(self.hand)

    @property
    def hand_sum(self) -> int:
        return hand_total(self.hand)

    def start(self) -> Optional[SabaccTurnResult]:
        if self.started:
            raise RuntimeError("Turn already started")
        self.started = True
        for _ in range(OPENING_CARDS):
            early = self._draw_one()
            if early:
                return self._finish(early)
        return None

    def hit(self) -> Optional[SabaccTurnResult]:
        if self.done:
            raise RuntimeError("Turn already finished")
        if not self.started:
            raise RuntimeError("Turn not started")
        early = self._draw_one()
        if early:
            return self._finish(early)
        return None

    def stay(self) -> SabaccTurnResult:
        if self.done:
            raise RuntimeError("Turn already finished")
        if not self.started:
            raise RuntimeError("Turn not started")
        total = hand_total(self.hand)
        if is_bomb(self.hand):
            self.log.append(f"Bomb-out at {total:+d}")
            return self._finish(
                SabaccTurnResult(
                    points=0, busted=True, hand=list(self.hand), total=total, log=list(self.log)
                )
            )
        pts = stand_points(self.hand)
        pure = total == 0
        tag = "Pure Sabacc!" if pure else f"Stand at {total:+d}"
        self.log.append(f"{tag} — bank {pts}")
        return self._finish(
            SabaccTurnResult(
                points=pts,
                pure=pure,
                hand=list(self.hand),
                total=total,
                log=list(self.log),
            )
        )

    def _draw_one(self) -> Optional[SabaccTurnResult]:
        card = self.game.draw()
        self.last_card = card
        self.hand.append(card)
        label = display_sabacc_card(card)
        self.log.append(f"Drew {label} (sum {hand_total(self.hand):+d})")
        if is_bomb(self.hand):
            total = hand_total(self.hand)
            self.log.append(f"Bomb-out — |{total}| > {BOMB_LIMIT}")
            return SabaccTurnResult(
                points=0, busted=True, hand=list(self.hand), total=total, log=list(self.log)
            )
        return None

    def _finish(self, result: SabaccTurnResult) -> SabaccTurnResult:
        self.result = result
        self.game._end_hand(self.hand, result)
        return result
