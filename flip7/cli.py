"""Terminal UI."""

from __future__ import annotations

import argparse

from .game import Flip7Game


def _prompt_choice(hand, has_shield) -> str:
    nums = [c for c in hand if isinstance(c, int)]
    print(f"  Hand: {hand}  |  numeric={sum(nums)}  |  shield={'ON' if has_shield else 'off'}")
    while True:
        raw = input("  [H]it or [S]tay? ").strip().upper() or "H"
        if raw.startswith("H") or raw.startswith("S"):
            return raw[0]
        print("  Enter H or S.")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Flip 7 — terminal multiplayer")
    parser.add_argument("--players", type=int, default=2, help="1–6 players (default 2)")
    args = parser.parse_args(argv)

    n = max(1, min(6, args.players))
    names = [f"Player {i + 1}" for i in range(n)]
    game = Flip7Game(names)

    print("=== Flip 7 ===")
    print(f"First to {game.TARGET}. Players: {', '.join(names)}\n")

    while True:
        player = game.players[game.current]
        print(f"-- {player.name}'s turn (score {player.score}) --")
        result = game.play_turn(_prompt_choice)
        for line in result.log:
            print(f"  · {line}")
        print(f"  → +{result.points}  |  running totals: " + ", ".join(f"{p.name}={p.score + (result.points if p is player else 0)}" for p in game.players))
        # apply_turn advances; show after apply
        winner = game.apply_turn(result)
        print(f"  Scores: " + ", ".join(f"{p.name}={p.score}" for p in game.players))
        print()
        if winner:
            print(f"*** {winner.name} wins with {winner.score}! ***")
            break


if __name__ == "__main__":
    main()
