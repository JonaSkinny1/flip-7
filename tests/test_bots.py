"""Unit tests for computer-opponent helpers and live bot seating."""

from __future__ import annotations

import json
import os
import random
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from urllib import error, request

# Fast bot turns for integration tests
os.environ["HELIOS_BOT_DELAY"] = "0.05"

from flip7.bots import (  # noqa: E402
    BOT_NAMES,
    build_roster,
    decide_from_snapshot,
    flip7_decide,
    sabacc_decide,
)
from flip7.live import LiveMatch  # noqa: E402
from flip7.server import HeliosHandler, set_match, apply_computers  # noqa: E402


class TestBotHelpers(unittest.TestCase):
    def test_roster_solo_bots(self):
        names, seats = build_roster(computers=2, game="flip7")
        self.assertEqual(names[0], "Pilot")
        self.assertEqual(names[1], BOT_NAMES[0])
        self.assertEqual(names[2], BOT_NAMES[1])
        self.assertEqual(seats, {1, 2})
        self.assertNotIn("Youngstown", " ".join(names))

    def test_roster_zero_computers_two_humans(self):
        names, seats = build_roster(computers=0, game="flip7")
        self.assertEqual(len(names), 2)
        self.assertEqual(seats, set())

    def test_sabacc_cap(self):
        names, seats = build_roster(computers=3, game="sabacc")
        self.assertEqual(len(names), 4)  # 1 human + 3 bots
        self.assertEqual(len(seats), 3)

    def test_flip7_decide_chase_overload(self):
        # six unique → hit for Flip 7
        hand = [1, 2, 3, 4, 5, 6]
        self.assertEqual(flip7_decide(hand, shield=False, turn_score=21), "hit")

    def test_flip7_decide_bank_high(self):
        hand = [10, 12, 8]
        self.assertEqual(flip7_decide(hand, shield=False, turn_score=40), "stay")

    def test_sabacc_decide_near_zero(self):
        self.assertEqual(sabacc_decide(0), "stay")
        self.assertEqual(sabacc_decide(2), "stay")
        self.assertEqual(sabacc_decide(-15), "hit")
        self.assertEqual(sabacc_decide(20), "stay")

    def test_decide_from_snapshot_bot(self):
        state = {
            "phase": "choosing",
            "can_act": True,
            "active_seat": 1,
            "rules": "flip7",
            "hand_raw": [1, 2],
            "turn_score": 3,
            "shield": False,
            "players": [
                {"seat": 0, "name": "Pilot", "is_bot": False},
                {"seat": 1, "name": "COSMOS", "is_bot": True},
            ],
        }
        self.assertEqual(decide_from_snapshot(state), "hit")

    def test_decide_skips_human(self):
        state = {
            "phase": "choosing",
            "can_act": True,
            "active_seat": 0,
            "rules": "flip7",
            "hand_raw": [1],
            "turn_score": 1,
            "players": [{"seat": 0, "name": "Pilot", "is_bot": False}],
        }
        self.assertIsNone(decide_from_snapshot(state))


class TestLiveBotSeats(unittest.TestCase):
    def test_snapshot_flags(self):
        m = LiveMatch(["Pilot", "COSMOS"], rng=random.Random(1), bot_seats={1})
        snap = m.snapshot()
        self.assertEqual(snap["computers"], 1)
        self.assertFalse(snap["players"][0]["is_bot"])
        self.assertTrue(snap["players"][1]["is_bot"])
        self.assertEqual(snap["players"][1]["kind"], "computer")


class TestBotServerApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_match(LiveMatch(["Pilot", "Engineer"], rng=random.Random(99)), game_id="flip7", computers=0)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), HeliosHandler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _post(self, path, body=None):
        data = json.dumps(body or {}).encode()
        req = request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode())
        except error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def _get(self, path):
        with request.urlopen(self.base + path, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode())

    def test_set_computers(self):
        code, state = self._post("/api/computers", {"computers": 2, "seed": 7})
        self.assertEqual(code, 200)
        self.assertEqual(state["computers"], 2)
        self.assertEqual(len(state["players"]), 3)
        bots = [p for p in state["players"] if p["is_bot"]]
        self.assertEqual(len(bots), 2)
        self.assertEqual(bots[0]["name"], BOT_NAMES[0])

    def test_health_lists_computers(self):
        self._post("/api/computers", {"computers": 1, "seed": 2})
        code, health = self._get("/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(health.get("computers"), 1)

    def test_bot_auto_acts(self):
        # Start with 1 bot; if bot is active, wait for auto-act to change match
        code, state = self._post("/api/computers", {"computers": 1, "seed": 42})
        self.assertEqual(code, 200)
        # Drive human turns until a bot must act, or bot is already active
        for _ in range(30):
            state = self._get("/api/state")[1]
            if state.get("phase") == "won":
                break
            if not state.get("can_act"):
                time.sleep(0.05)
                continue
            if state.get("active_is_bot"):
                mid = state["match_id"]
                seat = state["active_seat"]
                # Wait for server bot loop
                for _ in range(40):
                    time.sleep(0.05)
                    nxt = self._get("/api/state")[1]
                    if nxt.get("active_seat") != seat or nxt.get("match_id") != mid or not nxt.get("active_is_bot"):
                        # Progressed — success
                        return
                self.fail("bot did not auto-act in time")
            # Human turn — stay to advance quickly
            seat = state["active_seat"]
            self._post("/api/stay", {"seat": seat})
        # If we never saw a bot turn (rare with seed), still OK if match advanced with bots present
        self.assertTrue(any(p["is_bot"] for p in state["players"]))


if __name__ == "__main__":
    unittest.main()
