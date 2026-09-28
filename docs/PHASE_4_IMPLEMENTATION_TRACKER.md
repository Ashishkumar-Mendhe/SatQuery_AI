# Phase 4 implementation tracker

Last updated: **2026-09-11**

## Phase identity and authority

The fixed roadmap's exact Phase 4 title remains **“Original agreed title unavailable.”** The repository contains no authoritative source for the missing original title, so this tracker does not invent or rename it.

The user explicitly authorized the following Phase 4 working scope on 2026-09-10: provider-agnostic Earth-observation catalogue discovery, search-result normalization, and analytical asset selection. This working scope implements the existing PRD/TRD/API/database requirements for catalogue discovery and asset identity while preserving the roadmap's unresolved original-title record.

## Carried gates

These are not Phase 4 task completions and are not waived:

- Phase 1: real PostgreSQL/PostGIS connectivity, Alembic migration, and readiness-success verification remain not run.
- Phase 2: responsive browser inspection/screenshots remain not run.
- Phase 3: real browser/WebGL acceptance remains not run.
- Phase 3: authenticated owner integration, server-owned AOI CRUD/PostGIS persistence, and two-owner authorization tests remain unimplemented/not run.

Phase 4 catalogue contracts may be designed independently. Protected runtime endpoints must remain backend-authorized and may not use a client-supplied owner or fabricated identity.

## Task map

| Task | Requirements and deliverable | Dependencies | Status |
|---|---|---|---|
| **4A — Catalogue contract** | Define provider-agnostic search request/response and normalized scene/asset metadata for AOI, date range, collection, cloud-cover, pagination, thumbnails/previews, provenance, and access semantics. Resolve contradictions across `PRD.md`, `TRD.md`, `ARCHITECTURE.md`, `API_CONTRACT.md`, and `DATABASE.md`. Add executable schema validation without implementing provider calls or routes. | Existing Phase 3 AOI geometry contract; PRD-DSC-001, PRD-AST-001, TRD-AST-001, TRD-GEO-001, TRD-INT-001. | **COMPLETE — 2026-09-10** |
| **4B — Real catalogue provider connector** | Define the typed backend provider boundary and implement one working STAC adapter, defaulting to Earth Search because no provider was previously approved. Include collection discovery, AOI/time/cloud/sort search, item detail, bounded filter-preserving pagination, 4A normalization, restricted upstreams, timeout/retry/cache behavior, fixture tests, and one small live search. | 4A; explicit user scope override on 2026-09-10. | **COMPLETE — 2026-09-10** |
| **4C — FastAPI catalogue endpoints** | Expose public stateless collection listing, catalogue search, and item detail through the configured adapter with 4A validation, query-bound provider continuation, typed responses/request IDs, safe differentiated errors, focused API tests, and one live request through SatQuery's API. | 4A–4B; explicit user re-scope on 2026-09-11. | **COMPLETE — 2026-09-11** |
| **4D — Imagery search panel** | Add workspace selected-AOI, collection/date/provider-cloud filters and real catalogue cards with runtime validation, loading/empty/error/retry states, request cancellation, query association, actual provider continuation, and honest thumbnail/metadata fallbacks. | 4A–4C; explicit user re-scope on 2026-09-11. | **COMPLETE — 2026-09-11** |
| **4E — Scene footprints and selection** | Render actual result footprints on MapLibre; synchronize hover/selection with cards; keep AOI independent; expose composite provider/collection/item identity in typed workspace state; add metadata details, clear, and fit actions; invalidate stale AOI context; restore layers and clean listeners. Selection remains metadata context and must not claim analytical readiness. | 4D; explicit user re-scope on 2026-09-11. | **COMPLETE — 2026-09-11** |
| **4F — Selection persistence and provenance** | Persist the selected metadata context and exact query as a versioned, validated browser-local draft; restore through current SatQuery item metadata; retain safe provenance; handle corrupt, stale, and unavailable scenes honestly; never imply server persistence, raster possession, or analytical readiness. | 4E; explicit user re-scope on 2026-09-11. Server persistence remains blocked on authenticated owner integration. | **COMPLETE — 2026-09-11** |
| **4G — Phase verification and handoff** | Run unit/schema, API, authorization, adapter, UI/accessibility, browser, provider-sandbox where configured, and contract-consistency checks. Update authoritative docs and report every external gate as passed, failed, or not run. | 4A–4F. | **COMPLETE — 2026-09-11; PHASE PARTIALLY VERIFIED** |

## 4A contract decisions

