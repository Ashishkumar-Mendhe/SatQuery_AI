# Phase 8 report — bounded two-date optical change analysis

Last updated: **2026-09-25**  
Current status: **PHASE 8 PARTIALLY_VERIFIED; 8F EXECUTED; STOP BEFORE PHASE 9**

## Authority and scope

The original Phase 8 roadmap title and scope are unavailable. The user authorized a six-checkpoint two-date change working scope through 8F. The explicit 8D measurement/summary request superseded the earlier provisional job-integration placeholder; 8E explicitly included its protected integration prerequisite. This report does not claim recovery of missing roadmap wording and stops after the Phase 8 handoff.

## 8A outcome

The new closed Pydantic contract in `satquery.api.schemas.change` represents one two-date result without implementing a detector or claiming a real change observation. It binds chronological stable scene identities and dates, the validated AOI, the Phase 6 preparation job and common grid, an explicit algorithm/version and parameter digest, required bands, registration/unknown policies, fixed changed/unchanged/unknown class semantics, explicit joint-valid and joint-usable coverage, projected grid-cell areas, quality warnings, an opaque classification artifact, and checksum/software/time provenance.

Validators make the quantitative record internally auditable: joint usable cannot exceed joint valid, changed plus unchanged must equal joint-usable pixels, unknown must equal the remaining inside-AOI pixels, fractions must use the declared denominator, and areas must equal pixel counts times projected pixel area. `unknown` cannot have a joint-usable fraction, and zero usable coverage stays entirely unknown rather than becoming unchanged. Unknown quality evidence requires a limited result. URLs, filesystem paths, arbitrary confidence, inconsistent class codes, unavailable artifacts, mismatched source scenes, and unbound parameter provenance are rejected.

`ArtifactReference` and the persistence-side artifact kind union now recognize `change_classification` as an image/tiff kind. No route, job operation, migration, detector, threshold, raster output, database row, UI, or result was created in 8A.

## 8B outcome

The new internal `PairPreparationService` consumes only the exact Phase 6 pair request, common-grid arrays, registration result, and authoritative acquisition evidence. It validates chronological dates, equal required band order, common output dimensions/resolution, available QA, non-empty spatial overlap, and reliable registration. It independently rebuilds joint validity from the AOI plus both dates' all-band validity, then rebuilds joint usability by applying both dates' SCL-derived cloud/cirrus, cloud-shadow, cast-shadow, snow/ice, missing, unknown-quality, and outside-AOI exclusions.

Every outcome records source IDs/dates, band order, common grid, processing version and policies, registration/correction states, explicit inside-AOI denominator, valid/usable pixels, percentages and projected-cell areas, and stable rejection reasons/corrective actions. Unsupported, non-chronological, non-overlapping, QA-unavailable, band/grid-inconsistent, or unreliable-registration pairs receive `rejected` and `comparison_allowed=false`; no plausible change map is created.

The existing `prepare_optical` worker now adds a truthful `pair_comparability_assessed` stage for pair jobs. The recomputed `joint_valid` and `joint_usable` arrays are written through the existing atomic two-band mask artifact, and the manifest links that artifact to the complete 8B outcome. Rejected preparation jobs may still succeed technically so diagnostics remain inspectable, but the manifest contains `change_classification_artifact_id=null`. Processing/configuration versions changed, invalidating older cache identity. No new route, operation, database migration, UI, or classifier was added.

Changed implementation files are `backend/src/satquery/processing/change.py`, processing exports/job orchestration, the focused preparation/job tests, and `backend/scripts/verify_change_pair.py`. Phase 8, roadmap, API, architecture, feature, technical-requirement, README, decision, current-phase, and handoff documents were reconciled.

Focused synthetic verification passed for partial overlap, masks from both dates, cloud/shadow/nodata/outside-AOI exclusion, no overlap, chronological ordering, incompatible bands, and inconclusive registration. The existing pair job test confirms nine actual stages, atomic artifacts, explicit rejection, mask linkage, no classification artifact, and cache reuse.

Two bounded live attempts used real chronological Earth Search scenes `S2B_T43PGQ_20251223T051848_L2A` and `S2C_T43PGQ_20251228T052411_L2A` over a 0.01° Bengaluru AOI. The first stopped on the first scene's B04 encoded-tile failure. The final verifier completed the first scene and failed while reading the second, returning `state=unavailable`, `comparison_allowed=false`, stage `trusted_raster_extraction`, and `RASTER_READ_FAILED`. No common grid, registration result, usable observed pair area, production database job/artifact, or change map exists. Provider locations were not emitted.

