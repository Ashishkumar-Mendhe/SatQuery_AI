# SatQuery AI

SatQuery AI is an evidence-minded vision-language workspace under active development for multimodal remote-sensing image analysis through text queries. It is intended for analysts, researchers, planners, and other users who need to select or upload Earth-observation imagery, ask natural-language questions, and review answers alongside spatial evidence, provenance, uncertainty, limitations, and an execution trace.

The product is one unified professional geospatial workspace—there are no separate “Simple” and “Expert” modes. The workspace combines map/local AOI tools, real catalogue discovery, georeferenced visualization, two-date comparison, acquisition timeline, query/result panels, planned navigation, and inspectable empty states. Scientific analysis, measured evidence, and automated change results remain unavailable.

## Current repository state

Phase 2 now provides the responsive public homepage at `/` and the unified application workspace at `/workspace`. The workspace includes real connection-state handling, responsive navigation/panels, an editable question draft, accessible result tabs and help dialog, truthful empty states, and explicit unavailable-feature explanations. Its automated frontend checks and production build pass. Browser viewport inspection/screenshots could not run because the in-app browser connector failed before opening a tab, so Phase 2 is **PARTIALLY_VERIFIED**. See [the Phase 2 report](docs/PHASE_2_REPORT.md).

Phase 3 adds the MapLibre/OpenFreeMap basemap, Terra Draw rectangle/polygon editing, coordinate navigation, bounds entry, GeoJSON import/export, approximate geographic area, and validated browser draft persistence. It remains **PARTIALLY_VERIFIED**: real browser/WebGL checks and server-owned AOI implementation/verification are pending. Optional place search is unavailable until a suitable provider is configured. See [the Phase 3 report](docs/PHASE_3_REPORT.md).

Phase 5 is **COMPLETE** for its user-authorized imagery-viewer scope. The workspace searches real Earth Search Sentinel-2 metadata, resolves RGB COG assets server-side, serves bounded natural-colour WebMercator tiles, displays them in MapLibre, provides presentation controls, compares two actual dates, navigates loaded acquisitions, and restores validated browser-local viewer state. This is visualization only: it does not provide owned asset intake, scientific co-registration, analysis, change percentages, or confidence. See [the Phase 5 report](docs/PHASE_5_REPORT.md).

Phase 6 is **PARTIALLY VERIFIED** for its user-authorized optical processing-preparation working scope. Tasks 6A–6H implement closed contracts, calibrated AOI extraction, Sentinel-2 quality masks, common-grid pair preparation, bounded registration assessment, deterministic task readiness, durable protected jobs/artifacts, and the workspace quality panel. The complete non-database gate and real catalogue selection pass, but the real protected single/pair job, artifact/cache/interruption checks, and browser screenshots remain blocked by unavailable PostgreSQL/verified identity and browser sandbox metadata. No AI answer, change classification, or aggregate confidence exists. Stop before Phase 7. See [the Phase 6 report](docs/PHASE_6_REPORT.md).

Phase 7 is **PARTIALLY VERIFIED** after tasks 7A–7F. SatQuery has protected single-image inference jobs, exact chip/evidence artifacts, workspace question/caption/locate controls, and a pinned local box-grounding path. One real QA-ready Sentinel-2 chip reached the local detector and produced a source-bound box, but the box was over-broad. Live hosted VQA/caption are unavailable because runtime model settings are absent; production PostgreSQL/identity verification and a licence-reviewed annotated evaluation sample are also missing. No benchmark accuracy is claimed. See [the Phase 7 report](docs/PHASE_7_REPORT.md).

Phase 8 is **PARTIALLY VERIFIED** after 8F. SatQuery has a real direct optical pair preparation/change/measurement path and protected change job/API/artifact code, but production PostgreSQL/identity, protected real-job completion, and browser map verification remain open. See [the Phase 8 tracker](docs/PHASE_8_TASKS.md).

Phase 9 is **PARTIALLY_VERIFIED** after 9F. The workspace can select Sentinel-2 L2A and discover INPE Sentinel-1 RTC C-band scenes, display a dated SAR preview over the optical map, and request a protected job that summarizes separate calibrated source observations with coverage and limitations. Automated API/UI gates and the build pass, but the 9F real pair stopped at a trusted scientific raster read; a real protected optical/SAR job, browser inspection, independent cross-modal alignment, and NISAR PROVISIONAL HDF5 ingestion have not passed. PostgreSQL/verified identity, provider access, the browser bridge, and Earthdata staging remain gates. No fusion, flood/building cause, or model confidence is claimed. See [the Phase 9 report](docs/PHASE_9_REPORT.md).

