# Phase 6 — Original agreed title unavailable

Working scope: **Optical processing preparation contracts, one-scene preparation, one supported optical pair, quality/readiness, jobs/artifacts, and verification**

Status: **PARTIALLY VERIFIED — TASKS 6A–6H COMPLETE; 6I BLOCKED ON REAL INTEGRATION GATES; STOP BEFORE PHASE 7**

## Authority and scope

The repository does not contain the original agreed Phase 6 title or scope. On 2026-09-20 the user explicitly authorized the working scope and tasks 6A–6I recorded in `docs/PHASE_6_TASKS.md`; through 2026-09-23 the user explicitly supplied acceptance for 6B–6I. This report does not claim recovery of the missing original Codex roadmap wording. Work stops before Phase 7.

## Task 6I outcome

Task 6I verified the complete available path without converting missing infrastructure into success. A live request through SatQuery selected actual Earth Search Sentinel-2 L2A scenes `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`. Liveness, collection listing, and the bounded catalogue search passed. Database readiness returned `503 DEPENDENCY_UNAVAILABLE`, and the protected preparation request returned `503 CAPABILITY_UNAVAILABLE` because the application has no configured verified identity resolver. Public discovery remained available, as designed.

The existing live 6B/6C evidence remains valid for one scene: a 12×13 EPSG:32643 calibrated RGB extraction with 121 inside/valid pixels and provider scale `0.0001`/offset `−0.1` applied once, plus actual baseline-05.11 SCL statistics. Those independently measured arrays are not presented as a durable 6G job, artifact, cache hit, or workspace readiness result. Earlier real 6D/6E pair attempts failed on remote COG reads before harmonization/registration. The current production job verifier again stopped before job acceptance with `Interrupted job reconciliation failed.` because PostgreSQL is unavailable.

The missing orchestration risk was covered with a separate labelled synthetic pair. It ran through the real 6G job stages and produced two calibrated raster/validity/quality artifact sets, one joint pair mask, one manifest, a common EPSG:32631 grid, explicit pair coverage, an honest low-texture `inconclusive` registration, `not_ready` task readiness with `registration_evidence` blocking, and stable cache reuse. Existing known fixtures separately verify exact clipping/hole/nodata/calibration values, SCL counts, grid geometry and overlap, known translations and correction rejection, readiness boundaries, stale UI responses, interrupted jobs, atomic publication, and cross-owner denial.

The closed preparation schema now explicitly rejects thumbnail URLs, display-stretch objects, and client-claimed readiness as well as arbitrary source URLs; artifact responses reject supplied URLs, and missing measurements cannot pass. The workspace request is built from stable scene identities, AOI, profile, bands, and processing options only. Therefore preview thumbnails, screenshots, display stretches, and absent measurements cannot become scientific inputs or fabricated readiness evidence.

The full non-database repository gate passed after mechanically correcting the Phase 6 migration's import order and line wrapping: Ruff and format over 74 Python files, strict mypy over 61 source/test files, 160 backend tests with one database integration test deselected, frontend format/lint/type checks, 108 tests across 24 files, and the optimized Next.js build. The disposable database gate could not connect to the absent Docker Desktop Linux engine and is blocked, regardless of the script's final process status.

The required in-app browser inspection could not start because its sandbox setup lacked `sandboxPolicy`. No new laptop/mobile interaction or screenshots are claimed. Automated workspace tests cover success, warning, blocked, processing failure, stale/delayed results, missing quality, keyboard use, overlays, and responsive structure, but they do not substitute for browser evidence. Phase 6 is consequently **PARTIALLY VERIFIED**, not complete.

### Integrated workflow disposition

| Required step | Outcome |
|---|---|
| Select an AOI and real catalogue imagery | **PASSED** — bounded live search returned the two actual scenes above. |
| Prepare and inspect one real scene through the protected job | **BLOCKED** — identity and PostgreSQL unavailable; prior direct 6B/6C evidence remains separate. |
| Prepare and inspect a real optical pair | **BLOCKED** — no durable job; prior trusted remote COG pair reads failed. |
| Exercise warning/block behavior | **PASSED (synthetic)** — inconclusive registration produced `not_ready`; live missing capabilities returned explicit `503`. |
| Change inputs and reject stale results | **PASSED (automated UI)**; browser observation not run. |
| Repeat a request and reuse cache | **PASSED (synthetic)**; real durable cache reuse blocked. |
| Interrupted job and authorized artifact access | **PASSED (synthetic)**; real PostgreSQL/artifact evidence blocked. |
| Browser inspection and screenshots | **NOT RUN** — browser sandbox setup failed before tab creation. |

