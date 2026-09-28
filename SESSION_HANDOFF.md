# SatQuery session handoff

Last updated: **2026-09-28**

## 2026-09-28 presentation demo resume

- **Phase/status:** Phase 10 demo verification only; `BLOCKED`; Phase 11 not started.
- **Completed:** restored Docker/PostGIS; upgraded Alembic to `20260926_0003`; diagnosed Psycopg/Windows Proactor incompatibility and launched the backend with `asyncio.SelectorEventLoop`; readiness returned 200 with PostgreSQL 18.6/PostGIS 3.6.4/current migration. Filled only the existing generic runtime key's supported OpenAI provider/model selectors in ignored root `.env`.
- **Verification:** real chip verifier reproduced `110 × 113`, checksum `4fbf8bda6eb648d297d7c9ed3c781ffdcd8d2f4a08e711215b990ad425f05680`, Phase 6 `ready`, then failed safely with `MODEL_UPSTREAM_ERROR`. Browser fallback passed map → 4.82 km² AOI → six real scenes → `S2B_T43PGQ_20260422T052413_L2A` → question, then failed safely for missing configured identity. Screenshot: `docs/demo-blocked-question-2026-09-28.png`. In-app browser setup remained unavailable; georeferenced tile rendering stayed loading.
- **Files changed:** ignored `.env` provider/model selectors; `DEMO_HANDOFF.md`; `CURRENT_PHASE.md`; `SESSION_HANDOFF.md`; new screenshot `docs/demo-blocked-question-2026-09-28.png`. Git status was unavailable because this workspace has no `.git` directory. No API key value was exposed.
- **Remaining blockers:** real verified principal resolver; usable hosted-model access; committed inference/evidence; visibly rendered scientific tiles. Resume with the selector-loop command in `DEMO_HANDOFF.md`, make the direct verifier return an available answer, then repeat the protected browser path. Do not create a fixed dev principal or start Phase 11.

Read this concise resumption record with `AGENTS.md`, `CURRENT_PHASE.md`, `docs/PHASE_10_TASKS.md`, and `docs/PHASE_10_REPORT.md`.

## Presentation demo audit — 2026-09-27

- **BLOCKED for complete question-to-answer browser demo; do not begin Phase 11.** Public map/AOI/catalogue selection works, but protected inference fails at missing verified identity; PostGIS/Docker engine is unavailable, map raster tiles remained loading, and no xAI key was configured for a live request. A separate real Sentinel-2 scientific chip passed Phase 6 readiness but is not a browser/model result. The prior Phase 10 `PARTIALLY_VERIFIED` evidence is not overridden by the user's completion statement.
- Changed: backend config, inference transport/service and model-bound cache identity, config/VQA tests, new `backend/scripts/verify_demo_question.py`, local browser-check script, `.env.example`, `API_CONTRACT.md`, `README.md`, `DEMO_HANDOFF.md`, this checkpoint and `CURRENT_PHASE.md`; two local UI screenshots. No secret, frontend application code, satellite provider or Phase 11 code changed.
- Backend full non-integration **307 passed / 1 deselected**, Ruff/format/mypy passed; frontend format/lint/typecheck/build and focused assistant **9 passed**. Real catalogue search and direct ready chip extraction passed. Browser asked “What surface types are visible?” for `S2B_T43PGQ_20260422T052413_L2A` and displayed the precise identity error, not an answer. In-app browser connector failed; separate local headless Chrome produced the screenshots. Exact commands and results are in [DEMO_HANDOFF.md](DEMO_HANDOFF.md).
- Resume: user sets xAI key only in ignored root `.env` with pinned provider/model; restore PostGIS/Alembic and verified principal; test direct real-chip xAI response, then restart backend/frontend and verify the complete browser question/source evidence. Leave the demo `BLOCKED` until all pass.

## Phase 10 task 10F — 2026-09-26

- **Status: PHASE 10 PARTIALLY_VERIFIED; 10F executed; stop before Phase 11.** Synthetic route/service-double checks cover all four intent dispatches, same-AOI and changed-scene follow-ups, missing/ambiguous references, failures, separate sessions and fabrication-prompt rejection. Real Earth Search discovery and direct calibrated optical change-pair verification passed, but no live protected GeoAgent result or source-bound browser overlay was obtained. Phase 9's real optical/SAR pair remains unverified.
- Changed: backend routing/conversation, three GeoAgent test files including new `test_geoagent_phase10f.py`; frontend GeoAgent client, assistant panel/test; `API_CONTRACT.md`, `TESTING.md`, `ROADMAP.md`, Phase 10 tracker/report, `CURRENT_PHASE.md`, this handoff. Fixed explicit fabricated-result requests, one-image same-area context, and client inheritance of unchanged selection. No user data or analysis artifacts were deleted; temporary browser profiles created by this run were removed.
- Passed: backend focused **47**, full non-integration **301** (1 PostgreSQL test deselected), Ruff check/format and strict mypy; frontend format/lint/typecheck, **127 Vitest**, production build; real catalogue/direct optical-pair scripts. Live liveness 200; readiness 503 for database; protected conversation 503 for missing verified identity. In-app browser connector failed at `sandboxPolicy` setup; no new browser interaction/screenshot. Exact commands and source measurements are in the 10F tracker/report. Initial sandbox pytest temp ACL and temporary-browser-profile format errors were resolved before final green reruns.
- Resume only within Phase 10: restore PostgreSQL at `20260926_0003`, verified principal, Phase 7 answer model, and browser connector; run four real protected conversation paths to committed source-bound results/overlays, same-AOI/scene-change and failure/session browser checks; verify a real aligned optical/SAR pair. Do not mark COMPLETE or begin Phase 11 before those gates pass.

## Phase 10 task 10E — 2026-09-26

- **Status: 10A–D done; 10E implemented / partially verified; stop before 10F.** The workspace assistant now submits owner-scoped GeoAgent turns with current AOI/selected scenes and revision, polls real protected jobs, shows actual model or computed evidence, offers selection-specific suggestions/actions, and opens source-bound grounding/change/prepared-SAR overlays. Retry keeps the draft/request ID; changed inputs abort delayed display and mark results stale. Backend map/AOI commands remain unavailable.
- Changed: new `frontend/src/lib/geoagent-client.ts`; assistant panel/test, workspace shell/test, scene container, optical/SAR and imagery-discovery panels; desktop/mobile screenshots; `API_CONTRACT.md`, README files, `FEATURES.md`, Phase 10 tracker/report, `CURRENT_PHASE.md`, this handoff. No backend or scientific method changed.
- Validation: frontend format/lint/typecheck/build passed; focused assistant **8 passed**; final full frontend **126 passed / 30 files**. Headless Chrome desktop/mobile rendered an honest backend-unreachable state; in-app browser interaction failed before setup (`sandboxPolicy` metadata). Default Vitest fork worker timed out; threads with `--testTimeout=15000` passed. No real protected conversation/job, interactive browser overlay, production PostgreSQL/verified principal, or live answer model was verified. Exact commands and carried Phase 7–9 blockers in tracker.
- Resume 10E verification: restore browser automation and PostgreSQL/identity at Alembic `20260926_0003`, run actual selected-scene and pair/SAR turns to committed results, inspect source-bound overlays and keyboard/mobile/refresh/stale behavior. Keep 10E partial until done. Do not start 10F without authorization.

## Phase 10 task 10D — 2026-09-26

- **Status: 10A–D DONE (implementation/focused tests); stop before 10E.** Added protected owner/access-scope/conversation-ID state with current AOI, dated scene selection, bounded tool refs and committed-only analysis ref; unique earlier-image and area/result follow-ups clarify when ambiguous. Selection changes invalidate dependent context; late results return `stale` without output. Queued jobs may be owner-checked and promoted only after committed result access on a later turn. Map mutation remains unavailable; existing protected job cancellation remains separate. Conversation read/delete is owner-scoped; deletion does not cancel jobs.
- Changed: new `backend/src/satquery/api/schemas/geoagent_conversation.py`, `agent/conversation.py`, `db/geoagent_conversations.py`, migration `backend/alembic/versions/20260926_0003_geoagent_conversations.py`, updated GeoAgent routes, app factory, migration head, readiness fixtures, new 10D tests; updated API/database/architecture/security/testing/setup/roadmap/feature/decision docs, Phase 10 tracker/report, `CURRENT_PHASE.md`, this handoff.
- Focused 10A–D **42 passed**; backend non-integration **296 passed / 1 PostgreSQL integration deselected** after approved unsandboxed rerun for the known Windows temp ACL issue; strict mypy/Ruff/format and static Alembic head passed. Production PostgreSQL migration/verified principal, real job recovery, live provider/model and browser/frontend were **not run**. Retention/backup policy and Phase 7–9 live gates remain open. Exact commands/limitations in the tracker.
- Resume only after 10E authorization: connect the workspace composer to the protected conversation route, bind explicit selection/revision to UI results, and implement an authorized map bridge for a committed change artifact. Restore PostgreSQL/identity and verify durable restart before claiming live conversational persistence. Do not start 10E on this handoff.

## Phase 10 task 10C — 2026-09-26

- **Status: 10A–C DONE; stop before 10D.** A closed seven-tool registry and protected `/api/v1/geoagent/execute` route call actual trusted tile metadata or owner-scoped inference/change/optical-SAR job services after server-side intent routing and strict argument validation. Existing jobs supply idempotency, source/quality checks, status, cancellation and committed results. GeoAgent adds bounded submission timeouts, real IDs/output and safe execution summaries; map/AOI action remains unavailable until a separately authorized browser bridge. No conversation persistence, new scientific method or model fallback.
- Focused synthetic service/API **34 passed**; final backend non-integration **288 passed / 1 PostgreSQL integration deselected**; Ruff/format/mypy passed. No live provider/model, production DB/identity, browser or frontend build gate run. Phase 9 remains `PARTIALLY_VERIFIED`; real joint optical/SAR and NISAR pixel gates remain open.
- Changed: `backend/src/satquery/api/schemas/geoagent.py`, new `geoagent_execution.py`, `agent/routing.py`, new `agent/execution.py`, new `api/routes/geoagent.py`, `api/router.py`, updated `tests/test_geoagent_phase10.py`, new `tests/test_geoagent_execution_phase10c.py`, Phase 10 checkpoint/report, API/architecture/testing/feature/roadmap/README/decision docs, `CURRENT_PHASE.md`, this handoff. Exact commands in tracker. Next only on 10D authorization: owner-scoped durable conversation-to-job/result state, restart/cancel truth, stale-input binding; no client-only fake history.

## Phase 10 tasks 10A+B — 2026-09-26

- **Status: 10A+B DONE; stop before 10C.** Added strict internal GeoAgent message/selection/intent/dependency/tool-reference contracts and deterministic, non-executing router for single-image question/caption, grounding, dated optical change, source-separated optical/SAR observation, and map/AOI actions. It clarifies missing context, rejects unsupported measurements/causes/cross-sensor grounding/change, and records runtime availability as unknown unless trusted host evidence says otherwise. No public API route, job execution, model call, persisted conversation, UI action, or fabricated answer was added.
- Changed: new `backend/src/satquery/api/schemas/geoagent.py`, `backend/src/satquery/agent/__init__.py`, `backend/src/satquery/agent/routing.py`, `backend/tests/test_geoagent_phase10.py`; `API_CONTRACT.md`, `ARCHITECTURE.md`, `TESTING.md`, `ROADMAP.md`, `FEATURES.md`, `README.md`, `docs/DECISIONS.md`, Phase 10 tracker/report, `CURRENT_PHASE.md`, this handoff. Focused **18 passed**; final backend non-integration **272 passed / 1 DB integration deselected**; Ruff/format/mypy passed. Initial sandboxed full test had five pre-existing fixture setup errors from denied Windows pytest temp access; approved rerun passed. Frontend/live checks not run for backend-only seam.
- Phase 9 remains `PARTIALLY_VERIFIED`; live joint optical/SAR, production DB/identity/browser, and current NISAR pixel gates are still open. Exact next action, only on explicit 10C authorization: implement a protected executor over the plan with trusted source/quality re-resolution, actual dependency checks, owner-scoped allow-listed jobs and auditable result IDs. Do not count a routing plan as analysis or start 10C–F implicitly.

