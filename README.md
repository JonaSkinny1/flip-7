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

## Holotable (Reactor Overload stub)

Static Pepper’s Ghost / table + datapad chrome. Software only (no actuators / MQTT). Demo sync via `localStorage` between tabs; Python `flip7` rules stay the source of truth — see `holotable/BRIDGE.md`.

```bash
cd holotable && python3 -m http.server 8766
# public: http://127.0.0.1:8766/public.html
# pad: http://127.0.0.1:8766/pad.html
```

Reskin (UI chrome only): Freeze → Containment Lock · Flip 3 → Overcharge Pulse · Second Chance → Neutralizer Shield.

## Rules (summary)

- Deck: one `0`; card `N` appears `N` times for `N = 1..12`; three each of `SECOND_CHANCE`, `FREEZE`, `FLIP_THREE`.
- Hit draws; a duplicate nonzero number **busts** the turn (0 points) unless `SECOND_CHANCE` shields once.
- `FREEZE` banks the current numeric score and ends the turn.
- `FLIP_THREE` forces three draws (nested actions resolve as they appear).
- Seven unique numbers → `sum + 15` and end the turn.
- First to **200** wins.

## Roadmap

- [x] Terminal multiplayer rules engine
- [x] Holotable web stub (public table + datapad)
- [ ] Godot 4 table UI / Pepper’s Ghost layout
- [ ] Private “datapad” hands over local WebSocket

Owner: Jonathan Sarkkinen (`JonaSkinny1`)
