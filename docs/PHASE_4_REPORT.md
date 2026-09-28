# Phase 4 — Original agreed title unavailable

Working scope: **Provider-neutral EO catalogue discovery and analytical asset selection**

Status: **PARTIALLY VERIFIED**. Tasks **4A — Catalogue contract**, **4B — Real catalogue provider connector**, **4C — FastAPI catalogue endpoints**, **4D — Imagery search panel**, **4E — Scene footprints and selection**, **4F — Selection persistence and provenance**, and **4G — Integration verification and handoff** are complete. Phase 4 is not marked complete because browser rendering/workflow evidence and the carried real PostgreSQL/PostGIS migration/readiness gate remain unpassed.

## Authority and scope

The repository does not contain the original agreed Phase 4 title. The user explicitly authorized catalogue-discovery/asset-selection work and tasks 4A–4G on 2026-09-10 without supplying that missing title. `ROADMAP.md` therefore preserves the exact placeholder “Original agreed title unavailable.” This report describes the authorized working scope without claiming recovery of the original roadmap wording.

The implementation tracker is `docs/PHASE_4_IMPLEMENTATION_TRACKER.md`. The current session was explicitly limited to task 4G verification and handoff.

## Carried gates

Phase 4 authorization did not waive earlier evidence gaps:

- Phase 1 real PostgreSQL/PostGIS migration and readiness-success checks: **NOT RUN**.
- Phase 2 responsive browser evidence: **NOT RUN**.
- Phase 3 browser/WebGL acceptance: **NOT RUN**.
- Phase 3 authenticated owner integration, server-owned AOI persistence, and two-owner authorization tests: **NOT IMPLEMENTED / NOT RUN**.

The local Phase 3 map/AOI workflow was preserved and not redone.

## Task 4A outcome

Added `backend/src/satquery/api/schemas/catalog.py`, a closed Pydantic contract with no route or provider dependency:

- request schema version, configured provider identifier, bounded RFC 7946 Polygon/MultiPolygon AOI, ordered UTC acquisition range, provider-scoped unique collections, provider-reported cloud filter, fixed sort modes, page limit, and opaque cursor;
- finite longitude/latitude validation, ring closure/distinctness/non-zero area/self-intersection checks, antimeridian rejection, and a 500-position total limit;
- normalized provider/collection/asset identity, acquisition interval, optional platform/instrument/product/band/polarization/resolution/cloud metadata, footprint, and footprint-consistent bbox;
- explicit thumbnail/preview access and expiry behavior, licence fields with nullable analytical permission, and analytical access states that distinguish metadata-only discovery from mediated/provider access;
- adapter/source-record metadata digest and field-level provenance requirements; and
- page/provider/count/limit consistency, required warnings for partial pages, bounded attribution/warnings, and JSON Schema generation.

Added `backend/tests/test_catalog_schemas.py` with explicitly synthetic fixtures. No fixture represents a real provider, scene, thumbnail, licence, or analytical asset.

## Task 4B outcome

Added a typed internal catalogue provider protocol and `EarthSearchCatalogueProvider`, restricted to Earth Search STAC v1 and the currently discovered `sentinel-2-c1-l2a` collection. It implements:

- live capability and allow-listed collection discovery;
- `intersects` AOI search with UTC acquisition interval, provider-reported `eo:cloud_cover` ceiling, deterministic acquisition/item-ID sorting, and explicit rejection of unsupported unknown-cloud inclusion;
- item-detail retrieval and 4A normalization with actual provider metadata, null/unavailable preservation, field provenance, metadata digest, and distinct acquisition/retrieval timestamps;
- bounded query-bound continuation cursors that accept only the provider token from an exact approved Earth Search `POST /v1/search` link and reconstruct all filters from the validated request;
- exact HTTPS provider origin/path enforcement, disabled redirects, timeouts, at most two transient retries after the initial request with bounded jitter, a 10 MiB metadata-response ceiling, and a configurable bounded TTL/LRU cache; and
- metadata-only asset inspection, an explicit public-thumbnail host allow-list, preservation of collection licensing/access uncertainty, and no raster download or public direct raster href.

