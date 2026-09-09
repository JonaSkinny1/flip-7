# Holotable ↔ flip7 bridge (optional stub note)

Software-only. No actuators / MQTT.

The **Python `flip7` package** remains the rules source of truth (deck, bust, Freeze / Flip 3 / Second Chance, Flip-7 bonus, 200 win).

This `holotable/` UI is a **chrome stub**: shared demo state via `localStorage` (+ `BroadcastChannel` when available). It does **not** call the engine yet.

## Suggested thin bridge (TODO)

1. Expose a small local HTTP or WebSocket server from Python that wraps `flip7.game`.
2. Datapad posts actions: `hit` | `stay` (and later action-card resolves).
3. Public table polls or subscribes to state: scores, last flip, turn charge, active seat.
4. Keep Pepper’s Ghost / freighter reskin names in the UI only:
   - Freeze → Containment Lock
   - Flip 3 → Overcharge Pulse
   - Second Chance → Neutralizer Shield

Until then: `python3 -m http.server 8766` under `holotable/` is enough for layout demos.
