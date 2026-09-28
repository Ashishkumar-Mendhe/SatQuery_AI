# Phase 5 — Original agreed title unavailable

Last updated: **2026-09-15**

The repository's exact Phase 5 title remains **“Original agreed title unavailable.”** The user-authorized working scope is imagery viewer preparation, asset resolution, tiles, display controls, comparison, timeline/state, and verification through tasks 5A–5H. This tracker does not claim recovery of the missing original roadmap wording and does not assign scientific processing or analysis from later roadmap phases to Phase 5.

## Current task state

| Task | Scope and mandatory requirements | Status |
|---|---|---|
| 5A | Define closed typed contracts for stable scene identity (`provider`, `collection`, `item`); resolved imagery assets and supported render presets; tile metadata, WGS84 bounds, attribution, and access status; active imagery layer and display settings; comparison scene A/B with acquisition timestamps; timeline selection; and versioned saved viewer state. Keep catalogue availability, asset accessibility, successful rendering, and analysis readiness separate. Review the contracts with existing schema/type/test tooling and synchronize governing documentation. | **COMPLETE — 2026-09-12** |
| 5B | Resolve the selected catalogue scene through a FastAPI-owned, provider-neutral asset boundary. Validate identity and current provider metadata, allow-list provider asset roles/render presets, keep credentials server-side, classify licence/authorization/expiry/failure states, and return no usable resolved asset until required access and metadata checks pass. Do not perform scientific preprocessing or claim analysis readiness. | **COMPLETE — 2026-09-12** |
| 5C | Expose authorized imagery delivery through bounded tiles using the 5A tile contract. Enforce provider/destination policy, access expiry, bounds/zoom/media metadata, attribution, request correlation, and classified failures; never persist or log signed URLs. Prove tile availability separately from successful browser rendering and analytical usability. | **COMPLETE — 2026-09-12** |
| 5D | Add the imagery layer to the existing MapLibre workspace without replacing the AOI, catalogue footprints, or basemap responsibility. Bind it to exact resolved scene/asset/preset identity, show loading/ready/error/expired states truthfully, preserve layer order and style-reload cleanup, and record real browser/WebGL evidence before claiming rendering success. | **COMPLETE — 2026-09-13** |
| 5E | Add bounded viewer controls for supported render preset, visibility, opacity, brightness, contrast, and saturation using the 5A display contract. Keep controls accessible, resettable, and presentation-only; visual adjustments must not be described as scientific processing or evidence. | **COMPLETE — fixed natural-colour recipe plus debounced MapLibre display controls verified; unsupported presets disabled with reasons** |
| 5F | Add comparison scene A/B selection with stable identities and explicit UTC acquisition timestamps. Require distinct scenes and deterministic temporal ordering while keeping visual comparison readiness separate from later CRS/resolution/alignment/valid-overlap and scientific compatibility checks. | **COMPLETE — two real dates rendered in synchronized swipe/split views; visual-only boundary preserved** |
| 5G | Add timeline selection and versioned saved viewer state. Runtime-validate restoration, bind it to exact scene/asset/preset identities, exclude credentials and durable signed/tile URLs, handle missing/expired resources explicitly, and label browser-local versus future authenticated persistence truthfully. | **COMPLETE — actual acquisitions, navigation/comparison assignment, stale/incomplete-page handling, and browser-local restoration verified** |
| 5H | Run focused contract, failure-path, API, frontend, production-build, browser/WebGL, and documentation-consistency checks proportionate to implemented work. Recheck carried database/browser gates independently and report each check as passed, failed, blocked, or not run without treating liveness, tile access, or metadata discovery as rendering/analysis evidence. | **COMPLETE — 2026-09-15; integrated real-browser/API/security gates pass, database gate remains independently blocked** |

## Contract distinctions

The four capability states are independent and must never be collapsed:

1. **Catalogue availability** — normalized metadata for a stable scene identity is discoverable.
2. **Asset accessibility** — a specific imagery asset can be resolved under current access/licence policy.
3. **Successful rendering** — the browser has actually loaded and rendered the resolved imagery layer.
4. **Analysis readiness** — an identified asset has passed the separate ingestion, georeferencing, metadata, authorization, and method-specific validation required by a later analysis phase.

