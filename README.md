# Flip 7

Text-based multiplayer **Flip 7** (push-your-luck) in Python. Rules reference for a future **Godot 4** holographic-table build (freighter / “Reactor Overload” aesthetic).

## Run

```bash
python3 -m flip7
```

Optional player count:

```bash
python3 -m flip7 --players 4
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Rules (summary)

- Deck: one `0`; card `N` appears `N` times for `N = 1..12`; three each of `SECOND_CHANCE`, `FREEZE`, `FLIP_THREE`.
- Hit draws; a duplicate nonzero number **busts** the turn (0 points) unless `SECOND_CHANCE` shields once.
- `FREEZE` banks the current numeric score and ends the turn.
- `FLIP_THREE` forces three draws (nested actions resolve as they appear).
- Seven unique numbers → `sum + 15` and end the turn.
- First to **200** wins.

## Roadmap

- [x] Terminal multiplayer rules engine
- [ ] Godot 4 table UI / Pepper’s Ghost layout
- [ ] Private “datapad” hands over local WebSocket

Owner: Jonathan Sarkkinen (`JonaSkinny1`)