## Task 6H outcome

Task 6H adds a compact workspace preparation panel bound to the current selected AOI and either the selected catalogue scene or the ordered comparison pair. Before submission it names the Sentinel-2 L2A surface-reflectance profile, required RGB bands, common 10 m UTM grid, bilinear continuous and nearest categorical resampling, a 4,000,000-pixel request ceiling, and the additional configured server limits. It sends only stable scene identities and AOI geometry to the protected 6G API.

The panel reports backend-recorded state, stage, and completed/total units rather than an invented percentage. On success it reads the persisted 6F report and reproducibility manifest and displays acquisition dates, task readiness, measured coverage with denominators, cloud/shadow or unavailable quality evidence, native/output resolution and upsampling disclosure, registration explanation, warnings/unknowns/failures and corrective actions, checksummed artifact links, plus expandable grid and processing versions. Future analysis remains disabled; preparation success creates no AI answer, change result, aggregate accuracy, or confidence.

AOI geometry, ordered scene keys, profile, and UI processing version form the client result binding. Selection changes cancel the active request, increment a response sequence, remove overlays, and mark completed evidence outdated. Delayed responses are ignored. Retry uses a distinct idempotency attempt while the backend remains authoritative for stable processing-cache identity.

Optional map overlays preserve the original imagery and use only quality artifact UUIDs returned by an authorized successful job. The new protected route accepts only `usable` or `exclusions`, verifies the artifact owner/access scope and quality-mask kind, validates WebMercatorQuad coordinates, reads labelled mask bands, keeps nearest-neighbour categorical semantics, unions actual exclusion bands, and returns a private/no-store transparent PNG. It accepts no provider URL or filesystem path.

Focused UI/map regressions passed 21/21, and the complete frontend passed 108 tests across 24 files plus Biome lint, TypeScript, and the optimized Next build. Backend focused job/API checks passed 6/6; strict mypy passed for 41 source files; and the non-database suite passed 156 tests with one integration test deselected. All 6H Python files pass scoped Ruff/format. Full-repository Ruff remains failed solely by the pre-existing 6G Alembic migration import/line formatting. The in-app browser could not connect because required sandbox metadata was unavailable, so live laptop/mobile visual evidence is not claimed; responsive CSS and keyboard/component behavior passed automated checks. Verified identity, PostgreSQL, and the real 6G preparation remain independent blockers.

## Task 6G outcome

Task 6G connects the implemented preparation stages behind a durable bounded job. Alembic head `20260923_0002` adds the narrow preparation job/artifact/event subset. A lifespan-managed in-process dispatcher uses one default execution slot, real completed/total stage units, a 300-second default limit, a 4,000,000-pixel ceiling, conservative 512 MiB memory/output ceilings, restart reconciliation, durable queued redispatch, and cooperative cancellation between stages. Raster and CPU work is not performed on the request event loop.

The protected `/api/v1/processing` surface starts/idempotently reuses jobs, retrieves status, requests cancellation, returns the persisted 6F quality report, and streams committed artifacts. It requires a server-injected verified owner/access scope. The repository has no configured identity provider, so production routes fail closed instead of trusting a client owner header. Database or processing failure does not disable public catalogue search or imagery viewing.

Cache identity hashes safe trusted source IDs/version/grid/calibration evidence, canonical AOI geometry with holes, band order, target-grid and processing options, task/profile, code/config versions, owner ID, and access scope. It excludes server locations, expiring URLs, and credentials. Artifact files are written privately through temporary files and atomic rename; database success and artifact rows are committed together afterward. A cache hit additionally requires succeeded metadata, committed artifacts including a manifest, and every referenced file to exist.

Outputs are calibrated float32 GeoTIFFs, separate multi-band validity/AOI GeoTIFFs, SCL plus separate quality-category GeoTIFFs, pair joint-valid/joint-usable masks when applicable, and a JSON manifest. The manifest retains safe source provenance, calibration, band order/units, native/output resolution, grid, coverage, registration/correction evidence, explicit absent normalization/cross-sensor harmonization, the complete 6F report, code/config versions, and checksums. No change result, AI answer, overall accuracy, or confidence is produced.

