import random
import unittest

from flip7.game import Flip7Game
from flip7.turn import TurnController


class TestTurnController(unittest.TestCase):
    def test_stay_banks_numeric(self):
        g = Flip7Game(["A", "B"], rng=random.Random(1))
        # Force a known hand path: start then stay after first card if possible
        tc = TurnController(game=g)
        early = tc.start()
        if early:
            # opening draw ended turn (freeze/bust/flip7) — still a valid result
            self.assertIsInstance(early.points, int)
            return
        result = tc.stay()
        self.assertFalse(result.busted)
        self.assertEqual(result.points, tc.turn_score if not result.froze else result.points)
        self.assertGreaterEqual(result.points, 0)

    def test_hit_and_parity_with_play_turn(self):
        def scripted(choices):
            it = iter(choices)

            def chooser(hand, shield):
                return next(it)

            return chooser

        # Same seed → same deck order; stay immediately after opening if turn continues
        g1 = Flip7Game(["A", "B"], rng=random.Random(42))
        g2 = Flip7Game(["A", "B"], rng=random.Random(42))

        r_cli = g1.play_turn(scripted(["S"] * 20))
        tc = TurnController(game=g2)
        early = tc.start()
        r_live = early if early else tc.stay()
        self.assertEqual(r_cli.points, r_live.points)
        self.assertEqual(r_cli.busted, r_live.busted)
        self.assertEqual(r_cli.froze, r_live.froze)
        self.assertEqual(r_cli.flip7, r_live.flip7)


class TestLiveMatch(unittest.TestCase):
    def test_two_player_hit_stay_cycle(self):
        from flip7.live import LiveMatch

        m = LiveMatch(["Pilot", "Engineer"], rng=random.Random(7))
        snap = m.snapshot()
        self.assertIn(snap["phase"], ("choosing", "won", "between", "resolving"))
        # If choosing, active seat can stay
        if snap["phase"] == "choosing":
            seat = snap["active_seat"]
            before = snap["players"][seat]["score"]
            snap2 = m.stay(seat)
            self.assertGreaterEqual(snap2["players"][seat]["score"], before)

    def test_wrong_seat_rejected(self):
        from flip7.live import LiveMatch

        m = LiveMatch(["A", "B"], rng=random.Random(3))
        snap = m.snapshot()
        if snap["phase"] != "choosing":
            return
        wrong = 1 - snap["active_seat"]
        with self.assertRaises(RuntimeError):
            m.hit(wrong)


if __name__ == "__main__":
    unittest.main()
