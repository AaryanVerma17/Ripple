# Architecture and trust boundaries

## Request path
1. Next.js captures the proposal and calls FastAPI.
2. FastAPI validates typed inputs.
3. The engine loads the current fictional baseline, traverses explicit graph edges, and produces deterministic findings.
4. Optional Nebius model synthesis receives only the bounded report fields.
5. The result is stored as a JSON audit record and returned to the UI.
6. A reviewer can record a separate decision record.

## Trust boundaries
- Browser: no Nebius secret is present.
- API: only server-side component can call Nebius.
- Model: untrusted synthesis output; it cannot change deterministic statuses or persist decisions.
- Seed data: fictional; not production supplier specifications.
- Store: local JSON persistence is a hackathon simplification. For multi-instance production, replace it with PostgreSQL and migrations.

## Important engineering rule
A motor rated-voltage change is not itself proof that the driver input rail is out of bounds. Constraints must be attached to the correct entity, parameter, and applicability scope. Missing data yields `unknown`.