`backend/tests/fixtures/stac/earth_search_sentinel_2_c1_l2a.json` is a clearly marked captured-provider-metadata subset used only by tests; production code does not import it and has no fixture fallback. `backend/scripts/verify_earth_search.py` is the reproducible bounded live check.

The live check at `2026-09-10T16:10:27.358819Z` searched the Polygon `[[77.5,12.9],[77.7,12.9],[77.7,13.05],[77.5,13.05],[77.5,12.9]]`, interval `2025-01-01T00:00:00Z/2025-12-31T23:59:59Z`, collection `sentinel-2-c1-l2a`, provider cloud ceiling 100%, descending acquisition sort, and limit 2. It returned actual item IDs `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`, reported cloud cover 28.287384 and 4.321234, produced a continuation cursor, and retrieved detail for the second item at `2026-09-10T16:10:28.160611Z`.

## Task 4C outcome

Added a lifespan-managed provider dependency and public stateless FastAPI routes for configured collection listing, catalogue search, and item detail. The search request is authoritatively validated by the 4A schema; collections and normalized scenes have typed responses; request correlation remains in `X-Request-ID` and the common error envelope.

Pagination retains Earth Search's actual continuation token in the opaque 4B cursor. The adapter binds it to the normalized provider/query/collection/filter/page-size/order digest, reconstructs filters locally, and rejects mismatches before changed upstream search. The API distinguishes valid empty pages from invalid requests, unsupported capability, item absence, rate limiting, malformed provider data, unavailable service, and timeout.

The routes are anonymous only for the configured public metadata adapter. They do not access the database, persist search pages, fetch rasters, create owned asset references, or weaken authentication on any protected resource. Future saved searches, private providers, and analytical intake remain subject to verified identity/owner authorization and require owner/expiry-bound pagination.

The final live API check at `2026-09-11T09:58:30.595641Z` sent a bounded request through `POST /api/v1/catalog/searches`, returned HTTP 200 with request ID `catalog-api-live-smoke`, actual item `S2C_T43PGQ_20251228T052411_L2A`, and a continuation cursor. A database double configured to fail on access was untouched. No raster was fetched.

## Task 4D outcome

Added an imagery-discovery panel to the existing scrollable workspace map-tool surface and connected it to the implemented public catalogue API. The panel summarizes the selected local AOI, lists server-allowed collections, uses inclusive UTC start/end day boundaries, and exposes a provider-reported scene cloud threshold for the optical Sentinel-2 collection.

The browser client validates collection/search success payloads and the common error envelope with Zod. It distinguishes cancellation, network, timeout, validation, rate limiting, provider failure, and malformed responses. An active request is aborted when its AOI/filter fingerprint changes, completions are additionally sequence/fingerprint guarded, prior results are labeled as stale, and stale pages cannot use their continuation. Load more forwards the API cursor unchanged. The UI reports scenes loaded rather than a catalogue total.

Scene cards use normalized API values for acquisition date, provider/collection, platform, instruments, processing level, scene cloud metadata, and asset-access state. Public/temporary provider preview URLs render as thumbnails; missing, restricted, or failed images use an honest fallback. No demo scenes, AOI/date broadening, database write, saved search, asset selection, raster acquisition, or analysis was introduced.

The focused 4D suite passed 9 tests and all 59 frontend tests passed. Biome format/lint, strict TypeScript, and the optimized Next.js build passed. A live search through the running SatQuery API returned `S2B_T43PGQ_20250226T051939_L2A` and `S2C_T43PGQ_20250221T052428_L2A`; the next cursor returned distinct IDs `S2B_T43PGQ_20250216T052111_L2A` and `S2C_T43PGQ_20250211T052056_L2A`. Responses included MSI, provider-reported scene cloud values, public preview references, and Earth Search/Copernicus attribution.

