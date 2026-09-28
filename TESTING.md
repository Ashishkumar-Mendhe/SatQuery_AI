# Testing and verification strategy

## Phase 5 task 5F visual-comparison verification

`scene-comparison.test.ts`, `comparison-viewer.test.tsx`, and the workspace integration suite cover distinct chronological ordering, positive overlap, A/B assignment, swipe/split and side swap, guarded camera synchronization, keyboard divider semantics, linked/independent display values, one-side failure, resize, and cleanup. Synthetic maps prove state/lifecycle wiring only. Browser acceptance requires two exact real acquisitions and actual per-side tile-content events; map load alone is not rendering success. Correct placement is not co-registration or change evidence.

## Phase 5 task 5E display-control verification

Focused coverage in `backend/tests/test_imagery_tiles.py`, `frontend/src/lib/imagery-map-layer.test.ts`, and `frontend/src/components/workspace/scene-container.test.tsx` verifies the fixed preset boundary, invalid display/request parameters, visibility, opacity, brightness, contrast, saturation, reset defaults, unsupported-preset reasons, source/camera preservation, and AOI/scene retention. Synthetic map tests prove state wiring only. Live browser acceptance requires actual SatQuery tile traffic and must report provider partial/failure states truthfully.

## Phase 5 task 5D MapLibre imagery verification

Focused tests in `frontend/src/lib/imagery-tile-client.test.ts`, `frontend/src/lib/imagery-map-layer.test.ts`, and `frontend/src/components/workspace/scene-container.test.tsx` cover stable-only requests, wrong-scene/expired metadata, exact `xyz` metadata mapping, layer order, escaped attribution, imagery-only cleanup, ready/partial/failure events, removal preservation, and stale response rejection. They use synthetic maps and do not establish WebGL rendering.

The 2026-09-13 live Chrome check used WebGL2 and the existing workspace with a labelled synthetic context background. Real SatQuery z8 raster tiles rendered `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`, then scene switching removed it before rendering `S2B_T43PGQ_20251223T051848_L2A`. Exact UTC acquisition and attribution were visible. A genuine earlier upstream range-read failure produced the partial-tile state; retry at the bounded scene overview reached ready. Hiding the assistant changed the map canvas and backing buffer from 812 to 1204 pixels. This proves display only, not analysis readiness.

## Phase 5 task 5C imagery-tile verification

Task 5C adds `backend/tests/test_imagery_tiles.py` and `backend/scripts/verify_imagery_tiles.py`. Focused coverage verifies the closed stable-identity request, fixed recipe/dimensions, mediated metadata template, non-empty PNG delivery, invalid/unknown/outside tile coordinates, provider 403 access, renderer failure, local/internal/traversal destination rejection, and transparent nodata masks. Synthetic raster tests validate alpha behavior; they do not claim provider or browser rendering.

The live script resolves `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A` through SatQuery, requests WebMercatorQuad `z=8/x=183/y=118`, decodes the returned PNG, and fails unless it is 256×256 with real valid RGB pixels. The 2026-09-12 pass returned metadata/tile HTTP 200 with request IDs `phase-5c-live-metadata` and `phase-5c-live-tile`, 57,718 response bytes, 17,285 valid pixels, 48,251 transparent pixels, and valid RGB range 0–255. The database guard was untouched. This is server tile-delivery evidence only; MapLibre/WebGL rendering and analysis were not run.

## Phase 5 task 5B asset-resolution verification

Task 5B adds `backend/tests/test_asset_resolution.py` and `backend/scripts/verify_asset_resolution.py`. Synthetic tests deliberately use nonstandard provider asset keys and different per-band resolutions to prove mapping comes from STAC roles and `eo:bands`, not key conventions or shared-resolution assumptions. Coverage includes scale/offset/nodata/CRS/shape/transform preservation, thumbnail separation, no raster URL in the response, three bounded HEAD checks, missing RGB bands, unsupported formats, 403 credentials-required access, unapproved raster destinations, and rejection of client-supplied URL fields.

