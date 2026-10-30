# What changed from v1

1. Over-flagging: the old engine marked every neighbour as an issue. Now each change has a kind; propagation follows kind-aware edge rules; checks are data-driven rules with recorded inputs.
2. Lost power chain and wrong direction (ChatGPT build's traversal) replaced by typed, directed traversal with isolation (regulator isolates the controller).
3. Decisions were overwritten; now append-only with full history. History shows the latest decision.
4. Missing data was guessed or ignored; now `unknown`, with dependent-parameter invalidation (changing rated voltage drops the rated current and speed unless supplied) and a "supply a value" flow.
5. Units were not checked; now dimension-checked and conversion-aware; mismatches are rejected with a clear message.
6. Model output was shown unvalidated; now JSON-parsed tolerantly and rejected if it contains unknown IDs, new numbers or approval language.
7. Frontend build failure (React Flow default import) fixed; type for `review_decision` added; full UI rewritten.
8. Docker: tests copied into the image, `.env` optional, healthchecks/restart, `npm ci`, `.dockerignore`.
9. API: upload limits and magic-byte checks, per-client rate limiting on AI endpoints, CORS limited to configured origins.
