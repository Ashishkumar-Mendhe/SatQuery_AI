# Frontend

This Next.js application provides the SatQuery public homepage and unified workspace shell. It owns presentation and local interaction state only; it has no server credentials, authorization decisions, analytical assets, or geospatial measurements.

```powershell
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` must include `/api/v1` and may contain only an HTTP(S) URL without credentials. The health client rejects malformed/unexpected JSON and distinguishes a reachable backend with unavailable database from network and configuration failures.

Run `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run test:run`, and `npm run build`, or use the root `scripts/verify.ps1` workflow.

Open `http://localhost:3000/` for the homepage and `http://localhost:3000/workspace` for the workspace. The workspace remains usable when the backend is unreachable or its database is unavailable. Suggested questions populate an in-memory draft but never submit analysis.

The central scene container is the Phase 3 integration boundary. No map engine, AOI drawing, upload, catalogue, analysis pipeline, fabricated result, or persistent history exists yet.
