# Phase 9 — Original agreed title unavailable

Working scope: **Shared optical/SAR scene metadata foundation**

`ROADMAP.md` retains the unavailable original Phase 9 title. On 2026-09-25 the user explicitly authorized a six-checkpoint Phase 9 working scope beginning with a shared optical/SAR metadata contract. Each checkpoint 9A–9F was subsequently authorized separately; implementation and verification status remain distinct in the table and logs below.

## Checkpoints

| Task | Acceptance boundary | Status | Evidence / next action |
| --- | --- | --- | --- |
| 9A | Audit the actual Phase 8 imagery/map/analysis foundation and add strict typed contracts for available optical/SAR scene metadata, explicit unavailable metadata, and supported/unsupported scene-pair combinations. Preserve the existing optical contracts and runtime behavior. | **COMPLETE — 2026-09-25** | Internal schema `1.0` and focused optical/SAR/negative tests pass. No provider, route, persistence, raster read, SAR processing, fusion, map, or UI behavior was added. |
| 9B | Discover real Sentinel-1 SAR for an AOI/date range and prepare a bounded map-aligned, calibrated, terrain-corrected visualization input through a trusted provider adapter. Preserve analytical backscatter and actual polarization availability. | **COMPLETE — 2026-09-25** | INPE public `sentinel-1-rtc-1` only: GRD-derived Level-2 RTC gamma-0 power, Copernicus 30 m DEM, explicit layover/shadow plus nodata masks, and fixed display-only dB scaling. Live discovery/extraction/render passed. |
| 9C | Discover NISAR PROVISIONAL L2 GCOV L-band scenes by AOI/time and ingest an authenticated, operator-staged HDF5 layer on its native geocoded grid with exact mask/calibration/version evidence. | **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-25** | Real CMR search/resolve and public simulated sample HDF5/coordinate metadata pass; local windowed ingestion passes known HDF5 rasters. Live PROVISIONAL pixels remain unverified pending Earthdata Login staging. |
| 9D | Define and verify task-specific SAR or optical/SAR compatibility, common-grid preparation, alignment evidence, and unsupported outcomes without treating visual overlap as registration. | **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-25** | Internal Sentinel-2 L2A RGB + INPE Sentinel-1 RTC C-band co-location, separate calibrated values/units and masks, measured joint coverage/time gap, and distributed independent tie-point gate pass synthetic checks. Live joint raster and cross-modal feature alignment remain unverified; see 9D log. |
| 9E | Integrate the supported Phase 9 workflow through existing jobs, artifacts, authorization, API, and workspace patterns with source-bound overlays and truthful failures. | **IMPLEMENTED / PARTIALLY VERIFIED — 2026-09-25** | Bounded source-separated observation job/API, owner-scoped artifact/cache, SAR search/preview/map/assistant workflow, synthetic API/UI checks and build pass. Real protected pair completion and browser visual gate remain blocked; see 9E log. |
| 9F | Reconcile Phase 9 requirements and verify real plus synthetic workflows, negative cases, provenance, access control, UI behavior, tests, and build; close honestly. | **EXECUTED / PARTIALLY VERIFIED — 2026-09-26** | Full automated gate passes; real end-to-end pair, protected job/browser, and live NISAR ingestion remain blocked. See 9F log. |

## 9A acceptance criteria

- One strict schema version represents stable source identity, provider, mission, UTC acquisition interval, WGS84 footprint, native resolution, native CRS, processing level, product maturity, calibration state, and valid-data-mask evidence.
- Optical metadata contains an ordered non-empty optical-band collection and cannot contain SAR polarization fields. SAR metadata contains an ordered non-empty polarization collection and cannot masquerade as optical bands.
- Calibration distinguishes uncalibrated source values requiring a documented operation, values already calibrated in the source, and unavailable calibration evidence. Scale/offset coefficients are valid only for the scale/offset method.
- Valid-data-mask metadata states whether mask evidence is available and records its convention without exposing a provider URL or filesystem path.
- Unavailable metadata is a typed outcome with stable reason code, missing fields, retryability, and corrective action; it cannot carry a usable metadata record.
- Scene-pair assessment is a separate typed supported/unsupported outcome. It records both stable source identities and modalities, rejects duplicate sources and contradictory combination labels, and contains no fabricated confidence or readiness claim.
- Existing catalogue, optical asset-resolution, preparation, change, map, job, and assistant contracts remain unchanged and their focused regression tests pass.
- 9A adds no provider adapter, public route, database migration, artifact, raster processing, SAR calibration, fusion, map layer, UI control, or Phase 9 analysis result.

