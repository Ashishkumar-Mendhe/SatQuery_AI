# Phase 8 — Original agreed title unavailable

Working scope: **Bounded, reproducible two-date optical change analysis**

`ROADMAP.md` does not contain the original Phase 8 title or scope. The user explicitly authorized this six-checkpoint working scope through 8F without supplying the missing title. This tracker records that authority without claiming recovery of the original roadmap wording. The user-defined measurement/summary request superseded the earlier provisional 8D job-integration placeholder.

## Current task state

| Task | Acceptance boundary | Status | Evidence / remaining work |
| --- | --- | --- | --- |
| 8A | Audit the actual Phase 5–7 pair/preparation/map/job/assistant foundation; define and test a closed two-date result contract with source scenes/dates, AOI, processing parameters, changed/unchanged/unknown classes, explicit coverage/area denominators, warnings, and reproducible provenance. | **COMPLETE — 2026-09-24** | `satquery.api.schemas.change` and focused tests pass. Contract rejects inconsistent dates, counts, areas, class encodings, provenance, URLs/paths, and fabricated confidence. |
| 8B | Connect Phase 6 pair preparation to an explicit before/after comparability outcome; verify dates, bands, common grid, registration and overlap; recompute joint valid/usable masks from both dates; retain the outcome in existing jobs/artifacts. | **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-24** | Synthetic overlap, masking, ordering, bands, no-overlap, registration rejection, job stage, artifact linkage, cache, and manifest behavior pass. Two bounded real runs failed during trusted COG reads before a common pair existed, so no real comparability outcome is claimed. |
| 8C | Implement one deterministic bounded change method only over an 8B `comparable` pair, then add task-specific validity, uncertainty/limitation handling, exact measured-area verification, and synthetic known-change evaluation. | **COMPLETE — 2026-09-25** | Versioned calibrated-RGB RMS reflectance difference uses a provisional fixed 0.05 threshold only on the exact joint-usable mask. Synthetic known-change/masking/failure gates pass; no real run was possible because 8B produced no prepared real pair. |
| 8D | Compute CRS-correct areas and a deterministic before/after summary from completed 8C evidence. Changed percentage uses joint-valid observed area; coverage and unknown area stay separate; warnings are measured/contextual and cause remains undetermined. | **COMPLETE — 2026-09-25** | Schema 1.1 and the internal summary service pass denominator, projected-area, unknown-pixel, warning, and statement tests. Geographic degrees are rejected as metres; no vegetation/cause result is invented. |
| 8E | Add protected change jobs/API/artifacts plus the workspace change workflow, result summary, legends, source-bound raster/map overlay, stale-result handling, and accessible failure/unknown states. | **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-25** | Durable operation, atomic categorical artifact, authorized result/tile routes, computed-result assistant routing, stale invalidation, overlay/legend/opacity, API/service tests, UI interaction tests, lint/type/build pass. Browser inspection was blocked by its execution bridge; no real comparable pair or production PostgreSQL principal exists. |
| 8F | Reconcile requirements and verify synthetic known results plus the available real workflow, browser behavior, access control, build/tests, and honest limitations. | **EXECUTED / PARTIALLY VERIFIED — 2026-09-25** | A real same-sensor pair completed the direct scientific path, but two protected API-job runs failed on intermittent provider COG reads; production PostgreSQL/identity and browser inspection remain unavailable. Phase 8 is not complete. |

## 8A foundation audit

