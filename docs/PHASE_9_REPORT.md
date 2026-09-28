# Phase 9 report — shared optical/SAR foundation

Last updated: **2026-09-26**  
Current status: **PHASE 9 PARTIALLY_VERIFIED; 9F EXECUTED; STOP BEFORE PHASE 10**

## 9A outcome

The actual foundation was inspected before Phase 9 work. Earth Search Sentinel-2 L2A catalogue and trusted RGB/SCL resolution work; optical clipping/calibration/masking/common-grid/registration/change code passes synthetic gates and a direct real optical pair completed in Phase 8. Map layers and protected job/artifact paths have automated coverage. Production PostgreSQL/identity, protected real-pair completion, and browser verification remain carried blockers. No SAR provider, SAR pixels, SAR preprocessing, fusion, or SAR analysis exists.

Schema version `1.0` in `satquery.api.schemas.scene_metadata` adds an internal, strict shared metadata contract without changing existing optical behavior. Available records bind stable source ID/version, provider, mission, UTC acquisition interval, footprint with holes, native x/y resolution, CRS, processing level, product maturity, calibration, and valid-data-mask evidence. Optical records require unique ordered bands; SAR records require unique ordered polarizations. Cross-modality fields, arbitrary URLs/paths, extra readiness claims, provider/source mismatch, duplicate channels, invalid CRS identifiers, and contradictory calibration/mask encodings are rejected.

Unavailable metadata is a separate typed outcome with source/provider, expected modality, stable reason, missing fields, retryability, and corrective action. Only transient provider failures are retryable. A separate pair-outcome contract validates two distinct ordered source identities and their declared optical/optical, SAR/SAR, or optical/SAR modality combination. Unsupported combinations retain a stable reason and corrective action without confidence or fabricated readiness.

9A adds no adapter, network call, API route, database migration, artifact, raster read, calibration execution, job, map layer, UI, fusion, change method, or result. The existing Sentinel-2 contracts and implementation are unchanged.

## Validation

Commands were run from `backend/` unless noted:

- `..\.venv\Scripts\python.exe -m pytest tests\test_scene_metadata_schemas.py tests\test_catalog_schemas.py tests\test_viewer_schemas.py tests\test_processing_schemas.py tests\test_change_schemas.py -q`: **PASSED**, 86 tests.
- `..\.venv\Scripts\python.exe -m pytest tests\test_scene_metadata_schemas.py -q`: **PASSED**, 14 tests after correcting test-only formatting/type-narrowing findings.
- `..\.venv\Scripts\python.exe -m ruff check src\satquery\api\schemas\scene_metadata.py tests\test_scene_metadata_schemas.py`: **PASSED**.
- `..\.venv\Scripts\python.exe -m ruff format --check src\satquery\api\schemas\scene_metadata.py tests\test_scene_metadata_schemas.py`: initial run identified one test file needing formatting; final run **PASSED**, 2 files.
- `..\.venv\Scripts\python.exe -m mypy src\satquery\api\schemas\scene_metadata.py tests\test_scene_metadata_schemas.py`: initial run found four test-only narrowing/annotation errors; final run **PASSED**, 2 files.
- `..\.venv\Scripts\python.exe -m pytest -q`: **PASSED**, 234 tests; 1 PostgreSQL integration test skipped because `SATQUERY_TEST_DATABASE_URL` is not configured.
- `..\.venv\Scripts\python.exe -m ruff check .` and `..\.venv\Scripts\python.exe -m ruff format --check .`: **PASSED**, 100 files formatted.
- `..\.venv\Scripts\python.exe -m mypy src tests`: **PASSED**, 81 source files.
- Frontend tests/build: **NOT RUN** because 9A adds no frontend code, API route, or generated client contract.

Focused cases cover available optical and SAR records, UTC normalization, polygon-hole preservation, calibration modes, GDAL/categorical mask conventions, cross-modality rejection, duplicate bands/sources, provider mismatch, unavailable evidence and retryability, unsupported optical/SAR pairing, modality-order validation, and rejection of URLs, filesystem paths, extra readiness, and confidence claims.