A higher-numbered state is never inferred from an earlier one. A basemap, catalogue footprint, thumbnail, advertised provider reference, tile contract, or successful display is not an analytical asset and cannot enable analysis.

## Shared execution rules

- Complete only the requested subtask and stop.
- Update this checkpoint after meaningful edits and checks.
- Preserve the existing architecture, package workflows, authentication boundaries, and truthful health reporting.
- Continue independent work when an unrelated database check is pending; do not waive or misreport that check.
- Keep final responses under ten lines.
- Preserve scientific processing, comparison validation/alignment, and analysis within their later roadmap phases.
- Never claim tests, tile delivery, browser/WebGL behavior, or live rendering passed without direct evidence.
- Keep provider credentials and protected asset access server-side. Treat signed or temporary URLs as delivery mechanisms, never stable identities or durable saved state.
- Validate all provider payloads, restored browser state, identifiers, bounds, timestamps, settings, and access transitions at their owning boundary; unknown values remain null or explicitly unavailable.

## Carried requirements and evidence gaps

- Phase 4 tasks 4A–4G are complete, but Phase 4 remains **PARTIALLY VERIFIED**.
- The required in-app browser still could not create a tab (`sandboxPolicy` was missing), but the 5D fallback Chrome/WebGL run exercised live catalogue search/selection, provider thumbnail display, scene/AOI overlays, network requests, and panel resizing. Phase 4's explicit refresh interaction and full viewport/download-reimport acceptance set remain unpassed, so Phase 4 stays partially verified.
- The real PostgreSQL/PostGIS migration/readiness-success gate remains **BLOCKED / NOT RUN** because Docker/PostgreSQL tooling and a database listener are unavailable. Liveness HTTP 200 and readiness HTTP 503 are separate, truthful states.
- Phase 3 authenticated owner integration and server-owned AOI persistence remain unimplemented. Phase 5 must not use local browser state as proof of ownership or authorization.
- Phase 4's `provider_accessible` catalogue state means only that the provider advertised a reference. No analytical raster href or raster bytes were exposed, fetched, validated, georeferenced locally, or analyzed.

## Historical 5A stop boundary

Task 5A allowed schemas, browser runtime-validation contracts, contract tests, and governing documentation only. It did not implement provider asset resolution, tile routes, raster requests, MapLibre raster layers, viewer controls, comparison interaction, timeline persistence, scientific preparation, or analysis; its required stop was before 5B.

## 5D completion checkpoint — 2026-09-13

- Added a runtime-validating tile client and a dedicated MapLibre raster-source/layer adapter. Requests contain only stable scene identity and the fixed 5C recipe; returned metadata must match that scene and a same-origin mediated template.
- The selected scene has an explicit open/reload action. The active overlay reports exact identity, UTC acquisition, provider attribution, and loading, ready, partial-tile, failed, unavailable, expired, and retry behavior. Fit imagery, fit AOI, and remove are available; removal preserves AOI, catalogue context/results, and metadata selection.
- The imagery source uses backend bounds, 256-pixel `xyz` tiles, and backend zoom limits. It is inserted below scene/AOI overlays, restored on style changes, and removed with listeners on replacement/unmount. Sequence and abort guards prevent stale metadata from replacing a newer selection.
- MapLibre's pinned 6.9.0 module worker and shared module are served same-origin. The local verification style is explicitly synthetic context only. The map's ResizeObserver kept client/backing widths equal when the workspace changed from 812 to 1204 pixels.
- Focused tests passed 9/9. A real Chrome/WebGL run rendered two exact Sentinel-2 scenes from SatQuery z8 tiles: `S2C_T43PGQ_20251228T052411_L2A` and, after switching, `S2B_T43PGQ_20251223T051848_L2A`. An earlier upstream range-read failure surfaced as a partial-tile warning; it was not counted as success. The bounded retry reached the ready state for both scenes.
- Final repository verification passed: 101 non-database backend tests (one database test deselected), 85/85 frontend tests, all static checks, and the optimized build. The pinned worker/shared assets match the installed MapLibre 6.9.0 SHA-256 hashes and are excluded from Biome rewriting.
- Task 5E adds presentation-only display adjustments. No 5F comparison, 5G timeline/saved viewer state, scientific processing, or analysis was implemented. Stop before 5F.

