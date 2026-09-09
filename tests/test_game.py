import random
import unittest

from flip7.game import Flip7Game, TurnResult


class TestGame(unittest.TestCase):
    def test_target_constant(self):
        self.assertEqual(Flip7Game.TARGET, 200)

    def test_apply_turn_win(self):
        g = Flip7Game(["A", "B"], rng=random.Random(0))
        g.players[0].score = 190
        winner = g.apply_turn(TurnResult(points=15, hand=[1, 2], log=[]))
        self.assertIsNotNone(winner)
        self.assertEqual(winner.name, "A")
        self.assertEqual(winner.score, 205)

    def test_player_count_bounds(self):
        with self.assertRaises(ValueError):
            Flip7Game([])
        with self.assertRaises(ValueError):
            Flip7Game([f"P{i}" for i in range(7)])


if __name__ == "__main__":
    unittest.main()
