# Phase 4 tasks

Last updated: **2026-09-11**

The original agreed Phase 4 title remains unavailable. The user-authorized working scope is provider-neutral EO catalogue discovery and analytical asset selection. `docs/PHASE_4_IMPLEMENTATION_TRACKER.md` retains detailed acceptance and evidence.

## Current task state

| Task | Scope | Status |
|---|---|---|
| 4A | Provider-neutral catalogue request/normalized-scene contract | **COMPLETE — 2026-09-10** |
| 4B | Real backend catalogue provider connector: provider boundary plus one working STAC adapter, defaulting to Earth Search; collection discovery, AOI/time/cloud/sort search, item detail, bounded filter-preserving pagination, 4A normalization, restricted upstreams, timeout/retry/cache behavior, fixture tests, and one small live search | **COMPLETE — 2026-09-10** |
| 4C | FastAPI catalogue endpoints: public stateless collection listing, search, and item detail with authoritative validation, query-bound provider pagination, typed responses/request IDs, and classified failures | **COMPLETE — 2026-09-11** |
| 4D | Imagery search panel: selected-AOI context, live collection/date/cloud filters, runtime-validated catalogue results, honest thumbnail/metadata/error states, cancellation, and provider continuation | **COMPLETE — 2026-09-11** |
| 4E | Scene footprints and metadata-only selection: actual catalogue geometry on MapLibre, card/map synchronization, composite identity, selection details, fit/clear actions, AOI invalidation, style reload, and cleanup | **COMPLETE — 2026-09-11** |
| 4F | Versioned browser-local selection draft: stable scene identity, exact query context, safe provenance, current item-detail refresh, corrupt/stale handling, and honest local-only status | **COMPLETE — 2026-09-11** |
| 4G | Integration verification and Phase 4 handoff: live two-page/empty/detail workflow, controlled failures, repository gates, browser/database recheck, report, and exact resume instructions | **COMPLETE — 2026-09-11; PHASE PARTIALLY VERIFIED** |

## 4B boundaries

- Use a repository-approved provider if one exists; none was recorded before 4B, so use Earth Search at `https://earth-search.aws.element84.com/v1/`.
- Start with a suitable currently discovered Sentinel-2 Level-2A collection and do not add unrelated collections.
- Fetch STAC metadata only. Never bulk-download raster assets.
- Accept no arbitrary upstream URL. The configured provider origin/path policy applies to initial requests and pagination/item links.
- Preserve actual upstream metadata and null/unavailable fields; distinguish acquisition from retrieval time.
- Tests use clearly synthetic or captured-and-labeled fixture metadata and never provide a runtime fallback.
- Live verification is separate evidence. Failure leaves implementation intact and is reported as pending.
- Do not add a public FastAPI catalogue route, database table, or frontend catalogue UI in 4B.

## Carried gates

Phase 1 database, Phase 2 browser, and Phase 3 browser/authenticated-owner/persistence gates remain unwaived and unpassed. Git status/diff remain unavailable because this workspace has no `.git` metadata.

## 4G verification checkpoint — 2026-09-11

- Live FastAPI verification passed for collection listing, two exact query-bound pages with four distinct real Sentinel-2 IDs and zero duplicates, item detail/provenance/geometry/preview metadata, and an honest empty page. Controlled API failure tests passed for rate limit, unavailable upstream, and timeout envelopes.
- Focused available-workflow tests passed 20/20. The final repository script passed 68 non-database backend tests, all 74 frontend tests, Ruff, backend/frontend formatting, strict mypy/TypeScript, frontend lint, and production build; `pip check` passed.
- `scripts/verify.ps1` now uses the established 15-second Vitest timeout, and the scene integration test awaits propagated React state. These small verification fixes resolved the two failures found during 4G.
- Browser verification is not run: the connector failed before tab creation because `sandboxPolicy` metadata is missing. Direct preview bytes were blocked by the environment's unavailable loopback proxy. No screenshots, rendered WebGL/thumbnail, console/network, or laptop/mobile evidence is claimed.
- The isolated database workflow is blocked before Compose because Docker and PostgreSQL tools/listeners remain unavailable. Liveness is HTTP 200; readiness is separately HTTP 503 `DEPENDENCY_UNAVAILABLE` for `database` and is not reported as passed.
- Documentation/roadmap integrity passed with 26 relative links across 22 governed Markdown files, zero broken targets, 16 phase rows, one active phase row, and zero stale 4G status matches.
- Task 4G is complete, but Phase 4 remains **PARTIALLY VERIFIED** until the browser workflow and carried real PostgreSQL/PostGIS migration/readiness gate pass. Stop before Phase 5.

## 4F implementation checkpoint — 2026-09-11