The real verifier selected `S2C_T43PGQ_20251228T052411_L2A` and a 0.001° square AOI, but the Docker Desktop Linux engine/PostgreSQL service was unavailable. The production-bound run returned `{status: blocked, reason: "Interrupted job reconciliation failed."}` before job acceptance or provider raster processing. Consequently there is no real 6G job ID, artifact, coverage, or readiness result to report; the synthetic in-memory repository is used only for unit behavior and is not presented as database evidence.

## Task 6F outcome

Task 6F adds an internal `ScientificValidityEngine` and no route, LLM, worker, persistence, model, or UI. It selects an explicit version-1.0 profile from `PreparationRequest.intended_task` and `processing_profile`: `sentinel-2-l2a-single-scene-validity-v1` or `sentinel-2-l2a-pair-comparison-validity-v1`. Both require RGB calibrated surface reflectance, validity/quality evidence, native-resolution spatial support, authoritative acquisition metadata, and a requested spatial scale; the pair additionally requires joint overlap and reliable registration.

Each check records pass, warning, fail, unknown, or not-applicable; required status; numeric/text measurement; units and denominator; threshold; reason; corrective action; evidence source; and whether its threshold is provisional. Decision precedence is deterministic: any failure is `not_ready`; otherwise required unknown evidence is `unknown`; otherwise a warning is `limited`; only all required passes are `ready`. The report explicitly leaves map viewing and catalogue search unaffected. It contains no aggregate accuracy or AI-confidence value.

The versioned injectable default set is `provisional-engineering-v1`. These are honest engineering defaults, not universally validated scientific limits:

| Evidence | Pass | Warning | Fail |
|---|---:|---:|---:|
| Valid AOI coverage | ≥80% | ≥60% | <60% |
| Quality-usable AOI coverage | ≥60% | ≥30% | <30% |
| Cloud/cirrus over AOI | ≤20% | ≤40% | >40% |
| Cloud/cast-shadow union over AOI | ≤15% | ≤30% | >30% |
| Missing data over AOI | ≤5% | ≤20% | >20% |
| Pair valid overlap over AOI | ≥80% | ≥60% | <60% |
| Pair joint usable area over AOI | ≥50% | ≥25% | <25% |
| Worst required-band native resolution | ≤10 m | ≤20 m | >20 m |

Requested spatial scale must be at least three times the worst required-band native resolution; exactly the limit passes. This is a sampling-support guard and explicitly not a promise to detect objects at that size. Upsampling is a warning because it does not create detail. Missing QA makes usable/cloud/shadow checks unknown rather than clear. Pair registration must be 6E `reliable`; inconclusive evidence is unknown and unsupported evidence fails. Dates must be authoritative and chronological. Elapsed intervals above 365 days, seasonal day-of-year separation above 45 days, and different Sentinel-2 platforms are contextual warnings rather than evidence of incompatibility or change.

## Task 6E outcome

Task 6E adds an internal `RegistrationService` for two common-grid Earth Search Sentinel-2 L2A scenes with actual 6C quality information. It uses the comparable calibrated red band and requires both band validity and quality usability, excluding clouds/cirrus, cloud/cast shadows, snow/ice, unknown quality, and nodata. A deterministic 3×3 layout supplies five alternating estimation patches and four held-out validation patches rather than one global similarity value.