Status: **COMPLETE — 2026-09-10**. The executable schemas and synchronized core contracts were verified; no runtime provider/API/UI behavior is implied.

The contract must:

- accept only a validated RFC 7946 Polygon or MultiPolygon AOI in WGS84 longitude/latitude order, with explicit bounded complexity;
- require an ordered UTC acquisition date/time interval and reject reversed or invalid ranges;
- support provider-neutral collection collection identifiers without assuming cross-provider equivalence;
- treat cloud cover as an optional provider-reported filter/field whose meaning and source remain explicit;
- use bounded opaque cursor pagination with stable ordering and a nullable next cursor;
- normalize provider identity, provider asset ID/version, acquisition interval, platform, instruments, collection, product/processing level, footprint, bands/polarizations, resolution, quality metadata, and links without guessing unavailable values;
- distinguish thumbnail/preview visualization from analytical asset access;
- record provenance for every provider-derived value and retain raw-provider references only as safe, bounded identifiers/links rather than unvalidated payloads;
- distinguish catalogue discovery, asset-reference creation, metadata availability, and usable analytical-pixel access;
- represent unknown values as `null` or typed unavailable state, never fabricated defaults.

## 4A explicit exclusions

- No provider selection or network call.
- No catalogue endpoint or database table implementation.
- No frontend catalogue UI or asset-selection state.
- No synthetic scene presented as real provider data.
- No Phase 4B–4G implementation.
- No claim that a discovered scene is downloaded, owned, licensed for analysis, georeferenced locally, or analytically usable.

## 4A verification plan

- Validate executable request/response schemas with positive and negative synthetic fixtures.
- Verify OpenAPI-compatible schema generation through existing Pydantic/FastAPI tooling without adding a route.
- Run Ruff format/lint, strict mypy, and focused backend tests.
- Check cross-document terminology, links, Phase 0–15 row integrity, and carried-gate wording.
- Update `CURRENT_PHASE.md`, the Phase 4 report/checkpoint, `SESSION_HANDOFF.md`, and this tracker with exact results.

## 4A progress log

### 2026-09-10 — executable catalogue schemas

- Added provider-neutral Pydantic request/response models in `backend/src/satquery/api/schemas/catalog.py`; no route, provider, persistence, or UI code was added.
- Added synthetic positive/negative contract fixtures in `backend/tests/test_catalog_schemas.py`. Fixtures are explicitly synthetic and convey no real imagery, provider availability, or access rights.
- Final focused results after strengthening geometry/bbox/strict-number coverage: Ruff lint **PASSED**; Ruff format check **PASSED**; strict mypy **PASSED** for 26 source/test files; focused pytest **PASSED**, 22 tests.
- Initial static check exposed a mistyped Ruff target plus style, formatting, and literal-annotation issues. Those mechanical issues were corrected; no assertion failed.
- Changed files so far: `docs/PHASE_4_IMPLEMENTATION_TRACKER.md`, `backend/src/satquery/api/schemas/catalog.py`, and `backend/tests/test_catalog_schemas.py`.
- Full backend non-database regression: **PASSED**, 37 tests; the guarded integration test was deselected and not represented as passed.
- Final documentation/roadmap audit: **PASSED**, 26 relative links across 27 project documents, exactly 16 roadmap phase rows, and exactly one active phase row.
- Core contracts and status records were synchronized; see `docs/PHASE_4_REPORT.md` for decisions, changed files, and exact evidence.
- At task start, the next user request explicitly expanded 4B to include the real provider connector. `docs/PHASE_4_TASKS.md` records that override; 4B then became **IN PROGRESS** and 4C required later re-scoping. The task 4B completion checkpoint below supersedes this historical state.

### 2026-09-10 — task 4B start

At this implementation checkpoint, the provider-neutral protocol and constrained Earth Search `sentinel-2-c1-l2a` adapter were implemented. It is metadata-only, uses exact-origin/path enforcement, and includes query-bound pagination plus bounded retry/cache behavior. Ruff and strict mypy passed; 16 focused tests passed using a clearly marked captured-metadata fixture. The later completion checkpoint below supersedes the then-pending live and full-backend checks.

- Confirmed no repository-approved EO provider was recorded, so the user-authorized default is Earth Search.
- Confirmed `docs/PHASE_4_TASKS.md` was missing and created it before connector implementation.
- Historical next action at task start: discover Earth Search conformance/collections/search fields, then implement the backend connector and tests. This action is complete; use the completion checkpoint below for current status.

### 2026-09-10 — task 4B completion