| Component | What actually works | Unfinished prerequisite carried into Phase 8 |
| --- | --- | --- |
| Scene pair | Phase 5 browser verification rendered distinct, chronological Sentinel-2 dates in swipe, split, and blink modes with stable scene identity. | It is visual comparison only; shared display placement does not prove common-grid alignment, usable overlap, or change. |
| Raster preparation | Phase 6 synthetic fixtures verify clipping, holes, calibration, SCL masks, common-grid geometry, partial/no overlap, registration correction/rejection, and readiness. One real scene passed direct calibrated extraction/QA; Phase 7 later produced one real QA-ready chip. | Real two-scene common-grid preparation and registration did not complete because trusted COG reads were intermittent. No real protected pair artifact exists. |
| Map | Phase 5 real imagery and comparison rendering passed. Phase 6 mask overlays and Phase 7 grounding overlays have automated geometry/lifecycle coverage; one Phase 7 browser fallback exercised scene selection and safe failure. | No change-classification map layer exists. Phase 6 preparation overlays lack the required production identity/database browser path. |
| Jobs/artifacts | Preparation and inference jobs have tested state transitions, cancellation/restart handling, access-scoped cache identity, atomic artifacts, incomplete-cache rejection, and cross-owner denial using synthetic/in-memory coverage. | PostgreSQL/PostGIS and a verified production principal are unavailable, so real durable pair jobs, cache reuse, and authorized artifacts are not verified. |
| Assistant | The typed single-image question/caption/grounding API and workspace states are implemented; one real chip reached local grounding. | Hosted VQA/caption is unconfigured and unverified. Assistant prose or grounding is not an input to Phase 8 change measurement. |

## 8A contract acceptance

- Exactly two distinct stable scenes are labelled `before` and `after`; both dates are UTC and strictly chronological. The initial contract requires the same provider and collection.
- The AOI reuses the validated WGS 84 Polygon/MultiPolygon contract, including holes and the established no-antimeridian-crossing policy.
- Processing records the Phase 6 preparation job, common output grid, method/version, required band order, absence of radiometric harmonization, registration input policy, unknown-pixel policy, explicit parameters, and a canonical parameter digest.
- Fixed categorical meanings are `unchanged=0`, `changed=1`, and `unknown=255`. Unknown is not silently counted as unchanged.
- Coverage names `inside_aoi` as its denominator and records both joint-valid and joint-usable support. Changed plus unchanged pixels must equal joint-usable pixels; unknown must equal the remaining inside-AOI pixels, including valid but quality-excluded cells. Every fraction and projected-grid-cell area is arithmetically validated.
- The result references only an opaque, checksum-bound, available `change_classification` GeoTIFF artifact. Arbitrary URLs, paths, confidence, and extra fields are rejected.
- Provenance binds both prepared scene artifacts/masks, the preparation manifest/job, parameter digest, software versions, and UTC execution bounds. Unknown quality evidence forces a `limited` result.

## 8A files and validation

Changed:

- `backend/src/satquery/api/schemas/change.py`
- `backend/src/satquery/api/schemas/processing.py`
- `backend/src/satquery/db/processing.py`
- `backend/tests/test_change_schemas.py`
- `docs/PHASE_8_TASKS.md`
- `docs/PHASE_8_REPORT.md`
- `ROADMAP.md`
- `API_CONTRACT.md`
- `ARCHITECTURE.md`
- `FEATURES.md`
- `TRD.md`
- `README.md`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`
- `docs/DECISIONS.md`

Validation commands and final outcomes are recorded in `docs/PHASE_8_REPORT.md`.

## 8B checkpoint

`PairPreparationService` accepts only the effective calibrated `CommonGridResult`, its exact `RegistrationResult`, authoritative acquisition evidence, and the closed Phase 6 request. It recomputes `joint_valid` from the AOI and all-band validity on both dates. It recomputes `joint_usable` from that mask plus both dates' actual QA, explicitly excluding cloud/cirrus, cloud shadow, cast shadow, snow/ice, missing/invalid, unknown quality, and outside-AOI pixels.

The outcome is `comparable` only when dates are chronological, requested bands and grid shapes/resolution agree, quality information exists on both dates, valid and usable overlap are non-empty, and distributed registration is `reliable` with an applied or not-needed correction. Otherwise it is `rejected` with stable reason codes and corrective actions. A rejected pair retains diagnostic joint masks and measured coverage but has `comparison_allowed=false` and no change-classification artifact.

The existing protected `prepare_optical` job performs one real `pair_comparability_assessed` stage, stores the recomputed two-band joint mask through the existing atomic artifact store, and records source IDs/dates, grid, band order, coverage/areas, registration/correction states, parameters, processing version, mask artifact ID, and rejection reasons in the manifest. Code/configuration versions changed so older cache entries cannot masquerade as 8B results. No new route, job operation, migration, classification, map layer, or assistant behavior was added.

8B changed files:

- `backend/src/satquery/processing/change.py`
- `backend/src/satquery/processing/__init__.py`
- `backend/src/satquery/processing/jobs.py`
- `backend/tests/test_change_preparation.py`
- `backend/tests/test_processing_jobs.py`
- `backend/scripts/verify_change_pair.py`
- `docs/PHASE_8_TASKS.md`
- `docs/PHASE_8_REPORT.md`
- `ROADMAP.md`
- `API_CONTRACT.md`
- `ARCHITECTURE.md`
- `FEATURES.md`
- `TRD.md`
- `README.md`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`
- `docs/DECISIONS.md`

