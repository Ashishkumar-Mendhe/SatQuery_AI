# SatQuery AI

SatQuery AI is an evidence-minded vision-language workspace under active development for multimodal remote-sensing image analysis through text queries. It is intended for analysts, researchers, planners, and other users who need to select or upload Earth-observation imagery, ask natural-language questions, and review answers alongside spatial evidence, provenance, uncertainty, limitations, and an execution trace.

The product is one unified professional geospatial workspace—there are no separate “Simple” and “Expert” modes. The workspace combines map/local AOI tools, real catalogue discovery, georeferenced visualization, two-date comparison, acquisition timeline, query/result panels, planned navigation, and inspectable empty states. Scientific analysis, measured evidence, and automated change results remain unavailable.

## Current repository state

Phase 2 now provides the responsive public homepage at `/` and the unified application workspace at `/workspace`. The workspace includes real connection-state handling, responsive navigation/panels, an editable question draft, accessible result tabs and help dialog, truthful empty states, and explicit unavailable-feature explanations. Its automated frontend checks and production build pass. Browser viewport inspection/screenshots could not run because the in-app browser connector failed before opening a tab, so Phase 2 is **PARTIALLY_VERIFIED**. See [the Phase 2 report](docs/PHASE_2_REPORT.md).

Phase 3 adds the MapLibre/OpenFreeMap basemap, Terra Draw rectangle/polygon editing, coordinate navigation, bounds entry, GeoJSON import/export, approximate geographic area, and validated browser draft persistence. It remains **PARTIALLY_VERIFIED**: real browser/WebGL checks and server-owned AOI implementation/verification are pending. Optional place search is unavailable until a suitable provider is configured. See [the Phase 3 report](docs/PHASE_3_REPORT.md).

Phase 5 is **COMPLETE** for its user-authorized imagery-viewer scope. The workspace searches real Earth Search Sentinel-2 metadata, resolves RGB COG assets server-side, serves bounded natural-colour WebMercator tiles, displays them in MapLibre, provides presentation controls, compares two actual dates, navigates loaded acquisitions, and restores validated browser-local viewer state. This is visualization only: it does not provide owned asset intake, scientific co-registration, analysis, change percentages, or confidence. See [the Phase 5 report](docs/PHASE_5_REPORT.md).

Phase 1 separately remains **PARTIALLY_VERIFIED**: real PostgreSQL/PostGIS connectivity, Alembic migration verification, and database-backed readiness HTTP 200 remain unresolved. Later frontend work does not waive those checks. Authentication, server-owned domain resources, uploads, catalogue access, analysis, runtime AI, workers, object storage, and real reports remain unavailable.

## Documentation index

- [PRD.md](PRD.md): users, journeys, product requirements, scope, and acceptance criteria.
- [TRD.md](TRD.md): technical requirements, validation, jobs, integrations, operations, and deployment constraints.
- [ARCHITECTURE.md](ARCHITECTURE.md): current state, target components, flows, trust boundaries, and persistence.
- [FEATURES.md](FEATURES.md): stable feature inventory, dependencies, roadmap mapping, and status.
- [ROADMAP.md](ROADMAP.md): fixed Phase 0–15 roadmap and honest status.
- [CURRENT_PHASE.md](CURRENT_PHASE.md): active checkpoint and exact resume instructions.
- [TECH_STACK.md](TECH_STACK.md): confirmed baseline, proposals, and open technology decisions.
- [API_CONTRACT.md](API_CONTRACT.md): implemented health API plus future resource/job contracts.
- [DATABASE.md](DATABASE.md): implemented connection/migration baseline plus future logical schema.
- [TESTING.md](TESTING.md) and [SECURITY.md](SECURITY.md): verification and security requirements.
- [docs/DECISIONS.md](docs/DECISIONS.md): decision register.
- [docs/PHASE_0_REPORT.md](docs/PHASE_0_REPORT.md): Phase 0 inspection and handoff.
- [docs/PHASE_1_REPORT.md](docs/PHASE_1_REPORT.md): implementation evidence, verification, and remaining gate.
- [docs/PHASE_2_REPORT.md](docs/PHASE_2_REPORT.md): homepage/workspace implementation, interaction inventory, and visual-verification gap.
- [docs/PHASE_3_REPORT.md](docs/PHASE_3_REPORT.md): local map/AOI implementation, geometry/provider contracts, tests and remaining ownership/browser gates.