## 8C outcome

The pure `OpticalChangeDetector` implements one reproducible spectral baseline for the bands SatQuery actually prepares: calibrated dimensionless Sentinel-2 L2A red, green, and blue reflectance. Method `calibrated_rgb_rms_reflectance_difference`, version `8c-calibrated-rgb-rms-v1`, computes per-pixel RGB RMS difference on the exact 8B joint-usable mask and uses a fixed provisional engineering threshold of `0.05`. It performs no per-image normalization, display stretch, value clamping, radiometric harmonization, or semantic/causal classification.

Every masked pixel is `unknown=255`; only joint-usable pixels can be `unchanged=0` or `changed=1`. Outcomes retain sources/dates, method/version, input bands, threshold and units, comparison operator, class encoding, processing policies, exact counts/fractions/projected-cell areas, and a warning that observed spectral change cannot identify buildings, mud, seasonality, or another cause. Rejected 8B outcomes and zero overlap return `insufficient_evidence`; source/grid/mask/calibration inconsistencies return `failed`; neither produces a classification.

Synthetic tests verified 30 unchanged pixels and 3000 m² for an unchanged pair; an injected four-pixel change yielded 4 changed pixels / 400 m² and 26 unchanged pixels / 2600 m²; combined nodata, cloud, shadow, and outside-AOI cells remained unknown with `NaN` spectral differences. Tests also reject unreliable registration, no overlap, and a tampered joint mask. No real detector run was possible because the repository contains no successful comparable real 8B pair; the existing live attempt failed safely before common-grid preparation.

## 8D outcome

`ChangeSummaryService` produces deterministic measurements and concise prose only from a completed, source-matched 8C result. Changed area is class count times CRS-correct projected pixel area. Changed percentage is divided by the joint-valid observed area, not joint usability or AOI. Joint-valid observed coverage, joint-usable coverage, and inside-AOI unknown area are separate measurements with named denominators.

Pixel area uses the affine determinant and the raster CRS linear-unit conversion to square metres. Angular/geographic CRSs are rejected. A synthetic projected-foot test confirms unit conversion rather than assuming every coordinate unit is a metre. The `TwoDateChangeResult` contract advances to schema 1.1 and validates each changed/unchanged class fraction against joint-valid pixels independently of its usable fraction.

The summary retains exact source IDs/dates and AOI, method/version/threshold, reliable alignment disposition, actual AOI cloud/cirrus/shadow exclusion warnings, unknown area, and a provisional 45-day date-gap warning. Its sentences contain only computed values. No vegetation direction is emitted because the supported RGB preparation lacks the required NIR evidence; cause and land-cover category are always `not_determined`.

The main denominator fixture has 30 inside-AOI cells, 28 joint-valid cells, 26 joint-usable changed cells, and four unknown cells at 100 m² each. The reported result is therefore 2,600 m² changed, 92.857% of 2,800 m² joint-valid observed area, with 400 m² unknown. This is labelled synthetic evidence, not a live finding.

## Verified foundation and carried blockers

Phase 5's real browser-verified two-date viewer works as presentation. Phase 6's deterministic clipping/masking/grid/registration/readiness and in-memory job/artifact paths work, and 8F adds a direct real common-grid pair. Protected PostgreSQL jobs, a verified production principal, durable real cache/artifacts, and the browser change-overlay flow remain unverified. Phase 7 workspace inference and grounding do not supply change evidence; “What changed?” uses only the computed Phase 8 result.

## Validation