Phase 10 tasks **10A–E** add typed conversation contracts, deterministic intent routing, protected bounded execution, durable owner-scoped context, and a partially verified workspace connection to `POST /api/v1/geoagent/conversations/{id}/turns` (with protected `GET`/`DELETE`). The assistant binds the current AOI and dated scenes, shows actual job/result evidence and can open an authorized committed change layer; changing inputs marks old answers stale. A queued job is not an answer. Backend map/AOI control remains unavailable; browser-local map actions do not bypass authorization. Apply Alembic head `20260926_0003` and configure a verified principal before conversational persistence; production identity/database and interactive browser success were not verified here. Phase 9's partial verification is unchanged. See [the Phase 10 checkpoint](docs/PHASE_10_TASKS.md).

Phase 1 separately remains **PARTIALLY_VERIFIED**: real PostgreSQL/PostGIS connectivity, Alembic migration verification, and database-backed readiness HTTP 200 remain unresolved. Later work does not waive those checks. Authentication, server-owned domain resources, uploads, general analysis, external object storage, and real reports remain unavailable.

## Documentation index

- [PRD.md](PRD.md): users, journeys, product requirements, scope, and acceptance criteria.
- [TRD.md](TRD.md): technical requirements, validation, jobs, integrations, operations, and deployment constraints.
- [ARCHITECTURE.md](ARCHITECTURE.md): current state, target components, flows, trust boundaries, and persistence.
- [FEATURES.md](FEATURES.md): stable feature inventory, dependencies, roadmap mapping, and status.
- [ROADMAP.md](ROADMAP.md): fixed Phase 0–15 roadmap and honest status.
- [CURRENT_PHASE.md](CURRENT_PHASE.md): active checkpoint and exact resume instructions.
- [TECH_STACK.md](TECH_STACK.md): confirmed baseline, proposals, and open technology decisions.
- [API_CONTRACT.md](API_CONTRACT.md): implemented health API plus future resource/job contracts.
- [DATABASE.md](DATABASE.md): implemented connection/migration baseline plus future logical schema.
- [TESTING.md](TESTING.md) and [SECURITY.md](SECURITY.md): verification and security requirements.
- [docs/DECISIONS.md](docs/DECISIONS.md): decision register.
- [docs/PHASE_0_REPORT.md](docs/PHASE_0_REPORT.md): Phase 0 inspection and handoff.
- [docs/PHASE_1_REPORT.md](docs/PHASE_1_REPORT.md): implementation evidence, verification, and remaining gate.
- [docs/PHASE_2_REPORT.md](docs/PHASE_2_REPORT.md): homepage/workspace implementation, interaction inventory, and visual-verification gap.
- [docs/PHASE_3_REPORT.md](docs/PHASE_3_REPORT.md): local map/AOI implementation, geometry/provider contracts, tests and remaining ownership/browser gates.

## Folder responsibilities

- `frontend/`: Next.js homepage and unified workspace presentation plus the runtime-validating health client; no protected data access or authoritative computation.
- `backend/`: FastAPI application/configuration/database foundation; future orchestration, adapters, and worker code stay separate.
- `shared/`: versioned, language-neutral schemas and shared contract resources; no shared secrets or server logic.
- `docs/`: decision records and phase/implementation reports.
- `scripts/`: PowerShell prerequisite and verification workflows.
- `tests/`: future automated tests and clearly identified synthetic fixtures.
- `data/`: conventions for ignored local imagery and generated artifacts; not production storage.

## Local setup (PowerShell)

Prerequisites are Node.js 24.x with npm 11.x, Python 3.13 or 3.14, and Docker with Compose v2. The checked-in `.nvmrc` and `.python-version` record the preferred lines.

```powershell
.\scripts\check-prerequisites.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Review .env and replace the local database password in both matching values.

py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
Push-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.lock
Pop-Location

Push-Location frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
Pop-Location

docker compose up --wait -d db
Push-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

For subsequent starts with the existing dependencies and local environment files, run the frontend and backend in two separate PowerShell terminals. Leave both terminals open while using SatQuery; closing a terminal or pressing `Ctrl+C` stops its server. Do not rerun dependency installation or migrations just to restart the UI/API. The database is required for successful readiness, but not for the homepage, workspace shell, or API liveness.

Frontend terminal:

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\frontend'
npm.cmd run dev
```

Backend terminal:

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\backend'
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000
```

Open the homepage at `http://localhost:3000/` or the workspace at `http://localhost:3000/workspace`. Both render when the API or database is unavailable. API documentation is at `http://127.0.0.1:8000/docs`; liveness and readiness are at `/api/v1/health/live` and `/api/v1/health/ready`. Liveness checks only the application process. Readiness is `200` only when PostgreSQL, PostGIS, and Alembic revision `20260926_0003` are all current; otherwise it returns a safe retryable `503`.