Browser visual/search verification is **NOT RUN**. The browser skill's required in-app connector failed before tab creation because its sandbox metadata lacked `sandboxPolicy`. A direct preview retrieval attempt also failed because the environment tried an unavailable loopback proxy. Therefore no responsive screenshot, rendered thumbnail, browser console/network inspection, or live browser interaction is claimed; component coverage and the live API check remain separate evidence.

## Task 4E outcome

Added actual normalized catalogue Polygon/MultiPolygon footprints to MapLibre through a dedicated GeoJSON source and fill/line layers. Current, stale, hovered, and selected appearances are distinct. The catalogue layers remain independent of the Terra Draw AOI, are restored after style reloads, and use delegated listeners that are removed on unmount. The existing ResizeObserver continues to handle panel-driven map resizing.

`WorkspaceShell` now owns a typed scene result context, hover key, and selected metadata context. The stable identity is the tuple of provider ID, collection ID, and provider item ID, preventing cross-provider and cross-collection collisions. Cards and map features synchronize hover/selection; select, clear, and fit-to-scene actions are available. The details view shows real available preview and normalized metadata with honest fallbacks, explicitly states that the preview is not a georeferenced map layer, and does not enable raster viewing or analysis.

AOI changes do not replace or modify the AOI from scene geometry. They mark prior results stale, invalidate obsolete requests through the existing fingerprint/abort controls, clear hover, and revalidate or clear the retained selection against the current query. Route-component remount state is retained at the workspace boundary.

Seven focused 4E tests cover composite identity, exact geometry, stale context, feature states, style restoration, listener cleanup, card/map synchronization, select/clear/fit, AOI change, and route remount. All 66 frontend tests, Biome format/lint, strict TypeScript, and the optimized build passed. The first sandboxed suite start failed with Windows `spawn EPERM`; the first executing full suite found one test-only global map mock ordering failure, corrected with an injected map component before the final 66/66 pass.

The served `/workspace` route returned HTTP 200. A bounded live request through the running SatQuery API returned HTTP 200, request ID `phase-4e-live-geometry`, actual item `S2C_T43PGQ_20251228T052411_L2A`, Polygon geometry, bbox `76.8405435490709,12.560413606130458,77.86185827663547,13.561138787915565`, and a continuation cursor. Browser visual/WebGL verification remains **NOT RUN** because the in-app connector again lacked required `sandboxPolicy` metadata before tab creation.

## Task 4F outcome

Added versioned browser-local persistence for the selected scene metadata context and the exact catalogue query that produced it. The draft is validated at read time and stores the composite provider/collection/original-item identity, cursor-free search request, acquisition and metadata-retrieval timestamps, normalized scene/footprint, source record/version, metadata digest, field provenance, licence, advertised access state, and safe preview role/media metadata.

The durable representation does not store provider cursors, preview URLs, expiry timestamps, credentials, raster URLs, or raster bytes. The workspace clearly says `Saved in this browser`; this is not a server/database save, owned asset reference, or authentication substitute. Catalogue selection, advertised asset accessibility, and unsupported analysis readiness remain separate states. The 4A contract requires no compact metadata-export operation, so 4F does not invent one.

On refresh, the workspace restores only a validated local draft and calls the existing SatQuery item-detail endpoint for current metadata. A successful refresh updates the safe draft. A missing scene retains the last validated metadata/provenance as explicitly unavailable context; transient provider failure marks it stale and offers retry. Corrupt, unsupported, or internally inconsistent stored data is removed without replacing it with demo content.

The focused 4F and adjacent scene suite passed 27 tests across 7 files; all 74 frontend tests passed. Biome format/lint, strict TypeScript, and the optimized Next.js build passed. The first sandboxed focused-suite startup failed at Vite config loading with Windows `spawn EPERM`; the permission-scoped rerun passed. A live item-detail request through SatQuery returned HTTP 200 for `S2C_T43PGQ_20251228T052411_L2A` with current retrieval/source/preview/licence/access metadata. Browser interaction verification is **NOT RUN** because the connector failed before tab creation with missing `sandboxPolicy` metadata. No backend/database code or migration changed, so no database persistence or database verification is claimed.

