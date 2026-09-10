# Helios ↔ flip7 bridge

## Architecture

- **`flip7/`** Python package: Flip 7 rules (`deck`, `game`, `turn`, `live`) and Sabacc (`sabacc`, `sabacc_live`).
- **`python -m flip7.server`**: serves `holotable/` static UI, REST (`/api/*`), WebSocket (`/ws`).
- **Helios shell** (`index.html`): five stations (keys 1–5). WEATHER / NAV / BIO / COMMS are labeled mocks. Branding: **Ohio Outpost // Sol-3** / Ohio ground station.
- **REACTOR**: live match with **game picker** — `LiveMatch` (Flip 7 / Reactor Overload) or `SabaccLiveMatch`.
- **Datapads** (`pad.html?seat=N`): private Hit / Stay (Draw / Stand in Sabacc); state synced over WebSocket (REST poll fallback).

## Game switch API

| Method | Path / message | Body |
| --- | --- | --- |
| POST | `/api/game` | `{"game":"sabacc"\|"flip7", "players"?: [...], "seed"?: n}` |
| POST | `/api/new` | optional `"game"` to switch while resetting |
| WS | `set_game` | `{"type":"set_game","game":"sabacc"}` |
| GET | `/api/games` | lists games + `active` |
| GET | `/api/health` | includes `active_game`, `outpost` |

Snapshot always includes `rules` / `game` (`flip7` or `sabacc`) so the UI can re-skin.

## Out of scope (this build)

- Physical Pepper’s Ghost hardware, actuators, MQTT / Home Assistant
- Full Godot 4 port (phase 2)
- Live WEATHER/NAV APIs (stubs only)
- Official Sabacc / Lucasfilm IP (house rules only)

## Run

See root README.
