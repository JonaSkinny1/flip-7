"""Deck construction and draw helpers."""

from __future__ import annotations

import random
from typing import List, Union

Card = Union[int, str]

ACTION_CARDS = ("SECOND_CHANCE", "FREEZE", "FLIP_THREE")


def create_deck() -> List[Card]:
    deck: List[Card] = [0]
    for n in range(1, 13):
        deck.extend([n] * n)
    for action in ACTION_CARDS:
        deck.extend([action] * 3)
    return deck


def shuffle_deck(deck: List[Card], rng: random.Random | None = None) -> None:
    (rng or random).shuffle(deck)


def draw_card(deck: List[Card], discard: List[Card] | None = None) -> Card:
    if not deck:
        if not discard:
            raise RuntimeError("Deck and discard are empty")
        deck.extend(discard)
        discard.clear()
        shuffle_deck(deck)
    return deck.pop()


def numeric_score(hand: List[Card]) -> int:
    return sum(c for c in hand if isinstance(c, int))
