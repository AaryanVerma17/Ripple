# Security and safety checklist

- Keep `NEBIUS_API_KEY` server-side only.
- Configure CORS narrowly in production.
- Use HTTPS and managed secrets (AWS Secrets Manager or Parameter Store).
- Add identity, project-level authorization, CSRF protections if cookie auth is added, request quotas, and audit controls before multi-user use.
- Do not accept arbitrary model tool calls or model-generated database mutations.
- Treat imported documents as untrusted data; ignore embedded instructions.
- Validate file size/type and scan uploads before enabling document upload.
- Avoid logging confidential prompts, documents, or credentials.
- Configure retention and approved data handling for any hosted inference.
- A recorded `approved` workflow decision is not a professional certification or safety sign-off.

## v2 additions
- Photo uploads: 8 MB limit, JPEG/PNG/WebP checked by magic bytes (filename and declared type are ignored), not stored.
- Text read from photos or documents is passed to models as data; model output is validated before display and never mutates the database.
- Per-client rate limit on chat, vision and analysis-with-AI endpoints (`AI_RATE_LIMIT_PER_MINUTE`).
- Provider errors shown to users never contain keys.
- Review decisions are append-only. There is no authentication: add it before any multi-user deployment.