## Foundation audit

| Component | Confirmed working evidence | Carried limitation relevant to Phase 9 |
| --- | --- | --- |
| Optical catalogue and source identity | Earth Search Sentinel-2 L2A metadata, stable provider/collection/item identity, bounded AOI search, and trusted server-side RGB/SCL asset resolution are implemented and tested. | The provider allow-list contains no SAR collection; catalogue metadata does not prove analytical readiness. |
| Scientific imagery preparation | Windowed calibrated Sentinel-2 RGB extraction, SCL decoding, AOI masks, common projected grids, deterministic registration assessment, and explicit validity evidence pass synthetic tests; a direct real optical pair completed in 8F. | Protected real jobs remain vulnerable to intermittent remote COG reads; PostgreSQL/verified identity are unconfigured. No SAR pixels have been prepared. |
| Map and workspace | Real optical viewing works; prepared-mask, grounding, and computed-change map layer lifecycles have automated coverage. | The Phase 8 browser bridge was unavailable, and no SAR rendering or analytical overlay exists. |
| Change analysis | Versioned calibrated-RGB spectral change, CRS-correct areas, non-causal summaries, protected API/job/artifact code, and computed “What changed?” routing exist. | This optical method is not valid for SAR or cross-sensor fusion and must not be reused as proof of SAR change. |
| Jobs and access | Bounded stages, cancellation/restart semantics, scoped cache identity, atomic artifacts, and owner checks have synthetic/in-memory coverage. | Durable production PostgreSQL/principal verification remains open and cannot be waived by Phase 9. |

## 9A work log

Implemented `backend/src/satquery/api/schemas/scene_metadata.py` and `backend/tests/test_scene_metadata_schemas.py`. Reconciled the API contract, architecture, feature inventory, roadmap, decision log, Phase 9 report, current checkpoint, and session handoff. Existing optical schemas and runtime modules were not modified.

Validation:

- Focused new contract: **14 passed**.
- New contract plus catalogue/viewer/processing/change schema regressions: **86 passed**.
- Scoped Ruff check and final format check: **passed**.
- Scoped strict mypy: **passed**.
- Full backend regression: **234 passed, 1 PostgreSQL integration test skipped** because its test database URL is not configured.
- Full backend Ruff/format and mypy: **passed** over 100 formatted files and 81 source files.
- Frontend tests/build: **not run** because 9A changes no frontend or runtime API surface.
- The initial format/mypy run found only test-file formatting and type narrowing/annotation issues; these were corrected before the clean rerun.

Carried blockers: the original title remains unavailable; no SAR provider/product or licence/access/calibration/mask policy is selected; no SAR pixels have been accessed; PostgreSQL/verified identity and browser gates remain open.

## 9B acceptance criteria

- Discovery accepts only a bounded WGS84 AOI/date interval and the fixed server-side INPE provider/collection. It never accepts client asset URLs or paths.
- Returned metadata records actual item polarizations and never assumes VV/VH are both present.
- The supported raster is INPE Sentinel-1 Level-2 RTC, derived from GRD and supplied as calibrated, terrain-normalized gamma-0 power. Identity calibration is not applied twice.
- AOI extraction is windowed, retains source EPSG:4326 georeferencing, preserves polygon holes, enforces one million pixels, and rejects empty/all-invalid results.
- The analytical array retains float32 linear gamma-0 power. Nodata and non-zero provider layover/shadow cells remain invalid in a separate mask.
- Rendering alone applies documented `10*log10(power)` and a fixed -25 to 0 dB stretch. Display bytes never become analytical values.
- Metadata records source/date/polarization, checksum, resolution, grid, calibration, RTC/DEM evidence, mask counts, processing version, and warnings.
- Provider/access, polarization, georeferencing, grid, coverage, validity, and resource failures are actionable and explicit.
- Focused metadata/mask tests and one real discovery/extraction/render pass.