- `python -m pytest tests/test_change_schemas.py tests/test_processing_schemas.py -q`: **PASSED**, 32 tests.
- Scoped Ruff check: **PASSED** after removing two unused imports and formatting one long assertion.
- Scoped Ruff format check: **PASSED**.
- Strict mypy for all backend source modules: **PASSED**, 49 source files.
- Focused tests cover the valid contract, polygon holes, UTC dates, temporal/provider compatibility, fixed classes, counts/fractions/areas, zero-valid unknown handling, quality-limited state, artifact kind, provenance binding, and rejection of URLs/paths/confidence.
- Documentation audit: **PASSED**, 37 Markdown files, zero broken relative links, and exactly 16 roadmap phase rows.
- Git status/diff checks: **NOT RUN** because this workspace contains no `.git` directory.
- Focused 8B preparation/grid/registration/job tests: **PASSED**, 24 tests. The first added grid-mismatch assertion exposed an extra derived no-usable reason; the service was corrected to stop overlap inference when grids are inconsistent, and the clean rerun passed.
- Full backend: **PASSED**, 207 tests with one unconfigured PostgreSQL integration skip.
- Ruff check/format and strict mypy over source, tests, and scripts: **PASSED**, 89 Python files.
- Real pair preparation: **FAILED / UNAVAILABLE** during trusted provider raster reads as detailed above; no result was fabricated.
- Production PostgreSQL/verified-principal job and browser/UI checks: **NOT RUN**; those inherited dependencies remain unavailable and 8B adds no UI.
- Focused Phase 6/8 raster, masks, grid, registration, pair, schema, and job tests after 8C: **PASSED**, 57 tests.
- Full backend after 8C: **PASSED**, 213 tests with one unconfigured PostgreSQL integration skip.
- Ruff check/format and strict mypy after 8C: **PASSED**, 94 formatted Python files and 51 source files type-checked.
- Real 8C change detection: **NOT RUN** because no prepared comparable real pair is available; no synthetic result is represented as live evidence.
- Focused 8D change/schema/grid/registration/quality tests: **PASSED**, 49 tests.
- Full backend after 8D: **PASSED**, 217 tests with one unconfigured PostgreSQL integration skip.
- Ruff check/format and strict mypy over source and tests after 8D: **PASSED**, 96 formatted files and 79 files type-checked.
- Real 8D summary: **NOT RUN** because no comparable real 8B/8C result exists.

8C commands run from `backend/`:

- `..\.venv\Scripts\python.exe -m pytest tests\test_change_preparation.py tests\test_change_schemas.py tests\test_processing_jobs.py tests\test_common_grid.py tests\test_registration.py tests\test_quality_masks.py tests\test_raster_inputs.py -q`
- `..\.venv\Scripts\python.exe -m pytest -q`
- `..\.venv\Scripts\python.exe -m ruff check .`
- `..\.venv\Scripts\python.exe -m ruff format --check .`
- `..\.venv\Scripts\python.exe -m mypy src`

8D commands run from `backend/`:

- `..\.venv\Scripts\python.exe -m pytest tests\test_change_preparation.py tests\test_change_schemas.py tests\test_common_grid.py tests\test_registration.py tests\test_quality_masks.py -q`
- `..\.venv\Scripts\python.exe -m pytest -q`
- `..\.venv\Scripts\python.exe -m ruff check .`
- `..\.venv\Scripts\python.exe -m ruff format --check .`
- `..\.venv\Scripts\python.exe -m mypy src tests`

## 8E exact next action (historical)

## 8E outcome

The protected processing service now executes versioned two-date change jobs, exposes typed status/result/cancel routes, atomically commits a georeferenced classification artifact, and renders owner-authorized nearest-neighbour change tiles. The workspace starts and polls the API, presents measured dates/areas/coverage/unknowns/warnings, controls a source-aligned overlay, invalidates on AOI/pair changes, and routes “What changed?” to the computed result instead of Phase 7 inference.

Backend verification passed Ruff, format, strict mypy, and 218 tests (one PostgreSQL skip). Frontend verification passed Biome, TypeScript, 117 tests, and optimized build. A focused synthetic job committed and served an authorized result/tile and denied another owner. Browser automation was unavailable because its bridge rejected required sandbox metadata, and a real comparable provider pair plus production persistence remain absent; 8E is therefore partially verified.

Stop after 8E. Begin 8F only with explicit authorization; first restore browser inspection and complete the carried real-pair/database gates.

## 8F outcome

The direct real scientific workflow passed for same-sensor Sentinel-2 L2A scenes `S2B_T43PGQ_20251213T052354_L2A` and `S2B_T43PGQ_20251223T051848_L2A` over the Bengaluru AOI 77.585–77.605°E, 12.965–12.985°N. It produced one 220×225 EPSG:32643 grid at 10 m, reliable zero-shift registration evidence from six distributed patches, 4,806,800 m² joint-valid observed area, 4,757,800 m² joint-usable area, 138,700 m² changed, 4,619,100 m² unchanged, and 49,000 m² unknown. Changed percentage is 2.885495547973704% of joint-valid observed area, independently reproduced from `138700 / 4806800 × 100`. Provenance matches the two requested stable scene IDs, exact AOI, method `calibrated_rgb_rms_reflectance_difference` / `8c-calibrated-rgb-rms-v1`, and the processing version. The unannotated pair verifies execution, not semantic accuracy or a known cause.