## Phase 9 task 9F — 2026-09-26

- **Status: PHASE 9 PARTIALLY_VERIFIED; 9F executed; stop before Phase 10.** Live São Paulo Sentinel-2 `S2B_T23KLP_20250115T131403_L2A` and INPE Sentinel-1 `S1A_IW_RTCH_1SDV_20250201_057700_071CAB_B664` were discovered/resolved, but optical B02 scientific read failed (`RASTER_READ_FAILED`) before joint preparation. Separate INPE discovery and ASF sample TLS timed out. No real protected pair job, actual combined answer/display, or current PROVISIONAL NISAR pixel ingestion is claimed. Browser bridge failed before tab creation; PostgreSQL/verified principal absent.
- Fixed specific safe failed-job reporting and lowercase API error code, tightened preview/result binding to full source/date/polarization/request/version, and added synthetic cloud/date/provider-failure/wrong-provider regressions. Changed backend `optical_sar_jobs.py` and two Phase 9 test files; frontend `optical-sar-panel.tsx` and its test; Phase 9 tracker/report, `CURRENT_PHASE.md`, `ROADMAP.md`, README, this handoff.
- Final `scripts\verify.ps1` passed: Ruff/format/mypy, backend **254 passed / 1 DB integration deselected**, frontend Biome/lint/typecheck, **123 Vitest passed**, production build. Focused panel **3 passed**. Exact live commands/results and synthetic-vs-real limits in `docs/PHASE_9_REPORT.md`.
- Resume: restore trusted Earth Search/INPE raster access and production PostgreSQL/verified principal; complete one real protected optical/SAR job and inspect source/mask/grid/coverage/artifact plus independent cross-modal tie points. Restore browser bridge and inspect dated overlays/opacity/source-grounded answer/stale selection. Authenticate/stage an actual PROVISIONAL GCOV HDF5 for separate NISAR ingestion. Keep Phase 9 partial until these gates pass; do not start Phase 10.

## Phase 9 task 9E — 2026-09-25

- **Status: implemented / partially verified; stop before 9F.** Added trusted, owner-scoped optical/SAR observation jobs and typed API/artifact over the existing 9D pair. It returns separate calibrated optical red-reflectance and SAR linear gamma-0 medians, actual source IDs/dates, evidence bounding rectangles/CRS, pixel counts, AOI-denominator joint coverage/area, time gap, alignment state and limitations. It does not assert fusion, agreement, flood/building cause, or confidence; unsupported questions/insufficient quality are explicit.
- Workspace now searches real INPE RTC metadata by AOI/date, selects returned polarization, prepares a dated display-only SAR preview, overlays it on the optical map with visibility/opacity, starts/polls the protected job, and routes a matching assistant question to the computed result. AOI/scene/polarization/date changes clear stale results and overlays. Scientific inputs remain separate from display preview.
- Verification: approved focused backend 9E+9D+9B **14 passed**; full backend **253 passed, 1 PostgreSQL skip**; focused frontend map/panel/scene/assistant **18 passed**; backend Ruff/mypy, frontend type/lint/format and production build passed. The first sandboxed SAR fixtures failed on pytest temp ACL, approved rerun passed. Browser connector failed at tab creation (`sandboxPolicy` missing); no screenshot. Real protected pair job unverified due carried INPE GDAL proxy/Schannel failure and unconfigured PostgreSQL/verified principal. 9C live PROVISIONAL pixels also remain unverified.
- Changed: new optical/SAR backend schema, route, job service and tests; job/artifact type/repository/dependency/router/main integration; frontend optical/SAR client, SAR map layer, workspace panel and tests, assistant/map/scene/shell/CSS; `API_CONTRACT.md`, README, Phase 9 tracker/report, `CURRENT_PHASE.md`, this handoff. Exact commands in report. Resume: restore trusted INPE COG read and durable identity/database; run one protected real 9E job and inspect source evidence/artifact; restore browser bridge and capture dated layers, opacity, job answer and stale-input behavior. Begin 9F only after explicit authorization.

## Phase 9 task 9D — 2026-09-25

- **Status: implemented / partially verified; stop before 9E.** Internal Sentinel-2 L2A calibrated RGB/SCL + INPE Sentinel-1 RTC C-band co-location uses one AOI UTM grid, nodata-aware bilinear SAR power reprojection, nearest-neighbour categorical masks, and a joint optical/SAR usable mask. Original native optical and SAR values/units, source IDs, versions, time gap, resolutions, processing parameters, and measured AOI-denominator coverage remain attached. There is no change/fusion claim or numerical reflectance-versus-gamma-0 comparison.
- Readiness requires independent distributed cross-modal tie points within a provisional 0.5-pixel residual, actual optical QA, and at least 10% joint usable AOI coverage. Shared grid/overlap alone yield `insufficient_evidence`. No real tie points are available, so real analysis readiness is not claimed. NISAR L-band is explicitly unsupported by 9D; 9C live PROVISIONAL ingestion remains open.
- Synthetic 9D tests: 5 passed. Full backend: 248 passed, one unconfigured PostgreSQL skip (approved rerun after pytest temp ACL failure). Full Ruff/format/mypy passed. Bounded live São Paulo attempt resolved optical scientific data but SAR COG read failed on an unreachable inherited loopback proxy; a direct fixed-host retry is recorded in the report. No completed joint real raster is claimed without a successful retry. Frontend unchanged/not run.
- Changed: `backend/src/satquery/processing/optical_sar_pair.py`, `backend/src/satquery/processing/__init__.py`, `backend/tests/test_optical_sar_pair_phase9d.py`, `backend/scripts/verify_phase9d_real.py`, Phase 9 checkpoint/report, `API_CONTRACT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CURRENT_PHASE.md`, this handoff. Resume by restoring trusted INPE raster access, running the live script, inspecting joint coverage/masks and independent tie-point residuals; start 9E only after separate authorization. Carried PostgreSQL/identity/browser and NISAR staging gates remain.

## Phase 9 task 9C — 2026-09-25

- **Status: implemented / partially verified; stop before 9D.** Added trusted NASA CMR discovery for `NISAR_L2_GCOV_PROVISIONAL_V1` L-SAR and bounded server-staged HDF5 ingestion. Stable ASF concept/CRID, actual frequency/polarization, provisional QA metadata, native projected grid, separate AOI/GDAL/product-mask validity, and original linear gamma-0 values are retained. No NISAR analysis, display layer, fusion, or live pixel success is claimed.
- Real CMR search/resolve passed on `G4250117587-ASF` (CRID `P05023`, Frequency A/B both HH); an official older simulated GCOV sample's HDF5 layers, EPSG:32611 axes, and mask metadata were inspected. Final NISAR focused checks passed 5, 9A/9B/9C regression passed 22, full backend passed 243 with one PostgreSQL skip, and Ruff/format/mypy passed. Exact commands are in `docs/PHASE_9_REPORT.md`.
- Blocker: ASF HDF5 download requires Earthdata Login and no PROVISIONAL file was staged. The public older simulated sample exposed GDAL 3.12.4's missing georeferencing; pinned `h5py` now reads its EPSG:32611 projection/axes/mask metadata directly. Resume by authenticated host-side staging of the exact CMR granule, then verify one small native-grid AOI extraction, mask classes, metadata, and QA. Keep credentials outside source/logs. Carried PostgreSQL/identity/browser gates persist. Files changed are listed in the report.

## Phase 9 task 9B — 2026-09-25

- **Status: 9B COMPLETE; stop before 9C.** Added trusted INPE `sentinel-1-rtc-1` AOI/date discovery, actual item polarizations, populated 9A SAR metadata, bounded gamma-0 AOI clipping, nodata plus layover/shadow validity, and fixed visualization-only dB rendering. Existing optical behavior is preserved.
- Live São Paulo check passed on `S1A_IW_RTCH_1SDV_20250120_057525_0715BC_0DCC`: `VH,VV`, 35×35 EPSG:4326, 1,089 valid pixels, gamma-0 0.0474098–5.68852, and 1,198-byte PNG. No application accuracy is inferred.
- Checks: focused 18 passed; full backend 238 passed / 1 PostgreSQL skip; Ruff/format and strict mypy passed. Frontend was unchanged/not run. Files are listed in `docs/PHASE_9_REPORT.md`.
- Blockers: Brazil-only provider coverage/licence terms, memory-only previews, no durable SAR jobs/artifacts, no map UI, no task-specific SAR analysis, and carried PostgreSQL/identity/browser gates. Next: explicitly select one 9C SAR analytical task over linear gamma-0 and masks; do not use display pixels or start fusion.

## Phase 9 task 9A — 2026-09-25

- **Status: 9A COMPLETE; stop before 9B.** Created `docs/PHASE_9_TASKS.md` with bounded 9A–9F checkpoints while retaining the unavailable original Phase 9 title. Only 9A was implemented.
- Added strict shared optical/SAR metadata schema `1.0`: stable source/provider, mission/time/footprint, native resolution/CRS, processing level, product maturity, exact calibration state, valid-data-mask evidence, optical bands or SAR polarizations, explicit unavailable metadata, and typed supported/unsupported ordered pairs.
- Existing optical modules are unchanged. The contract adds no provider, route, database, artifact, raster read, job, map, UI, fusion, or SAR analysis. No SAR source is configured or claimed.
- Checks: 14/14 new contract tests; 86/86 focused contract plus catalogue/viewer/processing/change regressions; full backend 234 passed / 1 unconfigured PostgreSQL skip; full Ruff/format/mypy pass. Frontend was not rerun because 9A has no frontend or runtime route. Initial test-only formatting/type findings were fixed.
- Blockers/next action: select one trusted SAR metadata provider/product and verify licence/access, maturity/level, polarizations, resolution/CRS, calibration/mask authority, and version evidence after explicit 9B authorization. Production PostgreSQL/identity and browser gates remain carried. Do not begin SAR pixel processing or fusion in 9B unless separately authorized.

## Phase 8 task 8F — 2026-09-25

- **Status: Phase 8 PARTIALLY_VERIFIED; 8F executed; stop before Phase 9.** A direct real same-sensor Sentinel-2 pair completed extraction, quality masking, common grid, reliable registration, change detection, and summary. It measured 138,700 m² changed out of 4,806,800 m² joint-valid observed area (2.885495547973704%), 4,757,800 m² joint usable, and 49,000 m² unknown; source IDs/AOI/method/version were preserved and cause stayed `not_determined`.
- Fixed the discovered GDAL boolean-mask reprojection error, bumped processing/cache version to `phase-8f-v1`, and added regressions for all-false exclusions and muddy flood-like imagery. UI result/answer evidence now exposes exact source IDs, method/version, processing version, and job; map-layer tests bind authorized tiles/bounds/opacity/removal.
- Required synthetic failure/edge cases and computed “What changed?” routing pass. `.\scripts\verify.ps1` passes: 220 backend tests with one PostgreSQL deselection, 118 frontend tests, all lint/format/type gates, and optimized build.
- Two protected real-job attempts failed safely on intermittent provider COG reads. Production PostgreSQL/verified identity are not configured, and the browser bridge still lacks required sandbox metadata; therefore no durable protected real result/cache/tile, screenshot, or visual overlay pass is claimed.
- Phase 8 completion still requires durable database/identity, restored browser automation, and a successful protected real job/workspace pass. Its former stop-before-Phase-9 boundary was superseded only by the explicit contract-only 9A authorization above; no SAR runtime, fusion, or analysis was added.

## Phase 8 task 8E — 2026-09-25