## Task 4G outcome

The complete available workflow was verified across the running SatQuery API and focused browser-boundary/component tests. `GET /catalog/collections` returned HTTP 200 with request ID `phase-4g-live-collections` and the single allow-listed `sentinel-2-c1-l2a` collection. A Bengaluru-area 2025 search returned HTTP 200 with request ID `phase-4g-live-page-1` and actual items `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`. Reusing the exact query with only its provider cursor changed returned HTTP 200 with request ID `phase-4g-live-page-2` and distinct items `S2A_T43PGQ_20251220T051243_L2A` and `S2C_T43PGQ_20251218T052410_L2A`; duplicate count was zero and a further cursor remained available. An initial ad hoc output field called `FiltersPreserved` evaluated false only because the response has no `limit` field; that invalid probe was discarded. The accepted query-bound cursor and unchanged request body are the filter-preservation evidence.

The first scene reported acquisition `2025-12-28T05:25:27.400000Z`, scene-level cloud cover `28.287384`, MSI, a public `image/jpeg` preview on the approved Earth Search S3 host, and a Polygon footprint with bbox `76.8405435490709,12.560413606130458,77.86185827663547,13.561138787915565`. Item detail returned HTTP 200 with request ID `phase-4g-live-detail-final`, the same stable source-record ID, and retrieval time `2026-09-11T16:07:52.846920Z`. A 1900 query returned an honest HTTP 200 empty page with request ID `phase-4g-live-empty`, zero items, and no cursor. Controlled route tests returned the documented `429 RATE_LIMITED`, `503 UPSTREAM_UNAVAILABLE`, and `504 UPSTREAM_TIMEOUT` envelopes and confirmed no provider failure becomes empty success.

Focused workflow tests passed 20/20 and cover valid AOI selection, exact search, continuation, honest thumbnail/metadata fallback, map hover/selection/fit/clear/remount, actual footprint state, refresh restoration, corrupt/unavailable drafts, AOI-change invalidation, empty results, provider error, and retry. The final repository gate passed Ruff, Ruff format for 38 backend files, strict mypy for 33 source files, 68 non-database backend tests, frontend format/lint for 54 files, strict TypeScript, all 74 frontend tests, and the optimized Next.js build. `pip check` also passed.

Two small verification defects were corrected: `scripts/verify.ps1` now applies the repository's established 15-second Vitest timeout, and the scene integration test awaits React's propagated hover/selection state. Before those fixes, one persistent run failed the default-timeout workspace test and the next failed the immediate hover assertion; the focused rerun and final full gate passed. A prior non-persistent command capture ended before a conclusive final status and is not counted as evidence.

Browser verification remains **NOT RUN**. The required in-app browser failed before tab creation because its session metadata lacks `sandboxPolicy`, so no screenshot, real WebGL footprint, thumbnail rendering, console/network inspection, refresh interaction, or laptop/mobile layout claim is made. The public thumbnail URL was inspected from validated metadata, but direct HEAD attempts failed first in the legacy PowerShell TLS path and then because the environment routed the S3 request through unavailable proxy `127.0.0.1`; preview bytes were not observed.

Database verification remains **BLOCKED / NOT RUN**. No Docker, Podman, `psql`, or `pg_isready` command and no database listener is available. `scripts/verify-database.ps1` stopped at its deliberate Docker preflight. Live liveness returned HTTP 200 with request ID `req_1eb6e17646f74d39aa635684051b5d17`; readiness separately returned HTTP 503 `DEPENDENCY_UNAVAILABLE` for `database`, request ID `req_04f0bef1260d476891f0fff25f598c85`, `Cache-Control: no-store`, and `Retry-After: 5`. Liveness is not presented as readiness.

## Startup instructions

From `C:\Desktop\SatQuery`, with the existing `.env`, frontend `.env.local`, locked dependencies, and virtual environment available:

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\backend'
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000
```

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\frontend'
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000/workspace`. Liveness is `http://127.0.0.1:8000/api/v1/health/live`; readiness is `http://127.0.0.1:8000/api/v1/health/ready`. When Docker is available, run `C:\Desktop\SatQuery\scripts\verify-database.ps1` from the repository root for the isolated PostGIS/migration/readiness gate.