The live script calls `POST /api/v1/catalog/asset-resolutions` for the exact stable scene `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`. It fails if the database is touched and prints no raster location. The successful 2026-09-12 check returned HTTP 200/request ID `phase-5b-live-resolution`, status `supported`, component asset IDs `red`, `green`, `blue`, bands B04/B03/B02, EPSG:32643, 10 m, 10980×10980, scale 0.0001, offset −0.1, nodata 0, and three successful HEAD checks. Reported content lengths were provider headers, not downloaded bytes. This evidence proves current server-side metadata resolution/access only; tiles, browser/WebGL rendering, and analysis remain not run.

## Phase 5 task 5A contract verification

Task 5A has no asset resolver, route, tile service, raster request, map layer, viewer control, database write, or live browser-rendering behavior. Its executable gate is the closed Pydantic viewer contract plus matching Zod runtime/type contract using explicitly synthetic fixtures:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m ruff check src tests\test_viewer_schemas.py
..\.venv\Scripts\python.exe -m ruff format --check src tests\test_viewer_schemas.py
..\.venv\Scripts\python.exe -m mypy src tests\test_viewer_schemas.py
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_viewer_schemas.py

Set-Location ..\frontend
npm.cmd exec -- biome format src/lib/viewer-contracts.ts src/lib/viewer-contracts.test.ts
npm.cmd exec -- biome lint src/lib/viewer-contracts.ts src/lib/viewer-contracts.test.ts --error-on-warnings
npm.cmd run typecheck
npm.cmd run test:run -- src/lib/viewer-contracts.test.ts --testTimeout=15000
```

Coverage requires stable provider/collection/item identity; exact resolved asset identity/version; acquisition interval; visualization-only RGB/single-band render preset rules; valid WGS84 bounds; media type; attribution; catalogue/access/readiness distinctions; mediated relative tile templates, xyz markers, zoom/size/format, expiry and non-available behavior; bounded display settings; explicit render lifecycle; distinct chronological comparison A/B; unique chronological timeline membership; versioned closed saved state; and rejection of transient tile URLs/IDs, access/expiry, credentials, bytes, or rendering claims in saved state.

Task 5G additionally checks exact timestamp ordering including duplicate calendar dates/equal-time stable ordering, previous/next and rapid selection, stale AOI/filter invalidation, incomplete-pagination disclosure, partial comparison-slot retention, AOI/camera validation, corrupt state rejection, and fresh asset/tile resolution after reload without persisting delivery URLs.

Contract fixtures never establish a real provider asset, licence, access grant, tile, browser rendering, georeferencing, or analysis readiness. Later tasks must add focused resolver/authorization, tile delivery, MapLibre lifecycle, controls/accessibility, comparison, persistence, expiry/recovery, and live browser/WebGL checks as those behaviors are implemented. Metadata tests, HTTP success, or tile bytes cannot substitute for direct rendering evidence.

## Phase 4 task 4A contract verification

Task 4A has no provider, route, database table, or frontend behavior. Its executable gate is the Pydantic catalogue contract plus synthetic positive/negative fixtures:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m ruff check src tests
..\.venv\Scripts\python.exe -m ruff format --check src tests
..\.venv\Scripts\python.exe -m mypy src tests
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\test_catalog_schemas.py
```

Coverage requires Polygon/MultiPolygon shape and complexity, WGS84 order/bounds, antimeridian policy, UTC/date ordering, unique collections, cloud percentage/semantics, page/cursor limits, closed JSON schemas, normalized provider/scene metadata, footprint-derived bbox, preview URL/expiry rules, licence unknowns, analytical-access distinctions, required field provenance, provider/page consistency, and partial-response warnings. All scene/provider fixtures are explicitly synthetic and never establish real provider connectivity, imagery, licences, or access.

## Phase 4 task 4B provider verification

Task 4B adds `tests/test_earth_search_provider.py` and the clearly marked captured-metadata subset at `tests/fixtures/stac/earth_search_sentinel_2_c1_l2a.json`. Production code never imports this fixture and never uses it as fallback data. Coverage includes discovery/capabilities, AOI/time/cloud/sort request mapping, actual/null normalization, item detail, query-bound pagination, hostile next-link rejection, bounded transient retries, bounded cache eviction, content-type validation, unsupported filters/collections, and proof that no raster/thumbnail request is made.