- Status: implemented / partially verified; stop before 8F.
- Completed protected `analyze_change` jobs, scoped cache identity, 11-stage progress, failure/cancellation behavior, atomic classification/manifest, typed start/status/result/cancel API, and authorized nearest-neighbour change tiles.
- Connected the chronological pair/AOI workspace to measured dates, changed/observed/unknown areas, warnings, aligned overlay, legend/opacity, input invalidation, and computed-only “What changed?” answers.
- Checks: backend Ruff/format/mypy and 218 tests passed (one PostgreSQL skip); frontend Biome/TypeScript and 117 tests passed; optimized build passed. Browser connection failed because its execution bridge rejected required sandbox metadata, so no screenshot or browser success is claimed.
- Carried blockers: no completed comparable real pair; production PostgreSQL/verified principal unavailable. Resume after explicit 8F authorization by restoring browser automation, configuring durable identity/database, and running a real pair if provider reads permit.

## Phase 8 task 8D — 2026-09-25

- The user-defined 8D measurement/summary scope superseded the earlier provisional job-integration placeholder. Added affine/CRS-aware square-metre pixel area, joint-valid changed percentage, separate observed/usable coverage, and separate inside-AOI unknown area.
- Added deterministic, source-bound summary records/statements for dates, exact AOI, change extent, method, coverage, actual QA cloud/shadow exclusions, alignment, and a provisional 45-day seasonal-context warning. RGB supports no defensible vegetation direction, and cause/land-cover remains not determined.
- Change result schema is now 1.1 with validated joint-valid class fractions. Synthetic evidence verifies 2,600 m² changed / 2,800 m² observed = 92.857%, 400 m² unknown, projected-foot conversion, and degree-CRS rejection.
- Validation: focused 49/49; full backend 217 passed / 1 PostgreSQL skip; Ruff check/format and strict mypy passed. No real summary ran because no real comparable 8B pair exists.
- Changed: area/change/summary processing modules and exports, change schema/tests, and Phase 8/contract/architecture/requirements/feature/checkpoint documentation. No job, API, artifact, database, or UI integration was added.
- **Status:** 8D COMPLETE; 8E–8F NOT STARTED. Stop before 8E. Exact resume: explicitly scope 8E and implement the missing protected execution/API/cache/atomic-artifact prerequisite before exposing results in the workspace.

## Phase 8 task 8C — 2026-09-25

- Implemented pure `calibrated_rgb_rms_reflectance_difference` version `8c-calibrated-rgb-rms-v1` over only an exact 8B comparable pair. The fixed 0.05 dimensionless threshold is explicitly provisional; no per-date normalization, clamping, display stretch, harmonization, or causal label is applied.
- The detector independently binds scene/grid/registration/masks and calibrated RGB metadata. Joint-usable pixels are changed/unchanged; clouds, shadows, nodata, unknown quality, and outside-AOI cells remain unknown. Rejected/zero-overlap pairs are insufficient evidence and inconsistent/tampered inputs fail without output.
- Validation passed: focused processing 57/57, full backend 213 passed / 1 PostgreSQL skip, Ruff check/format, and strict mypy. Exact synthetic counts/areas passed for unchanged, known change, masks, unreliable registration, no overlap, and mask tampering. No real run occurred because no real comparable 8B pair exists.
- Changed: `backend/src/satquery/processing/change_detection.py`, processing exports, change preparation tests, and Phase 8/roadmap/contract/architecture/feature/checkpoint documents. No job/API/artifact/UI integration was added.
- **Status:** 8C COMPLETE; 8D–8F NOT STARTED. Stop before 8D. Exact resume: bind the detector and 8A result to the protected job/cache/atomic-artifact path, preserving the fixed 8C method and access scope.

## Phase 8 task 8B — 2026-09-24

- Implemented explicit pair comparability over Phase 6 outputs. It validates chronological dates, compatible band order/common grid, QA on both dates, overlap, and reliable registration; independently recomputes joint validity/usability from both scenes and all exclusion masks.
- Reused `prepare_optical` jobs and atomic storage: pair jobs now have nine stages including `pair_comparability_assessed`, store the recomputed two-band mask, and retain source/date/grid/coverage/parameters/version/reasons in the manifest. Rejected pairs set `comparison_allowed=false` and never reference a classification artifact.
- Validation passed: focused 24/24, full backend 207 passed / 1 PostgreSQL skip, Ruff/format and strict mypy over 89 files. One initial new grid-mismatch assertion failed and passed after the service stopped deriving overlap reasons from inconsistent grids. The final real pair run completed the first selected scene, then returned explicit `unavailable` / `RASTER_READ_FAILED` on the second before common-grid/registration work. No real pair outcome or map is claimed.
- Changed: `backend/src/satquery/processing/change.py`, processing exports/job orchestration/tests, `backend/scripts/verify_change_pair.py`, and Phase 8/roadmap/API/architecture/feature/checkpoint documentation. No route, job operation, migration, classifier, UI, or Phase 9 work was added.
- **Status:** 8B IMPLEMENTED / PARTIALLY VERIFIED; 8C–8F NOT STARTED. Stop before 8C. Exact resume: implement a deterministic classifier only for `comparable` outcomes and prove exact synthetic class counts/areas before artifact integration.

## Phase 8 task 8A — 2026-09-24

- Created the authorized 8A–8F tracker while retaining the unavailable original Phase 8 title. Audited Phase 5–7: real visual scene comparison works; synthetic preparation/grid/registration/job paths work; real single-scene extraction exists; real prepared pairs and production PostgreSQL/identity remain unverified; assistant output is not change evidence.
- Added the closed two-date result contract with chronological stable scene/date evidence, AOI, common-grid processing parameters, fixed changed/unchanged/unknown classes, explicit joint-valid/joint-usable coverage and projected-cell areas, warnings, classification artifact, and reproducible input/parameter/software provenance. Validators prevent unknown-as-unchanged, inconsistent arithmetic, unbound provenance, client URLs/paths, and fabricated confidence.
- Changed the schema/persistence artifact unions to recognize `change_classification`; no job operation, route, migration, detector, raster result, database row, or UI was added.
- Validation: focused schema/processing tests 32/32; scoped Ruff check/format and strict mypy passed. Live pair/change/database/browser checks were not run in contract-only 8A.
- **Status:** 8A COMPLETE; 8B–8F NOT STARTED. Stop before 8B. Exact resume: implement the pure deterministic 8B common-grid change service from exact synthetic arrays, without API/job/UI work.

## Phase 7 task 7F — 2026-09-24

- Executed Phase 7 closeout without starting Phase 8. One real Earth Search Sentinel-2 input produced a QA-ready 110×113 scientific chip with source identity, acquisition, RGB assets, EPSG:32643 affine, checksum, fixed rendering, 100% RGB validity, and 99.634% QA-usable coverage.
- Ran pinned `IDEA-Research/grounding-dino-tiny` on that exact chip. It returned one near-whole-chip `vegetation` rectangle (raw uncalibrated relevance 0.6482); model inference was 5.915 s CPU, cold load plus inference 30.159 s, end-to-end 77.200 s. Source/overlay inspection and independent projected-to-WGS84 conversion confirm placement, but the broad box is weak localization and not accuracy evidence.
- VQA/caption success is unavailable because the server provider/model/key settings are absent. No licence-reviewed annotated VQA/caption/grounding sample exists locally; evaluated real sample size is one unannotated chip and no benchmark metric is claimed. PostgreSQL/verified identity remain unavailable; bounded remote range reads are intermittent.
- Real browser fallback verified AOI restore, catalogue search, six results, scene selection, question submission, safe inference failure/retry, refresh clearing the result, and console/API failures. Automated tests cover unsupported measurement, failed/unknown quality, unavailable model, no detection, invalid grounding, stale scene, and unauthorized artifacts.
- Changed: `backend/src/satquery/inference/chip.py`, `backend/tests/test_vqa_inference.py`, real verification scripts, `docs/phase-7f-browser-outcome.png`, and the Phase 7/roadmap/setup/contract checkpoints. Passed `scripts/verify.ps1`, backend 187 passed / 1 skipped, frontend 114/114, focused backend 14/14, focused frontend 15/15, all lint/type/format gates, and production build.
- **Status:** Phase 7 PARTIALLY VERIFIED; 7F executed. Stop before Phase 8. Resume only to finish Phase 7 by configuring the pinned answer model and production PostgreSQL/principal, obtaining a licence-reviewed annotated sample, running successful real VQA and caption through the workspace, and repeating the real grounding map overlay.

## Phase 7 task 7E — 2026-09-24

- Connected the workspace composer to the typed Phase 7 start/status API for question, caption, and locate operations. The UI binds requests/results to the selected AOI and scene, reports actual job stages, preserves drafts for retry, rejects delayed/stale replacement, and retains old answers with a stale warning instead of placing them on a new scene.
- Added committed source-chip display, source/acquisition/model/quality/status details, explicit model-interpretation and unavailable language, pixel-box overlays, and validated UTM map footprints that can be hidden independently of the AOI. Updated backend artifact handling so the exact PNG input and evidence JSON are atomic, access-controlled, and jointly required for cache reuse.
- Changed frontend: `inference-client.ts`, `inference-grounding-map-layer.ts`, assistant/results/map/workspace components, responsive CSS, feature availability, and focused tests. Changed backend support: processing/VQA artifact schemas and inference/preparation job services. Added `backend/scripts/phase7e_verification_app.py` and desktop/compact screenshots under `docs/`.
- Passed: focused frontend 6/6, full frontend 114/114, frontend Biome/typecheck/build, full backend 186 passed / 1 skipped for absent PostgreSQL URL, backend Ruff/format/strict mypy. Browser layout screenshots were inspected. A real Earth Search job reached RGB extraction but failed safely at unreadable SCL; no real inference result exists. In-app browser automation was unavailable because sandbox policy metadata was missing, so full live click interactions are not claimed.
- **Status:** 7E IMPLEMENTED / PARTIALLY VERIFIED; stop before 7F. Resume by restoring browser automation and trusted SCL/model runtime, then complete real question→result and grounding→overlay interactions in the workspace.

## Phase 7 task 7D — 2026-09-24

- Added closed inference submission/evidence/job schemas; protected FastAPI start/status/result/cancel/artifact routes; and a durable inference worker over trusted catalogue, calibrated RGB extraction, SCL quality decoding, fixed scientific chip generation, 7B VQA/caption, and 7C grounding. No client URL/path or client-authored evidence is accepted.
- Generalized existing processing persistence to operation-scoped `prepare_optical`/`infer_single_image` submission, idempotency, cache, queued recovery, and claiming. Task 7E later extended the atomic result to an owner/scope-authorized exact PNG plus `inference_evidence` JSON pair. Quality decisions fail closed; model-unavailable, blocked, unknown, invalid grounding, interruption, cancellation, and safe failure remain distinct.
- Changed code: `backend/src/satquery/api/schemas/{processing,vqa}.py`, `api/routes/inference.py`, `api/router.py`, `api/dependencies.py`, `db/processing.py`, `inference/jobs.py`, `processing/jobs.py`, and `main.py`. Tests: `backend/tests/test_inference_api.py` plus operation-aware updates in `test_processing_jobs.py`. Contracts/checkpoints: `API_CONTRACT.md`, `docs/PHASE_7_{TASKS,REPORT}.md`, `CURRENT_PHASE.md`, and this file. No migration was needed because the existing table already has operation/version and unconstrained artifact-kind columns.
- Passed: focused 7D cases; Ruff; strict mypy; full backend 186 passed / 1 skipped (PostgreSQL URL absent). The FastAPI ASGI integration test runs a complete synthetic VQA job and cache reuse. An actual SatQuery API request naming real scene `S2C_T43PGQ_20251228T052411_L2A` returned expected `503 CAPABILITY_UNAVAILABLE` because verified identity/durable PostgreSQL are unavailable; no real inference result is claimed.
- **Status:** 7D IMPLEMENTED / PARTIALLY VERIFIED; stop before 7E. Resume 7D verification by configuring the existing principal resolver and PostgreSQL, applying the current migration, repeating the real protected request, and inspecting the authorized evidence artifact. 7B live VQA/caption and 7C real-scene grounding remain separately blocked as recorded.