## Contract boundary

Tasks 4A–4G add and verify the available public stateless catalogue metadata workflow, its workspace presentation, scene footprints, metadata-context selection, and versioned browser-local selection drafts. They do not add authentication integration, server/database persistence, owned analytical asset selection/intake, raster acquisition, or analytical pixels. Catalogue results remain metadata; previews and basemaps remain visualization; analytical access requires a separate authorized asset-reference/intake boundary.

The public semantics are synchronized in `API_CONTRACT.md`; technical boundaries are in `TRD.md` and `ARCHITECTURE.md`; server persistence remains unimplemented in `DATABASE.md`; security and test requirements are in `SECURITY.md` and `TESTING.md`. ADR-0024, ADR-0025, and ADR-0028 record the scope, catalogue, and local-draft decisions.

## Verification evidence

| Check | Result |
|---|---|
| Ruff lint, backend `src tests` | **PASSED** |
| Ruff format check, backend `src tests scripts` | **PASSED**, 32 files already formatted |
| Strict mypy, backend `src tests` plus live script | **PASSED**, 32 source/test/script files |
| Focused catalogue schema pytest | **PASSED**, 22 tests |
| Focused provider/config pytest | **PASSED**, 16 tests at the implementation checkpoint; final provider-only suite 11 tests |
| Full non-database backend pytest | **PASSED**, 51 tests; 1 integration test deselected |
| Backend installed dependency check | **PASSED**, no broken requirements |
| Pydantic JSON Schema generation | **PASSED** through focused tests; request/response schemas are closed and AOI uses a discriminator |
| Documentation links and roadmap integrity | **PASSED**; 26 relative links across 24 governed project documents, 16 phase rows, one active phase row |
| Frontend checks | **PASSED through 4G**; format, lint, strict type checking, production build, 20 focused workflow tests, and all 74 frontend tests |
| Real Earth Search metadata smoke | **PASSED**; collection/capability discovery, two-item search, continuation cursor, and one detail retrieval through the production adapter |
| Catalogue API route tests | **PASSED for 4C**, 16 tests through the FastAPI/adapter boundary |
| Database integration | **NOT RUN**; no Phase 4 migration exists and the carried runtime is unavailable |
| Browser catalogue workflow | **NOT RUN through 4G**; the in-app connector failed before tab creation because `sandboxPolicy` metadata was missing |
| Git status/diff | **NOT AVAILABLE**; the workspace has no `.git` metadata |

For task 4C, the combined API/provider/schema suite **PASSED**, 49 tests; the full non-database backend suite **PASSED**, 68 tests; Ruff, Ruff format for 35 files, strict mypy for 35 files, and `pip check` **PASSED**. The bounded live FastAPI request **PASSED** with the evidence recorded above. Database integration, frontend, and browser checks remain **NOT RUN**. One malformed marker-expression command **FAILED** after collecting zero tests; the explicit database-test ignore rerun passed 68 tests.

The final documentation/roadmap audit **PASSED**: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.

For task 4D, the focused client/panel suite **PASSED**, 9 tests; the complete frontend suite **PASSED**, 59 tests; Biome format/lint, strict type checking, and the optimized build **PASSED**. The live two-page FastAPI search **PASSED** with four distinct actual scene IDs and provider cursors. Browser rendering and direct preview-pixel verification remain **NOT RUN/FAILED BY ENVIRONMENT** as described above.

Intermediate outcomes are retained: an initial Vitest worker and the first post-compile build worker failed with Windows `spawn EPERM`; permission-scoped reruns passed. The first complete test run failed all 6 panel cases because the non-isolated suite had loaded the client before a global module mock; the panel now accepts a typed injected client for tests, and the final complete run passed 59/59. Initial format/lint/type fixture findings were corrected before the final clean checks.