- The explicit 4F instruction establishes browser-local, versioned selection persistence for the available scope. No authenticated owner integration exists, so no server/database persistence, asset intake, or migration was invented.
- The draft stores the selected scene's composite provider/collection/item identity, exact cursor-free query context, validated geometry, acquisition and retrieval times, source record/field provenance, licence/access state, and safe preview role/media metadata. It excludes provider cursors, preview URLs, expiry times, credentials, and raster data.
- Refresh restoration re-fetches current metadata through the existing SatQuery item-detail API. Corrupt/unsupported drafts are discarded; missing scenes remain visible as explicitly unavailable preserved context; provider failures remain stale with retry rather than becoming empty or current state.
- The details panel labels local durability as `Saved in this browser`, exposes refresh/clear controls, and continues to state that no raster is loaded and analysis is unavailable.
- Focused 4F and adjacent regression checks passed: 27 tests across 7 files, all 74 frontend tests, Biome format/lint, strict TypeScript, and production build. The first sandboxed focused-suite startup failed at Vite config loading with Windows `spawn EPERM`; its permission-scoped rerun passed. A live SatQuery item-detail request passed. Browser verification was not run because the connector failed before tab creation with missing `sandboxPolicy` metadata.
- Backend and database code were unchanged; no backend/database checks or migration verification were required or claimed. The carried real database gates remain unresolved.
- Documentation/roadmap integrity passed with 26 relative links across 22 governed Markdown files, zero broken targets, 16 phase rows, and one active phase row.
- **Historical 4F next action:** stop pending explicit 4G instruction. The 4G checkpoint above supersedes this boundary.

## 4E implementation checkpoint — 2026-09-11

- The user explicitly re-scoped 4E to scene footprints and selection. The workspace renders actual normalized Polygon/MultiPolygon geometry in dedicated MapLibre source/fill/line layers and keeps the active AOI independent and above catalogue footprints.
- Scene cards and map features synchronize hover and selection. Workspace-owned typed state uses provider ID + collection ID + item ID, supports clear and fit-to-scene, survives route-component remounts, and drives a metadata/details preview with honest missing-field/thumbnail fallbacks.
- AOI/filter changes retain old results only as clearly stale, invalidate obsolete requests, and clear/revalidate scene selection. Style reload restores footprint layers and state; map interaction listeners are removed on unmount. No preview is drawn as a raster overlay and no analysis capability is enabled.
- Seven focused 4E tests and all 66 frontend tests passed; Biome format/lint, strict TypeScript, and the production build passed. One sandboxed suite startup hit `spawn EPERM`; the first executing full suite found a test-only global mock ordering failure, fixed through explicit map-component injection before the clean rerun.
- `/workspace` returned HTTP 200. A live SatQuery API search returned actual scene `S2C_T43PGQ_20251228T052411_L2A`, Polygon geometry, its provider bbox, and a continuation cursor. Browser visual/WebGL verification remains not run because the in-app connector failed before tab creation with missing `sandboxPolicy` metadata.
- Documentation/roadmap integrity passed with 26 relative links across 22 Markdown files, zero broken targets, 16 phase rows, and one active phase row. The first audit ran from the wrong working directory and produced no valid counts; the repository-root rerun supplied this evidence.
- **Historical 4E next action:** stop after 4E pending explicit 4F instruction. The later 4F checkpoint above supersedes this boundary; analytical asset intake, authenticated ownership, server persistence, raster access, and analysis remain absent.

## 4C implementation checkpoint — 2026-09-11

- The user explicitly re-scoped 4C to FastAPI catalogue endpoints. Implemented `GET /api/v1/catalog/collections`, `POST /api/v1/catalog/searches`, and `GET /api/v1/catalog/collections/{collection_id}/items/{item_id}` using the 4A request/scene contract and the 4B configured provider.
- These routes expose public metadata only and are stateless: they do not query the database, persist the generated page `search_id`, create an owned asset, fetch raster bytes, or weaken authentication for any owned/protected resource. The existing readiness route still performs its database checks independently.
- FastAPI authoritatively validates the existing bounded AOI geometry, UTC-aware ordered acquisition interval, configured provider and allow-listed collection, provider-reported cloud percentage/semantics, page size, and cursor shape. Empty results are HTTP 200 empty pages; provider failure never becomes empty success.
- Earth Search continuation remains intact: the public opaque cursor carries only the bounded provider token plus provider/canonical-query binding, all filters are reconstructed locally, and mismatched cursors fail before a changed upstream search. Anonymous 4C cursors are not a contract for future owner-scoped saved searches, which require owner and expiry binding.
- Errors use the common request-ID envelope and distinguish validation/capability errors, missing items, rate limiting, invalid upstream metadata, unavailable upstream service, and timeout. Upstream `Retry-After` is bounded before exposure; credentials and unrestricted provider payloads are not returned or logged.
- Added 16 API tests using the production adapter behind FastAPI with controlled upstream responses and an unavailable database double. Focused catalogue/schema/provider verification passed: 49 tests. Final non-database backend verification passed: Ruff lint, Ruff format (35 files), strict mypy (35 source/test/script files), 68 tests, and `pip check`.
- Final live FastAPI smoke passed at `2026-09-11T09:58:30.595641Z`: `POST /api/v1/catalog/searches` returned HTTP 200, request ID `catalog-api-live-smoke`, actual item `S2C_T43PGQ_20251228T052411_L2A`, and a next cursor, while the database guard was not called. No raster was fetched.
- One attempted full-suite command failed because Windows shell parsing turned the pytest marker expression into a path and collected zero tests. The explicit `--ignore=tests\test_database_integration.py` rerun passed 68 tests. The guarded database integration test, frontend checks, and browser checks remain not run.
- **Changed files:** FastAPI catalogue route/dependency/router/lifespan/CORS wiring; catalogue collection response schemas; provider failure classification; API/provider tests; live API script; API/architecture/TRD/database/security/testing/feature/roadmap/decision contracts; Phase 4 tracker/report/checkpoint and session handoff.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, no broken targets, exactly 16 Phase 0–15 rows, and one active phase row.
- **Exact next action:** stop after 4C. Do not start 4D without a new instruction; its previous public-API portion is complete and its remaining authenticated/persistent boundary requires explicit re-scope.