## Phase 7 task 7C — 2026-09-24

- Implemented pinned local `IDEA-Research/grounding-dino-tiny` referring-object detection with typed request/result/preprocessing contracts, separate selected crop prompts, box clipping, crop-to-chip mapping, affine chip-to-map footprints, explicit outcome states, raw uncalibrated model scores, and boxes-only/no-mask semantics. Added pinned `torch`, `transformers`, and Pillow grounding dependencies and regenerated the lock.
- Verification passed: six focused grounding tests; full non-database backend 181/181; Ruff/format and strict mypy across 80 files; and the 34-file documentation audit with zero broken relative links and 16 roadmap rows. The actual public checkpoint ran locally on CPU against the labelled synthetic 16×16 chip, producing one near-full-chip `vegetation` box in 5.30 s. Visual inspection confirmed the overlay matches those coordinates; it is not accuracy or real-scene evidence.
- Blocked: `verify_grounding.py` reached three real Earth Search Sentinel-2 candidates, but each trusted COG extraction hit its bounded range deadline. No real chip reached the model, so the required real-scene region and visual inspection are unavailable. No thumbnail/basemap was substituted.
- **Status:** 7C PARTIALLY VERIFIED; stop before 7D. Restore reliable trusted COG reads, rerun the verifier, inspect the real source and overlay, and record the actual outcome/uncertainty before completing 7C.

## Phase 7 task 7B — 2026-09-24

- Implemented `satquery.inference`: trusted calibrated/SCL-masked RGB chip generation, provisional VQA input gate, pinned OpenAI Responses transport, separate VQA/caption operations, strict structured results, question/quality refusal, checksum binding, and bounded bytes/pixels/question/output/time/concurrency. Added optional all-or-none server settings and internal lifespan wiring; no route/job/UI or new dependency was added.
- The chip preserves stable scene and source assets, acquisition, fixed render recipe, dimensions, AOI footprint, CRS/affine, checksum, and Phase 6 context. Basemap/preview/thumbnail and arbitrary URL/path inputs are excluded. Model prose remains non-measured; confidence and grounding are unavailable.
- Passed: focused 23/23, Ruff/format 81 files, strict mypy 77 source/test/script files, non-database backend 175/175, and the 34-file documentation audit with zero broken relative links and 16 roadmap rows. The deterministic fake transport is labelled and never a production fallback.
- Blocked/not run: all runtime AI variables remain unconfigured, so actual VQA/caption output and provider latency are unavailable. Two real-scene verifier runs reached Earth Search but trusted COG range reads timed out, including unrestricted network. No display asset was substituted.
- **Status:** 7B PARTIALLY VERIFIED. Its former stop-before-7C boundary was superseded by the authorized 7C work above. To finish 7B, configure `RUNTIME_AI_PROVIDER=openai`, pinned `RUNTIME_AI_MODEL`, and server-only `RUNTIME_AI_API_KEY`; restore reliable COG range reads; run `backend/scripts/verify_vqa_inference.py`; and record both real outputs and latencies.

## Phase 7 task 7A — 2026-09-23

- Selected pinned hosted `gpt-4.1-mini-2025-04-14` as the first bounded single-image VQA/caption adapter target. It has not been called: no AI provider/model/credential is configured. The current host has about 15.7 GiB RAM and no demonstrated usable NVIDIA runtime or installed local model stack.
- Evaluated GeoChat-7B's real remote-sensing caption/VQA/grounding support, approximately 14.1 GB custom float16 checkpoint, Apache-2.0 model-card tag, custom runtime, and unresolved base/dataset deployment review. It is not feasible as the initial path here; it remains only a separately gated grounding research candidate.
- Added strict `vqa.py` contracts for the authorized fixed-render chip, pixel-edge/map transform, request, explicit answer availability, model/version, image evidence, retained Phase 6 quality, warnings/actions, optional coordinate-labelled grounding, and null-only calibrated confidence. Arbitrary URLs/paths/extras, inaccessible inputs, per-image normalization, quality contradictions, invalid coordinates, and numeric confidence are rejected.
- Verification passed: focused 6/6; Ruff/format 76 files; strict mypy 42 source files; non-database backend 166/166; docs 35 files, zero broken links, 16 roadmap rows. Live inference, endpoint/job/persistence/UI/browser, grounding accuracy, training, and database were not run or added.
- **Status:** 7A COMPLETE; 7B–7F NOT STARTED. Stop before 7B. Exact next action after explicit authorization: implement the bounded provider-neutral adapter with deterministic fake transport against `test_7b_acceptance_contract_fixture_is_executable_and_retains_failed_quality`, then conditionally report a pinned-model live caption/VQA smoke only if server configuration exists.

## Phase 6 task 6I — 2026-09-23

- Integrated available evidence passed for real catalogue selection, all non-database static/test/build gates, and a new synthetic pair through job/grid/registration/validity/artifact/cache code. The live search returned `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`; the synthetic pair correctly produced inconclusive registration and `not_ready`, not a fabricated alignment/readiness claim.
- Full gate: Ruff/format passed for 74 Python files, strict mypy for 61 source/test files, backend 160 passed/1 database test deselected, frontend 108 passed across 24 files, Biome, TypeScript, and optimized build. The 33-file documentation audit found zero broken relative links and 16 roadmap rows. Request schemas reject source/artifact URLs, thumbnail URLs, display stretches, and client-claimed readiness; missing measurements cannot pass.
- Blocked: Docker Desktop Linux engine/PostgreSQL, verified identity injection, real protected single/pair jobs, committed real report/artifacts/cache/interruption/access checks. Readiness and preparation returned truthful 503 responses; the production verifier stopped at interruption reconciliation. Browser setup failed on missing `sandboxPolicy`, so no new screenshots exist.
- **Status:** Phase 6 is PARTIALLY VERIFIED, not complete. Stop before Phase 7. Exact resume: restore Docker/PostgreSQL and apply migration `20260923_0002`, configure the server-owned verified principal resolver, run real single/pair preparation plus cache/interruption/artifact checks, then repeat the workspace browser workflow and capture laptop/mobile screenshots.

## Phase 6 task 6H — 2026-09-23

- Implemented the workspace preparation/quality panel for the current AOI and selected scene or ordered pair. It exposes profile/limits, actual job progress, source dates, readiness, measured coverage/quality, resolution/registration, warnings/unknowns/actions, retry, artifacts, and optional computed usable/exclusion map overlays. Future analysis is disabled and no AI answer/confidence exists.
- Result binding covers AOI geometry, scene keys, profile, and UI processing version. Changed inputs abort active polling, mark completed results outdated, remove overlays, and prevent delayed results from taking over. The new protected mask-tile endpoint accepts only authorized committed quality artifacts and allow-listed categorical views.
- Verification passed: focused frontend/workspace 21/21; full frontend 108/108, Biome lint, TypeScript, optimized build; backend focused 6/6, strict mypy for 41 source files, non-database pytest 156 passed/1 deselected, and scoped 6H Ruff/format. Full Ruff remains failed only by the pre-existing unformatted 6G Alembic migration. Live browser layout verification was unavailable because browser sandbox metadata was missing; automated responsive/keyboard checks passed, but no visual success is claimed.
- **Status at the 6H handoff:** Tasks 6A–6H were complete and 6I had not yet run. The authorized 6I checkpoint above supersedes that boundary; the identity/PostgreSQL and real-job gaps remain current.

## Phase 6 task 6G — 2026-09-23

- Implemented the protected durable preparation workflow: migration `20260923_0002`, PostgreSQL repository, bounded lifespan dispatcher, access-scoped/idempotent cache identity, restart/cancellation/failure semantics, atomic private local artifact store, full reproducibility manifest, and protected start/status/cancel/report/artifact routes.
- Routes require an injected verified principal and deliberately return capability-unavailable without identity configuration. Database/artifact publication is mandatory; no in-memory production fallback exists. Public catalogue/map paths remain independent.
- Focused processing job/API tests passed 6/6; Ruff/format, strict mypy, full non-database pytest (156 passed, 1 deselected), and static Alembic head/history passed. Docker engine/PostgreSQL remained unavailable. The production-bound real verifier stopped before acceptance with `Interrupted job reconciliation failed.`; no real artifact or quality result is claimed.
- **Status:** Tasks 6A–6G complete; stop before 6H. Exact resume action only with explicit authorization: execute Task 6H failure/security/performance/reproducibility verification. First rerun the real database/migration and `backend/scripts/verify_processing_job.py` gates when Docker/PostgreSQL is available.

## Phase 6 task 6F — 2026-09-23

- Completed only the deterministic Scientific Validity Engine and GeoFeasibility Guard. Explicit v1 single/pair profiles consume measured 6B–6E evidence plus authoritative acquisition metadata and requested scale. Checks cover required bands/L2A/calibration, AOI validity/quality, pair overlap/usability, resolution/upsampling, registration, sensor/product, dates/order, platform/seasonal context, and a three-native-pixel spatial-support floor. No LLM exists.
- Each check returns pass/warning/fail/unknown/not-applicable with measurements, units/denominator, provisional versioned threshold, reason, evidence source, and corrective action. Fail → not-ready; required unknown → unknown; warning → limited; all required pass → ready. Viewing/search are unaffected, and no overall accuracy/confidence or object-detection promise is produced.
- Six focused tests, Ruff/format for 62 files, strict mypy for 36 source files, and 150 non-database tests passed. Thresholds and boundary semantics are in `docs/PHASE_6_REPORT.md`. Stop before 6G.

## Phase 6 task 6E — 2026-09-23

- Completed only registration assessment and controlled correction for a 6D same-sensor Sentinel-2 pair. A quality-masked red band is evaluated in a 3×3 distributed layout using bounded integer masked ZNCC; five estimation patches establish spatial consensus and four held-out patches provide independent residual evidence. Matching grids, one score, low texture, missing QA, boundary peaks, or unavailable diagnostics never prove registration.
- Records include moving-B-to-reference-A row/column and map displacement, all patch diagnostics/distribution, agreement/inliers, held-out before/after evidence, and reliable/inconclusive/unsupported state. Only an independently improved integer translation may be applied; originals remain, data and masks move together, borders become missing, and overlap is recomputed. No flexible warp or accuracy claim exists.
- Six focused tests, Ruff/format for 60 files, strict mypy for 35 source files, 144 non-database tests, and the 86-file/zero-broken-link documentation audit passed. The real pair attempt failed at the trusted remote COG encoded-tile read before assessment, so no real displacement or ground-truth accuracy is claimed. Stop before 6F.

## Phase 6 task 6D — 2026-09-23

- Completed only common-grid/resolution harmonization. One AOI-derived, pixel-aligned UTM grid is declared once for one scene or pair; unsupported zones/hemispheres/latitudes and excessive grids fail. Every calibrated band is reprojected to it with the recorded continuous method and invalid input as nodata; every validity/SCL/quality mask uses nearest-neighbour.
- Results preserve source/calibration metadata and values without a second calibration or normalization. They expose per-band and per-scene validity, harmonized quality masks, pairwise joint-valid/joint-usable masks, explicit pixel/area denominators, native/output resolutions, upsampling disclosure, no radiometric harmonization, and `registration_status=not_assessed`.
- Six focused tests, Ruff/format for 57 files, strict mypy for 34 source files, 138 non-database tests, and the 86-file/zero-broken-link documentation audit passed. Three bounded real-pair attempts failed at remote COG encoded-tile reads despite unrestricted-network, alternate-scene, and alternate-AOI retries; no real-pair measurements are claimed. Stop before 6E.

## Phase 6 task 6C — 2026-09-23