The served `/workspace` route and configured frontend-origin catalogue POST preflight **PASSED** with HTTP 200. The final 4D documentation/roadmap audit **PASSED**: 26 relative links across 23 governed Markdown documents, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.

For task 4E, the 7 focused scene selection/map/integration tests **PASSED** and the complete frontend suite **PASSED**, 66 tests. Biome format/lint, strict TypeScript, and the optimized build **PASSED**. A live catalogue request through SatQuery returned actual Polygon geometry; `/workspace` returned HTTP 200. The first sandboxed suite startup failed with `spawn EPERM`, and the first executing suite failed one ordering-sensitive test due to a global map mock; explicit test component injection fixed it before the clean rerun. Browser rendering remains **NOT RUN** for the connector reason above.

For task 4F, the 27-test focused/adjacent suite and complete 74-test frontend suite **PASSED**. Biome format/lint, strict TypeScript, and the optimized build **PASSED**. A current item-detail request through SatQuery's API **PASSED** with HTTP 200 and the expected stable identity/provenance fields. Browser restore interaction is **NOT RUN** for the connector reason above. Backend and database checks are **NOT APPLICABLE** to the task because those surfaces did not change; the carried database integration gate remains **NOT RUN**.

For task 4G, the final `scripts/verify.ps1` run **PASSED** with 68 backend tests and 74 frontend tests plus every static/build gate. The focused available-workflow suite **PASSED**, 20 tests; the controlled provider-failure suite **PASSED**, 4 tests. Live collection, two-page search, detail, and empty-page requests **PASSED** with the exact evidence above. Browser and database gates remain **NOT RUN/BLOCKED** for the environment reasons above, so Phase 4 remains **PARTIALLY VERIFIED**.

The final 4G documentation/roadmap audit **PASSED**: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, one active phase row, and zero stale 4G status matches.

The final 4F documentation/roadmap audit **PASSED**: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.

The final 4E documentation/roadmap audit **PASSED**: 26 relative links across 22 Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row. A first combined audit was run from `frontend/`, could not resolve the root documents, and produced no valid counts; the repository-root rerun above is the recorded evidence.

## Files changed by task 4C

- `backend/src/satquery/api/routes/catalog.py`
- `backend/src/satquery/api/router.py`
- `backend/src/satquery/api/dependencies.py`
- `backend/src/satquery/api/schemas/catalog.py`
- `backend/src/satquery/main.py`
- `backend/src/satquery/providers/catalog/base.py`
- `backend/src/satquery/providers/catalog/earth_search.py`
- `backend/tests/test_catalog_api.py`
- `backend/tests/test_earth_search_provider.py`
- `backend/scripts/verify_catalog_api.py`
- The synchronized contracts and phase/handoff documents listed in the task checkpoint.

The first verification attempt found a mistyped Ruff target and static style/format/literal-annotation issues; focused assertions already passed. Those mechanical issues were corrected. A later Ruff rule required explicit `zip(strict=True)` and was corrected before the final clean gate. A temporary documentation typo in `DATABASE.md` was also caught and corrected before handoff.

## Files changed by task 4E

- `frontend/src/lib/scene-selection.ts`
- `frontend/src/lib/scene-selection.test.ts`
- `frontend/src/lib/scene-footprints.ts`
- `frontend/src/lib/scene-map-layers.ts`
- `frontend/src/lib/scene-map-layers.test.ts`
- `frontend/src/components/workspace/workspace-shell.tsx`
- `frontend/src/components/workspace/scene-container.tsx`
- `frontend/src/components/workspace/scene-container.test.tsx`
- `frontend/src/components/workspace/map-canvas.tsx`
- `frontend/src/components/workspace/imagery-discovery-panel.tsx`
- `frontend/src/components/workspace/imagery-discovery-panel.test.tsx`
- `frontend/src/app/globals.css`
- The synchronized contract, tracker, report, checkpoint, and handoff documents.

## Files changed by task 4F