## Folder responsibilities

- `frontend/`: Next.js homepage and unified workspace presentation plus the runtime-validating health client; no protected data access or authoritative computation.
- `backend/`: FastAPI application/configuration/database foundation; future orchestration, adapters, and worker code stay separate.
- `shared/`: versioned, language-neutral schemas and shared contract resources; no shared secrets or server logic.
- `docs/`: decision records and phase/implementation reports.
- `scripts/`: PowerShell prerequisite and verification workflows.
- `tests/`: future automated tests and clearly identified synthetic fixtures.
- `data/`: conventions for ignored local imagery and generated artifacts; not production storage.

## Local setup (PowerShell)

Prerequisites are Node.js 24.x with npm 11.x, Python 3.13 or 3.14, and Docker with Compose v2. The checked-in `.nvmrc` and `.python-version` record the preferred lines.

```powershell
.\scripts\check-prerequisites.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Review .env and replace the local database password in both matching values.

py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
Push-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.lock
Pop-Location

Push-Location frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm ci
Pop-Location

docker compose up --wait -d db
Push-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location
```

For subsequent starts with the existing dependencies and local environment files, run the frontend and backend in two separate PowerShell terminals. Leave both terminals open while using SatQuery; closing a terminal or pressing `Ctrl+C` stops its server. Do not rerun dependency installation or migrations just to restart the UI/API. The database is required for successful readiness, but not for the homepage, workspace shell, or API liveness.

Frontend terminal:

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\frontend'
npm.cmd run dev
```

Backend terminal:

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\backend'
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000
```

Open the homepage at `http://localhost:3000/` or the workspace at `http://localhost:3000/workspace`. Both render when the API or database is unavailable. API documentation is at `http://127.0.0.1:8000/docs`; liveness and readiness are at `/api/v1/health/live` and `/api/v1/health/ready`. Liveness checks only the application process. Readiness is `200` only when PostgreSQL, PostGIS, and Alembic revision `20260907_0001` are all current; otherwise it returns a safe retryable `503`.

Run all checks that do not require a database with `.\scripts\verify.ps1`. Run the isolated disposable PostGIS test as well with `.\scripts\verify.ps1 -IncludeDatabase`. Stop the persistent development database with `docker compose stop db`; its named volume is retained.

## Map and Area of Interest (AOI) Interaction

### Drawing and Validating an AOI
1. Open the workspace at `http://localhost:3000/workspace`.
2. Navigate the map using standard pan, scroll-zoom, or coordinate jump tools.
3. Draw an area of interest using the **Draw rectangle** or **Draw polygon** toolbar buttons. Click vertices and complete the polygon.
4. Or enter precise bounding coordinates (`[West, South, East, North]` in WGS84 degrees) or import a valid `.geojson` file.
5. The frontend displays immediate geodesic area and bounding box approximations, while asynchronously submitting the geometry to the authoritative backend validator (`POST /api/v1/aoi/validate`).
6. The AOI summary panel displays authoritative validation status badges (`Authoritative Valid`, `Valid (Notice)`, `Invalid AOI`, or `Validating…`), any geometric warnings/errors, and collapsible technical details.
7. Click **Fit AOI** to center the camera on the active AOI, or **Clear AOI** to safely purge the AOI and reset dependent states.

### Running AOI & Map Tests
- **Frontend test suite:**
  ```powershell
  Set-Location -LiteralPath 'frontend'
  npm.cmd run test:run
  ```
- **Backend AOI validation tests:**
  ```powershell
  Set-Location -LiteralPath 'backend'
  ..\.venv\Scripts\python.exe -m pytest tests/test_aoi_validation.py -v
  ```
- **Full repository verification:**
  ```powershell
  powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1
  ```