- Completed only the explicitly requested cloud/shadow/missing-data-mask scope. Earth Search now resolves the real `scl` QA COG separately from RGB through the same trusted destination/access boundary. No route was exposed.
- Added separate outside-AOI, missing/invalid, cloud/cirrus, cloud-shadow, cast-shadow, snow/ice, unknown, usable, and union masks. SCL class labels survive nearest-neighbour transfer; GDAL/NumPy inverse mask conventions are verified; valid dark/water pixels are preserved; absent QA becomes unknown and not usable. Coverage carries explicit denominators and overlaps are unioned once; catalogue cloud remains separate.
- Seven synthetic mask tests and two new provider cases pass; the focused asset/quality set passed 15/15. Ruff/format passed for 54 files, strict mypy for 33 source files, and the full non-database suite passed 132/132 with one database integration test deselected. The 26-file documentation audit found zero broken links, 16 phase rows, and one active row.
- Real verification used `S2C_T43PGQ_20251228T052411_L2A` SCL baseline 05.11: 25/107 cloud/cirrus, 82/107 cloud shadow, 14/121 unknown, exclusion union 121/121, usable 0/121; separate catalogue scene cloud 28.287384%. Stop before 6D.

## Phase 6 task 6B — 2026-09-23

- Completed only the explicitly requested AOI clipping and calibrated raster-input scope. Added an internal one-scene `RasterInputService`; no route was exposed while authentication/owned-resource authorization remains unavailable. Stable scene identity is resolved only by the trusted adapter, and production reads reuse existing destination, range, byte/deadline, content-length, and header checks.
- The service transforms WGS 84 AOIs to the source CRS, uses source-aligned window reads, preserves holes, and returns calibrated `float32` data plus a separate inside-AOI mask and per-band validity. Metadata includes exact source IDs/order, units `1`, provider/applied scale/offset, nodata, native resolution, CRS, affine, bounds, and dimensions. Invalid cells stay `NaN`; no clamp, contrast, date normalization, model normalization, reprojection, or resampling occurs.
- Focused synthetic tests passed 6/6; Ruff check/format passed for 51 files; strict mypy passed for 32 source files; the full non-database backend suite passed 123/123 with one database integration test deselected. The real script passed for scene `S2C_T43PGQ_20251228T052411_L2A`, producing a 12×13 EPSG:32643 window at 10 m with 121 valid inside-AOI pixels per RGB band. The 26-file documentation audit found zero broken relative links and 16 phase rows. Exact measured ranges are in the Phase 6 report.
- No job/queue, persistence, database, artifact file, quality/readiness, pair work, model, frontend/browser, AI answer, change class, percentage, or confidence was added. Stop before 6C; exact resume action is the unauthorized 6C row in `docs/PHASE_6_TASKS.md`.

## Phase 6 task 6A — 2026-09-20

- The user authorized an optical processing-preparation working scope through tasks 6A–6I while the original Phase 6 title/scope remains unavailable. Only 6A was implemented; stop before 6B.
- Added closed Pydantic contracts for one supported Sentinel-2 L2A scene or pair, validated AOI/bands/options, consistent output grid, prepared raster plus separate validity/quality masks, calibration, provenance, measured quality checks, independent task readiness, job lifecycle, and opaque artifact metadata. Successful processing does not imply suitability; unknowns stay null/unresolved.
- Backend Ruff format/check and strict mypy passed for 43 files; focused processing tests passed 15/15; the full non-database suite passed 117 tests with one database integration test deselected. The documentation audit passed for 26 governed Markdown files/43 relative links, zero broken targets, 16 phase rows, and one active row. An initial post-hardening test expected the later result validator but supplied a mathematically inconsistent passing quality outcome; the synthetic fixture was corrected before the clean passes.
- No endpoint, OpenAPI route, worker, persistent job, storage, database/schema migration, provider/raster fetch, artifact creation, frontend/browser flow, real preparation, pair alignment, AI answer, change class, percentage, or confidence was implemented or tested. Docker/PostGIS readiness remains independently blocked and unwaived.
- Changed files are listed in `docs/PHASE_6_REPORT.md`. Exact resume action: only if explicitly authorized, perform 6B as defined in `docs/PHASE_6_TASKS.md`; otherwise stop.

## Two-date comparison maintenance — 2026-09-15

- Completed the user-authorized comparison-only repair. Scene A is the earlier distinct acquisition and Scene B the later one; Swipe is default, Split uses synchronized side-by-side maps, and Blink alternates two retained synchronized maps. Labels expose exact UTC date, item ID, platform, and cloud percentage. Missing imagery and tile failures continue to use explicit existing states.
- Fixed the comparison canvas height cascade and mounted the existing real imagery layer before adding the AOI source/layers, keeping the AOI above both rasters. Added focused coverage for default/mode switching, automatic/manual Blink, map synchronization, metadata, and AOI presence. Changed frontend files: `src/components/workspace/comparison-viewer.tsx`, its test, `scene-container.tsx`, and `src/app/globals.css`.
- Live Chrome/WebGL passed with real Dec 23 Scene A and Dec 28 Scene B Sentinel-2 acquisitions: both raster states reached ready, Swipe moved to 68%, Split displayed both, Blink changed from A to B automatically, and a drag on A shifted both AOI outlines identically. Reassigning A to the real Dec 13 acquisition updated the reopened viewer without changing B. Verification used the repository's local synthetic basemap style only to isolate a transient external basemap-style outage; both comparison layers were real FastAPI-served georeferenced Sentinel-2 PNG tiles, never thumbnails or fixtures.
- Final verification passed: 20/20 focused frontend tests, frontend typecheck, focused Biome, optimized build, and 10/10 backend imagery-tile tests. One test timed out only during the initial concurrent check, then passed in isolation and in the complete rerun. No backend, database, AI, NDVI, scientific comparison, or Phase 6 work occurred. Resume only if explicitly directed; stop before Phase 6.

## Selected-scene rendering maintenance — 2026-09-15

- Wired catalogue result selection to the existing real imagery tile resolver so “Select scene” both records the selected metadata and opens the corresponding MapLibre raster layer. The explicit Reload imagery action remains available for retry/re-resolution, and the UI still labels raster display as visualization-only.
- Live localhost Chrome/WebGL passed with the Bengaluru AOI: real `S2C_T43PGQ_20251228T052411_L2A` imagery appeared, then real `S2B_T43PGQ_20251223T051848_L2A` replaced it and reached “Imagery rendered from georeferenced raster tiles.” The basemap, AOI outline, pan/zoom, selected metadata, and Fit scene remained functional.
- Verification: focused frontend tests 17/17, frontend typecheck, optimized build, and focused backend catalogue/imagery tests 26/26 all passed. A current May provider tile initially timed out and the existing partial/failure handling remained truthful; known December tiles subsequently rendered successfully. No backend/database/analysis/comparison code changed. Resume only if explicitly directed; do not begin Phase 6.

## Current state

- **Active phase:** Phase 6 — original agreed title unavailable. User-authorized working scope: optical processing preparation contracts, one-scene preparation, one supported optical pair, quality/readiness, jobs/artifacts, and verification through tasks 6A–6I.
- **Status:** Tasks 6A–6H are complete; 6I is partially verified and blocked on the recorded real integration gates. Phase 5 tasks 5A–5H remain complete. The real PostgreSQL/PostGIS readiness and 6G production job gates remain independently carried and unpassed.
- **Stop boundary:** stop before Phase 7; the original Phase 6 title/scope remains unavailable and was not invented.
- **Carried gates:** Phase 1 real PostGIS/migration/readiness, Phase 2 browser, and Phase 3 browser/authenticated-owner/persistence evidence remain unwaived and unpassed.
- **Repository state:** Git metadata is unavailable to the workspace. Task 6G adds a protected preparation route/job/persistence/artifact subset but no configured identity provider, provider secret, frontend, runtime model, AI answer, or change result.
- **Local verification services:** the temporary SatQuery frontend/backend verification processes were stopped after the live checks. PostgreSQL/PostGIS remains unavailable.

## Phase 3 AOI-selection verification — 2026-09-15

- Live MapLibre/Terra Draw verification passed for rectangle and polygon drawing, persistent highlight, valid closed Polygon GeoJSON, geodesic km² area, derived bounds, both existing AOI summaries, clear, browser-draft state, and exact-AOI catalogue recognition. A polygon search posted its exact coordinates and returned HTTP 200 with six real metadata results; no scene was opened.
- Fixed the sole observed gap: `Search imagery` was enabled without an AOI. It now remains disabled until `selectedAoi` exists; the request builder's defensive no-AOI validation remains.
- Final checks passed: frontend typecheck, 35/35 focused tests across AOI/storage/discovery/scene integration, and optimized build. The first sandboxed Vitest startup failed `spawn EPERM`; permission-scoped and final runs passed. The managed browser lacked `sandboxPolicy`, so isolated hidden Chrome supplied live evidence.
- Changed only `frontend/src/components/workspace/imagery-discovery-panel.tsx`, its focused test, and checkpoint documentation. No backend storage, database, imagery rendering, AI, dependency, environment, or new phase work occurred. Phase 5 remains complete; stop before Phase 6.
- Follow-up: added a compact always-visible map toolbar for `Draw rectangle`, `Draw polygon`, and `Clear AOI`, sharing the existing Terra Draw actions. Removed only the duplicate clear button from the scrolled GeoJSON section. Live Chrome confirmed selection survives zoom/pan, all three AOI status surfaces update, clear resets them and disables search, and polygon search succeeds. Final Biome/typecheck/build and 36/36 focused tests passed; an initial new-test assertion failed on the intentionally repeated empty-state text and passed after using the correct multi-element assertion.

## Phase 3 basemap repair — 2026-09-15

- Fixed only the real MapLibre/OpenFreeMap Liberty context basemap. A CSS cascade conflict changed `.map-canvas` from absolute to relative and collapsed it to 0 px even though its stage was 859 px high. The scoped `.map-stage > .map-canvas` rule now wins and explicitly fills the stage.
- `MapCanvas` now treats the Liberty `style.load` event as map-ready, avoiding a false 20-second timeout after the map is already rendered. The public style, TileJSON, sprites, glyphs, and visible tile resources returned HTTP 200; no static map, Google Maps, imagery, AI layer, backend, database, env, manifest, or dependency change was made.
- Live isolated Chrome at `/workspace` showed a 972×859 real map centered on India with water, context/terrain, boundaries, roads/place labels, attribution, and `Map ready`. Zoom changed 500 km to 300 km; drag-pan changed center 78.96290/20.59370 to 75.85550/22.32878. No page exception or console error was observed.
- Verification passed: frontend typecheck; focused SceneContainer 8/8; optimized Next build. The in-app browser still lacked required `sandboxPolicy`, so isolated hidden Chrome supplied browser evidence. Phase 5 remains complete; stop before Phase 6.

## Local startup verification — 2026-09-15

- Inspected the documented startup files, manifests, lockfiles, existing redacted local-environment key status, runtimes, dependencies, listeners, and entry points. The backend entry point is `satquery.main:create_app` from `backend/src/satquery/main.py`; the frontend command is `npm.cmd run dev` from `frontend/`.
- Reused the already-running SatQuery frontend on port 3000. Started the FastAPI development server with `..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host ::1 --port 8000` because another repository already owns `127.0.0.1:8000`. The frontend's existing `http://localhost:8000/api/v1` setting reaches SatQuery over IPv6 without a file change.
- Passed: root homepage HTTP/render, workspace HTTP/render, liveness HTTP 200 and exact SatQuery identity, docs/OpenAPI HTTP 200, browser-origin CORS preflight HTTP 200, browser fetch to liveness HTTP 200, and live catalogue collection HTTP 200. The workspace visibly reported `Database unavailable`; readiness correctly returned retryable HTTP 503 with no-store and Retry-After.
- Browser fallback found no page exception or console error. Its three resource-error entries were expected readiness 503 responses. The in-app browser connection itself remained unavailable because required `sandboxPolicy` metadata was absent.
- Docker, Podman, `psql`, and `pg_isready` are unavailable, so `docker compose up --wait -d db`, Alembic migration, and database-backed readiness HTTP 200 were not run. Redis is not declared or required by the current build.
- No application code, manifest, lockfile, environment file, dependency, database, or phase scope changed. Local verification screenshots are `tmp/startup-home.png` and `tmp/startup-workspace.png`. Exact resume action: reuse the two running services; after either stops, use the commands above and `npm.cmd run dev`, preserving the IPv6 host while the unrelated IPv4 port owner remains.