- `frontend/src/lib/catalog-client.ts`
- `frontend/src/lib/catalog-client.test.ts`
- `frontend/src/lib/scene-selection.ts`
- `frontend/src/lib/scene-selection.test.ts`
- `frontend/src/lib/scene-selection-storage.ts`
- `frontend/src/lib/scene-selection-storage.test.ts`
- `frontend/src/lib/use-scene-selection-draft.ts`
- `frontend/src/lib/use-scene-selection-draft.test.tsx`
- `frontend/src/components/workspace/workspace-shell.tsx`
- `frontend/src/components/workspace/scene-container.tsx`
- `frontend/src/components/workspace/scene-container.test.tsx`
- `frontend/src/components/workspace/imagery-discovery-panel.tsx`
- `frontend/src/components/workspace/imagery-discovery-panel.test.tsx`
- `frontend/src/app/globals.css`
- The synchronized contract, decision, tracker, report, checkpoint, and handoff documents.

## Files changed by task 4G

- `scripts/verify.ps1`
- `frontend/src/components/workspace/scene-container.test.tsx`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`
- `ROADMAP.md`
- `docs/PHASE_4_TASKS.md`
- `docs/PHASE_4_IMPLEMENTATION_TRACKER.md`
- `docs/PHASE_4_REPORT.md`

## Files changed

- `backend/src/satquery/api/schemas/catalog.py`
- `backend/tests/test_catalog_schemas.py`
- `backend/src/satquery/providers/__init__.py`
- `backend/src/satquery/providers/catalog/__init__.py`
- `backend/src/satquery/providers/catalog/base.py`
- `backend/src/satquery/providers/catalog/earth_search.py`
- `backend/tests/test_earth_search_provider.py`
- `backend/tests/fixtures/stac/earth_search_sentinel_2_c1_l2a.json`
- `backend/scripts/verify_earth_search.py`
- `backend/src/satquery/core/config.py`
- `backend/tests/test_config.py`
- `backend/pyproject.toml`
- `.env.example`
- `docs/PHASE_4_IMPLEMENTATION_TRACKER.md`
- `docs/PHASE_4_REPORT.md`
- `API_CONTRACT.md`
- `TRD.md`
- `ARCHITECTURE.md`
- `DATABASE.md`
- `FEATURES.md`
- `ROADMAP.md`
- `TESTING.md`
- `SECURITY.md`
- `docs/DECISIONS.md`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`
- `frontend/src/lib/catalog-client.ts`
- `frontend/src/lib/catalog-client.test.ts`
- `frontend/src/components/workspace/imagery-discovery-panel.tsx`
- `frontend/src/components/workspace/imagery-discovery-panel.test.tsx`
- `frontend/src/components/workspace/scene-container.tsx`
- `frontend/src/components/workspace/workspace-shell.tsx`
- `frontend/src/app/globals.css`

The backend manifest changed to make the already locked `httpx2==2.12.0` a runtime dependency; regenerating `requirements.lock` produced no content change because the exact package was already locked through the development extra. `.env.example` gained non-secret server-only adapter settings. No local environment file, frontend source, provider credential, route, migration, database, or raster asset changed.

## Exact resume instructions

1. Read `AGENTS.md`, `SESSION_HANDOFF.md`, `CURRENT_PHASE.md`, this report, and the implementation tracker.
2. Preserve the task 4A schemas/tests and all carried gate wording.
3. Preserve completed tasks 4A–4G. Do not start Phase 5.
4. When the in-app browser is usable, run the documented end-to-end workflow at laptop and mobile sizes, capture non-secret screenshots, inspect console/network behavior, and verify real thumbnail/MapLibre rendering plus refresh/AOI-change behavior.
5. When Docker is available, run `scripts/verify-database.ps1`; require the isolated PostGIS integration test, exact Alembic head, and readiness HTTP 200 before changing Phase 4 to complete.
6. Keep provider credentials/access server-side; do not expose arbitrary URLs or imply that discovered metadata supplies analytical pixels.

Stop here after 4G. Phase 4 remains **PARTIALLY VERIFIED**; do not start Phase 5.