### Real Satellite Imagery Discovery (Phase 2A)
1. Draw or load a valid AOI on the map workspace.
2. Select a target date range and optional maximum cloud cover threshold in the Imagery Discovery panel.
3. Click **Search scenes** to invoke `POST /api/v1/scenes/search`.
4. The backend searches the Element 84 Earth Search STAC API (`sentinel-2-c1-l2a`), normalizes metadata into typed `SatelliteScene` objects, and returns them to the frontend.
5. In offline development mode or upon upstream STAC failure (with `allow_mock_fallback=True`), the system degrades safely to synthetic `mock-scene-*` fixtures and tags the response with `data_origin: "fallback"` and a `MOCK_DATA_USED` warning.
6. Hover over scene cards to preview footprints on the map, and click a card to select the scene for downstream analysis.

### Satellite Imagery Retrieval & Multitemporal Preview Rendering (Phase 3A)
1. **Single Scene Retrieval:**
   - Select a discovered scene and choose an optical or SAR visualization preset.
   - Click **Retrieve Scene Imagery** to invoke `POST /api/v1/imagery/request`.
   - The backend retrieves the bounded AOI raster window, validates integrity via `RasterValidator`, caches with SHA-256 fingerprint in `AssetStore`, and serves an opaque URL `/api/v1/imagery/assets/{asset_id}`.
   - Adjust layer opacity slider (0%–100%), toggle layer visibility, or click **Fit to Imagery**.
2. **Product Types:**
   - `catalogue_thumbnail`: Low-res card thumbnail from catalogue discovery. Never rendered on the map as analytical evidence.
   - `map_preview`: Bounded contrast-stretched 8-bit RGB display image (PNG/JPEG) for fast map visualization.
   - `analysis_raster`: Lossless Float32 GeoTIFF retaining physical reflectance, exact CRS, affine transform, and band metadata for downstream scientific analysis.
3. **Visualization Presets:**
   - Optical: True Color RGB (`B04, B03, B02`), False Color NIR (`B08, B04, B03`), Vegetation Contrast (`B08, B04, B03`), Water Bodies (`B03, B08, B11`), Urban & Built-Up (`B12, B11, B04`).
   - SAR: Grayscale, VV Polarization, VH Polarization.
4. **Multitemporal Comparison Modes:**
   - In temporal pairing mode, select two validated scenes and click **Compare Imagery**.
   - **Swipe Slider:** Interactive split divider showing before scene on the left and after scene on the right.
   - **Side-by-Side:** Synchronized dual viewports for simultaneous visual inspection.
   - **Opacity Blend:** Single-viewport interactive cross-fade between before and after acquisitions.
   - **Grid Alignment Status:** Inspect the real-time banner (`Grids Aligned`, `Approximately Aligned`, `Requires Alignment`, `Incompatible`) evaluating CRS, pixel resolution delta, and affine grid match.

### Raster Harmonization, Reprojection & Analysis Preparation (Phase 3B)
1. **Preparing a Single Scene Raster:**
   - Retrieve an analysis-grade raster from Phase 3A.
   - Select the target metric CRS (e.g., auto-calculated UTM zone) and resampling method (`bilinear`, `cubic`, `nearest`).
   - Click **Prepare Raster for Analysis** to invoke `POST /api/v1/processing/prepare-raster`.
   - The engine clips to the exact AOI polygon via `geometry_mask`, reprojects to the target metric CRS, and writes a Float32 GeoTIFF and preview PNG.
2. **Preparing a Bi-Temporal Pair:**
   - Retrieve analysis-grade rasters for both Before and After dates.
   - Select the **Target Grid Strategy** (`Highest Resolution`, `Lowest Resolution`, `Reference Before`, `Reference After`, `Configured Resolution`, or `Common Intersection`).
   - Click **Prepare Temporal Pair for Analysis** to invoke `POST /api/v1/processing/prepare-temporal-pair`.
   - The engine snaps the spatial bounding box to integer grid coordinates, resamples both rasters onto a $100\%$ mathematically identical pixel grid `(crs, transform, width, height)`, computes a shared validity mask ($Mask_A \land Mask_B$), and derives explainable quality metrics.
