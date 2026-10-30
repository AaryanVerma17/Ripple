# Implementation status (v2)

**Verified here:** 25 backend tests pass; `next build` and `tsc` pass; the UI was exercised end to end in a headless browser (analysis, scenarios, map, cost, chat, camera page, parts, history, both themes) with no console errors.

**Not verified (needs your keys / your machine):**
- Gemini photo reading against the real API. Tested only with a mocked transport. Set `GEMINI_MODEL` to a current model name.
- Nebius text model: exact `NEBIUS_BASE_URL`, `NEBIUS_MODEL`, and whether `NEBIUS_JSON_MODE` works for your model.
- Webcam capture depends on browser permission (works on localhost).
- `docker compose up --build` on your Windows machine. The API and web were run directly, not through Docker, in this environment.

**Known limits:** one fictional project; the engine models electrical, mass, speed, runtime and cost only (no thermal, no mechanical stress);
effort and runtime figures rest on labelled assumptions; photo-read values are unverified by design; SQLite, no authentication (single-user demo).