Real verification used the chronological Bengaluru Sentinel-2 pair `S2B_T43PGQ_20251223T051848_L2A` then `S2C_T43PGQ_20251228T052411_L2A` over 77.5900–77.6000°E, 12.9700–12.9800°N. An initial execution failed on the first B04 encoded-tile read. The final bounded execution completed the first scene and advanced to the second, then returned explicit `unavailable` / `RASTER_READ_FAILED` during trusted raster extraction. No common grid, registration state, observed pair area, durable production job, or map was produced. This is a provider-read blocker, not a scientific rejection of the pair.

## Exact entry point for 8C

After explicit authorization, implement a pure deterministic change classifier that accepts only an 8B outcome with `state=comparable` and uses its effective calibrated scene arrays and exact `joint_usable` mask. Begin with independently specified synthetic arrays and exact changed/unchanged/unknown counts and projected-cell areas. Reject every `rejected` or tampered pair before producing an artifact. Do not add API/UI work or begin 8D.

## 8C checkpoint

`OpticalChangeDetector` consumes the exact 8B outcome, common grid, and bound registration result. It independently verifies scene/grid/registration identity, recomputes both-date validity and QA usability, requires dimensionless calibrated RGB metadata, and refuses a rejected, unregistered, zero-overlap, or tampered pair before classification.

The baseline is `calibrated_rgb_rms_reflectance_difference`, version `8c-calibrated-rgb-rms-v1`. For each joint-usable pixel it computes the root mean square of the before/after red, green, and blue surface-reflectance differences. Values greater than or equal to the fixed `0.05` dimensionless threshold are `changed=1`; lower values are `unchanged=0`; every pixel outside exact joint usability remains `unknown=255`. No per-date normalization, contrast stretch, clamping, radiometric harmonization, or causal class is applied. The threshold is a provisional engineering default, not a universally validated scientific limit.

Every completed, insufficient-evidence, or failed outcome retains the method/version, threshold, units, input bands, comparison operator, class encoding, normalization/harmonization policy, sources, dates, and 8B processing version. Completed outcomes also retain the spectral-difference array, categorical array, exact inside-AOI class counts/fractions, projected-cell areas, and an explicit non-causal interpretation. Artifact/job/API/UI integration remains 8D scope.

8C changed files:

