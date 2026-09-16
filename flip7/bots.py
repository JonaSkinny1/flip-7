"""Computer opponents for Helios REACTOR — Flip 7 and Sabacc heuristics.

Bots are server-driven: no datapad required. Sci-fi / Ohio Outpost names only.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Set, Tuple

# Ohio Outpost / Sol-3 flavor — no Youngstown
BOT_NAMES = ("COSMOS", "F.R.A.N.K.", "Probe-7", "ORBITAL", "HELIX", "NAV-3")

HUMAN_DEFAULT = "Pilot"
HUMAN_FILL = ("Engineer", "Gunner", "Science")


def max_players_for_game(game: str) -> int:
    g = (game or "flip7").strip().lower()
    if g in ("sabacc", "spike", "corellian"):
        return 4
    return 6


def max_computers(game: str, human_count: int = 1) -> int:
    """UI cap is 3; also respect seat limits."""
    return max(0, min(3, max_players_for_game(game) - max(1, human_count)))


def build_roster(
    computers: int = 0,
    human_names: Optional[Sequence[str]] = None,
    game: str = "flip7",
) -> Tuple[List[str], Set[int]]:
    """Build player name list and bot seat indices.

    Seat 0..H-1 are humans; remaining seats are computers (up to 3).
    With computers=0 and a single human name, fill a second human seat so
    the table still has ≥2 players (existing multi-pad default).
    """
    humans = [str(n).strip() or HUMAN_DEFAULT for n in (human_names or [HUMAN_DEFAULT])]
    humans = [h for h in humans if h] or [HUMAN_DEFAULT]
    # Keep at least one human
    if not humans:
        humans = [HUMAN_DEFAULT]

    cap = max_players_for_game(game)
    n_bots = max(0, min(int(computers), 3, cap - 1))
    # Prefer requested human count, but leave room for bots
    max_humans = cap - n_bots
    humans = humans[: max(1, max_humans)]

    if n_bots == 0 and len(humans) < 2:
        # Classic two-seat human table
        fill = list(HUMAN_FILL)
        while len(humans) < 2 and fill:
            humans.append(fill.pop(0))

    bot_names = list(BOT_NAMES[:n_bots])
    names = humans + bot_names
    if len(names) < 2:
        names.append(BOT_NAMES[0] if n_bots == 0 else HUMAN_FILL[0])
        # If we forced a bot name with computers=0, treat as human fill instead
        if n_bots == 0:
            names[-1] = HUMAN_FILL[0]

    names = names[:cap]
    bot_seats: Set[int] = set(range(len(humans), len(humans) + n_bots))
    # Clamp bot seats to actual names length
    bot_seats = {s for s in bot_seats if s < len(names)}
    return names, bot_seats


def flip7_decide(
    hand: Sequence[Any],
    shield: bool = False,
    turn_score: Optional[int] = None,
) -> str:
    """Return 'hit' or 'stay' for Reactor Overload / Flip 7.

    Simple risk heuristic: chase Flip 7 when close; bank when bust risk rises.
    """
    nums = [c for c in hand if isinstance(c, int)]
    uniques = set(nums)
    n_u = len(uniques)
    score = turn_score if turn_score is not None else sum(c for c in nums if c != 0) + (
        0 if 0 not in nums else 0
    )
    if turn_score is None:
        from .deck import numeric_score

        score = numeric_score(list(hand))

    # Six unique numbers → go for Reactor Overload (+15)
    if n_u >= 6:
        return "hit"
    # Empty / very early hand — always draw
    if n_u <= 2 and score < 25:
        return "hit"
    # High charge without shield — bank
    if score >= 40 and not shield:
        return "stay"
    if score >= 48:
        return "stay"
    # Crowded hand → duplicate risk climbs
    if n_u >= 5:
        if score >= 28 and not shield:
            return "stay"
        if score >= 35:
            return "stay"
        return "hit"
    if n_u >= 4:
        if score >= 32 and not shield:
            return "stay"
        if score >= 38:
            return "stay"
        return "hit"
    # Mid game — lean hit unless already strong
    if score >= 36 and not shield:
        return "stay"
    return "hit"


def sabacc_decide(hand_sum: int, bomb_limit: int = 23) -> str:
    """Return 'hit' or 'stay' for Sabacc (toward 0, bomb if |sum| > limit)."""
    abs_sum = abs(int(hand_sum))
    # Pure / near-zero — stand
    if abs_sum <= 3:
        return "stay"
    # Near bomb-out — do not draw
    if abs_sum >= bomb_limit - 4:
        return "stay"
    # Far from zero — draw to chase Spike
    if abs_sum >= 8:
        return "hit"
    # Mild distance — slight preference to stand
    if abs_sum <= 5:
        return "stay"
    return "hit"


def decide_from_snapshot(state: dict) -> Optional[str]:
    """Pick hit/stay from a match snapshot, or None if not a choosable bot turn."""
    if not state or state.get("phase") != "choosing" or not state.get("can_act"):
        return None
    if state.get("winner"):
        return None
    seat = state.get("active_seat")
    players = state.get("players") or []
    if seat is None or seat < 0 or seat >= len(players):
        return None
    pl = players[seat]
    if not pl.get("is_bot"):
        return None

    rules = state.get("rules") or state.get("game") or "flip7"
    if rules == "sabacc":
        return sabacc_decide(
            int(state.get("hand_sum") or 0),
            int(state.get("bomb_limit") or 23),
        )
    return flip7_decide(
        state.get("hand_raw") or [],
        shield=bool(state.get("shield")),
        turn_score=int(state.get("turn_score") or 0),
    )