3. **Key Concepts:**
   - **CRS & Metric Grids:** Analysis requires a projected metric CRS (such as UTM) rather than WGS84 degrees to avoid latitude-dependent distortion.
   - **Grid Alignment:** Temporal change detection requires identical pixel origins, pixel sizes, dimensions, and affine transforms.
   - **Readiness States:**
     - `Ready`: Co-registered, shared valid coverage $> 50\%$, quality score $\ge 0.80$, zero blocking issues.
     - `Ready with warnings`: Minor warnings present (e.g. upsampling or $< 50\%$ valid pixels), but analysis is mathematically safe.
     - `Not ready`: Hard blocking issue present (e.g. no shared valid pixels, grid mismatch, missing required bands).
4. **Optical & SAR Limitations:**
   - Optical preparation standardizes reflectance bands without applying spectral indices (NDVI/NDWI deferred to Phase 4A).
   - SAR preparation preserves polarizations and amplitude values without asserting unperformed speckle filtering or radiometric terrain correction.
   - Multimodal inputs are aligned to identical CRS/extents but retained as distinct assets; automated optical/SAR differencing is strictly prohibited.

### Running Preparation & Harmonization Tests
- **Backend Preparation & Harmonizer Tests:**
  ```powershell
  Set-Location -LiteralPath 'backend'
  ..\.venv\Scripts\python.exe -m pytest tests/test_raster_harmonizer.py tests/test_preparation_service.py tests/test_preparation_api.py -v
  ```
- **Frontend Preparation Panel & Hook Tests:**
  ```powershell
  Set-Location -LiteralPath 'frontend'
  npm.cmd run test:run -- src/components/workspace/raster-preparation-panel.test.tsx src/lib/use-raster-preparation.test.tsx src/lib/preparation-client.test.ts src/lib/preparation-contracts.test.ts
  ```

### Troubleshooting Preparation & Grid Alignment
- **Missing CRS Error (`CRS_MISSING`):** Source GeoTIFF lacks coordinate reference system metadata. Re-retrieve analysis asset from provider.
- **No Shared Coverage (`NO_SHARED_VALID_PIXELS`):** Before and After scenes do not overlap or all mutual pixels are clouded/masked. Choose an overlapping scene pair.
- **Pixel Limit Exceeded (`PIXEL_LIMIT_EXCEEDED`):** The combination of requested AOI and target resolution exceeds 16 megapixels (`IMAGERY_MAX_ANALYSIS_RASTER_PIXELS`). Choose a coarser target resolution or smaller AOI.
- **Grid Mismatch (`GRID_MISMATCH`):** Reprojected transforms do not match to $< 10^{-6}$ precision. Resubmit with `common_intersection` strategy.
- **Expired Asset (`ASSET_EXPIRED`):** The input raster expired from `AssetStore` cache. Re-retrieve the Phase 3A imagery asset.

## Pixel-Level Change Detection & Evidence (Phase 4B)

### Change Detection Workflow
1. **Prepare Temporal Pair:** Use the Phase 3B preparation pipeline to generate a strictly co-registered pair on an identical grid `(crs, transform, width, height)`.
2. **Select Change Method:** Choose from authoritative methods registered in the registry (`GET /api/v1/change/methods`):
   - `ndvi_difference`: Normalized Difference Vegetation Index difference ($\text{NDVI}_{\text{after}} - \text{NDVI}_{\text{before}}$) for vegetation vigor gain/loss.
   - `ndwi_difference`: Normalized Difference Water Index difference ($\text{NDWI}_{\text{after}} - \text{NDWI}_{\text{before}}$) for surface water/moisture expansion/contraction.
   - `ndbi_difference`: Normalized Difference Built-up Index difference ($\text{NDBI}_{\text{after}} - \text{NDBI}_{\text{before}}$) for spectral shifts toward built-up/bare surfaces.
   - `absolute_index_difference`: Magnitude screening ($|\Delta|$) for identifying major spectral disruptions regardless of polarity.
   - `multiband_change_magnitude`: Multi-spectral Euclidean distance ($\sqrt{\sum (\Delta \text{Band}_i)^2}$) across mutual surface-reflectance bands `(B02, B03, B04, B08)`.