## 9B work log

Implemented the trusted `InpeSarProvider`, typed SAR discovery/preparation API, bounded `SarRasterService`, and opaque preview route. The optical Earth Search adapter and routes remain unchanged. The provider is fixed to INPE collection `sentinel-1-rtc-1`; sources must be HTTPS `data.inpe.br` RTC GeoTIFFs under the allow-listed path.

The product decision follows [INPE collection metadata](https://data.inpe.br/stac/browser/collections/sentinel-1-rtc-1) and [INPE processing/mask documentation](https://data.inpe.br/dados/sentinel-1/): gamma-0 power is already radiometrically terrain corrected from Sentinel-1 GRD using the Copernicus GLO-30 DEM, is supplied in EPSG:4326 COGs, and exposes mask classes 0 valid, 1 shadow, 2 layover, 3 both, and 255 nodata. SatQuery retains only class 0. Raw Earth Search Level-1 GRD digital numbers were rejected because they need separate calibration/noise/terrain processing and use requester-pays storage. SatQuery applies no speckle filter. Copernicus documentation independently distinguishes GRD from gamma-0 terrain correction and orthorectification: <https://documentation.dataspace.copernicus.eu/Data/Sentinel1.html>.

Live evidence (São Paulo AOI `[-46.650,-23.560]` to `[-46.647,-23.557]`, January 2025): scene `S1A_IW_RTCH_1SDV_20250120_057525_0715BC_0DCC`, acquired `2025-01-20T08:31:11Z`, actual polarizations `VH,VV`; VV extraction produced 35×35 EPSG:4326 pixels, 1,089/1,089 valid AOI pixels, zero nodata and zero layover/shadow pixels, gamma-0 power 0.0474098–5.68852, and a 1,198-byte PNG. This proves one access/mechanics path, not application accuracy.

Validation:

- Focused Phase 9B plus 9A schemas: **18 passed**.
- Full backend: **238 passed, 1 PostgreSQL integration test skipped** because `SATQUERY_TEST_DATABASE_URL` is not configured.
- Full Ruff and format checks: **passed** over 87 files; strict mypy: **passed** over 58 source files.
- `cd backend; ..\.venv\Scripts\python.exe scripts\verify_phase9b_real.py`: **passed** with the live values above.
- Frontend checks: **not run**; 9B adds no workspace/UI code.

Carried blockers: INPE coverage is Brazil-only and its collection licence is provider-linked/proprietary; there is no durable SAR job/artifact/cache, protected access policy, WebMercator tile layer, workspace control, pair/fusion, or SAR analysis. EPSG:4326 pixels retain the provider grid; nominal metres are product metadata. Production PostgreSQL/identity and browser gates remain open.

**Status: 9B COMPLETE; STOP BEFORE 9C.** Exact 9C entry point after authorization: choose one bounded SAR analytical task and define its compatibility, validity, algorithm, and evidence contract over preserved linear gamma-0 and masks. Do not reuse display pixels, infer causes, start fusion, or widen providers implicitly.

## 9C checkpoint — NISAR PROVISIONAL L2 GCOV

The explicit 9C request supersedes the provisional SAR-analysis row. The supported collection is NASA/ASF `NISAR_L2_GCOV_PROVISIONAL_V1`, L-SAR only. Public CMR discovery accepts a validated WGS84 AOI, UTC interval, and limit 1–25; source resolution uses the stable ASF granule concept ID and re-fetches the CMR record. Actual frequency, polarization, bandwidth, CRID, PGE/product version, acquisition, footprint, QA-link availability, full-frame/joint-observation flags, and orbit-fidelity class come from the record. The projected CRS and exact pixel spacing remain unavailable until the HDF5 is opened. No S-band or unreported polarization is assumed.

Ingestion accepts only the selected stable source, AOI, frequency, supported real-valued diagonal covariance term, and a maximum of 1,000,000 pixels. The operator stages the exact CMR HDF5 file under `NISAR_PRODUCT_CACHE_ROOT/<concept-id>/<granule-ur>.h5`. The server resolves the expected filename from CMR, checks cache containment and HDF5 signature, then uses pinned `h5py` to read the documented covariance, `mask`, `projection`, and coordinate-axis datasets. It validates EPSG and regular metre axes before constructing the native affine and taking bounded windows. Values retain calibrated RTC gamma-0 **linear power** without a second scale, logarithm, or display stretch; unexpected scale/offset is rejected. The separate validity mask combines inside-AOI, finite/non-fill source values, and GCOV subswath mask values 1–254; product-mask 0 (invalid ensemble) and 255 (outside acquisition) are counted separately. Actual CRS/affine/dimensions/metre pixel spacing and the accepted dataset paths are returned. No NISAR visualization, task classifier, fusion, or scientific readiness claim is added.

Known PROVISIONAL limits from the [official NASA/ASF release notes](https://nisar-docs.asf.alaska.edu/provisional-known-issues/) are surfaced: limited-site validation, high-latitude ionosphere/geolocation, RFI filtering, low-level ripples, Frequency B 5 MHz calibration residuals, incompletely calibrated relative polarimetric phase, and incomplete L0B artifacts. CMR QA-summary/report availability and full-frame/orbit/joint flags remain distinct from measured pixel validity. See the [GCOV guide](https://nisar-docs.asf.alaska.edu/gcov/) for gamma-0, RTC, layers, native UTM grids, and the mask; the [availability guide](https://nisar-docs.asf.alaska.edu/availability-overview/) dates the PROVISIONAL release and L/S-band scope.

Live evidence: CMR returned actual concept `G4250117587-ASF`, granule `NISAR_L2_PR_GCOV_023_040_D_124_4005_SHSH_A_20260617T000743_20260617T000802_P05023_F_P_J_001`, acquired `2026-06-17T00:07:43Z`, product `1.0.11`, PGE `R05.02.3`, Frequency A 40 MHz HH and Frequency B 5 MHz HH. Its QA summary is linked, while the granule is partial-frame, non-joint, and has forecast orbit fidelity. The server resolved the trusted ASF HDF5 host. The [official public simulated GCOV sample](https://science.nasa.gov/mission/nisar/sample-data/) was downloaded (171,966,464 bytes) and its real HDF5 layers, axes, EPSG:32611 projection, dimensionless HHHH units, and categorical-mask description were inspected; its Frequency A grid is 4,545×6,220 with 20 m spacing. GDAL 3.12.4 opened the covariance array without georeferencing, which prompted the pinned `h5py` metadata path. The temporary download was removed. That older simulated `D00404` sample is not evidence of current PROVISIONAL calibration or live product ingestion.

**Live pixel-ingestion blocker and exact host step:** [NASA/ASF's Earthaccess instructions](https://nisar-docs.asf.alaska.edu/earthaccess/) require Earthdata Login for NISAR downloads. On the backend host, install `earthaccess` in an operator environment, run `earthaccess.login()` interactively or with a protected `.netrc` for `urs.earthdata.nasa.gov`, use the exact CMR granule identity above to select and download its HDF5 from `nisar.asf.earthdatacloud.nasa.gov`, and place the original filename under the configured cache root/concept-ID directory. Never log or store the credentials in SatQuery. Re-run ingestion on a small AOI and inspect its CRS, actual layers, mask values, QA, and output. Pinned `h5py` reads source projection/axes directly because installed GDAL 3.12.4 did not georeference the sample covariance subdataset; [dedicated GDAL NISAR support arrived in 3.13](https://nisar-docs.asf.alaska.edu/data-format/). Until a current granule is staged and read, live PROVISIONAL pixel ingestion is **UNVERIFIED**.

Host staging example after installing `earthaccess` in an operator Python environment (set `NISAR_PRODUCT_CACHE_ROOT` to the same configured backend cache root):

```python
from pathlib import Path
import earthaccess

concept = "G4250117587-ASF"
granule = "NISAR_L2_PR_GCOV_023_040_D_124_4005_SHSH_A_20260617T000743_20260617T000802_P05023_F_P_J_001"
results = earthaccess.search_data(
    short_name="NISAR_L2_GCOV_PROVISIONAL_V1", granule_name=granule, count=2
)
assert len(results) == 1 and results[0]["meta"]["concept-id"] == concept
earthaccess.login()  # prompts on the host or uses protected operator .netrc
destination = Path("<configured NISAR_PRODUCT_CACHE_ROOT>") / concept
destination.mkdir(parents=True, exist_ok=True)
earthaccess.download(results, local_path=str(destination))
assert (destination / f"{granule}.h5").is_file()
```

Validation: `..\.venv\Scripts\python.exe scripts\verify_phase9c_real.py` passed CMR search/resolve plus public sample signature; `..\.venv\Scripts\python.exe scripts\verify_phase9c_sample_grid.py` read real sample HDF5 layers/axes/EPSG and exposed GDAL 3.12.4's missing georeferencing. Final focused NISAR tests passed 5, 9A/9B/9C regression passed 22, and full backend passed 243 with one unconfigured PostgreSQL skip. Ruff/format and strict mypy passed. Synthetic HDF5 ingestion verifies CRS/affine, unchanged power, HDF5 staging gate, available and unavailable layers, mask 0/255, nodata, unexpected scale rejection, and public API URL rejection. Exact commands are in the Phase 9 report. Files changed: NISAR schema/provider/service/route, config/dependencies/router/main/provider exports, pinned h5py manifest/lock, focused tests, two real verification scripts, and Phase 9/API/architecture/checkpoint documentation.

**Status: 9C IMPLEMENTED / PARTIALLY VERIFIED. Stop before 9D.** The exact remaining 9C verification entry point is authenticated staging and one real PROVISIONAL GCOV AOI read with native CRS/mask QA inspection. Only after that should any later authorized 9D work consider SAR pair compatibility; no analysis or fusion result is established by 9C.

## 9D checkpoint — optical/SAR spatial co-location

The supported 9D pairing is deliberately narrow: one trusted Earth Search Sentinel-2 L2A calibrated RGB/SCL preparation and one trusted INPE Sentinel-1 RTC **C-band** scene with an actually available selected polarization. NISAR L-band is explicitly unsupported here; 9C live PROVISIONAL pixel ingestion remains unverified. The 9D result is an internal processing record, not an API route, job, fusion detector, change map, or claim that reflectance and gamma-0 are interchangeable.

`OpticalSarPairService.prepare_real` resolves stable scene IDs through the existing adapters, runs native optical extraction and SCL masking, defines a single bounded AOI UTM grid, and prepares SAR from provider-calibrated gamma-0 and terrain-mask assets. It bilinearly resamples **linear** SAR power with invalid values set to nodata; all validity/terrain categories use nearest neighbour. It retains optical reflectance (unit `1`) and SAR gamma-0 power separately, preserving optical calibration/source versions and SAR processing/checksum evidence through the returned source records. Display PNG and dB stretch never enter the pair. Joint validity requires both scenes and the AOI; joint usability additionally requires optical SCL usable pixels and SAR nodata/layover/shadow validity. Measured pixel counts and square metres use the common projected grid and an explicit inside-AOI denominator. Acquisition gap is reported in hours; the provisional 30-day warning is contextual, not a rejection threshold. Upsampling is warned as adding no detail. Processing version: `9d-optical-sar-colocation-v1`.

**Alignment gate:** a common CRS, transform, dimensions, and nonzero overlap do not verify feature registration. The optional internal independent-tie-point evidence uses corresponding **output-grid pixel-centre** coordinates over the joint-usable area. At least four points must span all four grid quadrants and each residual must be at most 0.5 output pixel. These are provisional engineering limits, not validated cross-modal accuracy. No automatic optical/SAR intensity correlation or flexible correction is attempted. Without independent evidence, or with low/no joint usable coverage (provisional minimum 10% of AOI), the typed outcome is `insufficient_evidence` with reasons. Actual real scenes have no such independently verified tie points yet, so none is called analysis-ready.

Synthetic fixtures (clearly not provider observations) verify EPSG:4326 SAR to EPSG:32631 optical-grid reprojection, 36 AOI cells at 20 m, optical clouds/shadows, a SAR terrain-invalid cell, unchanged linear power, 400 m² cell area, six-hour gap, zero overlap, missing QA, distributed aligned controls, a one-pixel alignment failure, mismatched AOIs, and NISAR rejection. Focused and full checks are recorded in the Phase 9 report. An actual bounded São Paulo Sentinel-2/INPE pairing was attempted; catalogue resolution and optical extraction reached the SAR read, but the first read inherited a dead local GDAL proxy. A direct trusted-host retry is recorded in the report. **No live optical/SAR joint raster or verified alignment is claimed unless that retry succeeds.**

Files: `backend/src/satquery/processing/optical_sar_pair.py`, `backend/src/satquery/processing/__init__.py`, `backend/tests/test_optical_sar_pair_phase9d.py`, `backend/scripts/verify_phase9d_real.py`, and Phase 9/architecture/API/checkpoint documents. Carried blockers: actual cross-modal tie-point validation, live NISAR PROVISIONAL staging, production PostgreSQL/verified identity, and browser gates. Exact next 9D verification: restore INPE raster connectivity, run `cd backend; ..\.venv\Scripts\python.exe scripts\verify_phase9d_real.py`, inspect both native inputs and projected masks/coverage, then establish independent distributed cross-modal correspondences and residuals before changing the real outcome to `analysis_ready`. **Stop before 9E.**

## 9E checkpoint — bounded optical + SAR workspace

The implemented flow is intentionally a **separate-source observation summary**, not optical/SAR fusion, object detection, flood mapping, or a semantic change detector. A selected Earth Search Sentinel-2 L2A scene and discovered INPE Sentinel-1 RTC C-band scene/polarization are rebound through trusted adapters. The existing 9D common-grid and joint masks supply calibrated red reflectance, linear gamma-0 power, pixel-mask evidence bounds in the target CRS, source dates/IDs, time gap, AOI-denominator joint coverage and area, and alignment limitations. Unsupported free-text interpretations yield `insufficient_evidence`; the one bounded supported question summarizes separate measurements. There is no model confidence or inferred agreement. Display dB stretch and map preview never become scientific inputs.

`POST /api/v1/optical-sar/jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/result`, `POST /jobs/{id}/cancel`, and owner-scoped `GET /artifacts/{id}` reuse the processing job table, scoped cache identity, restart reconciliation, bounded concurrency/timeout/pixels, and atomic JSON artifact store. No untrusted asset URL/path is accepted. The workspace searches actual SAR metadata for the AOI/date range, lets the user select only returned polarizations, prepares its labeled dated preview, adds a WGS84-bound MapLibre image layer with visibility/opacity, runs the protected job, and exposes measured source records and limitations. A matching assistant question routes to that computed result, not the single-image model. AOI, optical/SAR scene, polarization, date-range and version changes clear result/overlay and abort stale responses.

Synthetic tests (not live product evidence) passed for medians, units, 36-cell AOI denominator, joint coverage, evidence geometry, unsupported question, empty overlap, source validation, protected API start/status/result/artifact/owner denial/cache, map coordinates/opacity/URL rejection, UI success/failure/stale selection. Focused backend **14 passed** (9E + 9D + 9B; an initial sandboxed 9B fixture failed on Windows temp ACL and the approved rerun passed); full backend **253 passed, 1 unconfigured PostgreSQL skip**. Focused frontend **18 passed** (new panel/map and existing scene/assistant); typecheck, lint, format check, production build, backend Ruff and mypy passed. Browser skill could not create a tab because the connector returned `codex/sandbox-state-meta: missing field sandboxPolicy`; no screenshot or real browser interaction is claimed. The earlier 9D real pair reached a SAR COG but failed on GDAL proxy/Schannel access. Production PostgreSQL and verified identity are not configured, so no protected live 9E job or live joint optical/SAR observation is claimed.

Files: `backend/src/satquery/api/schemas/optical_sar.py`, `api/routes/optical_sar.py`, `api/schemas/processing.py`, `db/processing.py`, `api/dependencies.py`, `api/router.py`, `main.py`, `processing/optical_sar_jobs.py`, `processing/optical_sar_pair.py` (provider interface only), `backend/tests/test_optical_sar_phase9e.py`; `frontend/src/lib/optical-sar-client.ts`, `sar-map-layer.ts`, their map test, `components/workspace/optical-sar-panel.tsx` and test, `assistant-panel.tsx`, `map-canvas.tsx`, `scene-container.tsx`, `workspace-shell.tsx`, `app/globals.css`; and API/Phase 9/current-phase/handoff documentation. Exact commands and outputs are in the Phase 9 report.

**Status: 9E IMPLEMENTED / PARTIALLY VERIFIED; stop before 9F.** Exact 9E verification resume: restore trusted INPE COG access, configure durable PostgreSQL and a verified processing principal, rerun a small real optical/SAR job through `/api/v1/optical-sar/jobs`, inspect both source evidence records and authorized artifact; restore the browser bridge and verify discovery → two dated layers → opacity → job/assistant result → stale AOI/scene behavior with screenshots. Do not call the pair registered or fused without independent real tie points. Begin 9F only on separate authorization.

## 9F checkpoint — integration audit and handoff, 2026-09-26

**Outcome: EXECUTED / PARTIALLY VERIFIED; Phase 9 is not complete.** The bounded real São Paulo pair selected Sentinel-2 `S2B_T23KLP_20250115T131403_L2A` (2025-01-15T13:18:55.302Z) and INPE Sentinel-1 RTC `S1A_IW_RTCH_1SDV_20250201_057700_071CAB_B664` (2025-02-01T08:31:10Z). Trusted discovery and resolution worked, but scientific optical B02 read failed with `RASTER_READ_FAILED` before SAR pixels, joint grid, overlap, or aligned display could be inspected. A separate live Sentinel-1 check timed out during INPE discovery. The NISAR CMR path reached the public sample signature request, but ASF TLS timed out; no current PROVISIONAL HDF5 was staged or ingested. These are attempted real checks, **not** completed paired-scene, NISAR, or visual evidence.

Fixed two defects exposed by this audit: provider/raster/quality/grid failures now retain a safe specific job error instead of becoming `ANALYSIS_FAILED`, and stored error codes are normalized to the lowercase processing-job schema. The workspace now rejects a returned SAR preview or optical/SAR result if its full provider/collection/item, acquisition, polarization, request/job ID, or processing version is mismatched. A fake matching item ID from another provider cannot populate the answer panel. Synthetic regression checks cover all-cloud optical AOIs, a 45-day warning, no overlap, invalid SAR terrain/nodata cells, unsupported polarization, missing QA, failed provider reads, owner-scoped artifact denial, and stale selection. These fixtures are **not** claimed as real scene outcomes or model validation. Display-scaled SAR previews, optical thumbnails, and demo answers are not scientific inputs; the answer uses calibrated source arrays and reports separate source evidence only.

Verification: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\verify.ps1` from the repository root **passed**: Ruff/format, strict mypy (97 source files), backend pytest **254 passed / 1 PostgreSQL integration deselected**, frontend Biome/lint/typecheck, Vitest **123 passed**, and production build. The focused panel regression `cd frontend; npm run test -- --run src/components/workspace/optical-sar-panel.test.tsx` passed **3**. Live commands and failure detail are in `docs/PHASE_9_REPORT.md`. The in-app browser bridge failed before tab creation (`codex/sandbox-state-meta: missing field sandboxPolicy`); no screenshot, map placement, or actual browser answer is claimed.

Changed: `backend/src/satquery/processing/optical_sar_jobs.py`, `backend/tests/test_optical_sar_phase9e.py`, `backend/tests/test_optical_sar_pair_phase9d.py`, `frontend/src/components/workspace/optical-sar-panel.tsx` and its test, plus Phase 9/checkpoint/roadmap/README documents. No Phase 10 work. Exact resume: restore trusted Earth Search/INPE scientific raster access, PostgreSQL/PostGIS and a verified principal; rerun the bounded real pair and protected job, inspect source/calibration/mask/grid/coverage/artifact provenance and independent cross-modal tie points; restore browser bridge and verify dated layers/opacity/answer/stale input visually; authenticate Earthdata on the backend host and stage/read an actual PROVISIONAL GCOV HDF5 for the separate NISAR gate. Until these pass, retain `PARTIALLY_VERIFIED`.