Task 6G adds protected preparation-job routes under `/api/v1/processing`, durable PostgreSQL job/artifact metadata, and an atomic private local artifact backend. The routes deny access until a verified identity resolver is configured; public catalogue and map viewing remain independent. Processing limits are configured with `PROCESSING_*` settings in `.env.example`. A usable environment now requires PostgreSQL/PostGIS at Alembic head `20260926_0003` and application injection of a verified `ProcessingPrincipal`; no client header or local bypass is provided. Task 6I verified that missing dependencies return explicit `503` responses rather than an accepted or fabricated result.

Phase 7 inference routes are under `/api/v1/inference` and require the same durable database and verified principal. VQA/caption require a server-only configured model: either `RUNTIME_AI_PROVIDER=openai`, `RUNTIME_AI_MODEL=gpt-4.1-mini-2025-04-14`, and `RUNTIME_AI_API_KEY`, or `RUNTIME_AI_PROVIDER=xai`, `RUNTIME_AI_MODEL=grok-4.3`, and `XAI_API_KEY`. Set the xAI key only in the repository-root ignored `.env` or backend process environment, never in chat, `frontend/.env.local`, or a `NEXT_PUBLIC_*` value. Both options receive the exact fixed-render scientific image chip, stable source ID and Phase 6 quality outcomes; neither is a measurement engine. Local Grounding DINO needs the locked `grounding` optional dependencies and cached pinned checkpoint; CPU cold start on the inspected i5-1235U/15.7 GiB host measured about 30 seconds, while CUDA was unavailable. Use the documented `http://localhost:3000` frontend origin: CORS is exact-origin and `http://127.0.0.1:3000` is intentionally distinct unless explicitly added to backend configuration. See `DEMO_HANDOFF.md` for the verified demo status and startup steps.

For NISAR 9C, public `/api/v1/nisar/search` needs no Earthdata credentials. `/api/v1/nisar/ingestions` can read pixels only after an operator signs in to NASA Earthdata Login on the backend host and stages the exact ASF HDF5 as `NISAR_PRODUCT_CACHE_ROOT/<concept-id>/<granule-ur>.h5`. The host can use `earthaccess.login()` and `earthaccess.download()` as described in the [NASA/ASF NISAR guide](https://nisar-docs.asf.alaska.edu/earthaccess/). Keep `.netrc` and credentials outside this repository and inspect the selected CMR concept ID before download. The backend uses pinned `h5py` to read the product's projection and coordinate axes; installed GDAL 3.12.4 did not georeference the official older sample subdataset. The [Phase 9 checkpoint](docs/PHASE_9_TASKS.md) records the tested granule and remaining authenticated live-ingestion gate.

Run all checks that do not require a database with `.\scripts\verify.ps1`. Run the isolated disposable PostGIS test as well with `.\scripts\verify.ps1 -IncludeDatabase`. Stop the persistent development database with `docker compose stop db`; its named volume is retained.

## Development workflow

Phase 3 provider configuration is documented in `frontend/.env.example`. The default map style is `https://tiles.openfreemap.org/styles/liberty`; no key is required. Leave source attribution visible. Configure custom public style/name values only for a compatible provider. `NEXT_PUBLIC_*` values are bundled into the browser and must contain no secrets.

Place search is optional and submit-only. Supply an HTTPS, CORS-enabled Nominatim-compatible endpoint whose usage agreement permits browser queries, plus its display name. Public `nominatim.openstreetmap.org` is deliberately rejected: the client does not enforce an application-wide rate limit across tabs/users. No geocoder credentials are installed. Restart the frontend after changing environment configuration. Coordinate navigation, bounds entry, and local AOIs remain independent of geocoding/database availability.

The selected AOI (`satquery.aoi-draft.v1`), catalogue selection (`satquery.scene-selection-draft.v1`), and safe viewer settings (`satquery.viewer-state.v1`) are saved only in this browser. Viewer restoration keeps stable identities, AOI binding, camera, display, comparison, and timeline state but never provider/tile URLs, credentials, expiry state, pixels, or render claims; imagery access is re-resolved. Use **Export** to download `satquery-selected-aoi.geojson` and **Clear AOI** to remove AOI-bound state. Local drafts are not server Saved AOIs or authenticated persistence.

1. Read `AGENTS.md`, `CURRENT_PHASE.md`, and the relevant authoritative documents.
2. Confirm the active phase and decision status before implementation.
3. Make the smallest coherent change, preserving existing work and contract consistency.
4. Run the checks required by `TESTING.md`; record passed, failed, and not-run checks.
5. Update the current phase checkpoint and phase report before handoff.

On Windows, commands are documented for PowerShell without assuming Bash syntax. Local `.env` files are ignored; never commit them or place secrets in `NEXT_PUBLIC_*` values.
