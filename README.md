# Flip 7 · Helios · Reactor Overload · Sabacc

Python **Flip 7** rules engine plus a **Helios** five-station holotable web UI. The **REACTOR** station is a multiplayer table with a **game picker**: **Reactor Overload** (Flip 7 reskin) or **Sabacc** (simplified Corellian Spike–inspired house rules). Private datapads drive Hit/Draw and Stay/Stand.

Software only in this repo — no physical Pepper’s Ghost hardware, actuators, or MQTT.

**Sabacc disclaimer:** fan/home private-table house rules only. **Not a licensed Lucasfilm product.**

## Helios vs Reactor

| Layer | What it is |
| --- | --- |
| **Helios** | Ground-station shell on the public holotable: **WEATHER · NAV · REACTOR · BIO · COMMS** (keys `1`–`5`). Black / teal / hazard chrome for Pepper’s Ghost demos (**Ohio Outpost // Sol-3** / Ohio ground-station flavor). |
| **Reactor Overload** | Full Flip 7 game on the REACTOR station: real `flip7` deck & scoring, Containment Lock / Overcharge Pulse / Neutralizer Shield labels, race to **200**. |
| **Sabacc** | Second REACTOR game: +/- cards, goal near **0**, bomb-out if \|sum\| > 23, race to **100**. Switch via the on-table game picker (or `POST /api/game`). |
| **Other stations** | Polished **MOCK** stubs (solar/Kp, Earth/ISS orbit, vials SP-01–SP-08, frequency dial). Live APIs optional later. |

## Run — terminal Flip 7

```bash
python3 -m flip7
python3 -m flip7 --players 4
```

## Run — Helios holotable server

```bash
python3 -m flip7.server
# optional: --host 0.0.0.0 --port 8766 --players 3 --game sabacc
```

Then open:

```
# public Helios table (stations 1–5; REACTOR = live game picker)
http://127.0.0.1:8766/
http://127.0.0.1:8766/index.html#REACTOR
http://127.0.0.1:8766/public.html          # redirects to #REACTOR

# private datapads (one tab/device per seat)
http://127.0.0.1:8766/pad.html?seat=0
http://127.0.0.1:8766/pad.html?seat=1
```

Sync: **WebSocket** `ws://127.0.0.1:8766/ws?role=table|pad&seat=N` with REST fallback (`GET /api/state`, `POST /api/hit|stay|new|game`).

### Switch games

- On the **REACTOR** panel (or datapad): tap **Reactor Overload** or **Sabacc**.
- REST: `POST /api/game` with `{"game":"sabacc"}` or `{"game":"flip7"}`.
- WebSocket: `{"type":"set_game","game":"sabacc"}`.
- Boot: `python3 -m flip7.server --game sabacc`.

### Static-only (UI chrome, no engine)

```bash
cd holotable && python3 -m http.server 8766
# public: http://127.0.0.1:8766/public.html
# pad:    http://127.0.0.1:8766/pad.html
```

Without `flip7.server`, pads cannot drive real draws — use the Helios server for play.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Rules — Flip 7 / Reactor Overload (summary)

- Deck: one `0`; card `N` appears `N` times for `N = 1..12`; three each of `SECOND_CHANCE`, `FREEZE`, `FLIP_THREE`.
- Hit draws; duplicate nonzero number **busts** (0) unless Neutralizer Shield (`SECOND_CHANCE`) absorbs once.
- Containment Lock (`FREEZE`) banks numeric score and ends the turn.
- Overcharge Pulse (`FLIP_THREE`) forces three draws.
- Seven unique numbers → `sum + 15` (**Reactor Overload** / Flip 7) and end the turn.
- First to **200** wins.

## Rules — Sabacc (Helios house / Spike-inspired)

Fan/home private table — **not** a Lucasfilm product.

- **Players:** 2–4.
- **Deck:** two copies of each integer from **−10..−1** and **+1..+10**, plus two **Sylop** cards (value **0**). 42 cards.
- **Goal:** end your turn with a hand total as close to **0** as possible (Corellian Spike–inspired).
- **Deal:** two opening cards each turn; then **Draw** (hit) or **Stand** (stay).
- **Bomb-out:** if `|hand total| > 23` after any draw, you bust and score **0** for the turn.
- **Stand scoring:** `24 − |total|` (so exact **0** / Pure Sabacc = **24** points).
- **Match:** first to **100** wins.
- Actions reuse the same datapad Hit / Stay buttons and `/api/hit` · `/api/stay` endpoints.

## Holotable UX (UI pass)

REACTOR table and datapad polish for kiosk / dark-room viewing (no engine changes):

- **Table:** match HUD (game · turn · race target), clearer crew piles with **TURN** badge, higher teal/orange contrast.
- **Pad:** large Hit/Stay targets, **Your turn** banner, help collapsed under details.
- **Game picker:** oversized dual buttons with **ACTIVE** badge; re-tap of current game ignored.

Details: `holotable/BRIDGE.md` (UX notes).

## Architecture

- `flip7/` — Flip 7 (`deck`, `game`, `turn`, `live`) + Sabacc (`sabacc`, `sabacc_live`) + `server` (stdlib HTTP + WebSocket).
- `holotable/` — Helios static UI (`index.html`, `pad.html`, `css/`, `js/`).
- See `holotable/BRIDGE.md`.

## Roadmap / out of scope here

- [x] Terminal multiplayer rules engine
- [x] Helios five-station shell + Reactor Overload live server
- [x] Sabacc as second REACTOR game + game picker
- [ ] Godot 4 table UI / Pepper’s Ghost layout (phase 2)
- [ ] Physical Pepper’s Ghost, Helios station hardware, actuators, MQTT / Home Assistant
- [ ] Live WEATHER / NAV data feeds

Owner: Jonathan Sarkkinen (`JonaSkinny1`)