## Database-only recovery attempt — 2026-09-15

- Root cause remains an absent database runtime: no PostgreSQL/PostGIS listener/service/process, Docker/Podman command or engine, Docker Desktop installation, or WSL installation exists. The validated root `.env` and Compose connection tuple agree; the frontend API URL and readiness endpoint are correct.
- `scripts/verify-database.ps1` failed only at its Docker preflight. Real PostgreSQL connectivity, PostGIS, migration application, readiness HTTP 200, and frontend `Backend ready` remain failed/unavailable and were not simulated.
- Corrected `backend/alembic/env.py` to use `SelectorEventLoop` on Windows for Psycopg async and to pass the existing configured connection timeout into the Alembic engine. The migration command now reaches a bounded database connection timeout instead of the prior Proactor incompatibility or indefinite wait.
- Verification passed for scoped Ruff/format/mypy and 11/11 config/health tests; liveness remains HTTP 200, static Alembic head is `20260907_0001`, readiness remains the expected HTTP 503, and isolated Chrome confirmed `Database unavailable`. No map/feature/schema/dependency/env/phase work occurred.
- Resume only after Docker Desktop with a supported Linux-container backend is installed and running on the host; then run `docker compose up --wait -d db`, `backend\..\.venv\Scripts\python.exe -m alembic upgrade head`, and the real readiness/database gate. Stop before Phase 6.

## Phase 5 task 5H

- Completed the real browser workflow from AOI/catalogue through imagery, controls/reset, real two-date comparison, timeline, reload restoration, and AOI invalidation. The restored real scene was `S2B_T43PGQ_20260512T052201_L2A`; two fresh z8 tiles returned 200. Five screenshots are linked from `docs/PHASE_5_REPORT.md`.
- Fixed comparison draft normalization so A/B labels and assignments consistently mean earlier/later. Focused post-fix tests passed 10/10.
- Backend Ruff/format/mypy and 102/102 selected tests passed. The combined frontend worker timed out before tests ran; the clean standalone suite passed 98/98. Final format/lint/typecheck and optimized build passed.
- Failure/security checks passed for partial tiles, unreachable metadata, stale AOI state, invalid path/URL input, arbitrary presets, and internal providers. No arbitrary upstream-fetch surface or authorization bypass was introduced.
- `scripts/verify-database.ps1` remains blocked because Docker is unavailable. This carried Phase 1 readiness gate is unwaived; Phase 5 viewer-scope gates pass. Do not begin Phase 6 without explicit authorization and its authoritative title/scope.

## Phase 5 task 5G

- Added a chronological actual-acquisition timeline for current AOI/filter catalogue pages, exact timestamps and duplicate-date labels, direct/previous/next viewer selection, A/B assignment, stale invalidation, and explicit incomplete-pagination wording. Playback was not roadmap-required and was not added.
- Extended the version 1 closed saved-state contract with AOI fingerprint, camera, partial/complete comparison slots, and active timeline state. Browser storage contains stable identities/settings only; restore validates AOI/current metadata and re-resolves imagery, with no tile/provider URLs, credentials, expiry, or render claims.
- Backend contract Ruff/format/mypy and 17/17 tests passed. Frontend format/lint/typecheck, focused 19/19, prior full 97/97, and production build passed. Initial `spawn EPERM` and two worker-start timeouts before tests are recorded; a clean focused 8/8 rerun passed.
- Live Chrome/WebGL loaded six real current Sentinel-2 acquisitions, warned that more pages remained, rapidly selected Apr 17→22→27, rendered `S2C_T43PGQ_20260427T051531_L2A`, and restored the exact scene/camera after reload using fresh metadata and real z8 tiles. In-app attachment remained blocked by missing `sandboxPolicy`; [screenshot](docs/phase-5g-restoration.png).
- No server persistence, interpolation/playback, scientific co-registration/change result, or analysis was added. This historical 5G boundary is superseded by the completed 5H section above.

## Phase 5 task 5F

- Added selected-scene A/B assignment with distinct identity, chronological A/B normalization, bbox overlap gating, two real imagery maps, synchronized camera, swipe/split layouts, keyboard divider, accurate side swap, visible linked/independent opacity, metadata-difference disclosure, and per-side failure/cleanup.
- Evaluated but did not install `maplibre-gl-compare`; the local React-owned adapter fits MapLibre 6.9.0, native accessibility, typed lifecycle, and cleanup without a new package.
- Focused tests passed 10/10. Final Biome/typecheck, 91/91 frontend tests, and optimized build passed. Initial sandbox `spawn EPERM`, fork-worker timeout before tests, and corrected assertions/mocks are retained as failed attempts.
- Live Chrome/WebGL rendered real Dec 23/Dec 28 Sentinel-2 scenes from z8 SatQuery tiles. Divider 50→51, linked opacity 1→0.95, independent B 0.95→0.90, split/swap resize 866→432, and cleanup to one base canvas passed. An earlier real May B-side asset failure remained explicit. In-app attachment failed because `sandboxPolicy` was missing; [screenshot](docs/phase-5f-comparison.png).
- Documentation audit passed: 24 governed Markdown files, 32 relative links, zero broken targets, 16 phase rows, and one active row.
- No timeline/saved state, co-registration, automated change, percentage, confidence, scientific processing, or analysis was added. Resume only with 5G if explicitly authorized.

## Phase 5 task 5E

- Added accessible visibility, opacity, brightness floor/ceiling, contrast, saturation, supported-preset, and reset controls. Updates are validated/debounced MapLibre paint changes that preserve source, camera, AOI, catalogue results, and scene selection.
- Only `natural-color` is enabled. False colour lacks a resolved near-infrared band and single-band is not approved. The server validates exact RGB asset-role order, applies per-band scale/offset and one fixed 0.00–0.30 reflectance range, and rejects unsupported presets/extra display fields.
- Backend focused checks and 10/10 tile tests passed; the full selected backend suite passed 101 tests with one database test deselected. Frontend static checks, clean 86/86 tests, and optimized build passed. The combined script's frontend fork worker timed out before tests ran and remains a failed attempt.
- Live isolated Chrome/WebGL opened `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`, reached ready from real z8 tiles, verified keyboard and every supported control plus reset/visibility, preserved camera/AOI/selection, and issued no replacement metadata request. A later provider range failure was truthfully partial. The in-app connector remained unavailable because `sandboxPolicy` was missing.
- Documentation audit passed: 24 governed Markdown files, 28 relative links, zero broken targets, 16 phase rows, and one active row.
- No comparison, timeline/saved viewer state, persistence, scientific processing, or analysis was added. Resume only with 5F if explicitly authorized.

## Phase 5 task 5D

- Added stable-identity tile metadata client, MapLibre raster adapter, and workspace open/reload/fit/retry/remove flow. Imagery uses backend xyz metadata and stays below AOI/catalogue outlines; stale responses, style reload, replacement, and unmount are guarded/cleaned.
- Added same-origin MapLibre 6.9.0 worker/shared modules and a labelled synthetic background-only browser fixture. These are map runtime/verification assets, not analytical inputs.
- Focused tests passed 9/9. Live Chrome/WebGL2 rendered real z8 tiles for `S2C_T43PGQ_20251228T052411_L2A`, then removed it and rendered `S2B_T43PGQ_20251223T051848_L2A`. The UI truthfully surfaced an earlier provider failure as partial. Panel resize kept canvas/client widths aligned at 812 then 1204 pixels.
- Final verification passed: 101 non-database backend tests (one database test deselected), 85/85 frontend tests, static checks, and optimized build. MapLibre worker/shared public assets match the installed 6.9.0 hashes; Biome excludes only those vendor files from rewriting.
- Documentation audit passed across 24 governed Markdown files with zero broken relative links, 16 phase rows, one active row, and no stale current 5D boundary.
- No display adjustment controls, comparison, timeline/saved viewer state, database persistence, scientific processing, or analysis was added. Resume only with 5E if explicitly authorized.

## Phase 5 task 5C

