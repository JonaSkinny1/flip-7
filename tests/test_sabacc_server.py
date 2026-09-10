import json
import random
import threading
import unittest
from urllib import error, request
from http.server import ThreadingHTTPServer

from flip7.server import HeliosHandler, set_match, switch_game, get_game_id
from flip7.live import LiveMatch
from flip7.sabacc_live import SabaccLiveMatch


class TestSabaccServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_match(LiveMatch(["Pilot", "Engineer"], rng=random.Random(99)), game_id="flip7")
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

    def _get(self, path):
        with request.urlopen(self.base + path, timeout=3) as resp:
            return resp.status, json.loads(resp.read().decode())

    def _post(self, path, body=None):
        data = json.dumps(body or {}).encode()
        req = request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode())
        except error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_switch_to_sabacc(self):
        code, state = self._post("/api/game", {"game": "sabacc", "players": ["A", "B"], "seed": 3})
        self.assertEqual(code, 200)
        self.assertEqual(state.get("rules"), "sabacc")
        self.assertEqual(state.get("title"), "Sabacc")
        self.assertIn("hand_sum", state)
        self.assertEqual(get_game_id(), "sabacc")

        code, health = self._get("/api/health")
        self.assertEqual(health.get("active_game"), "sabacc")
        self.assertEqual(health.get("outpost"), "Ohio Outpost // Sol-3")

        code, games = self._get("/api/games")
        self.assertEqual(games.get("active"), "sabacc")
        ids = [g["id"] for g in games["games"]]
        self.assertIn("flip7", ids)
        self.assertIn("sabacc", ids)

    def test_switch_back_flip7(self):
        code, state = self._post("/api/game", {"game": "flip7", "players": ["X", "Y"], "seed": 2})
        self.assertEqual(code, 200)
        self.assertEqual(state.get("rules"), "flip7")
        self.assertEqual(state.get("title"), "Reactor Overload")

    def test_index_has_picker(self):
        with request.urlopen(self.base + "/", timeout=3) as resp:
            body = resp.read().decode()
            self.assertIn("game-picker", body)
            self.assertIn("Sabacc", body)
            self.assertNotIn("Youngstown", body)
            self.assertIn("Ohio Outpost", body)


if __name__ == "__main__":
    unittest.main()