## 5A completion checkpoint — 2026-09-12

- Added closed Pydantic and Zod contracts for every 5A contract surface. Both boundaries use the stable `{provider, collection, item}` scene identity and separately model catalogue availability, resolved-asset accessibility, rendering outcome, and analysis readiness.
- Resolved assets carry exact scene/asset identity, acquisition interval, WGS84 bounds, visualization-only render presets, access/readiness state, attribution, and resolution time without exposing a raster URL. Tile metadata permits only a relative mediated `/api/v1/` template, requires `{z}/{x}/{y}`, expiry, bounds/zoom/size/media metadata, attribution, and explicit tile access state.
- Active layers carry display-only visibility/opacity/brightness/contrast/saturation settings and explicit render state. Comparison requires distinct chronological A/B scenes with acquisition intervals. Timeline entries are unique and chronological. Version 1 saved state deliberately excludes tile templates, tile access, expiry, and render-success state.
- Focused backend verification **PASSED**: Ruff, Ruff format, strict mypy, and 16/16 synthetic Pydantic schema tests. Focused frontend static verification **PASSED**: Biome format/lint and strict TypeScript. Focused frontend tests **PASSED** 6/6 on the clean permission-scoped retry.
- The first frontend test start failed with Windows sandbox `spawn EPERM`; the first permission-scoped execution then timed out waiting for a Vitest fork worker with no tests run. The next clean permission-scoped retry passed. These startup failures are not product failures and are retained as execution evidence.
- Final `scripts/verify.ps1` **PASSED** on the clean rerun: Ruff and format for 40 backend files, strict mypy for 35 source files, 84 non-database backend tests with one integration test deselected, frontend format/lint for 56 files, strict TypeScript, all 80 frontend tests, and the optimized Next.js build.
- The first full run failed one existing Phase 4 scene-hover assertion at 79/80; it failed once more focused, then passed unchanged in isolation. Temporary diagnostic instrumentation was removed, and the clean full rerun passed. This intermittent timing history is retained rather than hidden.
- Governing contracts, roadmap, decision register, feature/testing/security/database notes, current checkpoint, Phase 5 report, and session handoff are synchronized. No route, provider resolution, tile request, raster layer, UI control, browser storage write, scientific processing, or analysis was added or tested.
- Final documentation/roadmap audit **PASSED**: 27 relative links across 30 project Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, one active phase row, and zero stale 5A in-progress matches.
- At this historical 5A checkpoint, task 5A was complete and the required stop was before 5B.

## 5B completion checkpoint — 2026-09-12