- Added closed tile-metadata and PNG endpoints using only stable scene identity and fixed `natural-color`/256-pixel WebMercatorQuad parameters. Opaque tile-set IDs expire, bind to access scope, and never expose provider locations.
- The service reuses 5B, validates exact provider destinations and raster metadata, and uses rio-tiler/Rasterio plus a validated HTTP range opener for windowed COG/overview reads. Nodata is transparent; upstream/all-invalid/timeout/access/expiry/bounds failures remain errors.
- Pinned rio-tiler 9.4.4, Rasterio 1.5.1, and NumPy 2.5.3; regenerated/synced the pip-tools lock. Worker concurrency, 30-second API time, range request count/bytes/deadlines/cache, GDAL cache, tile-set TTL/count, and tile-byte memory are bounded.
- Rasterio is explicitly declared as a direct production dependency. After the final manifest/lock reconciliation, `pip check`, scoped Ruff/format, strict mypy, 10/10 focused 5C tests, and 101 non-database backend tests passed; the guarded database test remained deselected.
- Ruff/format, strict mypy, 10/10 focused tile cases, and the current 101-test non-database backend suite passed. Live API verification passed for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`, tile z8/x183/y118: HTTP 200, 57,718-byte 256×256 PNG, 17,285 valid/48,251 transparent pixels, database untouched. Browser/WebGL and analysis remain not run.
- Final repository verification passed on the clean rerun: 48 backend files, strict mypy over 41 source/test files, 100 non-database backend tests, frontend static checks, 80/80 frontend tests, optimized build, and `pip check`. The first full run's Vitest fork-worker timeout happened before any frontend test ran and is retained as a startup failure.
- Native GDAL proxy/Windows Schannel attempts and a z12 request correctly ending in bounded 504 are recorded failure evidence. The validated Python range opener and z8 check supplied the successful result. This was the historical 5C stop before 5D; the completed 5D section above supersedes that boundary.
- Documentation/roadmap audit passed across 24 governed Markdown files with 28 relative links, zero broken targets, 16 phase rows, and one active row.

## Phase 5 task 5B

- Added the closed `POST /api/v1/catalog/asset-resolutions` route and provider protocol operation for stable provider/collection/item identity. Only the configured public `earth-search` / `sentinel-2-c1-l2a` boundary is supported; no client path/URL or provider raster location enters the API contract.
- Earth Search maps RGB from allow-listed STAC roles/common names, retains per-band media/scale/offset/nodata/CRS/resolution/shape/transform, separates thumbnails/licence/attribution, and returns only the fixed natural-colour visualization preset. All three COGs must pass exact-host/path validation and bounded HEAD checks; redirects are revalidated.
- Explicit states are `supported`, `unsupported_format`, `unavailable_asset`, and `access_credentials_required`; failures return no resolved asset/components. Catalogue/access/render/analysis states remain separate, with rendering `not_requested` and analysis `not_assessed`.
- Focused formatting/Ruff/mypy passed; dedicated tests passed 7/7 and adjacent asset/provider/catalogue API tests passed 34/34, including expiry classification. Final repository verification passed: 91 non-database backend tests, all 80 frontend tests, static checks, and optimized build. Final live FastAPI resolution passed at `2026-09-12T06:14:24.457891Z` for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: HTTP 200, B04/B03/B02, EPSG:32643, 10 m, 10980×10980, scale 0.0001, offset −0.1, nodata 0, and three HTTP 200 HEAD checks. No body was downloaded; database guard untouched.
- Documentation/roadmap audit passed for 24 governed root/docs files, 28 relative Markdown links, zero broken targets, 16 phase rows, and one active row. A broad attempt that hit inaccessible generated pytest/tmp directories was discarded before the scoped clean rerun.
- Historical 5B stop: backend tiles and later viewer work were not implemented then. The 5C and 5D sections above supersede that boundary; tasks 5E–5H remain not started.

## Phase 5 task 5A

- Created `docs/PHASE_5_TASKS.md` before substantial work and assigned every mandatory requirement to tasks 5A–5H while preserving the exact unavailable-title placeholder and later scientific boundaries.
- Added `backend/src/satquery/api/schemas/viewer.py` and `frontend/src/lib/viewer-contracts.ts`. Their closed contracts cover stable scene/asset identity, visualization-only presets, tile metadata/access, active display/render state, comparison A/B acquisition, timeline selection, and safe versioned saved state.
- Catalogue availability, asset accessibility, render status, and analysis readiness are independent. Resolved assets contain no raster URL; tiles permit only mediated relative API templates; durable viewer state excludes tile delivery/access/expiry/render claims and secrets.
- Added synthetic contract suites: backend Ruff/format/mypy and 16/16 tests passed; frontend Biome/typecheck and 6/6 tests passed on a clean permission-scoped retry. The initial sandbox `spawn EPERM` and one permission-scoped worker timeout with no tests run are retained as execution evidence.
- Final `scripts/verify.ps1` passed on the clean rerun: 84 non-database backend tests, 80 frontend tests, all formatting/lint/type gates, and the optimized build. The first full run's intermittent existing scene-hover failure (79/80), its focused reproduction, unchanged isolated pass, and earlier focused worker startup failures are recorded in `docs/PHASE_5_REPORT.md`.
- At the historical 5A checkpoint, governing documentation and checks were synchronized and the required stop was before 5B.

## Completed task 4G

- Verified live collection listing, two query-bound catalogue pages with four distinct real Sentinel-2 items and zero duplicates, item detail/provenance/preview metadata/actual Polygon geometry, and an honest successful empty query through SatQuery's API.
- Verified controlled `429 RATE_LIMITED`, `503 UPSTREAM_UNAVAILABLE`, and `504 UPSTREAM_TIMEOUT` envelopes; provider failures did not become empty success. Focused workflow tests passed AOI search/change, pagination, card/map selection, fit/clear/remount, restore, corrupt/unavailable draft, empty, error, and retry behavior.
- Fixed the verification script to use the established 15-second Vitest timeout and made the scene integration assertion await React state propagation. The final full repository gate passed.
- Browser verification remains unavailable before tab creation because `sandboxPolicy` is missing. Direct preview bytes are blocked by an unavailable loopback proxy. Database verification remains blocked by missing Docker/PostgreSQL tooling; readiness remains HTTP 503 for `database`.

## Completed task 4F

- Added versioned browser-local persistence at `satquery.scene-selection-draft.v1` for the selected scene and exact cursor-free query. Runtime validation checks composite identity, query agreement, UTC interval, geometry/bbox, acquisition ordering, and safe licence reference.
- The draft preserves stable provider/collection/original-item identity, acquisition/retrieval time, source record/version, metadata digest, field provenance, licence/access state, and safe preview role/media metadata. It excludes preview URLs/expiry, provider cursors, credentials, raster URLs, and raster bytes.
- Restoration re-fetches current metadata through the existing item-detail API. Missing items retain explicitly unavailable historical provenance; provider failure remains stale with retry; corrupt/unsupported drafts are removed. The UI says `Saved in this browser` and keeps selection, advertised access, and unavailable analysis separate.

## Completed task 4E

- Added actual catalogue Polygon/MultiPolygon footprint layers to MapLibre with distinct current/stale/hover/selected states, card/map synchronization, clear and fit actions, style-reload restoration, and listener cleanup.
- Added typed workspace result/selection state keyed by provider ID + collection ID + item ID. AOI changes keep AOI geometry independent, mark old results stale, and clear/revalidate selection against the new query context.
- Added a metadata-only scene details view with real available preview and normalized metadata plus honest fallbacks. Provider previews stay in the panel; no raster layer, analytical asset, persistence, or analysis was enabled.

## Completed task 4D

- Added `catalog-client.ts`, a Zod-validating, abortable client for public collection listing/search and the common request-ID error envelope.
- Added the imagery-discovery panel inside the existing workspace map tools: selected AOI context, live collection/date/provider-cloud filters, search/retry/load-more, loading/empty/validation/provider states, real normalized scene cards, and honest missing thumbnail/metadata handling.
- AOI/filter fingerprints plus request sequence guards prevent obsolete completions from replacing current results. Prior-query cards are labeled and cannot paginate; the API continuation is forwarded unchanged and counts are explicitly loaded-card counts.
- Map navigation and AOI editing code remains intact. Discovery stays public/stateless and does not create a saved search, owned asset, analytical selection, or raster access.

## Completed task 4C

- Added public stateless `GET /api/v1/catalog/collections`, `POST /api/v1/catalog/searches`, and `GET /api/v1/catalog/collections/{collection_id}/items/{item_id}` routes backed by the configured provider.
- The FastAPI boundary uses the 4A AOI/date/timezone/provider/collection/cloud/page/cursor validation and typed output. Valid empty pages remain HTTP 200; invalid requests, unavailable capability, missing item, rate limiting, malformed upstream data, unavailable provider, and timeout remain distinct request-ID error envelopes.
- Provider continuation is preserved rather than offset-emulated. The cursor is bound to provider and canonical query/filter/page/order values and is validated before use. Anonymous public cursors do not replace future owner/expiry-bound saved-search cursors.
- Catalogue routes never access the database or persist pages. Anonymous access is limited to the configured public metadata adapter; authentication remains required for future saved searches, private providers, AOIs, owned asset intake, and analysis.
- Added `tests/test_catalog_api.py` with 16 tests and `scripts/verify_catalog_api.py` for a bounded live request through SatQuery's API. Provider timeout/rate/unavailable classes were made explicit; upstream retry guidance is bounded.

## Completed task 4B

- Added the provider-neutral protocol in `backend/src/satquery/providers/catalog/base.py` and the metadata-only `EarthSearchCatalogueProvider` in `earth_search.py`.
- The adapter is restricted to `https://earth-search.aws.element84.com/v1/` and `sentinel-2-c1-l2a`. It discovers capabilities/collections, uses AOI `intersects`, UTC interval, provider-reported cloud ceiling, stable acquisition/item sorting, item detail, and 4A normalization.
- Pagination accepts only a bounded token from an exact approved Earth Search `POST /v1/search` link and binds its opaque cursor to the original provider/query. All filters are reconstructed locally.
- Outbound controls: exact provider origin/path, no redirects, 10-second default timeout, two retries after the initial attempt with bounded jitter for classified transient failures, 10 MiB metadata ceiling, 32-entry/300-second default TTL/LRU cache, and an explicit public-thumbnail host allow-list.
- Actual missing metadata remains null/unavailable. Acquisition and retrieval timestamps are distinct. `provider_accessible` means only an advertised provider reference; no raster href is returned publicly and no raster bytes are fetched.
- Runtime configuration is in `backend/src/satquery/core/config.py` and `.env.example`. `httpx2==2.12.0` moved from dev-only to runtime dependencies; it was already present unchanged in `requirements.lock`.
- Test fixture `backend/tests/fixtures/stac/earth_search_sentinel_2_c1_l2a.json` is explicitly marked captured metadata, false for production fallback, and never imported by production code.

## Verification and errors fixed

