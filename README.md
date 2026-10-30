# Ripple — Engineering Change Impact Agent

Change one part and see, before you build anything: what it touches, which checks fail (with the arithmetic and the evidence),
what it does to speed, runtime, mass and cost, which catalogue parts would fix it, and what that fix costs.

Built for the Nebius × NVIDIA Global AI Hackathon 2026 (Best Apps and Agents).

**Principle:** the language model only interprets and explains. A deterministic engine does every number, and a validator rejects any
model text that invents an ID, a number or an approval. Ripple never approves a change; the engineer records the decision.

## Run it

```bash
cp .env.example .env        # optional: add keys (see below)
docker compose up --build
```
Open http://localhost:3000 (API docs at http://localhost:8000/docs). It works with **no keys at all**.

| Feature | Needs |
|---|---|
| Impact analysis, scenarios, cost, fix options, review, history, export | nothing |
| What-if chat (rule-based reading and answers) | nothing |
| Chat/report wording by a model, model-assisted sentence reading | `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEBIUS_MODEL` |
| Camera: identify a part from a photo | `GEMINI_API_KEY` (+ `GEMINI_MODEL`, check the current name in Google's docs) |

Run the tests: `docker compose exec api pytest -q` (25 tests: engine, parser, validator, API, mocked-Gemini photo flow).

## What's in it

- **Kind-aware impact graph.** A voltage change travels along electrical links, a mass change along mechanical ones, a cost change reaches only the budget.
  The 5 V regulator isolates the controller, so it is reported unaffected, with the reason.
- **Scenarios.** If a new part's voltage doesn't match the rail, Ripple shows A (keep the rail), B (raise it, change nothing else) and C (raise it and swap the cheapest catalogue parts that fix each failure).
- **Honest results.** `verified_issue` (recorded values fail), `potential_issue` (fails under an assumption), `unknown` (data missing), `no_violation_found`. Missing data is never guessed.
- **Cost.** Per-unit parts delta against the budget, plus a one-off effort estimate from editable, labelled assumptions.
- **Camera.** Upload or capture a photo; Gemini reads the part and label; matches are validated against real parts and catalogue IDs; label values are marked unverified; each offered change opens the normal analysis.
- **What-if chat.** "What if the motor is 24 V?", "…the chassis is 0.5 kg lighter?", "…battery capacity doubles?" Then ask why, what it costs, what to fix, what's missing.
- **Data audit.** Supply a missing rating with a source note; it becomes `engineer_supplied` evidence and resolves unknowns.
- **Review.** Append-only decisions per analysis; Markdown export; print.
- **UI.** Dark/light theme, command palette (Ctrl/Cmd+K), radial dependency map, reduced-motion support.

## Layout
`services/api` FastAPI + SQLite · `apps/web` Next.js 14 · `scripts/build_dataset.py` sample data · `docs/` architecture, security, demo script, fixes.

All sample data is fictional. See `docs/FIXES.md` for what changed from v1 and `IMPLEMENTATION_STATUS.md` for what is and isn't verified.