- Live production-adapter check at `2026-09-10T16:10:27.358819Z` discovered STAC 1.0.0, queryable `eo:cloud_cover`, and `sentinel-2-c1-l2a`; the bounded Bengaluru-area 2025 search returned actual IDs `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`, created a continuation cursor, and retrieved the second item's detail. No raster request was made.
- The first live adapter check exposed Earth Search's standard `application/schema+json` queryables response. The metadata validator was corrected to accept `application/json` and standard `application/*+json` types, and a regression test was added. Two earlier inline smoke commands failed only at local Python parsing before adapter/network execution; the checked-in reproducible script replaced them.
- Final backend checks: Ruff passed; Ruff format passed for 32 files; strict mypy passed for 32 source/test/script files; 51 non-database tests passed with one guarded database integration test deselected; `pip check` reported no broken requirements.
- Task 4B is complete. Exact next action: stop. Do not start 4C; its scope must be explicitly redefined because its former adapter deliverable was absorbed into 4B.
- Final documentation/roadmap audit passed: 26 relative links across 24 governed Markdown documents, exactly 16 phase rows, and exactly one active phase row.

### 2026-09-11 — task 4C completion

- Added lifespan-managed provider injection and the three public stateless routes documented in `API_CONTRACT.md`. Search uses the closed 4A schema; collection and item output is typed; all responses retain `X-Request-ID`.
- Kept public metadata discovery independent of PostgreSQL/PostGIS. No search page is persisted, and no authenticated/owned resource, frontend behavior, analytical asset, raster request, or provider credential boundary was added.
- Added explicit API mappings for invalid request/cursor, unavailable capability, missing item, rate limiting, malformed provider response, upstream outage, and timeout. Valid no-match searches remain distinguishable HTTP 200 empty pages.
- Added 16 focused API tests plus a POST CORS regression. The focused API/provider/schema suite passed 49 tests; Ruff, format, strict mypy, all 68 non-database tests, and `pip check` passed. One malformed pytest marker invocation collected zero tests and failed; its explicit-ignore replacement passed.
- The final bounded live API script passed at `2026-09-11T09:58:30.595641Z` with HTTP 200, correlated request ID, actual item `S2C_T43PGQ_20251228T052411_L2A`, a continuation cursor, and no database access. No raster was fetched.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, zero broken targets, 16 phase rows, and one active phase row.
- Task 4C is complete. Exact next action: stop before 4D; its residual authenticated/persistence scope requires an explicit instruction and the unresolved identity/owner decision remains unwaived.

### 2026-09-11 — task 4D completion

- Added a Zod catalogue client and responsive imagery-discovery panel in the existing workspace tool surface. The exact selected AOI, inclusive UTC day boundaries, server-listed collection, and applicable provider-reported scene cloud threshold form each search.
- Added explicit loading, empty, validation, provider/error-envelope, retry, load-more, missing-metadata, and thumbnail-failure states. Cards display only real normalized API metadata and describe cloud values as scene metadata, not AOI measurements.
- Active requests are aborted on filter/AOI changes and guarded by sequence plus query fingerprint. Results retain their originating query; stale cards are labeled and cannot paginate. Load more forwards the API cursor unchanged and loaded-card counts are not called totals.
- Focused client/component tests passed 9 tests and the full frontend suite passed 59. Biome format/lint, strict TypeScript, and the Next production build passed.
- Earlier attempts are recorded: Vitest and the build initially hit Windows worker `spawn EPERM`; permission-scoped reruns passed. The first full-suite run found non-isolated module mocking and failed the 6 panel cases; dependency injection replaced the global module mock and the complete rerun passed. Initial formatter/linter/type fixture findings were corrected before the clean gate.
- A live two-page request through the running FastAPI application returned four distinct actual Sentinel-2 item IDs, provider cloud/MSI metadata, public thumbnail references, and continuation cursors. Browser search/screenshots were not run because the in-app connector failed before tab creation with missing sandbox metadata; the environment also blocked direct thumbnail retrieval through its unavailable loopback proxy.
- The served workspace and catalogue POST CORS preflight returned HTTP 200. Documentation/roadmap integrity passed with 26 relative links across 23 governed Markdown documents, no broken targets, exactly 16 phase rows, and one active phase row.
- Historical 4D stop boundary: 4E was not authorized at that checkpoint. The later explicit 4E instruction and completion record below supersede it; no analytical asset, persistence, owner integration, raster bytes, or analysis was added by 4D.

### 2026-09-11 — task 4E completion