8F exposed and fixed a scientific defect in boolean-mask reprojection: categorical zero was incorrectly supplied as destination nodata and could turn every all-false exclusion mask true. Nearest-neighbour boolean reprojection now treats zero as a valid category. The cache/code version is `phase-8f-v1`. Regression coverage and the real rerun demonstrate the corrected usable masks. UI evidence was strengthened to display source IDs, method/version, processing version, and job ID in the result and computed “What changed?” response; the map-layer unit test verifies the authorized classification tile URL, source bounds, opacity, and cleanup.

Synthetic evidence covers the required known-change, unchanged, cloud/shadow/nodata/outside-AOI unknown, zero-overlap, unreliable-registration, and muddy flood-like cases. The brown spectral-change fixture remains cause `not_determined` and contains no unsupported new-building/construction/flood/mud statement. The computed-question test proves no Phase 7 model is invoked. API/job tests recompute the changed percentage from joint-valid area, bind sources/AOI/versions, verify cache reuse and map PNG delivery, and deny unauthorized artifact access.

The complete protected/browser gate did not pass. Two production-shaped HTTP jobs for the real pair failed safely during intermittent remote COG reads, so no protected real result, cache hit, or tile is claimed. PostgreSQL and a production verified principal remain unconfigured; the HTTP verifier therefore used explicitly labelled in-memory persistence and a fixed verification principal. The browser connector failed before tab creation with `codex/sandbox-state-meta: missing field sandboxPolicy`, so no browser screenshot or visual map interaction is claimed. Phase 8 is therefore **PARTIALLY_VERIFIED**, not complete.

### 8F commands and results

- `backend\..\.venv\Scripts\python.exe scripts\discover_change_candidates.py`: **PASSED**; selected the two same-sensor real scenes above from live Earth Search metadata.
- `backend\..\.venv\Scripts\python.exe scripts\verify_change_pair.py`: **PASSED** direct real extraction/preparation/registration/detection/summary with the measurements above.
- `backend\..\.venv\Scripts\python.exe scripts\verify_phase8_workflow.py`: **FAILED SAFELY twice** on remote encoded-tile reads (first B02, then B03); accepted job/status behavior was observed and no result was served.
- `backend\..\.venv\Scripts\python.exe -m pytest tests\test_change_preparation.py tests\test_common_grid.py tests\test_registration.py tests\test_processing_jobs.py tests\test_processing_api.py -q`: **PASSED**, 37 tests.
- `frontend\npm.cmd run test:run -- src\components\workspace\change-analysis-panel.test.tsx src\components\workspace\assistant-panel.test.tsx src\lib\change-map-layer.test.ts --testTimeout=15000`: **PASSED**, 8 tests after the sandbox-only child-process restriction was removed.
- `backend\..\.venv\Scripts\python.exe -m ruff check scripts\verify_phase8_workflow.py src\satquery\processing\grid.py tests\test_common_grid.py tests\test_change_preparation.py tests\test_processing_jobs.py`: **PASSED**.
- `backend\..\.venv\Scripts\python.exe -m pytest tests\test_processing_jobs.py -q` plus scoped Ruff/format after the final cache-version bump: **PASSED**, 7 tests and 2 formatted files.
- `.\scripts\verify.ps1`: first run **STOPPED** on one formatter-only frontend difference after all 220 backend tests passed; corrected and rerun **PASSED**: Ruff, 98-file format check, strict mypy over 79 source files, 220 backend tests with one PostgreSQL test deselected, frontend format/lint/typecheck, 118 tests across 28 files, and optimized Next.js build.
- Browser connector call: **BLOCKED before navigation** by missing sandbox-policy metadata; screenshots not produced.
- Git status/diff: **UNAVAILABLE** because the workspace has no `.git` directory.

## Final Phase 8 status and resume action

**PARTIALLY_VERIFIED; 8F executed; stop before Phase 9.** Configure PostgreSQL and the production verified principal, restore the browser bridge, rerun `backend/scripts/verify_phase8_workflow.py` until a protected real result/cache/tile completes, then exercise the same pair in the workspace and capture result, overlay, stale-input invalidation, and computed “What changed?” evidence. Do not begin SAR, optical fusion, NISAR, or any Phase 9 work during that closeout.