The reproducible live metadata smoke is `..\.venv\Scripts\python.exe scripts\verify_earth_search.py`. It performs a two-item bounded search plus one item-detail lookup and prints the complete query, retrieval timestamps, and real returned IDs. Network/provider results must be recorded separately from fixture tests; failure remains pending and never enables fixture fallback.

Tasks 4C–4G must add API error/pagination, UI/accessibility, asset-selection provenance, authorization where protected resources exist, and real browser coverage as their behavior exists. No earlier-task test can mark those later checks passed.

## Phase 4 task 4C API verification

Task 4C adds `tests/test_catalog_api.py` and `scripts/verify_catalog_api.py`. The focused suite runs the real Earth Search adapter behind FastAPI with a controlled transport and an unavailable database double. It covers collection listing, successful search/item detail, nullable optional metadata, AOI/date/timezone/provider/collection/cloud/page-size validation, unsupported cloud semantics, actual continuation-token forwarding, cursor/query mismatch rejection, successful empty pages, rate limiting, upstream unavailability, upstream timeout, request IDs, and proof that provider failure is not serialized as empty success.

The live script sends one bounded `POST /api/v1/catalog/searches` through the application factory to configured Earth Search and fails if the catalogue route touches the database. Provider results are external evidence and must be recorded with their actual retrieval time and IDs. The public routes do not satisfy future authenticated saved-search, owned asset, database, frontend, or browser gates.

## Phase 4 task 4D frontend verification

Task 4D adds `src/lib/catalog-client.test.ts` and `src/components/workspace/imagery-discovery-panel.test.tsx`. Focused tests cover runtime response/error-envelope validation, exact selected-AOI queries, inclusive UTC boundaries, provider-reported scene cloud filtering, missing optional metadata/thumbnail fallbacks, outdated AOI responses, filter/result association, provider continuation, loaded-count wording, valid empty pages, provider errors, request IDs, and retry controls.

Run `npm run format:check`, `npm run lint`, `npm run typecheck`, `npm run test:run -- --testTimeout=15000`, and `npm run build` from `frontend/`. A live workspace check must create an AOI and search through SatQuery's API, inspect returned scene metadata/thumbnail behavior and load more, confirm map/AOI controls still work, and check responsive layout plus console/network errors. If the in-app browser cannot create a tab, record browser evidence as not run; direct API calls and component tests do not substitute for visual evidence.

## Phase 4 task 4E frontend verification

Task 4E adds `scene-selection.test.ts`, `scene-map-layers.test.ts`, and focused integration coverage in the workspace imagery/scene tests. Coverage requires composite provider/collection/item identity, exact catalogue Polygon/MultiPolygon use, distinct stale/hover/selected feature state, style-reload restoration, complete delegated-listener cleanup, card-to-map hover/selection, clearing, fit-to-scene, AOI-change invalidation, retained-selection revalidation, and route-component remount behavior. Tests must also confirm that scene selection leaves AOI state independent and does not imply raster access or analysis.

Task 4F adds `scene-selection-storage.test.ts` and `use-scene-selection-draft.test.tsx`, plus item-detail and restored-details coverage in the existing catalogue/panel suites. Coverage requires versioned round-trip restoration, composite identity and exact query binding, safe provenance/licence/access retention, exclusion of provider cursors and temporary/signed preview URLs, current item-detail refresh, corrupt/unsupported draft rejection, missing-item stale handling, provider retry state, and storage-write failure behavior. Tests must distinguish browser-local durability, advertised asset accessibility, and unavailable analysis.

## Phase 4 task 4G integration verification

Task 4G runs `scripts/verify.ps1`, focused catalogue workflow/component tests, controlled API failure tests, live collection/two-page/detail/empty requests through FastAPI, the browser workflow when available, and `scripts/verify-database.ps1` when its isolated Docker/PostGIS prerequisites exist. The repository script uses a 15-second Vitest timeout on the observed Windows host. Browser and database checks remain distinct from unit/component/API evidence and must never be inferred from liveness or synthetic transports.