3. **Configure Thresholds & Noise Filtering:**
   - **Threshold Strategies:** `fixed` cutoffs, `standard_deviation` ($\mu \pm k\cdot\sigma$), `percentile` ($P$-th upper percentile), `otsu` automatic bimodal clustering, or `manual`.
   - **Cluster Size Filtering:** Remove noisy isolated pixels ($< \text{min\_cluster\_size\_pixels}$, default 5 px).
4. **Calculate Change Evidence:**
   - Invoke `POST /api/v1/change/calculate`.
   - Engine verifies spatial grid alignment, computes difference arrays over shared valid pixels, segments into 3 discrete classes ($+1$ gain, $-1$ loss, $0$ stable), extracts vectorized polygon clusters, calculates spatial areas ($\text{km}^2$), and derives traceable evidence records.
5. **Inspect Metrics & Map Overlays:**
   - **Percentage Denominator:** All area percentages strictly divide by `shared_valid_pixels`, never total AOI bounding box pixels.
   - **Map Overlays:** Toggle between Continuous Difference colormap and 3-Class discrete mask (Gain=Green, Loss=Red, Stable=Transparent) with adjustable opacity.
   - **Candidate Regions Table:** Inspect vectorized polygons with area, mean magnitude, and confidence scores.
   - **Scientific Disclaimers:** Clear separation between spectral reflectance measurements and ground-truth land-cover conclusions (e.g. positive NDBI difference is *not* confirmed construction; dry soil and cleared ground show identical responses).

### Running Change Detection Tests
- **Backend Change Detection Tests:**
  ```powershell
  Set-Location -LiteralPath 'backend'
  ..\.venv\Scripts\python.exe -m pytest tests/test_change_registry.py tests/test_change_engine.py tests/test_change_service.py tests/test_change_api.py -v
  ```
- **Frontend Change Detection Tests:**
  ```powershell
  Set-Location -LiteralPath 'frontend'
  npm.cmd run test:run -- src/lib/change-contracts.test.ts src/lib/change-client.test.ts src/lib/use-change-detection.test.tsx src/components/workspace/change-detection-panel.test.tsx
  ```

### Troubleshooting Change Detection
- **Grid Alignment Error (`GRID_ALIGNMENT_FAILED`):** Before and After rasters have unequal CRS, dimensions, or affine transforms ($> 10^{-5}$ delta). Ensure input temporal pair was processed through `POST /api/v1/processing/prepare-temporal-pair`.
- **Zero Shared Valid Area (`ZERO_SHARED_VALID_AREA`):** No mutual cloud-free, unmasked valid pixels exist between the two dates. Select scenes with lower cloud cover or different acquisition dates.
- **Ambiguity Warning (`SPECTRAL_AMBIGUITY`):** Spectral changes (e.g. NDBI gain) cannot confirm semantic changes (new buildings) without ground truth. Review visual imagery alongside difference overlays.

## Multimodal Optical and SAR Evidence Fusion (Phase 4C)

### Multimodal Fusion Workflow
1. **Prepare Optical and SAR Pairs:** Use the Phase 4B pipeline to generate an optical spectral change result (e.g. NDVI, NDWI, NDBI difference), and the Phase 3B pipeline to prepare a co-registered SAR temporal pair (Sentinel-1 GRD).
2. **SAR Backscatter Differencing ($\Delta\text{dB}$):**
   - Calibrated SAR rasters are transformed to decibels ($\text{dB} = 10 \cdot \log_{10}(\text{power})$).
   - SAR difference array $\Delta\text{dB} = 10 \cdot \log_{10}(\text{power}_{\text{after}} / \text{power}_{\text{before}})$ is evaluated against configurable increase/decrease thresholds (default $+2.0\text{ dB} / -2.0\text{ dB}$).
