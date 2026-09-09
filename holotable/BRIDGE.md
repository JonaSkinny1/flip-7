# Helios ↔ flip7 bridge

## Architecture

- **`flip7/`** Python package: Flip 7 rules (`deck`, `game`, `turn`, `live`).
- **`python -m flip7.server`**: serves `holotable/` static UI, REST (`/api/*`), WebSocket (`/ws`).
- **Helios shell** (`index.html`): five stations (keys 1–5). WEATHER / NAV / BIO / COMMS are labeled mocks.
- **REACTOR**: live `LiveMatch` — real draw / bust / stay / Containment Lock / Overcharge Pulse / Neutralizer Shield / Flip-7 (+15) / race to 200.
- **Datapads** (`pad.html?seat=N`): private Hit / Stay; state synced over WebSocket (REST poll fallback).

## Out of scope (this build)

- Physical Pepper’s Ghost hardware, actuators, MQTT / Home Assistant
- Full Godot 4 port (phase 2)
- Live WEATHER/NAV APIs (stubs only)

## Run

See root README.