Run the full Phase 4D frontend gate after focused 4E tests. Real browser verification should inspect footprint rendering and layering, card/map synchronization, clear/fit, AOI changes, remount behavior, preview containment, responsive panel resizing, and console/network errors. If the in-app connector fails before tab creation, record visual/WebGL evidence as not run; component/map-double tests and HTTP/API responses remain separate evidence.

## Phase 2 frontend verification

Run the Phase 2 frontend gate from `frontend/`:

```powershell
npm run format:check
npm run lint
npm run typecheck
npm run test:run
npm run build
```

`typecheck` generates typed App Router route declarations before running strict TypeScript. Vitest uses one forked worker for stable execution on the supported Windows development host. Focused tests cover homepage/workspace navigation targets, mobile navigation state, suggestion insertion, draft editing/clearing/preservation, sidebar and assistant controls, accessible tabs, dialog focus/Escape behavior, unavailable analysis, and ready/degraded/unreachable/unexpected connection states.

The final Phase 2 results are in `docs/PHASE_2_REPORT.md`: 20 frontend tests, format/lint/type checks, production build, and route HTTP smokes passed. Browser viewport, console, and screenshot review was **NOT RUN** because the in-app browser connector failed before creating a tab. This omission keeps Phase 2 `PARTIALLY_VERIFIED`; a build or HTTP 200 is not visual evidence.

## Phase 3 verification checkpoint

Run the existing frontend `format:check`, `lint`, `typecheck`, `test:run`, and `build` scripts from `frontend`. The Phase 3 suite adds synthetic geometry edge cases, coordinate/bbox/area invariants, import/export round trips, explicit geocoder configuration and provider failures, invalid/versioned storage, quota/denied-storage recovery, bounds/import selection preservation, and stale-import protection. The scene mock establishes UI/geometry boundaries only; jsdom has no real WebGL context. Current results and exact outstanding gates are in `docs/PHASE_3_REPORT.md`.

Real browser acceptance remains required: render provider resources, draw rectangle/polygon, drag vertices and finish/cancel, reject invalid imports without replacing the AOI, download and reimport the actual file, refresh/clear storage, pan/zoom/rotate/north/fit, resize sidebar/assistant, test laptop/mobile controls, inspect console/network and capture screenshots. Repeat local AOI editing with real readiness 503. Verify missing WebGL, provider failure/retry, and strict remount cleanup without duplicate controls/listeners. No mocked test or HTTP 200 establishes these results.

The final Phase 3 test invocation was `npm.cmd run test:run -- --testTimeout=15000`: 50 tests passed. The default five-second limit intermittently timed out in the existing typing test on this Windows host; a separate attempt timed out starting the fork worker. These failures and the passing rerun are retained in the report; the repository's default test configuration was not changed.

The Phase 3 ownership gate additionally requires an implemented authenticated AOI API/PostGIS schema and tests across two owners. These are not yet implemented; an unavailable database alone is not the only outstanding work.

## Phase 1 verification commands

The checked-in PowerShell workflows are the executable local gates:

```powershell
# Backend and frontend checks without external services
.\scripts\verify.ps1

# Also starts the isolated PostGIS service and exercises the real migration
.\scripts\verify.ps1 -IncludeDatabase
```

`verify.ps1` runs Ruff lint/format, strict mypy, non-integration pytest, Biome format/lint, strict TypeScript, Vitest, and the optimized Next.js build. `verify-database.ps1` accepts only a loopback `_test` database, starts the Compose `db-test` profile, runs Alembic from empty, verifies PostGIS and the expected revision through the real readiness code, checks Alembic current/head, then removes only the test container.

The Phase 1 results are recorded in `docs/PHASE_1_REPORT.md`. All non-database automated checks and HTTP degraded-state smoke checks passed. The real database/migration gate was **NOT RUN** because Docker/PostgreSQL/PostGIS are unavailable on the inspected machine. The in-app browser smoke was **NOT RUN** because the available browser connector could not establish its sandboxed session; the frontend server itself returned `200`, the production build passed, and component/client tests cover the status transitions. These omissions keep Phase 1 at `PARTIALLY_VERIFIED`.