- Added `POST /api/v1/catalog/asset-resolutions` with a closed request containing only schema version and stable `{provider, collection, item}` identity. The stateless route uses the existing configured public-provider lifecycle and does not touch the database, accept file paths/URLs, create an owned asset, or expose provider raster locations.
- Extended the provider-neutral protocol and Earth Search adapter. Current item metadata is retrieved by validated identity; only `sentinel-2-c1-l2a` assets with allow-listed `data`/`reflectance` roles and `eo:bands.common_name` red/green/blue are selected. The fixed `natural-color` preset is visualization-only and references the exact three provider asset IDs.
- Each component returns asset ID/version, band/common name, band index, canonical TIFF media type, nullable scale/offset/nodata, exact CRS, its own resolution, shape, transform, safe content length, and HEAD-check status. Thumbnail/licence/attribution remain separate. The response exposes catalogue/access/render/analysis states independently and fixes rendering to `not_requested` and analysis to `not_assessed`.
- Initial and redirected raster locations are restricted to credential-free HTTPS on the configured Earth Search Sentinel object host and collection path. Redirects are not automatically followed: each hop is revalidated within a three-request bound. Only HEAD is used; complete scene bodies are not requested. A usable result appears only after all three component metadata and access checks pass.
- Resolution states are exactly `supported`, `unsupported_format`, `unavailable_asset`, and `access_credentials_required`. Every non-supported state includes a reason and returns no resolved asset/components. Focused synthetic coverage includes metadata-driven key mapping with deliberately unequal resolutions, missing bands, unsupported format, 403 restriction, hostile destination rejection, thumbnail separation, and client-URL rejection.
- Focused Ruff and strict mypy checks **PASSED**. Focused/adjacent provider and catalogue API tests **PASSED 34/34**; the dedicated 5B suite **PASSED 7/7**, including expiry classification. The permission-limited pytest cache warning is non-product test-runner noise; test assertions passed.
- Final repository verification **PASSED**: Ruff and format for 43 backend files, strict mypy for 37 source files, 91 non-database backend tests with one database integration test deselected, frontend format/lint for 56 files, strict TypeScript, 80/80 frontend tests, and the optimized Next.js build.
- Final live FastAPI resolution **PASSED** at `2026-09-12T06:14:24.457891Z` for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: HTTP 200, request ID `phase-5b-live-resolution`, status `supported`, assets `red`/`green`/`blue` (B04/B03/B02), EPSG:32643, 10 m, 10980×10980, scale 0.0001, offset −0.1, nodata 0, and three HTTP 200 HEAD checks. Header content lengths were 239542527, 234345783, and 235058884 bytes; no raster body was downloaded and the database guard was untouched.
- Final documentation/roadmap audit **PASSED** across 24 governed root/docs Markdown files: 28 relative Markdown links, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row. An initial recursive audit encountered permission-denied generated pytest/tmp directories and was discarded; the explicit governed-directory rerun supplied these counts.
- Tile delivery, browser/MapLibre imagery rendering, viewer controls, comparison/timeline UI, persistence, scientific preprocessing, and analysis remain **NOT IMPLEMENTED / NOT RUN**. Carried browser and real PostGIS gates remain unchanged.
- Historical 5B stop: task 5B was complete and 5C–5H had not started. The 5C checkpoint below supersedes that boundary.

## 5C completion checkpoint — 2026-09-12

- Added closed `POST /api/v1/imagery/tile-sets` and opaque-ID `GET /api/v1/imagery/tiles/{tile_set_id}/{z}/{x}/{y}.png` routes. Requests accept stable scene identity plus only the fixed `natural-color`/256-pixel recipe; no client URL, path, band expression, credential, or unrestricted render option is accepted.
- The lifespan-managed service resolves every scene through 5B and revalidates exact Earth Search HTTPS host/collection destinations. Runtime raster reads reject redirects, local/internal/loopback locations, credentials, queries, fragments, traversal, non-GTiff content, mismatched length/ranges, and raster headers inconsistent with trusted dimension/CRS/transform/band metadata.
- Pinned NumPy 2.5.3, Rasterio 1.5.1/GDAL 3.12.4, and rio-tiler 9.4.4. rio-tiler performs WebMercatorQuad window/overview reads and reprojection; the fixed recipe applies per-band scale/offset and combines nodata masks into PNG transparency. All-invalid and genuine read failures return errors rather than empty successful images.
- Rasterio is a direct production dependency, not merely a transitive rio-tiler dependency. The final manifest/lock reconciliation passed `pip check`, scoped Ruff/format, strict mypy, 10/10 focused tile tests, and all 101 selected non-database backend tests.
- Tile size is fixed at 256 and zoom at 0–16. Raster work is outside FastAPI's event loop with two request slots and three bounded component readers; range reads, deadlines, downloaded bytes, caches, native cache, tile-set lifetime/count, and tile-byte memory are bounded. Cache keys include access scope, scene, recipe, and tile coordinates; provider expiry shortens tile-set expiry.
- Focused/current backend checks **PASSED**: Ruff/format, strict mypy, and 101 non-database tests with one integration test deselected. The ten 5C cases cover stable-only input, unsupported recipe, invalid identity, tile bounds/outside/unknown set, nodata transparency, cache identity/access scope, upstream failure, provider restriction, and five hostile destination forms.
- Final repository gate **PASSED on the clean rerun**: Ruff/format for 48 backend files, strict mypy for 41 source/test files, 100 non-database backend tests, frontend format/lint/typecheck, 80/80 frontend tests, optimized Next.js build, and `pip check`. After adding the cache-key regression case, static checks, 10/10 focused tests, and the current 101-test backend suite passed; frontend code was unchanged. The first full run reached Vitest but its fork worker timed out before running tests and is retained as a failed startup.
- Live API delivery **PASSED** for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: metadata and tile HTTP 200; WebMercatorQuad z8/x183/y118; 57,718-byte 256×256 PNG; 17,285 valid and 48,251 transparent pixels; RGB range 0–255; database guard untouched.
- Two earlier live attempts are retained as failure evidence: native GDAL first inherited an unavailable loopback proxy, then the Windows Schannel build failed TLS; the validated Python range opener replaced that path. A z12 trial correctly timed out with 504 under the 30-second bound; the bounded z8 verification then passed. These failures were not reported as successful tiles.
- Final documentation/roadmap audit **PASSED** across 24 governed root/docs Markdown files: 28 relative links, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.
- At the historical 5C boundary, no MapLibre/browser layer or WebGL claim had been added and the required stop was before 5D. The 5D and 5E checkpoints supersede that display boundary; tasks 5F–5H remain not started.