3. **4-Role Temporal Compatibility & Timeline:**
   - Tracks 4 acquisition roles (`optical_before`, `optical_after`, `sar_before`, `sar_after`).
   - Computes before-offset, after-offset, and interval overlap ratio against user-defined temporal tolerance (default $30$ days).
4. **Coverage Partitioning & 5-State Joint Classification:**
   - AOI area is partitioned into: Jointly Observable ($J = O \cap R$), Optical Coverage Only, SAR Coverage Only, and Neither Sensor Available.
   - Within $J$, every pixel is classified into one of 5 states: `both_detect_change`, `optical_response_only`, `sar_response_only`, `neither_above_threshold`, or `uncertain`.
5. **Metric Calculations & Percentage Denominator Discipline:**
   - Exact spatial areas ($\text{km}^2$) calculated using projected metric grids.
   - State percentage statistics strictly use $J = \text{jointly\_observable\_area\_km2}$ as the denominator. If $J = 0$, percentages are `null`.
6. **Vectorized Regions & Map Overlays:**
   - Vector polygons extracted for joint state clusters, sorted by area, with explainable rule descriptions and calibrated confidence scores.
   - 5-color discrete map overlay served via `GET /api/v1/fusion/results/{result_id}/overlay`.
7. **Scientific Grounding Disclaimer:**
   - Co-observed response change is evidence of joint physical sensor excitation, *not* verified physical ground truth (e.g. flood inundation or building demolition).

### Running Multimodal Fusion Tests
- **Backend Fusion Tests:**
  ```powershell
  Set-Location -LiteralPath 'backend'
  ..\.venv\Scripts\python.exe -m pytest tests/test_sar_engine.py tests/test_fusion_engine.py tests/test_fusion_service.py tests/test_fusion_api.py -v
  ```
- **Frontend Fusion Tests:**
  ```powershell
  Set-Location -LiteralPath 'frontend'
  npm.cmd run test:run -- src/lib/fusion-contracts.test.ts src/lib/fusion-client.test.ts src/lib/use-multimodal-fusion.test.tsx src/components/workspace/multimodal-fusion-panel.test.tsx
  ```


## Development workflow

Phase 3 provider configuration is documented in `frontend/.env.example`. The default map style is `https://tiles.openfreemap.org/styles/liberty`; no key is required. Leave source attribution visible. Configure custom public style/name values only for a compatible provider. `NEXT_PUBLIC_*` values are bundled into the browser and must contain no secrets.

Place search is optional and submit-only. Supply an HTTPS, CORS-enabled Nominatim-compatible endpoint whose usage agreement permits browser queries, plus its display name. Public `nominatim.openstreetmap.org` is deliberately rejected: the client does not enforce an application-wide rate limit across tabs/users. No geocoder credentials are installed. Restart the frontend after changing environment configuration. Coordinate navigation, bounds entry, and local AOIs remain independent of geocoding/database availability.

The selected AOI (`satquery.aoi-draft.v1`), catalogue selection (`satquery.scene-selection-draft.v1`), and safe viewer settings (`satquery.viewer-state.v1`) are saved only in this browser. Viewer restoration keeps stable identities, AOI binding, camera, display, comparison, and timeline state but never provider/tile URLs, credentials, expiry state, pixels, or render claims; imagery access is re-resolved. Use **Export** to download `satquery-selected-aoi.geojson` and **Clear AOI** to remove AOI-bound state. Local drafts are not server Saved AOIs or authenticated persistence.

1. Read `AGENTS.md`, `CURRENT_PHASE.md`, and the relevant authoritative documents.
2. Confirm the active phase and decision status before implementation.
3. Make the smallest coherent change, preserving existing work and contract consistency.
4. Run the checks required by `TESTING.md`; record passed, failed, and not-run checks.
5. Update the current phase checkpoint and phase report before handoff.

On Windows, commands are documented for PowerShell without assuming Bash syntax. Local `.env` files are ignored; never commit them or place secrets in `NEXT_PUBLIC_*` values.