## Files changed

- `backend/src/satquery/api/schemas/scene_metadata.py`
- `backend/tests/test_scene_metadata_schemas.py`
- `docs/PHASE_9_TASKS.md`
- `docs/PHASE_9_REPORT.md`
- `API_CONTRACT.md`
- `ARCHITECTURE.md`
- `FEATURES.md`
- `ROADMAP.md`
- `docs/DECISIONS.md`
- `CURRENT_PHASE.md`
- `SESSION_HANDOFF.md`

## Blockers and exact 9B entry point

The original Phase 9 title remains unavailable. No SAR provider/product, licence/access policy, calibration convention, terrain/orbit inputs, quality-mask authority, or supported downstream task has been selected or verified. Production PostgreSQL/identity and browser gates remain unwaived.

**Stop after 9A.** After explicit 9B authorization, evaluate and select one provider/product that can populate the 9A contract from trusted server-side metadata. Verify product maturity, processing level, polarizations, native CRS/resolution, calibration semantics, valid-data-mask authority, licence, access method, and stable version evidence before adding any adapter. Do not read or process SAR raster pixels in 9B unless that later request explicitly authorizes it.

## Task 9B — Sentinel-1 RTC discovery and bounded preparation

Status: **COMPLETE — 2026-09-25**

SatQuery now uses one explicit SAR product: [INPE public collection `sentinel-1-rtc-1`](https://data.inpe.br/stac/browser/collections/sentinel-1-rtc-1), a Sentinel-1 GRD-derived Level-2 RTC product. [INPE's processing documentation](https://data.inpe.br/dados/sentinel-1/) identifies Copernicus GLO-30 and mask values 0 valid, 1 shadow, 2 layover, 3 both, and 255 nodata; SatQuery retains only class 0. The adapter discovers scenes from a validated AOI and UTC interval, reports the polarizations actually present, populates the 9A contract, and resolves only fixed INPE HTTPS RTC assets. Client URLs and filesystem paths are absent from the contract.

The raster service performs windowed AOI extraction with polygon-hole preservation and a one-million-pixel bound. INPE's calibrated, terrain-normalized gamma-0 power remains float32 linear power for analysis. Validity combines inside-AOI, finite/non-nodata source values, and the aligned provider layover/shadow mask. SatQuery applies no additional calibration, terrain correction, normalization, or speckle filter. A separate PNG renderer uses fixed `10*log10(power)` and -25 to 0 dB solely for display.

Real verification used São Paulo AOI `[-46.650,-23.560,-46.647,-23.557]` and January 2025. It discovered `S1A_IW_RTCH_1SDV_20250120_057525_0715BC_0DCC` with actual `VH,VV`, then read VV as a 35×35 EPSG:4326 window. All 1,089 AOI pixels were valid; nodata and layover/shadow counts were zero; retained gamma-0 power ranged 0.0474098–5.68852; the fixed renderer returned a 1,198-byte PNG. The terrain model recorded by the item is Copernicus 30 m Global DEM. This is a single access/mechanics verification, not scientific task validation.

Commands and results:

- `..\.venv\Scripts\python.exe -m pytest -q tests/test_sar_phase9b.py tests/test_scene_metadata_schemas.py`: **18 passed**.
- `..\.venv\Scripts\python.exe -m pytest -q`: **238 passed, 1 skipped** (`SATQUERY_TEST_DATABASE_URL` absent).
- `..\.venv\Scripts\python.exe -m ruff check src tests scripts\verify_phase9b_real.py`: **passed**.
- `..\.venv\Scripts\python.exe -m ruff format --check src tests scripts\verify_phase9b_real.py`: **passed**, 87 files formatted.
- `..\.venv\Scripts\python.exe -m mypy src`: **passed**, 58 source files.
- `..\.venv\Scripts\python.exe scripts\verify_phase9b_real.py`: **passed** with the live values above.
- Frontend checks: **not run**, because no frontend code changed.

Files added or changed for 9B:

- `backend/src/satquery/api/schemas/sar.py`
- `backend/src/satquery/api/routes/sar.py`
- `backend/src/satquery/providers/catalog/inpe_sar.py`
- `backend/src/satquery/processing/sar.py`
- `backend/src/satquery/api/dependencies.py`
- `backend/src/satquery/api/router.py`
- `backend/src/satquery/main.py`
- `backend/src/satquery/providers/catalog/__init__.py`
- `backend/tests/test_sar_phase9b.py`
- `backend/scripts/verify_phase9b_real.py`
- `API_CONTRACT.md`, `ARCHITECTURE.md`, `FEATURES.md`, `ROADMAP.md`
- `docs/PHASE_9_TASKS.md`, `docs/PHASE_9_REPORT.md`, `CURRENT_PHASE.md`, `SESSION_HANDOFF.md`

Remaining limits: the selected public collection covers Brazil and reports provider-linked proprietary licensing; preparations/previews are memory-only, not durable authorized jobs or artifacts; there is no WebMercator SAR map layer or workspace UI; no SAR analysis, pair comparison, fusion, or semantic cause is implemented. Production PostgreSQL/identity and browser verification remain carried blockers.

**Stop after 9B.** Exact 9C entry point after explicit authorization: select one defensible SAR analytical task and define its compatible product/mode/polarization, validity/quality requirements, bounded method, output evidence, and failure states over preserved linear gamma-0. Do not analyze display colours or silently begin fusion.

## Task 9C — NISAR PROVISIONAL L2 GCOV

Status: **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-25**. The explicit user request changed the provisional 9C analytical-operation plan to NASA/ASF NISAR discovery and ingestion. Only this scope was implemented.

The backend now exposes typed `/api/v1/nisar/search` and `/api/v1/nisar/ingestions`. Public CMR search uses the fixed `NISAR_L2_GCOV_PROVISIONAL_V1` collection and bounded AOI/time. The trusted adapter re-fetches a selected ASF concept ID, accepts only NISAR L-SAR and provisional CRID `P05023` or later, and resolves only a fixed ASF HDF5 host. Actual CMR frequency/polarization, acquisition/footprint, product/PGE/CRID, QA-link availability, full-frame/joint flags, and orbit-fidelity class are retained. S-band and absent polarization are not invented. The granule CRS remains an unavailable metadata field until the HDF5 is read.

The ingestion service expects the exact ASF HDF5 under a server-configured cache root after host-side Earthdata Login. It checks containment and HDF5 signature, then uses pinned `h5py==3.16.0` to validate the source EPSG projection, regular metre coordinate axes, dimensionless gamma-0 units, fill value, and covariance/mask alignment before a bounded HDF5 window. Values remain float32 calibrated RTC gamma-0 linear power, with no extra scale or display normalization; unexpected scale/offset is rejected. GCOV product-mask 1–254 is valid; 0 is an invalid ensemble; 255 is outside acquisition. AOI and finite/non-fill source validity remain separate, with explicit counts. A one-million-pixel cap, typed unavailable reasons, processing version, actual affine/CRS/pixel spacing, and provisional quality warnings are returned. No preview, classifier, fusion, or SAR scientific analysis result was added.

Live verification: `..\.venv\Scripts\python.exe scripts\verify_phase9c_real.py` **passed**. NASA CMR returned actual ASF concept `G4250117587-ASF`, granule `NISAR_L2_PR_GCOV_023_040_D_124_4005_SHSH_A_20260617T000743_20260617T000802_P05023_F_P_J_001`, acquisition `2026-06-17T00:07:43Z`, CRID `P05023`, product version `1.0.11`, PGE `R05.02.3`, Frequency A 40 MHz HH and Frequency B 5 MHz HH. Its linked QA summary, partial-frame flag, non-joint observation, and forecast orbit fidelity were retained. The adapter resolved the trusted ASF HDF5 host. An [official public simulated GCOV sample](https://science.nasa.gov/mission/nisar/sample-data/) was downloaded (171,966,464 bytes); `h5py` read its Frequency A HHHH/mask layers, EPSG:32611 projection, coordinate axes, and dimensionless source units. Its grid is 4,545×6,220 at 20 m. The temporary sample was removed after inspection. GDAL 3.12.4 opened the covariance array without georeferencing, which led to the direct HDF5 metadata implementation. This older sample predates PROVISIONAL and is not calibration or pixel-ingestion evidence for that release.

Verification commands from `backend/`: focused `..\.venv\Scripts\python.exe -m pytest tests\test_nisar_phase9c.py -q --basetemp=.pytest-tmp\phase9c-h5`: **5 passed**, including real-structure synthetic HDF5, scale rejection, typed public API, and URL rejection; 9A/9B/9C focused regression previously passed **22** tests. Final full `..\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp\phase9c-last`: **243 passed, 1 skipped** (unconfigured PostgreSQL test). `..\.venv\Scripts\python.exe -m ruff check src tests scripts\verify_phase9c_real.py scripts\verify_phase9c_sample_grid.py`: **passed**. `..\.venv\Scripts\python.exe -m ruff format --check src tests scripts\verify_phase9c_real.py scripts\verify_phase9c_sample_grid.py`: **passed**, 93 files. `..\.venv\Scripts\python.exe -m mypy src`: **passed**, 62 source files. `..\.venv\Scripts\python.exe scripts\verify_phase9c_sample_grid.py`: **passed for HDF5 metadata and documented GDAL georeferencing failure**, with temporary sample removed. Frontend was unchanged and not run. An initial sandboxed pytest run failed on temp-directory ACL, then the same focused suite passed with approved execution. The first live check AOI had no intersecting scene; the verification script now derives an actual granule footprint before exercising AOI search.

Diagnostic failures were retained as evidence: direct GDAL `/vsicurl/` HDF5 subdataset opening failed; the local sample opened as float32 but had no GDAL CRS/transform. `curl` failed through the host proxy/TLS configuration, while bounded `httpx2` with `trust_env=False` downloaded the public sample and removed it after inspection. Offline `pip-compile --no-index` could not resolve pinned build dependencies; the final `pip-compile --no-build-isolation --output-file=requirements.lock --strip-extras requirements.in` completed and pinned `h5py==3.16.0`. No Earthdata credential or authenticated granule was available.

Files changed: `backend/src/satquery/api/schemas/nisar.py`, `api/routes/nisar.py`, `providers/catalog/nisar_cmr.py`, `processing/nisar.py`, API router/dependencies, application wiring, settings, provider export, `backend/tests/test_nisar_phase9c.py`, `backend/scripts/verify_phase9c_real.py`, `backend/scripts/verify_phase9c_sample_grid.py`, `backend/pyproject.toml`, `backend/requirements.lock`, `.gitignore`, `.env.example`, `README.md`, `API_CONTRACT.md`, `ARCHITECTURE.md`, `FEATURES.md`, `ROADMAP.md`, `docs/DECISIONS.md`, `docs/PHASE_9_TASKS.md`, `docs/PHASE_9_REPORT.md`, `CURRENT_PHASE.md`, and `SESSION_HANDOFF.md`.

**Remaining gate:** [NASA/ASF requires Earthdata Login for HDF5 download](https://nisar-docs.asf.alaska.edu/earthaccess/). On the backend host, authenticate with `earthaccess.login()` through a protected `.netrc` for `urs.earthdata.nasa.gov` or an interactive operator session, select the exact CMR granule, and place its original `.h5` filename at `NISAR_PRODUCT_CACHE_ROOT/<concept-id>/`. Then run a small AOI ingestion and inspect actual layers, CRS, source values, mask counts, and product QA. **Live PROVISIONAL pixel ingestion remains UNVERIFIED. Stop before 9D.**

## 9D optical/SAR pair preparation

Implemented an internal bounded co-location service for Sentinel-2 L2A calibrated RGB/SCL and INPE Sentinel-1 RTC **C-band** gamma-0 power. It resolves selected stable scene IDs through the existing trusted adapters, uses the existing native optical extractor, SCL decoder, common AOI UTM grid, and SAR extractor, and never accepts client asset locations. The SAR linear power is reprojected with bilinear interpolation over source-valid cells; masks are reprojected nearest-neighbour. This follows [Rasterio's reprojection](https://rasterio.readthedocs.io/en/stable/topics/reproject.html) and [resampling guidance](https://rasterio.readthedocs.io/en/stable/topics/resampling.html). The INPE RTC product supplies already-calibrated gamma-0 and an actual layover/shadow mask ([collection documentation](https://data.inpe.br/stac/browser/collections/sentinel-1-rtc-1)). There is no additional calibration or display stretch in this pair service.

The result retains each source identity, acquisition UTC, absolute gap in hours, original optical calibrated bands/unit `1`, original SAR analytical raster and gamma-0 units, provider calibration/mask/version/checksum records, one target CRS/affine/dimensions/resolution, resampled SAR power, separate SAR valid/terrain masks, and joint valid/usable masks. AOI-denominator coverage and area use the projected grid cell area. Optical cloud/cirrus, cloud/cast shadows, snow, missing data and unknown SCL remain excluded by the existing quality masks; SAR nodata and provider terrain-invalid cells remain excluded. INPE Sentinel-1 C-band and NISAR L-band are not numerically interchangeable; NISAR is not a supported 9D pair. No optical/SAR change detector, cause classifier, cross-sensor normalization, correction warp, display input, public route, job, artifact, or map overlay was added.

An `analysis_ready` state requires at least 10% AOI joint usability (provisional engineering minimum), actual optical QA, and at least four independently identified corresponding features distributed across all four grid quadrants, each with <=0.5 target pixel residual. The residual uses output-grid pixel-centre coordinates. These bounds are unvalidated engineering policy, not scientific accuracy or model confidence. **No independent real-scene tie points are available**, so the real path cannot claim feature registration or analysis readiness from a shared grid. Missing/poor alignment, absent joint overlap, low coverage, or missing optical QA yields `insufficient_evidence` with reasons. Gap >30 days and upsampling are contextual warnings; upsampling adds no detail.

Validation from `backend/`:

- `..\.venv\Scripts\python.exe -m pytest tests\test_optical_sar_pair_phase9d.py -q --basetemp=.pytest-tmp\phase9d2` — **5 passed** (synthetic differing CRS/origins, 36-cell AOI, 400 m² cell area, preserved gamma-0, cloud/shadow/terrain masks, no overlap, missing QA, distributed alignment pass/fail, AOI mismatch, and NISAR rejection).
- `..\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp\phase9d_full_escalated`, `..\.venv\Scripts\python.exe -m pytest -q --disable-warnings --basetemp=.pytest-tmp\phase9d_export_final`, and final `..\.venv\Scripts\python.exe -m pytest -q --disable-warnings --basetemp=.pytest-tmp\phase9d_native_final` — **248 passed, 1 PostgreSQL integration skip** each. The first sandboxed full run reached test execution but its pytest temp directory was inaccessible at teardown; approved non-sandboxed reruns passed. This is an environment ACL, not a test assertion failure.
- `..\.venv\Scripts\python.exe -m ruff check src tests scripts`, `..\.venv\Scripts\python.exe -m ruff format --check src tests scripts`, `..\.venv\Scripts\python.exe -m mypy src/satquery` — **passed** (112 formatted files, 63 typed source files). Final post-edit `..\.venv\Scripts\python.exe -m pytest tests\test_optical_sar_pair_phase9d.py -q --disable-warnings --basetemp=.pytest-tmp\phase9d_final4` also passed **5/5**.
- `..\.venv\Scripts\python.exe scripts\verify_phase9d_real.py` — selected actual `S2B_T23KLP_20250115T131403_L2A` (2025-01-15 13:18:55Z) and `S1A_IW_RTCH_1SDV_20250201_057700_071CAB_B664` (2025-02-01 08:31:10Z) over the bounded São Paulo AOI. Optical scientific bands resolved and the optical AOI extraction reached the SAR stage, which failed safely at the INPE gamma-0 COG read with `SAR_RASTER_UNAVAILABLE`: GDAL inherited an unreachable `127.0.0.1` HTTPS proxy. A diagnostic retry excluding only the fixed trusted `data.inpe.br` host from that verification process also failed: direct GDAL/cURL Schannel returned `SEC_E_NO_CREDENTIALS` after a long thread shutdown. The proxy override was removed from the final script. No joint real raster, alignment, or analysis readiness is claimed.

Files changed: `backend/src/satquery/processing/optical_sar_pair.py`, `backend/src/satquery/processing/__init__.py`, `backend/tests/test_optical_sar_pair_phase9d.py`, `backend/scripts/verify_phase9d_real.py`, `docs/PHASE_9_TASKS.md`, `docs/PHASE_9_REPORT.md`, `CURRENT_PHASE.md`, `SESSION_HANDOFF.md`, `ROADMAP.md`, `API_CONTRACT.md`, and `ARCHITECTURE.md`. No frontend changes; frontend checks not run for this internal backend-only 9D checkpoint. The live 9C PROVISIONAL staging gate, production PostgreSQL/identity, and browser verification remain open.

**9D status: IMPLEMENTED / PARTIALLY VERIFIED.** Exact resume: restore trusted INPE raster connectivity, rerun the bounded live script and inspect source IDs/time gap/grid/quality and joint counts; obtain independently checked cross-modal tie points and residuals before calling a real pair `analysis_ready`. Then, only on explicit authorization, begin 9E integration. Stop before 9E.

## 9E optical + SAR workspace and evidence job

Implemented a bounded **separate-source** summary over the existing 9D preparation. The new protected job/API re-resolves stable Sentinel-2 L2A and INPE Sentinel-1 RTC IDs server-side, prepares AOI scientific arrays (not thumbnails or preview colours), computes median calibrated red reflectance and median linear gamma-0 power only on their respective valid masks, and records per-source evidence bounds in the common projected CRS, dates, valid-cell counts, joint AOI coverage/area, time gap, alignment status, warnings, and version. It cannot infer cross-sensor agreement, flood extent, building change, cause, or calibrated confidence. No NISAR pairing was added. The single supported question is a source-separated observation summary; other text yields `insufficient_evidence`. Missing quality/low or zero overlap also prevents a positive limited observation state. The answer does not claim registration merely from the common grid.

The job reuses durable processing records, bounded concurrency/timeout/one-million-pixel cap, owner/scope cache identity, restart reconciliation, stage counts, atomic JSON evidence artifact and owner-scoped artifact access. The workspace uses the existing selected AOI/optical scene, real SAR search and returned polarizations, a dated display-only SAR preview aligned by actual WGS84 bounds, opacity/visibility control, job status/limit explanations, and assistant routing to the computed summary. Inputs changing abort pending responses and clear overlays/results. The optical viewer remains the existing scientific-scene rendering path; the SAR PNG is display-only and never enters analysis.

Verification (2026-09-25):

- Backend `..\.venv\Scripts\python.exe -m pytest tests/test_optical_sar_phase9e.py -q`: **5 passed**, including synthetic API start/status/result/private artifact, owner denial, cache reuse, source-separated measurement, unsupported question, empty overlap, untrusted source and fail-closed identity. `..\.venv\Scripts\python.exe -m pytest tests/test_optical_sar_phase9e.py tests/test_optical_sar_pair_phase9d.py tests/test_sar_phase9b.py -q` initially hit sandbox Windows pytest temp ACL after 12 assertions; approved rerun **14 passed**. `..\.venv\Scripts\python.exe -m mypy src/satquery` and Ruff source/test check **passed**.
- Final backend `..\.venv\Scripts\python.exe -m pytest -q --disable-warnings`: **253 passed, 1 skipped** (PostgreSQL integration URL not configured). Final 9E+9D rerun **10 passed**, strict source mypy and Ruff **passed**.
- Frontend `npm run test:run -- src/components/workspace/optical-sar-panel.test.tsx src/lib/sar-map-layer.test.ts src/components/workspace/scene-container.test.tsx src/components/workspace/assistant-panel.test.tsx --pool=threads --testTimeout=10000`: **18 passed** after correcting a discovery-status regression found by the first run. Initial forked Vitest worker stalled and sandboxed Vite subprocess received EPERM; approved threaded run passed. `npm run typecheck`, `npm run lint`, `npm run format:check`: **passed**. `npm run build` compiled but sandbox denied a TypeScript subprocess (EPERM); approved rerun **passed**, static `/workspace` generated.
- Browser interaction: **NOT VERIFIED**. The required browser connector failed before tab creation with `codex/sandbox-state-meta: missing field sandboxPolicy`; no screenshot or visual map assertion is claimed. Real protected 9E API completion: **NOT VERIFIED** because production PostgreSQL/verified principal is unconfigured and the previous bounded live 9D pair failed at trusted INPE COG access (proxy/Schannel). Existing 9B live SAR discovery/preview and 9D optical source resolution are retained evidence only, not a successful joint 9E run.

Files changed: new `backend/src/satquery/api/schemas/optical_sar.py`, `api/routes/optical_sar.py`, `processing/optical_sar_jobs.py`, `backend/tests/test_optical_sar_phase9e.py`, `frontend/src/lib/optical-sar-client.ts`, `sar-map-layer.ts`, `sar-map-layer.test.ts`, `components/workspace/optical-sar-panel.tsx`, `optical-sar-panel.test.tsx`; updated backend job/artifact schema/repository/router/dependencies/main, 9D provider Protocol typing, frontend assistant/map/scene/shell/CSS, API contract, Phase 9 task report, current phase and session handoff.

**9E status: IMPLEMENTED / PARTIALLY VERIFIED.** Restore INPE COG access and a durable PostgreSQL/verified principal, run one real protected 9E job, compare its artifact provenance/masks/coverage with the selected source pair, then restore browser automation to verify both layers, opacity, job/assistant response, and stale-input invalidation with screenshots. These are concrete 9E verification blockers, not 9F completion evidence. **Stop before 9F.**

## 9F integration verification and handoff — 2026-09-26

**Result: PARTIALLY_VERIFIED, not COMPLETE.** Existing 9B evidence contains one successful real INPE Sentinel-1 RTC VV raster/preview (`S1A_IW_RTCH_1SDV_20250120_057525_0715BC_0DCC`, 2025-01-20; 35×35 EPSG:4326, 1,089 valid AOI cells); Phase 8 contains a separately completed real Sentinel-2 optical pair. Neither establishes a working *joint* optical/SAR job or registered map display. This 9F run selected the real São Paulo Sentinel-2 `S2B_T23KLP_20250115T131403_L2A` (2025-01-15T13:18:55.302Z) and INPE Sentinel-1 RTC `S1A_IW_RTCH_1SDV_20250201_057700_071CAB_B664` (2025-02-01T08:31:10Z). Catalogue discovery and trusted asset resolution reached optical B02 scientific extraction, which failed with `RASTER_READ_FAILED`; SAR pixel preparation, common-grid mask/coverage, independent alignment, protected result, and display were therefore **not verified**. A second live SAR discovery timed out at INPE. Real negative-case outcomes were not manufactured from these failures.

NISAR: `NISAR_PRODUCT_CACHE_ROOT` was not configured and no authenticated PROVISIONAL HDF5 was staged. The 9F CMR/sample attempt timed out on the ASF public-sample TLS connection. Prior 9C CMR metadata and older public simulated sample checks remain useful format evidence, not a real PROVISIONAL end-to-end ingestion. [ASF's Earthdata Login guide](https://nisar-docs.asf.alaska.edu/earthaccess/) gives the required host authentication/staging step; the current product's [provisional limitations](https://nisar-docs.asf.alaska.edu/provisional-known-issues/) remain applicable. NISAR is not silently treated as an INPE C-band layer.

Defects fixed: trusted raster/quality/grid exceptions now yield safe specific failed-job codes/messages; the stored code is normalized to the existing lowercase API schema, so a failed job status itself does not cause HTTP 500. Workspace preview/result binding checks full provider/collection/item, acquisition, polarization, request/job ID and processing version before showing returned pixels or an answer. Synthetic API/UI regressions prove error reporting and reject a matching item ID with the wrong provider. No source thumbnail, display stretch, basemap, fixture, or demo answer is used for measured evidence. The supported computed answer describes optical reflectance and SAR gamma-0 **separately**, carries source identities/dates/evidence footprints/coverage, and explicitly limits interpretation; it does not infer a flood, new building, agreement, or confidence.

Negative-path evidence: backend synthetic tests passed for unavailable/unsupported polarization, zero overlap, cloud-covered optical with zero joint usable pixels, a 45-day contextual time-gap warning, SAR nodata/terrain exclusions, missing optical QA, mismatched AOIs, unreliable registration, unavailable provider raster, and owner-scoped artifact access. Frontend tests passed for scene/AOI invalidation, safe job failure, overlay binding, and wrong-provider result rejection. These are fixture checks, not real-scene scientific validation. The browser connector returned `codex/sandbox-state-meta: missing field sandboxPolicy` before a tab was created; no laptop/mobile visual assertion or screenshot exists. Production `DATABASE_URL`/`SATQUERY_TEST_DATABASE_URL` and a verified principal were absent, so protected real job/cache/artifact checks remain open.

Commands and actual outcomes (repository root unless noted):

- `cd backend; ..\.venv\Scripts\python.exe scripts\verify_phase9d_real.py` — real pair discovered/resolved; failed on optical B02 scientific raster read (`RASTER_READ_FAILED`), before joint output.
- `cd backend; ..\.venv\Scripts\python.exe scripts\verify_phase9b_real.py` — INPE Sentinel-1 discovery timed out; no new 9F SAR raster success.
- `cd backend; ..\.venv\Scripts\python.exe scripts\verify_phase9c_real.py` — ASF public sample TLS timeout after CMR metadata work; no current NISAR pixel read.
- `cd frontend; npm run test -- --run src/components/workspace/optical-sar-panel.test.tsx` — **3 passed** (approved unsandboxed rerun after Windows spawn denial).
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` — **passed** on final run: backend Ruff and format (120 files), strict mypy (97 source files), backend pytest **254 passed, 1 PostgreSQL integration deselected**; frontend Biome format/lint, TypeScript, Vitest **123 passed in 30 files**, Next.js production build. Two intermediate runs exposed and corrected a new test's Biome formatting and TypeScript annotation; the final gate is authoritative. Vitest emitted expected jsdom canvas-unavailable notices; no WebGL/browser verification is inferred.

Changed in 9F: `backend/src/satquery/processing/optical_sar_jobs.py`, `backend/tests/test_optical_sar_phase9e.py`, `backend/tests/test_optical_sar_pair_phase9d.py`, `frontend/src/components/workspace/optical-sar-panel.tsx`, `frontend/src/components/workspace/optical-sar-panel.test.tsx`, this report, `docs/PHASE_9_TASKS.md`, `docs/DECISIONS.md`, `CURRENT_PHASE.md`, `SESSION_HANDOFF.md`, `ROADMAP.md`, and `README.md`.

**Exact resume gate:** restore trusted Earth Search/INPE COG access; configure PostgreSQL/PostGIS and a verified principal; rerun a bounded real pair through `/api/v1/optical-sar/jobs`, inspect native calibrated inputs, optical/SAR masks, joint coverage/area, source versions and protected artifact, and obtain independent cross-modal tie-point evidence. Restore the browser bridge to inspect both dated layers/opacity and the source-grounded answer with stale-input behavior. Separately authenticate Earthdata on the backend host, stage an actual PROVISIONAL GCOV HDF5 under the configured cache root, and inspect a bounded native layer/mask/QA read. Mark COMPLETE only after those required real-data and UI gates pass. **Stop before Phase 10.**