- `backend/src/satquery/processing/change_detection.py`
- `backend/src/satquery/processing/__init__.py`
- `backend/tests/test_change_preparation.py`
- `docs/PHASE_8_TASKS.md`
- `docs/PHASE_8_REPORT.md`
- `ROADMAP.md`
- `API_CONTRACT.md`
- `ARCHITECTURE.md`
- `FEATURES.md`
- `TRD.md`
- `README.md`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`
- `docs/DECISIONS.md`

Validation: focused Phase 6/8 processing tests passed 57/57; the full backend passed 213 tests with one unconfigured PostgreSQL skip; Ruff check/format and strict mypy passed. Synthetic cases prove all-unchanged output, a known four-pixel change with exact areas, cloud/shadow/nodata/outside-AOI unknown preservation, zero overlap, unreliable registration, and tampered-mask rejection. A real 8C execution was not run because the repository has no successfully prepared comparable real pair; the recorded real 8B attempt failed during the second trusted COG read.

## 8D checkpoint

The user-authorized 8D scope superseded the earlier provisional job-integration placeholder. `ChangeSummaryService` now accepts only the exact completed 8C result plus its request, 8B pair, common grid, and registration evidence. It returns the exact AOI and dates, method/version/threshold, a deterministic area record, alignment context, computed warnings, concise statements, no directional measurement, and `cause_or_land_cover_category=not_determined`.

Changed percentage is `changed pixels / joint-valid pixels`, explicitly named `joint_valid_observed_area`; it is not divided by joint usability or total AOI. Observed coverage is joint-valid area divided by rasterized AOI area. Usable coverage is also retained. Unknown is every inside-AOI pixel outside joint usability and is reported independently in pixels, square metres, and percent of AOI; it is never counted as unchanged.

Pixel area is the absolute affine determinant converted through the projected CRS linear-unit factor. Geographic/angular CRSs fail rather than treating degrees as metres. The result contract is schema `1.1` and records `fraction_of_joint_valid` separately from the retained usable fraction. Exact class and coverage arithmetic remain validated.

Summary prose is template-driven from computed evidence, not model-generated. It includes dates, exact AOI geometry reference/type, changed extent and joint-valid denominator, observed/usable coverage, unknown area, method/version/threshold, actual AOI QA cloud/shadow exclusions, reliable alignment context, and a provisional date-gap warning at 45 days. RGB alone supports no defensible vegetation-direction measurement, so none is emitted. Mud, flood effects, buildings, and all other causes or land-cover categories remain not determined.

8D changed files:

- `backend/src/satquery/processing/area.py`
- `backend/src/satquery/processing/change.py`
- `backend/src/satquery/processing/change_detection.py`
- `backend/src/satquery/processing/change_summary.py`
- `backend/src/satquery/processing/__init__.py`
- `backend/src/satquery/api/schemas/change.py`
- `backend/tests/test_change_preparation.py`
- `backend/tests/test_change_schemas.py`
- Phase 8, roadmap, architecture, API, requirements, features, README, decision, current-phase, and handoff documents

Validation: focused change/schema/grid/registration/quality tests passed 49/49; full backend passed 217 tests with one unconfigured PostgreSQL integration skip; Ruff check/format and strict mypy over 79 source/test files passed. Synthetic evidence verifies a 2,600 m² change is 92.857% of 2,800 m² joint-valid area while 400 m² remains unknown, UTM metre cells, projected-foot conversion, degree-CRS rejection, computed date/AOI/method statements, actual QA warnings, seasonal context, and absence of causal or vegetation-gain claims. No real summary was run because no comparable real 8B pair exists.

## Exact entry point for 8E

Stop after 8D. Before workspace work, explicitly authorize and implement the still-missing protected change execution/API/cache/atomic-artifact path, or define how that prerequisite belongs in 8E. A browser must not call this internal service directly or display a synthetic summary as a real result.

## 8E checkpoint

The existing processing worker now supports the distinct `analyze_change` operation. Cache identity binds owner/access scope, trusted source evidence, canonical AOI/pair, preparation settings, detector/summary versions, and code/configuration versions. It repeats trusted preparation, fails rejected pairs, runs 8C/8D off the request loop, and atomically commits a georeferenced categorical artifact plus manifest/result. Startup reconciliation, progress, cancellation, limits, and authorization reuse existing infrastructure.

Protected routes start analysis, return operation-specific status/result, request cancellation, and render only authorized classification artifacts with nearest-neighbour reprojection. The workspace binds results to exact AOI and chronological comparison keys, aborts delayed work on changes, and clears stale results/overlays. It shows dates, changed area with joint-valid denominator, observed coverage, unknown area, alignment, warnings, legend, visibility, and opacity. “What changed?” uses this computed result or asks the user to run analysis; it never calls Phase 7 inference.

Validation passed: backend Ruff/format, strict mypy, and 218 tests with one unconfigured PostgreSQL skip; frontend Biome, TypeScript, 117 tests, and optimized build. A synthetic job verifies committed measured output, cross-owner denial, and map PNG rendering. Browser automation could not connect because its execution bridge rejected required sandbox metadata, so no browser screenshot or live interaction is claimed. A real result remains unavailable because 8B has no completed comparable real pair and production persistence/identity remain unconfigured.

## Exact entry point for 8F

Stop after 8E. Restore browser automation, configure PostgreSQL and verified identity, obtain a successfully prepared real comparable pair, then inspect result/overlay/stale behavior and reconcile Phase 8 without upgrading partial evidence to complete.

## 8F checkpoint

A real Earth Search Sentinel-2 L2A pair over Bengaluru completed trusted extraction, calibration, SCL decoding, one common EPSG:32643 grid, distributed registration assessment, change detection, and deterministic measurement. The chronological inputs were `S2B_T43PGQ_20251213T052354_L2A` and `S2B_T43PGQ_20251223T051848_L2A`; the AOI was 77.585–77.605°E, 12.965–12.985°N. The 220×225 grid used 10 m pixels. Registration was reliable with zero estimated correction, six spatially distributed usable patches, three agreeing estimation patches, and three independent validation patches.

The AOI raster contained 48,068 cells. Joint-valid observed area was 4,806,800 m²; joint-usable area was 4,757,800 m² (98.9806108%); 1,387 pixels / 138,700 m² met the spectral-change threshold; 46,191 pixels / 4,619,100 m² were unchanged; and 490 pixels / 49,000 m² were unknown. The changed percentage was 2.885495547973704%, independently reproduced as `138700 / 4806800 × 100`. This is observed spectral change on an unannotated real pair, not a known causal change or benchmark accuracy. Cause remains `not_determined`.

8F found and fixed a boolean-mask reprojection defect: GDAL destination nodata had treated valid categorical zero (`False`) as nodata, turning all-false exclusion masks true after reprojection. Boolean nearest-neighbour reprojection now preserves zero as a valid category, and a regression test covers all exclusion masks. The processing code version advanced to `phase-8f-v1` so affected cached results cannot be reused. Result and computed-answer panels now show exact source IDs, method/version, processing version, and job provenance; a focused map-layer test verifies the authorized categorical tile route, exact bounds, opacity, and removal.

Synthetic gates verify an all-unchanged pair, exact known changed pixels, cloud/shadow/nodata/outside-AOI unknown preservation, no overlap and unreliable-registration rejection, and a muddy brown flood-like spectral patch that remains `not_determined` and emits no building, construction, flood, or mud claim. Job/API tests independently check the joint-valid percentage denominator, source/AOI/version provenance, cache reuse, authorized tile access, and cross-owner denial. The computed “What changed?” UI test proves the Phase 7 model client is not called.

Two production-shaped protected HTTP job attempts used the same real pair and trusted provider. Both were accepted and reported real stages, then failed safely on intermittent remote COG encoded-tile reads (B02, then B03); the result endpoint was unavailable rather than returning a partial map. These runs used in-memory verification persistence and a fixed test principal because production PostgreSQL and verified identity are unconfigured, so they do not satisfy the durable production gate. The browser bridge again failed before tab creation because required `sandboxPolicy` metadata was absent; no screenshot or visual overlay pass is claimed.

8F changed:

- `backend/src/satquery/processing/grid.py`
- `backend/src/satquery/processing/jobs.py`
- `backend/tests/test_common_grid.py`
- `backend/tests/test_change_preparation.py`
- `backend/tests/test_processing_jobs.py`
- `backend/scripts/discover_change_candidates.py`
- `backend/scripts/verify_change_pair.py`
- `backend/scripts/verify_phase8_workflow.py`
- `frontend/src/components/workspace/assistant-panel.tsx`
- `frontend/src/components/workspace/assistant-panel.test.tsx`
- `frontend/src/components/workspace/change-analysis-panel.tsx`
- `frontend/src/components/workspace/change-analysis-panel.test.tsx`
- `frontend/src/lib/change-map-layer.test.ts`
- Phase 8 report, roadmap, current-phase, and session-handoff documents

Final commands and outcomes are recorded in `docs/PHASE_8_REPORT.md`. **Status: PHASE 8 PARTIALLY_VERIFIED; 8F executed; stop before Phase 9.** Exact resume action: configure PostgreSQL plus a verified production principal, restore the browser bridge, rerun `backend/scripts/verify_phase8_workflow.py` until the protected real job and cache/tile checks succeed, then select the same pair in the workspace and capture the result, overlay, stale-input behavior, and computed “What changed?” evidence before reconsidering `COMPLETE`.
