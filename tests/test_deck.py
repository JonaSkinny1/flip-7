import unittest

from flip7.deck import ACTION_CARDS, create_deck, numeric_score


class TestDeck(unittest.TestCase):
    def test_composition(self):
        deck = create_deck()
        self.assertEqual(deck.count(0), 1)
        for n in range(1, 13):
            self.assertEqual(deck.count(n), n, msg=f"count of {n}")
        for action in ACTION_CARDS:
            self.assertEqual(deck.count(action), 3)
        # 1 + sum(1..12) + 9 = 1+78+9 = 88
        self.assertEqual(len(deck), 88)

    def test_numeric_score(self):
        self.assertEqual(numeric_score([1, 2, "FREEZE", 3]), 6)


if __name__ == "__main__":
    unittest.main()