## Phase 0 verification

Phase 0 uses lightweight inspection rather than an invented application test suite. Required checks are:

- all required documents/configuration and minimal directories exist and contain substantive, SatQuery-specific content;
- relative Markdown links and referenced repository paths resolve;
- project name, phase numbering, technology status, API resources/job states, database entities, and ownership/evidence terminology agree;
- PRD IDs map to technical requirements, feature IDs, and observable acceptance criteria;
- planned behavior is not presented as implemented and no later-phase runtime artifacts were added;
- `.env.example` contains no credentials, `.gitignore` excludes local secrets while allowing `.env.example` and small synthetic fixture conventions;
- structured configuration is syntactically valid where a suitable installed parser exists;
- `git diff --check` and intended-diff review run when the workspace is a Git repository; otherwise they are explicitly not run.

Actual commands/outcomes belong in `docs/PHASE_0_REPORT.md` and `CURRENT_PHASE.md`.

## Verification layers

| Layer | Required coverage |
|---|---|
| Unit/schema | Configuration validation; geometry/metadata rules; percentage denominators; state transitions; error serialization; tool argument validation; provenance/result schemas |
| API contract | OpenAPI/schema compatibility, statuses, pagination, timestamps, idempotency, concurrent mutation, unsupported/unavailable behavior, signed-access expiry |
| Authorization/security | Every resource and nested reference across two or more owners; upload limits; SSRF/redirect handling; injection/tool allow-list; secret/log redaction; deletion authorization |
| Database/migrations | Empty and upgrade migration paths, constraints, owner indexes, spatial indexes/query plans, job claiming races, cascade/tombstone lifecycle, backup/restore |
| Geospatial | Known CRS/axis-order fixtures, invalid geometry, georeferenced vs pixel-only inputs, nodata/valid masks, reprojection/resampling, overlap, area methods, antimeridian/poles where supported |
| Model/analysis | Versioned representative datasets, sensor/resolution/domain stratification, baselines, task metrics and thresholds, calibration where claimed, ambiguity/abstention, drift/regression |
| Adapter/integration | Contract fixtures plus opt-in sandbox tests for EO, storage, identity, queue, and AI; timeouts, rate limits, malformed payloads, missing credentials, and unavailable dependencies |
| Worker/reliability | Queue/claim, heartbeat/stall recovery, bounded retries, cancellation, idempotency, duplicate delivery, atomic result/artifact finalization, truthful nullable progress |
| UI/accessibility | Unified journeys, viewer/layer/evidence association, responsive states, keyboard/screen-reader coverage, textual evidence alternatives, error/expiry/reconnect behavior |
| End-to-end | Upload/select → validate → query → job → result/evidence; AOI discovery; comparison; compatible optical/SAR; unsupported/failure; history/report when implemented |

## Evidence rules for tests

- Synthetic fixtures must be named/labeled synthetic and never appear as real product results. Small textual/GeoJSON fixtures may be tracked under `tests/fixtures`; large imagery stays outside Git with documented retrieval/checksum/licensing.
- Expected measurements come from independently reviewed fixture truth or a declared algorithmic invariant, not copied uncritically from current output.
- Numerical tolerances include units, CRS, resolution, nodata, denominator, and platform/library sensitivity. Image snapshots alone cannot validate scientific correctness.
- Model scores, heuristic quality, calibrated probabilities, and task accuracy are tested/reported separately. Validate claims within the documented sensor, resolution, geography, and preprocessing domain.
- Every quantitative regression failure exposes the supporting asset/fixture, method/tool version, parameters, units, and relevant masks/assumptions.

## Test execution and gates

Every handoff states each relevant check as `PASSED`, `FAILED`, or `NOT RUN` with reason; no claim of a build, provider, database, browser, or model test is allowed without its output. CI selection is unresolved, but merges should ultimately gate format/lint/type/unit tests, contract drift, migrations, and targeted security checks, with slower geospatial/model/E2E suites scheduled according to cost and risk.