- **PASSED:** Ruff check; Ruff format check, 32 files; strict mypy, 32 source/test/script files; 51 non-database pytest tests; `pip check` with no broken requirements.
- **PASSED:** documentation/roadmap audit, 26 relative links across 24 governed Markdown documents, exactly 16 phase rows, and one active phase row.
- **PASSED:** live production-adapter smoke at `2026-09-10T16:10:27.358819Z`. Query: Bengaluru-area Polygon `[77.5,12.9]` to `[77.7,13.05]`, 2025 UTC interval, `sentinel-2-c1-l2a`, cloud ceiling 100%, descending, limit 2. Actual IDs: `S2C_T43PGQ_20251228T052411_L2A`, `S2B_T43PGQ_20251223T051848_L2A`; next cursor present; second-item detail retrieved.
- **FIXED:** Earth Search serves queryables as standard `application/schema+json`; the validator now accepts `application/json` and `application/*+json`, with a regression test. Two earlier inline live-check attempts failed at Python parsing before adapter/network execution; `backend/scripts/verify_earth_search.py` is the checked-in reproducible replacement.
- **Historical 4B NOT RUN:** the one guarded database integration test, frontend/build/browser checks, catalogue API/OpenAPI checks, and Phase 4 database checks because 4B added none of those surfaces. The catalogue API checks were subsequently implemented and passed in 4C below.
- **PASSED for 4C:** Ruff, Ruff format for 35 files, strict mypy for 35 source/test/script files, focused API/provider/schema pytest with 49 tests, all 68 non-database backend tests, and `pip check`.
- **PASSED final live API at `2026-09-11T09:58:30.595641Z`:** HTTP 200 from `/api/v1/catalog/searches`, request ID `catalog-api-live-smoke`, actual item `S2C_T43PGQ_20251228T052411_L2A`, next cursor present, database guard untouched, and no raster fetched.
- **PASSED documentation/roadmap audit:** 26 relative links across 22 governed Markdown files, no broken targets, exactly 16 phase rows, and one active phase row.
- **FAILED then corrected:** `pytest -m not integration` was misparsed by the Windows shell as a path and collected zero tests. The explicit `--ignore=tests\test_database_integration.py` rerun passed 68 tests.
- **NOT RUN for 4C:** guarded database integration, frontend, browser, and authenticated-owner checks; these remain outside 4C and unwaived.
- **PASSED for 4D:** Biome format/lint, strict TypeScript, optimized Next build, 9 focused catalogue-client/panel tests, and all 59 frontend tests.
- **FAILED then corrected for 4D:** initial Windows workers hit `spawn EPERM`; scoped reruns passed. The first full suite revealed cross-file global-mock leakage and failed 6 panel cases; a typed injected client removed that coupling and the final run passed 59/59. Initial static format/lint/type findings were corrected before clean reruns.
- **PASSED live for 4D:** collection listing plus two search pages through the running SatQuery API returned four distinct actual Sentinel-2 IDs, MSI/cloud metadata, public preview references, attribution, and provider continuations.
- **PASSED for served boundaries:** `/workspace` returned HTTP 200 and the configured frontend-origin catalogue POST preflight returned HTTP 200 with `GET, POST, OPTIONS`.
- **PASSED documentation/roadmap audit:** 26 relative links across 23 governed Markdown documents, zero broken targets, 16 phase rows, and one active phase row.
- **NOT RUN for 4D browser:** the required in-app connector failed before tab creation because browser sandbox metadata lacked `sandboxPolicy`. A direct preview fetch also failed through the environment's unavailable loopback proxy; no rendered-thumbnail, screenshot, console/network, or responsive-browser evidence is claimed.
- **PASSED for 4E:** 7 focused scene-selection/map/integration tests, all 66 frontend tests, Biome format/lint, strict TypeScript, and the optimized Next build.
- **FAILED then corrected for 4E:** the sandboxed full-suite startup hit Windows `spawn EPERM`; an elevated rerun executed and exposed one global map-mock ordering failure. Explicit map-component injection removed the cross-file coupling, and the focused plus complete reruns passed.
- **PASSED live for 4E:** `/workspace` returned HTTP 200. `POST /api/v1/catalog/searches` returned HTTP 200 with request ID `phase-4e-live-geometry`, actual scene `S2C_T43PGQ_20251228T052411_L2A`, Polygon geometry, bbox `76.8405435490709,12.560413606130458,77.86185827663547,13.561138787915565`, and a continuation cursor. The first PowerShell-generated body flattened coordinate tuples and was correctly rejected with 422 before the literal valid GeoJSON rerun passed.
- **NOT RUN for 4E browser:** the required in-app connector again failed before tab creation because browser sandbox metadata lacked `sandboxPolicy`; no rendered MapLibre, responsive, screenshot, or console/network evidence is claimed.
- **PASSED documentation/roadmap audit:** 26 relative links across 22 Markdown files, zero broken targets, 16 phase rows, and one active phase row. The first audit used the wrong working directory and its invalid empty counts were discarded before the repository-root rerun passed.
- **PASSED for 4F:** 27 focused/adjacent tests across 7 frontend files, all 74 frontend tests, Biome format/lint, strict TypeScript, and the optimized Next build.
- **FAILED then passed for 4F:** the first sandboxed focused-suite startup failed while Vite loaded its config with Windows `spawn EPERM`; the permission-scoped rerun passed 27/27.
- **PASSED live for 4F:** the existing item-detail endpoint returned HTTP 200 for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`, including current retrieval/source/preview/licence/access metadata.
- **NOT RUN for 4F browser:** the required in-app connector failed before tab creation because browser sandbox metadata lacked `sandboxPolicy`; no rendered refresh/restore interaction is claimed.
- **NOT APPLICABLE for 4F backend/database:** no backend, database, or migration code changed. Browser-local storage is not reported as database persistence; carried database gates remain not run.
- **PASSED final 4F documentation/roadmap audit:** 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 phase rows, and one active phase row.
- **PASSED for 4G live API:** collection listing HTTP 200; page 1 HTTP 200 (`phase-4g-live-page-1`) with `S2C_T43PGQ_20251228T052411_L2A`, `S2B_T43PGQ_20251223T051848_L2A`; page 2 HTTP 200 (`phase-4g-live-page-2`) with `S2A_T43PGQ_20251220T051243_L2A`, `S2C_T43PGQ_20251218T052410_L2A`; zero duplicates; item detail HTTP 200; empty search HTTP 200 with zero items/no cursor.
- **PASSED for 4G controlled failures:** 4 focused backend tests covered 429, 503, two 504 paths, and no empty-success conversion.
- **PASSED for 4G focused workflow:** 20 frontend tests cover exact AOI search, continuation, metadata fallback, scene/map selection, fit/clear/remount, restored/stale/corrupt state, AOI invalidation, empty, provider error, and retry.
- **PASSED final repository gate:** Ruff; Ruff format for 38 files; strict mypy for 33 source files; 68 backend tests with 1 database integration test deselected; frontend format/lint for 54 files; strict TypeScript; 74 frontend tests; optimized build; `pip check`.
- **FAILED then corrected in 4G:** one repository run timed out a workspace test at Vitest's 5-second default, then one run exposed an immediate hover-state assertion race. `scripts/verify.ps1` now passes `--testTimeout=15000`; the test now awaits state propagation. Focused and full reruns passed.
- **NOT RUN for browser:** in-app connection failed before tab creation because `sandboxPolicy` is absent. No screenshots, rendered WebGL/thumbnail, console/network, refresh, or laptop/mobile evidence is claimed.
- **BLOCKED / NOT RUN for database:** `scripts/verify-database.ps1` stopped at the deliberate missing-Docker preflight. Liveness was HTTP 200; readiness was HTTP 503 `DEPENDENCY_UNAVAILABLE` for `database`, with no-store and Retry-After 5.
- **PASSED final 4G documentation/roadmap audit:** 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 phase rows, one active phase row, and zero stale 4G status matches.

## Exact resume sequence

1. Read the governing files listed above and inspect the workspace before editing.
2. Preserve completed Phase 4 tasks 4A–4G, Phase 5 tasks 5A–5H, and Phase 6 tasks 6A–6H, including the stable-ID provider boundary, protected preparation workflow, workspace quality panel, and scientific-analysis exclusions.
3. Stop before 6I. Run the integrated phase gate only with explicit authorization; do not infer later scope from the unavailable original Phase 6 title.
4. When Docker is available, run `scripts/verify-database.ps1`; require the integration test, exact Alembic head, and readiness HTTP 200 before closing the carried Phase 1 database gate.
5. Never reinterpret browser rendering, catalogue availability, or asset access as database readiness or scientific analysis evidence.

## Files changed by task 6G

- Runtime/API/persistence: `backend/alembic/versions/20260923_0002_processing_jobs.py`, `backend/src/satquery/db/processing.py`, `backend/src/satquery/processing/jobs.py`, `backend/src/satquery/storage/`, `backend/src/satquery/api/routes/processing.py`, `backend/src/satquery/api/dependencies.py`, `backend/src/satquery/api/router.py`, `backend/src/satquery/api/schemas/processing.py`, `backend/src/satquery/core/config.py`, `backend/src/satquery/db/migrations.py`, and `backend/src/satquery/main.py`.
- Verification/config: `backend/tests/test_processing_jobs.py`, `backend/tests/test_processing_api.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`, `backend/scripts/verify_processing_job.py`, `.env.example`, and `.gitignore`.
- Contracts/checkpoints: `README.md`, `ROADMAP.md`, `API_CONTRACT.md`, `ARCHITECTURE.md`, `TRD.md`, `DATABASE.md`, `FEATURES.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_6_TASKS.md`, `docs/PHASE_6_REPORT.md`, `CURRENT_PHASE.md`, and `SESSION_HANDOFF.md`.

## Files changed by task 6F

- Runtime: `backend/src/satquery/processing/validity.py`, `backend/src/satquery/processing/__init__.py`.
- Verification: `backend/tests/test_validity_engine.py`.
- Contracts/checkpoints: `API_CONTRACT.md`, `ARCHITECTURE.md`, `TRD.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_6_TASKS.md`, `docs/PHASE_6_REPORT.md`, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 6E

- Runtime: `backend/src/satquery/processing/registration.py`, `backend/src/satquery/processing/__init__.py`.
- Verification: `backend/tests/test_registration.py`, `backend/scripts/verify_registration.py`, `backend/scripts/verify_common_grid.py`.
- Contracts/checkpoints: `API_CONTRACT.md`, `ARCHITECTURE.md`, `TRD.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_6_TASKS.md`, `docs/PHASE_6_REPORT.md`, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 6D

- Runtime: `backend/src/satquery/processing/grid.py`, `backend/src/satquery/processing/__init__.py`.
- Verification: `backend/tests/test_common_grid.py`, `backend/scripts/verify_common_grid.py`.
- Checkpoints: `docs/PHASE_6_TASKS.md`, `docs/PHASE_6_REPORT.md`, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 5C

- Runtime/API: `backend/src/satquery/api/routes/imagery.py`, `backend/src/satquery/api/router.py`, `backend/src/satquery/api/dependencies.py`, `backend/src/satquery/api/schemas/viewer.py`, `backend/src/satquery/tiles/`, `backend/src/satquery/main.py`, provider source boundary, and configuration.
- Dependencies/verification: `backend/pyproject.toml`, generated `backend/requirements.lock`, `.env.example`, `backend/tests/test_imagery_tiles.py`, and `backend/scripts/verify_imagery_tiles.py`.
- Governing records: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `TECH_STACK.md`, `DATABASE.md`, `FEATURES.md`, `ROADMAP.md`, `SECURITY.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_5_TASKS.md`, `docs/PHASE_5_REPORT.md`, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 5B

- Contracts/API: `backend/src/satquery/api/schemas/asset_resolution.py`, `backend/src/satquery/api/routes/catalog.py`, `backend/src/satquery/providers/catalog/base.py`.
- Provider/verification: `backend/src/satquery/providers/catalog/earth_search.py`, `backend/tests/test_asset_resolution.py`, `backend/scripts/verify_asset_resolution.py`.
- Governing records: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `FEATURES.md`, `ROADMAP.md`, `SECURITY.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_5_TASKS.md`, `docs/PHASE_5_REPORT.md`, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 4C

- API/runtime: `backend/src/satquery/api/routes/catalog.py`, catalogue route exports/dependencies/schemas, application provider lifecycle and POST CORS wiring.
- Provider: public failure classification and bounded retry guidance in the catalogue provider boundary/Earth Search adapter.
- Verification: `backend/tests/test_catalog_api.py`, the adjusted provider assertion, and `backend/scripts/verify_catalog_api.py`.
- Contracts/checkpoints: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `DATABASE.md`, `FEATURES.md`, `ROADMAP.md`, `SECURITY.md`, `TESTING.md`, `docs/DECISIONS.md`, Phase 4 task/tracker/report files, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 4D

- Frontend: `frontend/src/lib/catalog-client.ts`, its tests, `frontend/src/components/workspace/imagery-discovery-panel.tsx`, its tests, `scene-container.tsx`, `workspace-shell.tsx`, and `frontend/src/app/globals.css`.
- Contracts/checkpoints: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, Phase 4 task/tracker/report files, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 4E

- Frontend state/map: `frontend/src/lib/scene-selection.ts`, `scene-footprints.ts`, `scene-map-layers.ts`, `workspace-shell.tsx`, `scene-container.tsx`, `map-canvas.tsx`, `imagery-discovery-panel.tsx`, and `frontend/src/app/globals.css`.
- Verification: `frontend/src/lib/scene-selection.test.ts`, `scene-map-layers.test.ts`, `frontend/src/components/workspace/scene-container.test.tsx`, and `imagery-discovery-panel.test.tsx`.
- Contracts/checkpoints: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `DATABASE.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, Phase 4 task/tracker/report files, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 4F

- Frontend client/state: `frontend/src/lib/catalog-client.ts`, `scene-selection.ts`, `scene-selection-storage.ts`, `use-scene-selection-draft.ts`, `workspace-shell.tsx`, `scene-container.tsx`, `imagery-discovery-panel.tsx`, and `frontend/src/app/globals.css`.
- Verification: `frontend/src/lib/catalog-client.test.ts`, `scene-selection.test.ts`, `scene-selection-storage.test.ts`, `use-scene-selection-draft.test.tsx`, `frontend/src/components/workspace/scene-container.test.tsx`, and `imagery-discovery-panel.test.tsx`.
- Contracts/checkpoints: `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `DATABASE.md`, `FEATURES.md`, `ROADMAP.md`, `SECURITY.md`, `TESTING.md`, `docs/DECISIONS.md`, Phase 4 task/tracker/report files, `CURRENT_PHASE.md`, and this handoff.

## Files changed by task 4G

- Verification: `scripts/verify.ps1`, `frontend/src/components/workspace/scene-container.test.tsx`.
- Checkpoints: `CURRENT_PHASE.md`, `ROADMAP.md`, `FEATURES.md`, `TESTING.md`, `docs/PHASE_4_TASKS.md`, `docs/PHASE_4_IMPLEMENTATION_TRACKER.md`, `docs/PHASE_4_REPORT.md`, and this handoff.

## Files changed by task 4B

- Provider code: `backend/src/satquery/providers/__init__.py`, `backend/src/satquery/providers/catalog/{__init__,base,earth_search}.py`
- Verification: `backend/tests/test_earth_search_provider.py`, its STAC fixture, `backend/scripts/verify_earth_search.py`, and `backend/tests/test_config.py`
- Runtime/config: `backend/src/satquery/core/config.py`, `backend/pyproject.toml`, `.env.example`; regenerated lock content was unchanged
- Documentation: `docs/PHASE_4_TASKS.md`, implementation tracker/report, API/TRD/architecture/stack/security/testing/features/roadmap/decisions, `CURRENT_PHASE.md`, and this handoff

## Handoff maintenance rule

After every major task, refresh this file with exact status, changed files, checks, errors/blockers, decisions, remaining work, and the precise resume action. Include no secrets or fabricated/unverified evidence.