- Added typed workspace scene context and composite provider/collection/item selection identity, actual catalogue GeoJSON footprint layers, distinct current/stale/hover/selected styling, card/map synchronization, clear/fit actions, and metadata-only details with provider previews kept out of the map.
- AOI changes mark results stale and clear/revalidate selection without modifying the AOI from scene actions. Map style reload restores source/layers/feature state, delegated listeners are removed on unmount, and existing ResizeObserver behavior remains intact.
- Seven focused 4E tests and the complete 66-test frontend suite passed. Biome format/lint, strict TypeScript, and the optimized Next build passed. The initial sandboxed suite startup failed with `spawn EPERM`; the first executing full suite exposed test-only global mock leakage, corrected with explicit component injection before the final pass.
- `/workspace` returned HTTP 200 and a bounded live SatQuery API search returned an actual Polygon footprint/bbox for `S2C_T43PGQ_20251228T052411_L2A`. Browser visual/WebGL verification remains not run because the connector failed before tab creation with missing `sandboxPolicy` metadata.
- The final documentation/roadmap audit passed: 26 relative links across 22 Markdown files, zero broken targets, exactly 16 phase rows, and one active phase. A wrong-working-directory attempt produced invalid empty counts and was replaced by the repository-root rerun.
- Historical 4E stop boundary: stop before 4F. The later explicit 4F completion below supersedes it; 4E added no owned asset, persistence, raster bytes, georeferenced raster layer, or analysis.

### 2026-09-11 — task 4F completion

- Added a versioned `satquery.scene-selection-draft.v1` browser draft for the composite scene identity and its exact cursor-free catalogue query. Runtime validation covers identity/query agreement, ordered UTC dates, bounded AOI geometry, footprint/bbox agreement, acquisition ordering, and safe licence references.
- The durable form preserves acquisition/retrieval time, source record/version, metadata digest, field provenance, licence, advertised asset-access state, and available preview role/media metadata. It deliberately excludes preview URLs, expiry timestamps, provider cursors, credentials, and raster bytes.
- Restoration immediately exposes only previously validated metadata context and re-fetches current item detail through SatQuery's API. Missing scenes are retained as explicitly unavailable provenance; other provider failures remain stale with retry; corrupt or unsupported drafts are discarded.
- Focused 4F plus adjacent scene regression verification passed 27 tests across 7 files; all 74 frontend tests passed. Biome format/lint, strict TypeScript, and the optimized build passed. The first sandboxed focused-suite startup failed at Vite config loading with Windows `spawn EPERM`; its permission-scoped rerun passed. A live item-detail request through SatQuery returned current metadata for the selected Earth Search scene.
- Browser verification was not run because the connector failed before tab creation with missing `sandboxPolicy` metadata. Backend/database code and migrations were unchanged; no database persistence is claimed and the carried database gates remain unverified.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.
- Historical 4F stop boundary: stop before 4G. The explicit 4G completion below supersedes it; 4F added no owned asset, server persistence, raster acquisition, or analysis.

### 2026-09-11 — task 4G completion

- Live FastAPI checks passed for collection discovery, two provider-cursor pages with four distinct actual Sentinel-2 scenes and no duplicates, current item detail, actual footprint/bbox, preview metadata, and a successful empty page. The unchanged query plus accepted query-bound cursor is the filter-preservation evidence.
- Controlled route tests passed for HTTP 429/503/504 provider failures without empty-success conversion. Focused workflow tests passed 20/20 across AOI, continuation, selection/map, restore, stale AOI, empty, and retry behaviors.
- Final `scripts/verify.ps1` passed 68 non-database backend tests, 74 frontend tests, all format/lint/type gates, and the production build; `pip check` passed. The script's Vitest timeout and one asynchronous test assertion were corrected during verification.
- Browser workflow/screenshots remain not run because the connector lacks `sandboxPolicy`; direct preview bytes were blocked by the unavailable loopback proxy. Database integration remains blocked at the safe Docker preflight, and readiness remains an honest HTTP 503 database dependency failure.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, one active phase row, and zero stale 4G status matches.
- Task 4G is complete. Phase 4 remains **PARTIALLY VERIFIED** pending the browser and carried real PostGIS/migration/readiness gates. Stop before Phase 5.

## Persistent execution rules

- Keep frontend, backend, database, and documentation contracts synchronized.
- Provider credentials and protected provider access remain server-side.
- A basemap is visualization only; a catalogue result is metadata only; analysis requires an identified and usable analytical asset.
- Never fabricate provider data, search results, access status, measurements, coordinates, progress, or verification evidence.
- After every major task, update this tracker and `SESSION_HANDOFF.md` with exact changed files, checks, blockers, and the next task.
- Never mark an unexecuted check as passed.