## 5E checkpoint — 2026-09-14

- The active imagery overlay now exposes keyboard-operable visibility, opacity, brightness floor/ceiling, contrast, saturation, preset, and reset controls. Paint changes are debounced and preserve the map camera, AOI, catalogue results, and selected scene.
- Only the approved `natural-color` preset is enabled. False colour is explicitly disabled because near-infrared was not resolved; single-band is explicitly disabled because it is not approved by the current renderer. The backend continues to reject arbitrary recipes and display-only request fields.
- The server recipe uses red/green/blue in explicit resolved order, applies each band's scale/offset, and uses one fixed 0.00–0.30 reflectance range for the scene. Browser paint adjustments do not mutate source values and are not analysis.
- Backend focused checks passed with 10/10 tile tests; the selected full backend gate passed 101 tests with one database test deselected. Frontend static checks, a clean 86/86 test run, and the optimized build passed. One combined-script Vitest worker startup timed out before tests ran and remains recorded as failed.
- Isolated Chrome/WebGL verified the real scene `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: first open reached ready from real z8 tiles; each supported control affected the imagery; reset restored exact defaults; scene/AOI/camera persisted; and no control change requested replacement tile metadata. Genuine later provider failures produced `partial`, not false success.
- Documentation/roadmap audit passed across 24 governed Markdown files with 28 relative links, zero broken targets, 16 phase rows, and one active row.
- No 5F comparison, 5G timeline/state persistence, scientific preprocessing, or analysis was started. Stop before 5F.

## 5F checkpoint — 2026-09-14

- Added stable selected-scene assignment to A/B, duplicate rejection, chronological normalization, overlap checking, synchronized swipe/side-by-side MapLibre views, accessible divider, accurate display-side swap, linked/independent opacity, per-side lifecycle, and complete cleanup.
- The official comparison plugin was evaluated and not installed because the local controlled adapter better fits current MapLibre 6.9.0, React ownership, native keyboard accessibility, typed failure state, and cleanup; no dependency changed.
- Focused tests passed 10/10; final frontend static/type checks, all 91 tests, and optimized build passed. Initial sandbox `spawn EPERM`, one fork-worker timeout before tests, and corrected test assertions/mocks remain recorded failures.
- Live Chrome/WebGL rendered real Dec 23/Dec 28 Sentinel-2 scenes through SatQuery tiles, verified synchronization controls, keyboard swipe, side swap, linked/independent opacity, resize, and cleanup. A separate real one-side access failure stayed explicit. See [the comparison screenshot](phase-5f-comparison.png).
- Documentation audit passed across 24 governed Markdown files with 32 relative links, zero broken targets, 16 phase rows, and one active row.
- No co-registration, change map/percentage/confidence, timeline, saved viewer state, persistence, or analysis was added. Stop before 5G.

## 5G checkpoint — 2026-09-15

- Added an exact-acquisition chronological timeline derived only from the current AOI/filter results. Previous/next and direct selection open stable scenes through the established renderer; same-date entries retain exact UTC times and ordinal labels. Pagination warnings state that more pages remain unloaded without implying absent dates, and stale AOI/filter results remove the timeline.
- Version 1 browser-local viewer state runtime-validates the AOI draft fingerprint, camera, active stable asset/preset/display, partial or complete comparison slots, chronological timeline identities, and active entry. Tile-set IDs/templates, provider URLs, expiry/access state, credentials, bytes, and render claims are excluded. Restoration rejects another AOI, uses no substitute, and re-resolves active imagery; unloaded saved scenes are reported as partial.
- Playback was not added because the roadmap/tracker does not require it. No interpolation, invented frame, server persistence, scientific processing, or automated change output was added.
- Backend contract Ruff/format/mypy and 17/17 tests passed. Frontend format/lint/type checks, focused 19/19 tests, the prior full 97/97 suite, and production build passed. One sandbox `spawn EPERM` and two fork-worker startup timeouts with no tests remain recorded; a clean focused rerun passed 8/8.
- Real Chrome/WebGL loaded six current Earth Search acquisitions for the Bengaluru AOI, warned that more pages remained, rapidly navigated Apr 17→22→27, rendered `S2C_T43PGQ_20260427T051531_L2A`, then restored the exact scene/camera after reload and fetched fresh metadata plus two real z8 tiles. The in-app browser failed before attachment because `sandboxPolicy` was missing; [restoration screenshot](phase-5g-restoration.png).
- At this historical 5G checkpoint, task 5H had not started. The completed 5H checkpoint below supersedes that boundary.

## 5H checkpoint — 2026-09-15

- The complete available AOI → real catalogue → raster viewer → display/reset → two-date comparison → timeline → reload/restore → AOI invalidation workflow passed in isolated Chrome/WebGL. The integration used real Earth Search Sentinel-2 acquisitions and SatQuery z8 imagery tiles; it did not treat catalogue metadata or HTTP success alone as browser rendering.
- A small defect found during integration was fixed: after temporal normalization, comparison A/B assignments now adopt the same earlier/later identities shown in the viewer. Focused SceneContainer/comparison tests passed 10/10 after the fix.
- The authoritative non-database workflow passed backend Ruff/format/mypy and 102/102 selected tests, then the combined Vitest worker timed out before running a frontend test. A clean standalone rerun passed 98/98; final frontend typecheck, format, lint, focused tests, and optimized build passed.
- Live asset resolution and tile scripts passed. The tile was a real 256×256 RGBA PNG with 17,285 valid and 48,251 transparent pixels. Browser reload captured fresh metadata and two HTTP 200 z8 tiles with no console errors; only a Next.js development LCP warning and expected reload aborts appeared.
- Controlled browser network blocking produced explicit partial-tile and imagery-metadata failure UI. Closed API requests containing `file:///etc/passwd`, an arbitrary expression preset, or an internal provider all returned 422; existing public catalogue/imagery authorization was unchanged and no arbitrary fetch surface was added.
- Laptop comparison, 390×844 mobile UI, repeated comparison entry/exit, state restoration, and AOI invalidation were inspected. No duplicate comparison maps were visible; exact listener/map cleanup remains covered by component/map-adapter tests. Screenshots are in the Phase 5 report.
- The isolated PostgreSQL/PostGIS check was rerun and remains **BLOCKED / NOT RUN** because Docker is unavailable. This independent Phase 1 gate is not waived and does not convert liveness or viewer success into database readiness.
- All 5A–5H viewer-scope requirements are reconciled in the Phase 5 report. Phase 5 is complete; stop before Phase 6.