## 4D implementation checkpoint — 2026-09-11

- The user explicitly re-scoped 4D to an imagery-discovery panel. It is embedded in the existing responsive workspace map-tool panel and consumes the public stateless 4C API; it adds no database, authentication bypass, saved search, selected analytical asset, or raster download.
- The UI shows the selected AOI summary, the server's allow-listed collections, inclusive UTC date boundaries, and provider-reported scene cloud threshold. Search/retry/load-more, loading, empty, validation, collection/provider failure, missing metadata, and failed-thumbnail fallbacks are implemented.
- A Zod client validates successful collection/search payloads and the common error envelope. Requests are abortable and sequence/fingerprint guarded; changed AOI/filter state cannot accept an outdated completion or use the prior query's continuation.
- Scene cards show real acquisition, provider/collection, platform/instrument/processing/access metadata and allowed provider thumbnails when available. Cloud is explicitly labeled scene metadata, and the count is the number loaded rather than a catalogue total.
- Frontend format, lint, strict type checking, optimized build, 9 focused tests, and all 59 frontend tests passed. A live two-page search through SatQuery's API returned actual Earth Search scenes and provider cursors. Browser verification was not run because the in-app connector failed before tab creation with missing `sandboxPolicy` metadata; direct preview retrieval was also blocked by the environment's unavailable proxy.
- The served workspace and configured frontend-origin catalogue POST preflight returned HTTP 200. The documentation/roadmap audit passed with 26 relative links across 23 governed Markdown documents, zero broken targets, 16 phase rows, and one active phase row.
- **Historical next action:** 4E had not yet been authorized at this checkpoint. The explicit later 4E instruction and completion checkpoint above supersede this stop boundary; authenticated persistence and asset intake remain absent.

## 4B implementation checkpoint — 2026-09-10

- Added the provider-neutral backend protocol and a metadata-only Earth Search adapter for `sentinel-2-c1-l2a`.
- Implemented capability/collection discovery, `intersects` search, acquisition interval, provider-reported cloud ceiling, deterministic acquisition sorting, item detail, 4A normalization, and acquisition/retrieval time separation.
- Opaque cursors are query-bound and extract only a bounded provider continuation token from an exact approved `POST /v1/search` link. All upstream metadata requests use the configured exact HTTPS origin, disable redirects, and have bounded timeouts, retries, response size, and TTL/LRU cache settings.
- Added a clearly marked captured-provider-metadata fixture that production code never imports. Ruff and strict mypy pass; 16 focused provider/config tests pass, including failure paths and proof that no raster URL is requested.
- Live adapter verification passed at `2026-09-10T16:10:27.358819Z`: STAC 1.0.0, queryable `eo:cloud_cover`, collection `sentinel-2-c1-l2a`, actual IDs `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`, a continuation cursor, and detail retrieval for the second item. No raster was fetched.
- Final verification passed: Ruff, Ruff format (32 files), strict mypy (32 source/test/script files), 51 non-database backend tests, and `pip check`. One guarded database integration test was deselected and remains not run. Task 4B is complete; stop before 4C.
- **Changed files:** provider protocol/adapter package; provider/config tests and captured metadata fixture; reusable live-smoke script; backend manifest/settings and root environment example; API/architecture/TRD/stack/security/testing/feature/roadmap/decision contracts; phase tracker/report/checkpoint and session handoff. The generated lock content was unchanged.
- **Blockers:** none within 4B. Carried database/browser/owner gates remain unwaived and unrelated later-task surfaces remain absent.
- **Exact next action:** stop after 4B. Do not start 4C; its former adapter scope was absorbed into 4B and it must be explicitly re-scoped before work.
