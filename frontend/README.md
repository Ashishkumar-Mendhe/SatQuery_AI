# Frontend

This Next.js application provides the SatQuery public homepage and unified workspace shell. It owns presentation and local interaction state only; it has no server credentials, authorization decisions, analytical assets, or geospatial measurements.

```powershell
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
npm run dev
```

`NEXT_PUBLIC_API_BASE_URL` must include `/api/v1` and may contain only an HTTP(S) URL without credentials. The health client rejects malformed/unexpected JSON and distinguishes a reachable backend with unavailable database from network and configuration failures.

Run `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run test:run`, and `npm run build`, or use the root `scripts/verify.ps1` workflow.

Open `http://localhost:3000/` for the homepage and `http://localhost:3000/workspace` for the workspace. The map and local draft remain usable when the backend is unreachable, but protected analysis cannot run without the configured backend, database and verified identity. The Phase 10E assistant sends the current AOI and selected scene(s) to the owner-scoped GeoAgent conversation turn API; suggested questions only populate the draft until the user submits. It then displays actual job state and committed evidence, or an explicit clarification/unavailable/failure. The conversation UUID is browser-tab session storage; raw messages and model outputs are not stored there. Changing inputs marks prior results stale and removes their map overlay. Existing result and tile routes still enforce backend authorization. See [the Phase 10 checkpoint](../docs/PHASE_10_TASKS.md) for unresolved live/browser verification and Phase 7–9 prerequisites.