Each patch searches only integer translations from −6 through +6 rows/columns with masked zero-normalized cross-correlation. This is a bounded form of the established masked normalized cross-correlation family described by the [scikit-image registration documentation](https://scikit-image.org/docs/stable/api/skimage.registration.html); no scikit-image dependency was added. Low texture, insufficient valid fraction/count, weak or ambiguous peaks, and estimates on the search boundary are unusable. Correlation alone is never a registration pass.

The output records every patch location/purpose, usable count and spatial distribution, correlation/peak diagnostics, consensus displacement, inliers and tolerance, held-out before/after median residual correlation, improvement count, and a `reliable`, `inconclusive`, or `unsupported` state. The shift convention is explicitly the translation applied to moving scene B to align with reference A: positive row is array-down/south, positive column is east; map x/y use the common affine pixel vectors. Unavailable measurements are `None`, not NaN evidence.

Only an integer translation can be applied. At least three distributed estimation inliers and 60% agreement within 0.75 pixel are required. A nonzero translation additionally needs at least two independent validation patches, median residual correlation ≥0.55, median improvement ≥0.03, and improvement on at least 60% of validation patches. The original pair remains retained; data, per-band validity, categorical SCL, and every quality mask move by the same integer copy. Exposed borders become missing and valid/usable pair overlap is recomputed. No interpolation, elastic/optical-flow warp, feature deformation, or radiometric adjustment occurs.

### Real registration verification

The verifier requested actual `S2C_T43PGQ_20251218T052410_L2A` and `S2C_T43PGQ_20251228T052411_L2A` assets for a bounded same-tile AOI through the trusted adapter. It failed on the first `B04.tif` remote encoded-tile read before a common pair existed. Therefore real registration state, displacement, residuals, correction, and ground-truth accuracy are all unavailable; catalogue identity and prior display rendering are not substituted as registration evidence.

## Task 6D outcome

Task 6D adds an internal `CommonGridService` that consumes only the calibrated 6B arrays and 6C masks. It derives one target grid from the request AOI: the single supported UTM zone and hemisphere, request pixel size, extent snapped outward to that pixel size, north-up transform, dimensions, and bounds are computed once. AOIs outside 80°S–84°N, spanning zones or hemispheres, empty pixel-centre grids, and grids above the lower request/service pixel limit are explicit failures.

All scene bands are reprojected to the one declared grid. The request-recorded method is used for continuous calibrated reflectance (bilinear in the real verification profile), while validity and all categorical SCL/quality masks always use nearest-neighbour. Invalid source samples are passed as nodata during interpolation, independently transferred per-band validity must also pass, and invalid destinations stay `NaN`. Existing calibrated values and their source/calibration metadata are preserved without applying scale/offset again; no clamp, contrast, per-image normalization, or cross-sensor radiometric harmonization is performed.

Each scene retains per-band validity, an all-required-band valid-data mask, the separate 6C quality masks, native resolutions, output resolution, and explicit upsampling metadata stating that interpolation does not create spatial detail. A pair adds joint-valid and joint-usable masks. Coverage names its AOI or valid-overlap denominator and reports pixel count, denominator count, percentage, and square metres using projected pixel count × pixel area. Grid agreement is explicitly `registration_status=not_assessed`: shared CRS/transform/dimensions do not prove feature registration.

### Real pair verification

The checked-in real verifier uses two actual same-tile Earth Search Sentinel-2 L2A acquisitions and a 0.001° AOI, resolves inputs only through the trusted adapter, and requests a 10 m EPSG:32643-class UTM grid with bilinear continuous and nearest categorical resampling. Three executions reached provider resolution but failed before harmonization because remote `B04.tif`/`B03.tif` COG encoded-tile reads returned short/read errors. This included an unrestricted-network retry, an alternate acquisition, and a different small AOI/internal tile. The real pair is therefore **not verified**, and no grid, overlap, usability, or area outcome is claimed from those failed runs.

## Task 6C outcome

Task 6C adds a trusted Earth Search SCL resolution path and an internal `QualityMaskService`. The implementation follows the [Copernicus Sentinel-2 processing documentation](https://sentiwiki.copernicus.eu/web/s2-processing): SCL 0 no-data, 1 saturated/defective, 2 cast shadow, 3 cloud shadow, 4 vegetation, 5 not vegetated, 6 water, 7 unclassified, 8 medium-probability cloud, 9 high-probability cloud, 10 thin cirrus, and 11 snow/ice. The exact product processing baseline is retained. The current profile treats 4/5/6 as usable only when all requested source bands are valid and excludes every other class while preserving each reason separately.

The result has independent outside-AOI, missing/invalid, cloud/cirrus, cloud-shadow, cast-shadow, snow/ice, unknown-quality, usable, and union-exclusion masks. Missing QA marks all inside-AOI quality unknown and none usable. Dark reflectance and water remain valid unless source validity or actual SCL excludes them. SCL categories are resized/reprojected only with nearest-neighbour. Following [Rasterio mask semantics](https://rasterio.readthedocs.io/en/stable/topics/masks.html), the implementation reads GDAL nonzero-valid and NumPy `True`-invalid masks and rejects any failure of their inverse relationship.

Coverage records pixel count, denominator name/count, and percentage. Cloud, cloud-shadow, cast-shadow, and snow use quality-assessed pixels; missing, unknown, usable, and union exclusion use inside-AOI pixels; outside AOI uses output-window pixels. The exclusion union prevents overlap double-counting. Provider-reported scene `eo:cloud_cover` stays separate from measured AOI cloud/cirrus.

### Real quality-mask verification

The real script used SCL asset `scl` for `S2C_T43PGQ_20251228T052411_L2A`, processing baseline 05.11, on the same 121-pixel AOI as 6B. Classes 3, 5, 7, and 8 occurred in the output window. Inside the AOI, 107 pixels had assessed quality: 25 were cloud/cirrus (23.3644859813% of 107) and 82 were cloud shadow (76.6355140187% of 107). Fourteen pixels were unknown (11.5702479339% of 121); missing/invalid, cast shadow, and snow/ice were zero. The non-double-counted exclusion union was 121/121 (100%), so usable was truthfully 0/121. The separate catalogue scene-cloud value was 28.287384% and was not used as AOI measurement.

## Task 6B outcome

Task 6B adds an internal `RasterInputService` for one supported Earth Search Sentinel-2 L2A scene. It accepts only the closed 6A stable scene/AOI/band/profile/options request. The service calls the existing provider resolver; no client location or path reaches the reader. Production access reuses the existing exact HTTPS destination restrictions, content-length-bound range reader, request/byte/deadline bounds, and driver/dimension/CRS/transform/band header comparison. No HTTP route was added because the repository still lacks the required verified identity and owned-resource authorization boundary.

The service transforms the validated RFC 7946 WGS 84 geometry into the source CRS, uses a native-grid window read, and rasterizes the exact geometry separately so holes remain outside. It returns calibrated `float32` data, a boolean inside-AOI mask, per-band boolean validity, output CRS/transform/bounds/dimensions, requested band order, exact source identities and band indices, dimensionless reflectance units, native resolution, nodata, and provider/applied scale/offset metadata. Invalid and outside-AOI cells remain `NaN`; coefficients are applied exactly once only to valid values. Identity scale/offset preserves already-calibrated values. No value clamp, display contrast, per-date normalization, model normalization, reprojection, or resampling is performed.

The hard Task 6B window ceiling is 4,000,000 pixels, further reduced by the request limit. Empty intersection, no pixel-centre overlap, missing georeferencing, native-grid disagreement, non-native target resolution, unsupported band/task/grid policy, expired source access, header mismatch, and resource excess are explicit failures. Originals are read-only and untouched.

### Real extraction

`backend/scripts/verify_raster_inputs.py` passed against real scene `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A` for the WGS 84 AOI 77.5940–77.5950° E, 12.9700–12.9710° N. The actual output was EPSG:32643, 12×13 pixels, affine transform `(10, 0, 781410, 0, -10, 1435370)`, bounds `(781410, 1435240, 781530, 1435370)` metres, and 121 inside/valid pixels per RGB band. Each band reported 10 m native resolution and provider scale `0.0001`, offset `−0.1`, applied once. Measured calibrated ranges were red 0.0448–0.2200, green 0.0550–0.1824, and blue 0.0469–0.2026 in dimensionless reflectance units. The script printed no provider location and created no artifact.

## Task 6A outcome

Task 6A adds closed Pydantic processing contracts in `backend/src/satquery/api/schemas/processing.py`. They reuse the existing stable provider/collection/item scene identity and bounded RFC 7946 WGS 84 AOI schema. The initial request profile is deliberately limited to the already-working `earth-search` / `sentinel-2-c1-l2a` collection and accepts one single-scene or two distinct pair inputs, unique red/green/blue/NIR requirements, an explicit intended task, original preservation, AOI clipping, grid policy/resolution, metadata calibration, continuous/mask resampling, and a bounded pixel ceiling. Extra URLs, paths, credentials, and arbitrary options are rejected.

The output contract declares a finite north-up metre-based UTM grid whose CRS, affine transform, dimensions, resolution, bounds, and 100-million-pixel ceiling agree. A prepared raster retains source scene/band identity and references separate checksum-bound data, validity-mask, and quality-mask artifacts. Validity has explicit invalid/valid classes; quality masks retain their own meanings. Artifacts expose opaque UUIDs, kind, media type, checksum, byte size, and access state—not provider locations, object keys, paths, or signed URLs.

Calibration distinguishes applied metadata scale/offset, identity/not-required, and unavailable/null coefficients. Provenance records request/parameter digests, source identity and checksum availability, calibrations, ordered steps, software versions, and UTC timing. Quality checks require a measured value, units, threshold, outcome, and explanation, and validators ensure passed/failed outcomes agree mathematically; unresolved measurements remain null. Task readiness references exact checks and unresolved IDs. A technically successful preparation can remain limited, not ready, or unresolved, while failed processing cannot expose prepared outputs or claim readiness.

The job-status contract follows the existing queued/running/cancelling/succeeded/failed/cancelled lifecycle with consistent attempts, UTC timestamps, optional measured work units, safe errors, and committed available artifact references. It defines no persistence or execution.

## Verification

- **PASSED (6I live discovery):** SatQuery liveness and collection/search calls returned HTTP 200; the bounded real search returned `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A` with a continuation cursor.
- **PASSED (6I full non-database gate):** Ruff/format over 74 Python files, strict mypy over 61 source/test files, 160 backend tests with 1 database integration test deselected, frontend format/lint/type checks, 108 frontend tests across 24 files, and optimized production build.
- **PASSED (6I documentation audit):** 33 governed Markdown files, zero broken relative links, and exactly 16 Phase 0–15 roadmap rows.
- **PASSED (6I synthetic pair integration):** real job orchestration code produced a common grid, two calibrated scene artifact sets, joint masks, manifest, explicit coverage, inconclusive registration, blocked readiness, and cache reuse. Closed schemas reject scientific input from source URLs, thumbnails, display stretches, and claimed readiness.
- **BLOCKED (6I real preparation/database):** readiness returned HTTP 503, protected preparation returned HTTP 503, `verify_processing_job.py` stopped at interruption reconciliation, and `verify-database.ps1` could not connect to the absent Docker Desktop Linux engine. No real job/artifact/cache result is claimed.
- **NOT RUN (6I browser/screenshots):** the browser sandbox failed before tab creation because required `sandboxPolicy` metadata was missing. Automated UI evidence is not represented as visual evidence.
- **PASSED (6H frontend):** focused preparation/workspace/map-layer regressions 21/21; complete frontend suite 108/108 across 24 files; Biome lint across 74 files; TypeScript; and optimized Next production build.
- **PASSED (6H backend):** focused preparation job/API tests 6/6, including allow-listed usable/exclusion mask rendering and cross-owner denial; strict mypy across 41 source files; non-database suite 156 passed with 1 integration test deselected; scoped Ruff/format for all changed 6H Python files.
- **RESOLVED IN 6I (carried Ruff gate):** the two 6G migration style findings were mechanically corrected; the full Ruff/format gate now passes.
- **NOT RUN (6H live layout):** the required in-app browser connection rejected setup because sandbox metadata was unavailable. Automated mobile/laptop responsive CSS, semantic controls, keyboard submission, and production rendering passed, but no live visual result or screenshot is claimed.
- **BLOCKED (real preparation):** no verified identity resolver or PostgreSQL/PostGIS service is available, so a real 6G-backed job and real computed overlay were not run from the workspace.
- **PASSED (6G):** six focused processing-job/API tests cover a real synthetic pipeline through grid, validity, GeoTIFF/manifest writes, repeated and changed requests, owner denial, failed stages, restart interruption, incomplete cache, AOI canonicalization with holes, storage-limit atomicity, and identity-deny-by-default behavior.
- **PASSED (6G):** Ruff format/check, strict mypy, and the full non-database backend suite (156 passed, 1 integration test deselected).
- **PASSED (6G static migration):** Alembic reports one head, `20260923_0002`, the expected two-revision history, and a successful PostgreSQL offline SQL upgrade render.
- **PASSED (6G documentation):** 33 governed Markdown files, zero broken relative links, 16 roadmap phase rows, and exactly one active row.
- **BLOCKED (6G database/real job):** Docker CLI exists but the Desktop Linux engine pipe is absent. PostgreSQL/PostGIS migration and the production-bound real job could not start; the verifier stopped before durable acceptance. No real output is claimed.

- **PASSED (6F):** six focused validity tests covering ready single/pair profiles, required missing evidence, exact inclusive boundary values, below-resolution rejection, contradictory pass/fail precedence, pair-specific registration, and contextual platform warnings.
- **PASSED (6F):** backend Ruff check/format for 62 files, strict mypy for 36 source files, and complete non-database backend suite 150/150 with the database integration test excluded.
- **PASSED (6E):** six synthetic tests covering known row/column and projected-map translation, invalid borders and mask consistency, low texture, a one-third changed region, conflicting distributed estimates, and rejection when held-out patches fail to improve.
- **PASSED (6E):** backend Ruff check/format for 60 files, strict mypy for 35 source files, and complete non-database backend suite 144/144 with the database integration test excluded.
- **PASSED (6E):** documentation audit across 86 Markdown files with zero broken relative links, exactly 16 roadmap phase rows, and one active row.
- **FAILED / EVIDENCE GAP (6E):** the bounded real-pair run failed at the existing trusted remote COG read boundary before registration. No real displacement, reliability, correction, or accuracy result is claimed.
- **PASSED (6D):** six synthetic common-grid tests covering differing CRS/resolution/origins, one deterministic AOI grid, calibrated-value preservation, native/output resolution, partial overlap, zero overlap, explicit denominators/area, nearest-neighbour categorical preservation, upsampling disclosure, and unsupported geographic extents.
- **PASSED (6D):** backend Ruff check/format for 57 files, strict mypy for 34 source files, and complete non-database backend suite 138/138 with the database integration test excluded.
- **PASSED (6D):** documentation audit across 86 Markdown files with zero broken relative links, exactly 16 roadmap phase rows, and one active row.
- **FAILED / EVIDENCE GAP (6D):** three bounded actual-pair attempts failed at remote COG encoded-tile reads before a pair could be harmonized. No real-pair metrics are reported.
- **PASSED (6B):** focused synthetic raster extraction 6/6; clipping boundary, WGS84-to-EPSG:3857 transform, polygon hole, exact affine/bounds, requested band order, scale/offset and identity calibration, distinct nodata, per-band validity, empty overlap, missing CRS, expired access, pixel limit, and client-file-URL rejection.
- **PASSED (6B):** backend Ruff check/format for 51 files, strict mypy for 32 source files, and complete non-database backend suite 123/123 with one database integration test deselected.
- **PASSED (6B):** the small real Earth Search extraction above using actual raster range reads and calibrated values.
- **PASSED (6B):** documentation audit across 26 Markdown files with zero broken relative links and exactly 16 Phase 0–15 roadmap rows.
- **PASSED (6C):** seven focused synthetic SCL tests and two adjacent provider tests, 15/15 combined with the existing asset-resolution suite.
- **PASSED (6C):** backend Ruff check/format for 54 files, strict mypy for 33 source files, and complete non-database backend suite 132/132 with one database integration test deselected.
- **PASSED (6C):** live baseline-05.11 SCL extraction/decoding with the exact measured outcome above.
- **PASSED (6C):** documentation audit across 26 Markdown files with zero broken relative links, exactly 16 roadmap phase rows, and one active row.
- **PASSED:** Ruff format/check for all 43 backend files.
- **PASSED:** strict mypy for all 43 backend source/test files.
- **PASSED:** 15/15 focused synthetic Pydantic tests and the complete 117-test non-database backend suite; one database integration test was deselected.
- **PASSED:** documentation/roadmap audit across 26 governed Markdown files and 43 relative links; zero broken targets, exactly 16 Phase 0–15 rows, and one active row.
- **NOT RUN / NOT IMPLEMENTED:** API route/OpenAPI exposure, artifact bytes, worker/job backend, storage, database, frontend, browser, quality thresholds/readiness decision, feature-registration assessment, model input, AI, and change analysis.
- **BLOCKED / CARRIED:** real PostgreSQL/PostGIS migration/readiness HTTP 200 because the Docker Desktop Linux engine remains unavailable. This is independent of the passing 6A contract gate.

## Changed files

- 6I verification hardening: `backend/tests/test_processing_jobs.py`, `backend/tests/test_processing_schemas.py`, `backend/tests/test_common_grid.py`, `backend/tests/test_validity_engine.py`, and formatting-only corrections in `backend/alembic/versions/20260923_0002_processing_jobs.py`.
- 6I handoff/reconciliation: `README.md`, `ROADMAP.md`, `API_CONTRACT.md`, `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`, `docs/PHASE_6_TASKS.md`, `docs/PHASE_6_REPORT.md`, `CURRENT_PHASE.md`, and `SESSION_HANDOFF.md`.
- 6H frontend workflow: `frontend/src/lib/preparation-client.ts`, `frontend/src/lib/preparation-mask-map-layer.ts`, `frontend/src/components/workspace/preparation-panel.tsx`, `frontend/src/components/workspace/scene-container.tsx`, `frontend/src/components/workspace/map-canvas.tsx`, and `frontend/src/app/globals.css`.
- 6H frontend verification: `frontend/src/components/workspace/preparation-panel.test.tsx` and `frontend/src/lib/preparation-mask-map-layer.test.ts`.
- 6H protected mask rendering: `backend/src/satquery/processing/jobs.py`, `backend/src/satquery/api/routes/processing.py`, `backend/tests/test_processing_jobs.py`, and `backend/tests/test_processing_api.py`.
- 6G runtime/API/persistence: `backend/src/satquery/processing/jobs.py`, `backend/src/satquery/db/processing.py`, `backend/src/satquery/storage/`, `backend/src/satquery/api/routes/processing.py`, `backend/src/satquery/api/dependencies.py`, `backend/src/satquery/api/router.py`, `backend/src/satquery/main.py`, `backend/src/satquery/core/config.py`, `backend/src/satquery/api/schemas/processing.py`, `backend/src/satquery/db/migrations.py`, and `backend/alembic/versions/20260923_0002_processing_jobs.py`.
- 6G verification/config: `backend/tests/test_processing_jobs.py`, `backend/tests/test_processing_api.py`, `backend/scripts/verify_processing_job.py`, `.env.example`, and `.gitignore`.

- 6F runtime: `backend/src/satquery/processing/validity.py`, `backend/src/satquery/processing/__init__.py`.
- 6F verification: `backend/tests/test_validity_engine.py`.
- 6E runtime: `backend/src/satquery/processing/registration.py`, `backend/src/satquery/processing/__init__.py`.
- 6E verification: `backend/tests/test_registration.py`, `backend/scripts/verify_registration.py`, reusable real-pair setup in `backend/scripts/verify_common_grid.py`.
- 6D runtime: `backend/src/satquery/processing/grid.py`, `backend/src/satquery/processing/__init__.py`.
- 6D verification: `backend/tests/test_common_grid.py`, `backend/scripts/verify_common_grid.py`.
- 6B runtime: `backend/src/satquery/processing/__init__.py`, `backend/src/satquery/processing/raster.py`.
- 6B verification: `backend/tests/test_raster_inputs.py`, `backend/scripts/verify_raster_inputs.py`.
- 6C runtime: `backend/src/satquery/providers/catalog/base.py`, `backend/src/satquery/providers/catalog/__init__.py`, `backend/src/satquery/providers/catalog/earth_search.py`, `backend/src/satquery/processing/__init__.py`, `backend/src/satquery/processing/quality.py`.
- 6C verification: `backend/tests/test_asset_resolution.py`, `backend/tests/test_quality_masks.py`, `backend/scripts/verify_quality_masks.py`.
- Runtime contracts: `backend/src/satquery/api/schemas/processing.py`.
- Verification: `backend/tests/test_processing_schemas.py`.
- Governance/contracts: `README.md`, `ROADMAP.md`, `API_CONTRACT.md`, `ARCHITECTURE.md`, `TRD.md`, `FEATURES.md`, `SECURITY.md`, `TESTING.md`, `docs/DECISIONS.md`, `docs/PHASE_6_TASKS.md`, `CURRENT_PHASE.md`, `SESSION_HANDOFF.md`, and this report.

## Exact next action

Stop before Phase 7. To complete Phase 6, start the Docker Desktop Linux engine, run the isolated PostgreSQL/PostGIS migration/readiness gate, configure the application-owned verified identity resolver without a client bypass, run one real protected single-scene and one real protected pair job, inspect their committed report/artifacts/cache/interruption/access behavior, and repeat the workspace browser workflow with laptop/mobile screenshots. Preserve failed provider reads and inconclusive registration as failures/unknowns; do not add model input, AI output, aggregate confidence, or change classification.
