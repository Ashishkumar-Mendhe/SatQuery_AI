# Current phase checkpoint

## Critical Recovery R4 — Imagery Identity, AOI-Specific Assets, Analysis Correctness and Workspace Stabilization — 2026-09-22

- **Scope & Objectives:**
  - Resolved all release-blocking correctness, hydration, asset identity, visual QA grounding, and UI issues:
    1. **Next.js Hydration Mismatch Fixed**: Synchronized SSR default basemap and client-mount preference resolution in `map-canvas.tsx` and `scene-container.tsx`. Eliminated client/server state drift on `aria-pressed` and active CSS classes without resorting to `suppressHydrationWarning`. Zero hydration errors or warnings.
    2. **Immutable Imagery Identity Manifest**: Extended `ImageManifest` in backend schemas with `provider`, `collection`, `platform`, `sensor`, `media_type`, `scene_bbox`, `aoi_id`, `aoi_revision`, `crop_bounds`, `resolution_meters`, `preview_type`. Asset preparation generates deterministic synthetic and real GeoTIFF rasters with scoped IDs (`${asset_id}__${aoi_fingerprint}`).
    3. **Three Distinct Image Products**:
       - *Full-Scene Provider Thumbnail*: Quick-browse 100x100km image, labeled explicitly as `"Full-scene preview (100×100 km)"`.
       - *AOI-Specific Preview*: Bounded display render clipped to exact AOI boundary, labeled `"Selected-area preview"`.
       - *Analysis Asset*: Registered analysis-grade raster bound to the immutable imagery manifest and AOI revision.
    4. **Cache Key Integrity & Isolation Across AOIs**: Evaluated cache keys ensuring different AOIs produce distinct crop bounds, geometry hashes, and asset IDs. Changing AOI invalidates previous crops and prevents stale result reuse.
    5. **Area-Specific Visual Question Answering**: Grounded visual observations trace strictly through the selected AOI crop. Replaced pre-validation error panels with compact inline guidance (`"Select a satellite scene from the discovery panel or timeline to ask a visual question."`) and disabled submission until an asset is selected.
    6. **Clean Acquisition Timeline & Mode-Aware Comparison**: Redesigned comparison labels to explicit `"Before acquisition"` and `"After acquisition"` and mode-aware timeline assignment buttons without raw oversized clutter.
    7. **Satellite Hybrid Label Typography & Halos**: Clean sans-serif hierarchy, dark 2px halos, zoom-dependent visibility, and zero glyph request failures.
- **Verification Evidence:**
  - **Full Repo Verification**: `powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1` **PASSED** with exit code 0 (`Non-database repository verification passed.`).
  - **Backend**: Ruff format/lint clean, strict Mypy (141 files) clean, Pytest (302 passed, 0 failed, 1 deselected) including dedicated `test_r4_imagery_identity.py`.
  - **Frontend**: Biome format/lint clean (0 errors, 0 warnings across 169 files), TypeScript typecheck (`tsc --noEmit`) clean, Vitest (303 passed across 69 test files, 100%), Next.js 16.3.4 production build clean.
  - **Live Browser CDP Walkthrough**: Verified via headless Chromium/CDP (`verify_r4.mjs`):
    - `Hydration errors detected: 0`.
    - Captured 8 PNG screenshots at 1920x1080 and 1366x768 in artifact directory:
      - `r4_01_workspace_prerequisite_guidance_1920x1080.png`
      - `r4_02_discovery_layout_aoi_a_1920x1080.png`
      - `r4_03_scene_selected_aoi_a_preview_1920x1080.png`
      - `r4_04_acquisition_timeline_clean_1920x1080.png`
      - `r4_05_answer_evidence_aoi_a_1920x1080.png`
      - `r4_06_aoi_b_preview_distinct_1920x1080.png`
      - `r4_07_answer_evidence_aoi_b_1920x1080.png`
      - `r4_08_workspace_responsive_1366x768.png`
- **Stop Boundary & Next Action**: Recovery R4 complete. Stop after R4. Rerun Phase 7A validation. Do not proceed to Phase 7B first.

## UI Correction R3 — Map-First Layout, Compact Controls and Hybrid Map Labels — 2026-09-22

- **Scope & Objectives:**
  - Refined the SatQuery workspace shell into a dense, map-first geospatial interface:
    1. **Map-First Grid**: Implemented responsive CSS grid (`14.5rem 1fr 22.5rem`), compact topbar (`3.75rem`), compact sidebar (`2.35rem` items, ~232px expanded, ~68px collapsed), and responsive collapse/hide behavior with single-call map canvas resize (`map.resize()`).
    2. **Compact Step Toolbar & Draw AOI**: Single-row workflow banner (`height: ~48px`) with mode-aware dynamic step chips (4 for single-image, 5 for bi-temporal) and a compact primary button (`height: 2.15rem`, ~36px) replacing the oversized CTA.
    3. **Compact Floating AOI Summary Card**: Compact card (~18.5rem, ~295px) with collapsible details, status chip, area formatted in km², bounding box coordinates, and compact "Edit", "Fit AOI", and "Remove" action buttons.
    4. **Hierarchical Place Labels & Hybrid Satellite View**:
       - Default (OpenFreeMap Liberty) and Terrain (OpenTopoMap) render multi-level place labels and contours.
       - Satellite basemap implements a true **Hybrid View** combining Esri World Imagery raster tiles with an Esri Reference transparent vector labels and administrative boundaries overlay (`satellite-hybrid-labels-layer`).
       - Added a compact "Labels: On/Off" toggle button adjacent to the basemap switcher.
       - Dynamically synchronized and restored AOI and analysis vector layers over basemap style changes without duplicate layers or canvas flashes.
    5. **Correct Dynamic Attribution & Status**: Active basemap text and attribution accurately reflect active source (OpenTopoMap on Terrain, Esri on Satellite Hybrid, OpenFreeMap on Default).
    6. **Slimmer, Denser Assistant Panel**: Compact tabs, bounded composer textarea (`5.5rem–8.5rem`), bounded decorative empty state icons (`.result-empty-icon` / `.selected-assets-notice svg` max 1.15rem), eliminating oversized SVG overflow.
- **Verification Evidence:**
  - **Backend**: Pytest 298 passed (0 failed, 1 skipped for remote PostGIS), Ruff format/lint clean, strict Mypy clean.
  - **Frontend**: Biome format/lint clean, strict TypeScript (`tsc --noEmit`) clean, Vitest 303 passed across 69 test files (100%), Next.js 16.3.4 production build clean.
  - **Live Browser Verification & Measurements**: Verified at 1920×1080 and 1366×768 via headless Chromium/CDP:
    - Expanded sidebar: 232px; collapsed sidebar: 68px.
    - Header: 60px; workflow banner: 48px.
    - Map stage: dominant viewport (~1108×708px at 1920×1080; ~541×443px at 1366×768).
    - Assistant: 360px; empty state icons: 36×36px with 18×18px inner SVGs.
    - Horizontal scrollbar: None (`hasHorizontalScroll: false`).
- **Next Action**: Rerun Phase 7A validation before Phase 7B.

## Feature Correction R2 — Basemap Modes, Analysis-Type Selection and AOI-Only Processing — 2026-09-21

- **Scope & Objectives:**
  - Resolved the three core product gaps following Critical Recovery R1:
    1. **Basemap Switcher**: Implemented three mutually exclusive basemap styles on the map canvas: **Default** (OpenFreeMap Liberty vector), **Terrain** (OpenTopoMap topographic relief), and **Satellite** (ESRI World Imagery visual context). Preserved AOI, analysis overlays, footprints, and center/zoom across style updates without triggering re-analysis.
    2. **Analysis-Type Selection (Mode-First Workflow)**: Mode selection is the real first step in the workspace workflow, offering three distinct first-class choices: **Single Image Analysis** (1 scene VQA/grounding), **Change Detection** (bi-temporal pair ΔNDVI/ΔNDWI), and **Optical + SAR Analysis** (Sentinel-2 + Sentinel-1 multimodal fusion).
    3. **Strict AOI-Only Processing**: Verified that raster masking via `geometry_mask(..., invert=True)` strictly sets non-AOI pixels to nodata, and downstream metric calculations isolate the AOI domain so outer pixels cannot influence change or spectral percentages.
    4. **Cloud-Cover Scoping**: Labeled clearly as *"Maximum scene cloud cover — optical only"* with contextual hint; disabled automatically with explanatory message when SAR sensor is selected.
- **Verification Evidence:**
  - **Backend**: Pytest 298 passed (0 failed, 1 skipped for remote PostGIS), Ruff format/lint clean, strict Mypy (141 source files) clean.
  - **Frontend**: Biome format clean, Biome lint clean, strict TypeScript (`tsc --noEmit`) clean, Vitest 303 passed across 69 test files, Next.js 16.3.4 production build clean.
  - **Repository Verification**: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed with `Non-database repository verification passed.`
  - **Live Browser Verification**: Verified at 1920×1080 and 1366×768 with browser subagent recording and screenshots.
- **Next Action**: Rerun Phase 7A validation before Phase 7B.

## Recovery R1 — Database Readiness, Map Canvas, Workspace UI and Feature Connectivity — 2026-09-21

- **Scope & Objectives:**
  - Resolved all critical workspace blockers identified in Recovery R1:
    1. **Database & Readiness Persistence**: Added `aiosqlite` local development engine alongside production PostgreSQL/PostGIS. Auto-initializes persistence tables (`workspaces`, `saved_aois`, `saved_scenes`, `analysis_results`, `reports`) on lifespan startup. Configured `DATABASE_URL=sqlite+aiosqlite:///./data/satquery.db`. `/api/v1/health/ready` now reports HTTP 200 OK (`Backend ready`).
    2. **Map Canvas & Tile Rendering**: OpenFreeMap Liberty base layer renders cleanly with zoom controls, scale bar, attribution, and "Map ready" badge without blank/dark void.
    3. **Workspace CSS Grid & Layout**: Fixed `.workspace-main-column` positioning (`grid-column: 2; grid-row: 2`) and nested `.restored-draft-banner` to eliminate grid column displacement and squeezed typography.
    4. **Assistant Operations Controls**: Styled `.visual-operation-selector` with segmented `.op-pill` buttons for "Describe", "Locate Feature", and "Compare Pair".
    5. **Navigation & Feature Connectivity**: Implemented live navigation and dedicated responsive pages for `/history`, `/saved-aois`, and `/reports` connected to backend persistence. Marked `Missions` clearly with `Phase 12` roadmap badge.
- **Verification Evidence:**
  - **Backend**: Pytest 296 passed (0 failed, 1 skipped for remote PostGIS), Ruff format/lint clean, strict Mypy (140 source files) clean.
  - **Frontend**: Biome format clean, Biome lint clean, strict TypeScript (`tsc --noEmit`) clean, Vitest 297 passed across 68 test files, Next.js 16.3.4 production build clean.
  - **Repository Verification**: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` passed with `Non-database repository verification passed.`
  - **Live Browser Verification**: Verified at 1920×1080 and 1366×768 with browser subagent recording and screenshots:
    - `Backend ready` service status badge visible.
    - `REAL DATA` data origin badge visible.
    - MapLibre canvas rendering OpenFreeMap base tiles with `Map ready`.
    - Operation pills separate and interactive.
    - Full navigation working across Workspace, History, Saved AOIs, Reports, and Missions.

## Phase 7B — SIH Demo Rehearsal, Contingency Pack and Final Handoff — 2026-09-21

- Executed end-to-end rehearsal automation, targeted blocker fixes, presenter runbooks, judge technical Q&A, and candidate freeze for the Smart India Hackathon (SIH) live demonstration:
  - Automated Demo Rehearsal Suite (`backend/scripts/rehearse_demo.py`):
    - Executed 6 consecutive end-to-end rehearsals (3 live Primary passes using Element 84 Earth Search STAC and 3 offline Fallback passes) achieving a **100% pass rate**.
    - Target AOI: Bengaluru Urban / Bellandur Green Corridor (9.64 km² WGS84 geodesic area).
    - Pipeline stages verified: Geodesic AOI validation $\to$ Multi-temporal Sentinel-2 L2A discovery $\to$ 10m GSD UTM grid co-registration (95,630 valid pixels) $\to$ NDVI bi-directional differencing $\to$ Grounded question answering with server-side claim validation $\to$ ReportLab Platypus PDF & JSON export with SHA-256 integrity hash.
    - Average Primary pass latency: **2.28s**; average Fallback pass latency: **0.83s**.
  - Targeted Rehearsal Blocker Fixes:
    - Fixed band description propagation in `backend/src/satquery/services/raster_harmonizer.py` (lines 679–693) so output rasters retain optical band identities (`B02, B03, B04, B08, B11, B12`).
    - Fixed vector region coordinate reprojection in `backend/src/satquery/services/change_engine.py` (line 368) ensuring polygon geometries transform from projected metric CRS (`EPSG:32643`) to WGS84 (`EPSG:4326`) GeoJSON.
  - Demonstration Documentation Package:
    - Authored [`docs/DEMO_SCRIPT.md`](file:///c:/Desktop/SatQuery%20-AG/docs/DEMO_SCRIPT.md): Timed 5–7 min live demo script, 3 min compressed script, 90 sec emergency path, and judge interruption safe points.
    - Authored [`docs/DEMO_RUNBOOK.md`](file:///c:/Desktop/SatQuery%20-AG/docs/DEMO_RUNBOOK.md): PowerShell startup commands, preflight checklists (T-60, T-15, T-0), and symptom-based fast recovery guide with 20-second on-stage rule.
    - Authored [`docs/JUDGE_QA.md`](file:///c:/Desktop/SatQuery%20-AG/docs/JUDGE_QA.md): 18 comprehensive, evidence-based technical answers covering remote sensing physics, optical vs SAR, grounding, hallucination mitigation, and data provenance.
    - Authored [`docs/FINAL_DEMO_HANDOFF.md`](file:///c:/Desktop/SatQuery%20-AG/docs/FINAL_DEMO_HANDOFF.md): Candidate freeze reference, **GO** verdict, telemetry logs, startup commands, and roadmap status.
- Verification Results:
  - Automated Rehearsals: 6/6 passed (100%), summary logged to `backend/tmp/rehearsal_output/rehearsal_summary.json`.
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (297 passed across 68 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with `Non-database repository verification passed.`
- Sprint Closure:
  - Phase 7B officially concludes the **SIH Demo-Readiness Sprint**. Zero prompts remain in this sprint.
  - Final Readiness Verdict: **GO (SIH DEMONSTRATION READY)**.
  - The broader 16-phase SatQuery product roadmap (Phases 0–15 in `ROADMAP.md`) remains preserved. Post-hackathon development will resume from Phase 8.

- Executed comprehensive release-candidate validation, contract hardening, error recovery audits, and automated test verification across the entire SatQuery AI application:
  - Report Contract & UI Hardening (`frontend/src/components/workspace/report-export-dialog.tsx`):
    - Added type guard `hasFormat(fmt: ReportFormat)` resolving the union type between array formats and record dictionary formats in `ReportResponse`.
    - Tested format toggling, single-format enforcement, generation stage spinner, and PDF/JSON downloads (4/4 tests passed).
  - Scientific Accounting & Epistemic Segregation Verification:
    - Verified strict percentage calculations: Gain/Loss/Stable/Uncertain percentages divide by `shared_valid_pixels` ($V$).
    - Verified coverage calculations: Coverage percentage divides by total AOI area ($A$).
    - Verified visual bounding boxes (`observation_source: "model_prediction"`, `semantic_status: "unverified"`) remain segregated and are strictly NOT counted towards measured physical change totals.
    - Verified natural language summaries describe spectral/backscatter differences without unverified causal claims.
  - Transparent Data Origin Verification:
    - Verified synthetic and mock scenes are prominently labeled with `data_origin: "mock"` / `data_origin: "fallback"` and `is_mock_data: true`.
    - Verified mock origin banners appear in both PDF Platypus reports and JSON snapshots.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (297 passed across 68 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with `Non-database repository verification passed.`
- Stop boundary: Phase 7A complete. Stopped before Phase 7B (Demo Rehearsal and Handoff). Awaiting user confirmation.

## Phase 6B — Full Workflow Integration and Blocker Fixes — 2026-09-21

- Implemented full reactive multi-step workflow integration across all analysis modes and resolved routine blocker issues:
  - Unified Workflow State Machine (`frontend/src/lib/workspace-workflow.ts`):
    - Added comprehensive pipeline stages (`awaiting_aoi` -> `awaiting_date_range` -> `ready_for_pairing` / `ready_for_scene_discovery` -> `ready_for_raster_prep` -> `ready_for_analysis` -> `analysis_completed` / `ready_for_export`).
    - Added `WorkflowContext` derivation incorporating `mode`, `selectedAoi`, `dateRange`, `beforeWindow`, `afterWindow`, `hasSelectedScene`, `hasSelectedPair`, `isRasterPrepared`, `hasAnalysisResult`, `hasAnswer`, and `questionDraft`.
    - Added unit test suite in `frontend/src/lib/workspace-workflow.test.ts` verifying all single-scene and temporal pairing transitions (9/9 passed).
  - Workflow Readiness Banner (`frontend/src/components/workspace/workflow-readiness-banner.tsx`):
    - Displays dynamic readiness pills (Mode, AOI, Dates, Scenes, Analysis, Dossier) reflecting current pipeline state.
    - Added actionable trigger buttons (`Discover Imagery`, `Harmonise & Prepare Rasters`, `Run Analysis`, `Ask Assistant`, `Export Report Dossier`) wired through `onTriggerAction`.
    - Tested in `frontend/src/components/workspace/workflow-readiness-banner.test.tsx` (2/2 passed).
  - Scene Container Integration (`frontend/src/components/workspace/scene-container.tsx`):
    - Destructured workflow notification callbacks (`onChangeResult`, `onFusionResult`, `onRasterPrepared`, `onPairSelected`).
    - Properly bound `effectiveBeforeScene?.id` and `effectiveAfterScene?.id` across `useRasterPreparation` and `RasterPreparationPanel`.
    - Aligned `MultimodalFusionPanel` callback props (`onSelectOpticalResultId`, `onSelectSarBeforeAssetId`, `onSelectSarAfterAssetId`, `onSelectRegionId`).
  - Workspace Shell Reactive Orchestration (`frontend/src/components/workspace/workspace-shell.tsx`):
    - Maintained state for `changeResult`, `fusionResult`, `isRasterPrepared`, and `hasSelectedPair`.
    - Bound `useQueryAssistant` with `activeChangeResultId` and `activeFusionResultId` for seamless context transfer.
    - Synchronized active analysis results directly into `exportContext` for dossier report export.
  - Report Service & Client Fixes (`backend/src/satquery/services/report_service.py`, `frontend/src/lib/use-report-export.ts`):
    - Fixed `ReportStatus.PARTIALLY_COMPLETED` typing in backend service.
    - Resolved upstream snapshots cleanly from `change_service` and `fusion_service` cache with proper `AOIGeometry`.
    - Added `buildClientReportSnapshot` in `use-report-export.ts` conforming strictly to `reportSnapshotSchema`.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (297 passed across 68 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with `Non-database repository verification passed.`
- Stop boundary: Phase 6B complete. Stopped before Phase 7A (Final Validation and Stability). Awaiting user confirmation.

## Phase 6A — Evidence-Based Reports and Export — 2026-09-21

- Implemented professional, immutable evidence-based report snapshot capture, ReportLab PDF rendering, portable JSON export, and frontend export UI:
  - Backend Dependencies & Schemas (`backend/src/satquery/api/schemas/reports.py`):
    - Added `reportlab==5.0.1` and `pillow==12.3.0` to `backend/pyproject.toml` and installed into active environments.
    - Strict Pydantic models: `REPORT_SCHEMA_VERSION = "1.0.0"`, `ReportStatus`, `ReportSection`, `ReportFigureType`, `ReportFigure`, `ReportSnapshot`, `ReportRequest`, `ReportFormatStatus`, `ReportResponse`.
    - Denominator and accounting discipline: $V = \text{shared\_valid\_pixels}$ for class percentages, $A = \text{total\_aoi\_area}$ for coverage.
    - Strict epistemic segregation: computed physical measurements, model predictions (visual bounding boxes segregated and never added to measured change totals), and AI natural language interpretation.
  - Snapshot Capture & Assembly Engine (`backend/src/satquery/services/report_builder.py`):
    - `ReportSnapshotBuilder`: Resolves AOI, scene metadata, change/spectral/fusion results, AI answers, and visual model observations into an immutable, versioned snapshot.
    - Generates and attaches registered figure assets with captions, CRS labels, orientation markers, and legends.
    - Computes deterministic SHA-256 integrity hash over canonical snapshot JSON payload.
  - Print-Ready PDF Renderer (`backend/src/satquery/services/pdf_renderer.py`):
    - `SatQueryPdfRenderer`: Built using ReportLab Platypus document architecture with custom two-pass `NumberedCanvas` ("Page X of Y").
    - Professional SatQuery branding: Dark slate headers, teal accents, structured executive summary, acquisition scenes table, quantitative findings table with explicit denominators, visual evidence card figures, verified AI claims, visual model predictions clearly disclaimed, confidence quality breakdown, warnings callouts, and provenance methods register.
    - Prominent origin banner for mock / fallback data: `[ SYNTHETIC DEMO DATA — NOT A MEASURED SATELLITE OBSERVATION ]`.
    - Safe escaping of user text and XSS mitigation via HTML entity escaping.
  - Report Lifecycle Service & API (`backend/src/satquery/services/report_service.py`, `backend/src/satquery/api/routes/reports.py`):
    - `ReportService`: In-memory and disk persistence for report snapshots, PDF binary generation, JSON export streaming, and cache retention management.
    - Endpoints:
      - `POST /api/v1/reports/request`: Build snapshot and generate requested formats (PDF, JSON, or both).
      - `POST /api/v1/reports/snapshot-export`: Direct export from client-provided or cached snapshot.
      - `GET /api/v1/reports/{report_id}`: Poll generation status, format statuses, and download URLs.
      - `GET /api/v1/reports/{report_id}/snapshot`: Retrieve raw immutable JSON snapshot.
      - `GET /api/v1/reports/{report_id}/download/{format_str}`: Download PDF or JSON file with appropriate Content-Type and Content-Disposition headers.
  - Frontend Contracts, Client & Hook (`frontend/src/lib/`):
    - `report-contracts.ts`: Zod schemas matching backend: `reportSnapshotSchema`, `reportFigureSchema`, `reportFormatStatusSchema`, `reportGenerationRequestSchema`, `reportResponseSchema`.
    - `report-client.ts`: Typed API client with `requestReportGeneration`, `exportSnapshotDirect`, `getReportStatus`, `getReportSnapshot`, `getReportDownloadUrl`, and `downloadReportFile`.
    - `use-report-export.ts`: React hook managing dialog state, format toggles, section selection, generation progress, and file download triggers.
  - Frontend Export UI & Workspace Integration (`frontend/src/components/workspace/`):
    - `ReportExportDialog`: Accessible modal dialog with AOI/scene context card, format toggles (PDF / JSON), editable report title, dossier section selection checkboxes, progress spinner, completed download buttons with SHA-256 digest, and error retry alert.
    - `ResultsTabs`: Integrated "Export Dossier" action button into assistant tabs header.
    - `WorkspaceShell`: Integrated `useReportExport` hook and connected `ReportExportDialog`.
    - `globals.css`: Rich styling for export container, format toggles, context cards, checksum badges, and download buttons.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 integration deselected).
  - Backend Known-Answer Fixture Test: Verified 2.00 km² AOI, 1.00 km² valid comparison area (50% coverage), 0.20 km² gain (20%), 0.10 km² loss (10%), 0.65 km² stable (65%), 0.05 km² uncertain (5%), 1.00 km² excluded (50%), and 0.03 km² model box strictly NOT counted in change totals.
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (296 passed across 68 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with `Non-database repository verification passed.`
- Stop boundary: Phase 6A complete. Stopped before Phase 6B (Full Workflow Integration and Blocker Fixes). Awaiting user confirmation.

- Implemented Visual Question Answering (VQA) from actual satellite imagery pixels and mathematically verified spatial grounding:
  - Backend Schemas (`backend/src/satquery/api/schemas/visual.py`):
    - Strict Pydantic models: `ImageInputRole`, `ObservationSource`, `CoordinateStatus`, `SemanticStatus`, `MapGroundingStatus`, `VisualOperation`, `ImageManifest`, `GroundedVisualRegion`, `VisualObservation`, `VisualQueryRequest`, `VisualQueryResponse`, `VisualCapabilitiesResponse`.
    - Canonical bounding box definition: normalized continuous pixel-edge coordinates $[xmin, ymin, xmax, ymax]$ on $[0.0, 1.0]$.
  - Spatial Grounding Engine (`backend/src/satquery/services/spatial_grounding.py`):
    - Exact 6-step inverse transformation pipeline: denormalize to submitted pixels $\to$ undo recorded padding (detecting padding-only boxes) $\to$ undo resizing $\to$ undo cropping $\to$ source raster affine transformation $\to$ WGS84 (EPSG:4326) GeoJSON reprojection with $[lon, lat]$ RFC 7946 ordering.
    - Provider coordinate adapter converting Gemini $[ymin, xmin, ymax, xmax]$ on scale $0..1000$ to canonical $[xmin, ymin, xmax, ymax]$ on $0..1$.
    - Spatial overlap and evidence association engine (`compute_evidence_overlap`) linking visual model observations with computed change/spectral/fusion regions.
    - Non-georeferenced imagery discipline: sets `image_only_no_georeference` without guessing coordinates when CRS is missing.
    - Verified against known-answer geometry fixture: $[W=503000, E=505000, N=2398500, S=2397500]$.
  - AI Provider Visual Capabilities (`backend/src/satquery/providers/ai/`):
    - `AIProvider` abstract protocol updated with `generate_visual_qa(request: VisualQARequest) -> VisualQAResponse`.
    - `MockAIProvider`: Deterministic offline visual Q&A engine returning structured visual observations with canonical boxes for single-image and bi-temporal comparison scenarios.
    - `GeminiAIProviderAdapter`: Implemented live multimodal Gemini vision Q&A with base64 image encoding and structured schema extraction.
    - `AIProviderRegistry`: Controlled dispatch and transparent fallback handling.
  - Image Preparation & Query Orchestration (`backend/src/satquery/services/`):
    - `VisualImagePreparer`: Resolves stored raster assets, generates high-fidelity visual PNGs, computes SHA-256 digests, and builds immutable `ImageManifest` records.
    - `VisualQueryService`: Orchestrates image preparation, AI provider invocation, spatial grounding, evidence overlap calculation, and execution tracing.
  - FastAPI Endpoints (`backend/src/satquery/api/routes/query.py`):
    - `POST /api/v1/query/visual`: Processes single-image and bi-temporal visual queries with exact spatial grounding.
    - `GET /api/v1/query/visual/capabilities`: Lists supported operations, providers, and grounding statuses.
    - `GET /api/v1/query/manifests/{manifest_id}`: Retrieves immutable image manifest record.
  - Frontend Contracts, Client & Hook (`frontend/src/lib/`):
    - `visual-contracts.ts`: Zod schema parity for visual requests, manifests, observations, grounded regions, and responses.
    - `visual-client.ts`: Typed API client with `askVisualQuery`, `getVisualCapabilities`, `getImageManifest`.
    - `use-visual-qa.ts`: React hook managing visual Q&A mode, active manifests, highlighted observation synchronization, and map overlays.
  - Enhanced Workspace UI (`frontend/src/components/workspace/`):
    - `AssistantPanel`: Added VQA Mode toggle, visual operation selector (`Describe`, `Locate Feature`, `Compare Pair`), selected image counter, and grounded visual observation cards with confidence badges.
    - `ResultsTabs`: Enhanced Answer and Evidence tabs to display Visual Prediction cards with canonical boxes, grounding badges, and "Highlight on Map" triggers.
    - `WorkspaceShell`: Integrated `useVisualQA` hook with scene selection and map overlay layers.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (132 source files) clean, Pytest (287 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (287 passed across 66 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 5B complete. Stopped before Phase 6 (Confidence, Warnings & Report Generation). Awaiting user confirmation.

## Phase 5A — Query Routing and Evidence-Grounded AI Answers — 2026-09-20

- Implemented Natural-Language Query Routing and Evidence-Grounded Answering Subsystem:
  - Backend Schemas (`backend/src/satquery/api/schemas/query.py`):
    - Strict Pydantic models: `QueryIntent` (9 typed intents), `SufficiencyStatus` (6 states), `GenerationMode` (`llm_explanation`, `deterministic_summary`, `mock_demo`), `ClaimKind` (`measurement`, `interpretation`, `background`, `limitation`), `ClaimValidationStatus` (`valid`, `repaired`, `invalid_omitted`), `WorkspaceContextSnapshot`, `QueryPlan`, `AnswerClaim`, `SuggestedNextAction`, `ProcessingTraceStep`, `QueryRequest`, `QueryAnswer`, `QueryCapabilitiesResponse`.
  - Intent Routing Engine (`backend/src/satquery/services/query_router.py`):
    - Regex and rule-based deterministic classifier mapping natural language questions to 9 intents (`evidence_summary`, `spectral_summary`, `change_summary`, `multimodal_summary`, `locate_evidence`, `explain_quality`, `needs_processing`, `clarification_required`, `unsupported`).
    - Produces `QueryPlan` recording intent, required evidence, missing inputs, approved operations, and routing reason.
  - Multi-Modality Evidence Retriever (`backend/src/satquery/services/evidence_retriever.py`):
    - Gathers `EvidenceItem`, `Finding`, `ChangeMetrics`, `JointStateMetrics`, and spectral measurements from active change, spectral, and fusion results.
    - Performs strict lineage deduplication and extracts spatial regions and warning factors into an `EvidenceBundle`.
  - Input Sufficiency Evaluator (`backend/src/satquery/services/sufficiency_checker.py`):
    - Evaluates AOI existence, scene selection, and computation status against query plan requirements.
    - Emits actionable `SuggestedNextAction` targets (`prepare_scenes`, `calculate_change`, `calculate_fusion`, `draw_aoi`) without triggering expensive raster computations synchronously.
  - Claim Validator & Grounding Enforcer (`backend/src/satquery/services/claim_validator.py`):
    - Rejects causal hallucinations: NDBI increase mapped strictly to "Built-up-related spectral increase" (never "confirmed construction"); NDVI decrease to "Vegetation-related spectral decrease" (never "confirmed deforestation"); SAR delta to "backscatter response change" (never "confirmed flooding").
    - Validates numeric measurements, percentages, and denominators ($V = \text{shared\_valid\_pixels}$ or $J = \text{jointly\_observable\_area\_km2}$) against authorized evidence.
    - Resolves spatial region IDs to current geometry and formats deterministic measurement cards.
  - Query Service Orchestrator (`backend/src/satquery/services/query_service.py`):
    - Orchestrates router -> retriever -> sufficiency -> AI provider / summary fallback -> claim validator -> trace recorder.
    - Seamlessly degrades to `deterministic_summary` mode when AI provider is missing/unavailable/disabled, maintaining full claim validation and map references.
  - FastAPI Endpoints (`backend/src/satquery/api/routes/query.py`):
    - `GET /api/v1/query/capabilities`: Supported intents, generation modes, sufficiency statuses, and max question length.
    - `POST /api/v1/query/ask`: Full natural-language query processing endpoint with trace instrumentation.
- Frontend Contract, State & UI Integration:
  - Zod Schemas (`frontend/src/lib/query-contracts.ts`): Complete schema parity with backend Pydantic models.
  - Client API (`frontend/src/lib/query-client.ts`): `getQueryCapabilities` and `askQuery` with `AbortSignal` cancellation and structured `QueryClientError`.
  - Custom Hook `useQueryAssistant` (`frontend/src/lib/use-query-assistant.ts`):
    - Context snapshot construction, fingerprinting, query submission, cancellation, error recovery, and interactive highlight state (`highlightedRegionId`, `highlightedEvidenceId`).
    - Stale context detection: invalidates pending answers when AOI, scenes, or result IDs change.
  - Enhanced Workspace Panels:
    - `AssistantPanel` (`frontend/src/components/workspace/assistant-panel.tsx`): Natural-language input with 500-char limit counter, loading stage indicator, stale context warning banner, retry button, and quick suggestion chips.
    - `ResultsTabs` (`frontend/src/components/workspace/results-tabs.tsx`):
      - **Answer Tab**: Status badge, generation mode tag ("Evidence summary — AI explanation unavailable" for fallback), plain summary prose, verified measurement cards with explicit denominators, analytical limitations callout, and suggested next actions.
      - **Evidence Tab**: Evidence items with source dates and methods, candidate spatial regions with "Highlight on Map" triggers, and data quality warnings.
      - **Activity Tab**: Real step-by-step query execution timeline with stage durations and AI provider metadata.
    - `WorkspaceShell` (`frontend/src/components/workspace/workspace-shell.tsx`): Integrated `useQueryAssistant` hook with AOI contract conversion.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (126 source files) clean, Pytest (276 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (275 passed across 63 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 5A complete. Stopped before Phase 5B (Image VQA and Verified Spatial Grounding). Awaiting user confirmation.

## Phase 4C — Multimodal Optical and SAR Evidence Fusion — 2026-09-20

- Implemented Explainable Multimodal Evidence Fusion Engine:
  - SAR Radiometric Differencing Engine (`backend/src/satquery/services/sar_engine.py`):
    - Linear power to decibel conversion: $\text{dB} = 10 \cdot \log_{10}(\text{power})$, $\Delta\text{dB} = 10 \cdot \log_{10}(\text{power}_{\text{after}} / \text{power}_{\text{before}})$ without artificial epsilon clamping.
    - Zero/negative linear power masking, direct decibel subtraction, unit validation, polarization mismatch rejection.
    - Generates Float32 $\Delta\text{dB}$ GeoTIFF with nodata `-9999.0` and discrete 3-class RGBA preview PNG overlays.
  - Core Multimodal Fusion & Classification Engine (`backend/src/satquery/services/fusion_engine.py`):
    - 4-Role Temporal Compatibility Assessment (`optical_before`, `optical_after`, `sar_before`, `sar_after`), computing before/after offsets and interval overlap ratios against temporal tolerance (default 30 days).
    - AOI Coverage Partitioning: strictly partitions AOI into Jointly Observable ($J = O \cap R$), Optical Coverage Only, SAR Coverage Only, and Neither Sensor Available.
    - 5-State Joint Observation Classification within $J$: `both_detect_change` (amber), `optical_response_only` (emerald), `sar_response_only` (blue), `neither_above_threshold` (slate), `uncertain` (purple).
    - Scientific Area & Percentage Denominator Discipline: All joint state percentages strictly use $J = \text{jointly\_observable\_area\_km2}$ as the denominator. Percentages are `null` when $J = 0$.
    - Vectorized GeoJSON Candidate Regions extracted using `rasterio.features.shapes`, sorted by area descending, with calibrated confidence and explainable rule descriptions.
    - Discrete 5-color RGBA preview PNG generation.
  - Service Orchestration & Asset Management (`backend/src/satquery/services/fusion_service.py`):
    - `FusionService` coordinates optical change results and prepared SAR pairs, persists discrete PNG overlay preview assets in `AssetStore` (`ast-fusprv-*`), and handles partial single-modality requests.
  - FastAPI Endpoints (`backend/src/satquery/api/routes/fusion.py`):
    - `GET /api/v1/fusion/capabilities`: List supported rules, sensors, and default parameter configs.
    - `POST /api/v1/fusion/analyze`: Executes multimodal fusion across optical change and SAR pairs.
    - `GET /api/v1/fusion/results/{result_id}`: Retrieves complete fusion result envelope.
    - `GET /api/v1/fusion/results/{result_id}/overlay`: Streams 5-color discrete preview PNG overlay.
- Frontend Contract, State & UI Integration:
  - Zod Schemas (`frontend/src/lib/fusion-contracts.ts`): Strict schema parity with backend Pydantic models.
  - Client API (`frontend/src/lib/fusion-client.ts`): Typed request dispatching with `AbortSignal` cancellation and structured `FusionClientError`.
  - Custom Hook `useMultimodalFusion` (`frontend/src/lib/use-multimodal-fusion.ts`): Reactive state manager for fusion inputs, tolerances, thresholds, and result caching.
  - UI Component `MultimodalFusionPanel` (`frontend/src/components/workspace/multimodal-fusion-panel.tsx`):
    - Observation stream inputs and 4-role timeline badges.
    - Coverage partition cards (Total AOI breakdown).
    - Joint observation state table with strict $J$ denominator percentages.
    - Scientific Grounding Disclaimer banner.
    - Candidate fused regions list and map overlay opacity controls.
- Verification Results:
  - Backend: Pytest (260 passed, 0 failed, 1 integration test skipped).
  - Frontend: Vitest (12/12 fusion tests passed).
- Stop boundary: Phase 4C complete. Stopped before Phase 5A. Awaiting user confirmation.

## Phase 4B — Pixel-Level Change Detection and Change Evidence — 2026-09-20

- Implemented Scientifically Defensible Pixel-Level Change Detection Engine:
  - Authoritative Change Method Registry (`backend/src/satquery/services/change_registry.py`):
    - Specifications and formulas for 5 distinct change methods: `ndvi_difference`, `ndwi_difference`, `ndbi_difference`, `absolute_index_difference`, and `multiband_change_magnitude`.
    - Sensor support, expected ranges, color ramps (`RdYlGn`, `RdBu_r`, `YlOrRd`, `viridis`, `magma`), limitations, and default threshold configurations.
  - Core Pixel Differencing & Classification Engine (`backend/src/satquery/services/change_engine.py`):
    - `validate_grid_alignment`: Enforces rigid spatial equality across before/after rasters: matching CRS, width, height, and affine transform ($<10^{-5}$ delta).
    - `compute_difference_array`: Computes bi-temporal difference arrays over shared valid pixels with NaN/Inf sanitization.
    - `apply_thresholds_and_classify`: Segments difference into 3 discrete classes ($+1$ gain, $-1$ loss, $0$ stable) across strategies (`fixed`, `standard_deviation`, `percentile`, `otsu`, `manual`).
    - `compute_change_metrics`: Strictly divides by `shared_valid_pixels` as the percentage denominator, computing spatial area in metric $\text{km}^2$.
    - `vectorize_change_regions`: Extracts vectorized GeoJSON polygon clusters using `rasterio.features.shapes`, filters noise clusters ($< \text{min\_cluster\_size\_pixels}$), simplifies geometry, sorts by area descending, and bounds to `max_regions`.
    - `generate_scientific_geotiff`: Emits Float32 difference GeoTIFF with nodata `-9999.0`.
    - `generate_continuous_preview_png` & `generate_classified_preview_png`: Emits RGBA PNG overlays.
    - `calculate_confidence`: Multi-factor confidence score ($0.0 - 1.0$) with explainable breakdown.
  - Service Orchestration & Asset Management (`backend/src/satquery/services/change_service.py`):
    - Integrates with `AssetStore`, creating derived assets for difference GeoTIFF (`ast-chg-*`), continuous preview (`ast-chgprv-*`), and discrete mask preview (`ast-chgcls-*`).
  - FastAPI Endpoints (`backend/src/satquery/api/routes/change.py`):
    - `GET /api/v1/change/methods`: Lists all registered change detection methods.
    - `POST /api/v1/change/calculate`: Executes change calculation on co-registered pair.
    - `GET /api/v1/change/results/{result_id}`: Retrieves completed result envelope.
    - `GET /api/v1/change/results/{result_id}/overlay`: Streams continuous or discrete (`?classified=true`) PNG.
- Frontend Contract, State & UI Integration:
  - Zod Schemas (`frontend/src/lib/change-contracts.ts`): `changeDetectionMethodSchema`, `thresholdStrategySchema`, `changeThresholdConfigSchema`, `changePixelCountsSchema`, `changeMetricsSchema`, `changeRegionSchema`, `changeDetectionRequestSchema`, `changeDetectionResultSchema`, `changeMethodsResponseSchema`.
  - Client API (`frontend/src/lib/change-client.ts`): `listChangeMethods`, `calculateChangeDetection`, `getChangeResult`, `getChangeOverlayUrl` with `ChangeClientError`.
  - Custom Hook `useChangeDetection` (`frontend/src/lib/use-change-detection.ts`): Manages method selection, threshold tweaking, overlay mode, opacity, and automatic invalidation upon pair changes.
  - UI Component `ChangeDetectionPanel` (`frontend/src/components/workspace/change-detection-panel.tsx`):
    - Method selector with description, formula, and sensor support.
    - Threshold strategy picker and numerical parameter inputs.
    - Quantitative metrics cards (Gain, Loss, Stable, Shared Valid area).
    - Scientific Disclaimer banner (explicit separation of spectral difference from ground truth/construction claims).
    - Candidate change regions table with area, magnitude, confidence, and zoom selection.
    - Overlay display toggles (Continuous Δ vs 3-Class Mask vs Hidden) and opacity slider.
    - Provenance & traceability metadata card.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (105 source files) clean, Pytest (245 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (251 passed across 56 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 4B complete. Stopped before Phase 5 (Map Overlays & Grounded Evidence). Awaiting user confirmation.


- Implemented Scientifically Defensible Raster Harmonization & Preparation Engine:
  - Coordinate & Metric Projection Module (`backend/src/satquery/services/raster_harmonizer.py`):
    - Deterministic centroid-based UTM zone calculation (`calculate_utm_epsg`) mapping WGS84 coordinates to EPSG:32601–32660 (North) / EPSG:32701–32760 (South).
    - Preserves existing metric projected CRS where valid; warns on geographic CRS or multi-zone AOI extents.
  - AOI Polygon Masking & Resampling Pipeline (`reproject_and_harmonize_single`):
    - Clips raster to exact AOI polygon using `rasterio.features.geometry_mask`, setting exterior pixels to NaN/nodata.
    - Reprojects and resamples using semantic-aware algorithms: `bilinear` / `cubic` for continuous reflectance, `average` for continuous downsampling, `nearest` for masks and categorical data.
    - Generates lossless Float32 GeoTIFF analysis rasters and RGBA PNG previews.
  - Strict Bi-Temporal Grid Co-Registration (`harmonize_and_align_temporal_pair`):
    - Calculates common spatial extent across mutual AOI and scene footprints.
    - Snaps bounding coordinates to integer grid intervals ($\lfloor \text{minX}/\text{res} \rfloor \cdot \text{res}$).
    - Enforces $100\%$ rigid mathematical equivalence on both rasters: matching CRS, width, height, resolution, and affine transform ($<10^{-6}$ delta).
    - Computes bi-temporal shared validity mask ($Mask_{\text{shared}} = Mask_A \land Mask_B$) and reports valid/invalid pixel counts.
  - Explainable Quality & Readiness Assessment (`RasterQualityMetrics`):
    - Evaluates metadata completeness, valid coverage, AOI coverage, and grid alignment score.
    - Emits truthful readiness classifications (`ready`, `ready_with_warnings`, `not_ready`) with hard blocking overrides (`NO_SHARED_VALID_PIXELS`, `GRID_MISMATCH`, `CORRUPT_SOURCE`, `MIXED_DATA_ORIGIN`).
  - Storage & Service Orchestration (`backend/src/satquery/services/preparation_service.py`):
    - `PreparationService` integrates with `AssetStore`, generating derived assets (`ast-prep-*` GeoTIFF and `ast-prepprv-*` PNG) with opaque UUIDs and TTL. Source imagery assets remain strictly immutable.
  - API Routes (`backend/src/satquery/api/routes/preparation.py`):
    - `POST /api/v1/processing/prepare-raster`: Prepares single-scene analysis raster.
    - `POST /api/v1/processing/prepare-temporal-pair`: Prepares co-registered bi-temporal pair.
- Frontend Contract, State & UI Integration:
  - Zod Runtime Contracts (`frontend/src/lib/preparation-contracts.ts`): `rasterPreparationModeSchema`, `targetGridStrategySchema`, `resamplingMethodSchema`, `preparationStatusSchema`, `rasterQualityMetricsSchema`, `preparedRasterAssetSchema`, `preparedTemporalPairSchema`.
  - Client Functions (`frontend/src/lib/preparation-client.ts`): Typed request dispatching with `AbortSignal` cancellation and structured `PreparationClientError`.
  - Custom Hook `useRasterPreparation` (`frontend/src/lib/use-raster-preparation.ts`): Reactive state manager with automatic input fingerprint invalidation upon AOI or scene changes.
  - UI Panel `RasterPreparationPanel` (`frontend/src/components/workspace/raster-preparation-panel.tsx`):
    - Configuration controls for CRS, target resolution, and grid strategies.
    - Progress stages (`validating_inputs`, `clipping`, `reprojecting`, `aligning`, `ready`).
    - Readiness badges, co-registered grid metrics, warnings banner, and disclaimer notice ("Images are spatially prepared for analysis. No change detection has been performed yet").
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (87 source files) clean, Pytest (209 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (226 passed across 52 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 3B complete. Stopped before Phase 4A (Spectral Indices and Evidence Generation). Awaiting user confirmation.

## Phase 3A — Analysis-Grade Imagery Retrieval and Preview Rendering — 2026-09-20

- Implemented Secure Imagery Retrieval & Preview Rendering Pipeline:
  - Bounded AOI Raster Processing Engine (`backend/src/satquery/services/imagery_service.py`):
    - Windowed raster extraction preventing full-scene downloads.
    - Optical band mappings (`true_color`, `false_color`, `vegetation`, `water`, `urban`) with 2%–98% percentile linear contrast stretching.
    - SAR polarization mappings (`sar_grayscale`, `sar_vv`, `sar_vh`).
    - Lossless Float32 GeoTIFF analysis raster generation and 8-bit PNG/JPEG map preview generation.
    - Spatial Grid Alignment Analyzer evaluating bi-temporal CRS, pixel resolution delta (<1%), dimensions (<2px), and affine transform match.
  - Strict Raster Integrity & Security Validator (`backend/src/satquery/services/raster_validator.py`):
    - Magic signature verification for TIFF, PNG, JPEG. Rejection of HTML/JSON error responses.
    - Rasterio dataset validation: finite bounds, CRS existence, non-degenerate Affine transform, AOI overlap check, and safe sample decodability.
  - Bounded Disk Asset Storage with Opaque IDs (`backend/src/satquery/services/asset_store.py`):
    - Opaque UUIDv4 identifiers (`ast-*`); absolute filesystem paths never exposed.
    - Path traversal prevention, atomic file creation, SHA-256 fingerprint deduplication, and TTL expiration cleanup.
  - API Endpoints (`backend/src/satquery/api/routes/imagery.py`):
    - `POST /api/v1/imagery/request`: Single-scene bounded preview/analysis raster retrieval.
    - `POST /api/v1/imagery/temporal-request`: Bi-temporal imagery pair retrieval.
    - `GET /api/v1/imagery/assets/{asset_id}`: Binary streaming with strict MIME type and cache headers.
    - `GET /api/v1/imagery/assets/{asset_id}/metadata`: JSON endpoint for geospatial and processing metadata.
- Frontend Contract, State & Map Rendering:
  - Zod Runtime Contracts (`frontend/src/lib/imagery-contracts.ts`): `imageryProductTypeSchema`, `visualizationPresetSchema`, `imageryFormatSchema`, `rasterMetadataSchema`, `imageryAssetSchema`, `temporalImageryResponseSchema`, `alignmentStatusSchema`.
  - Client Functions (`frontend/src/lib/imagery-client.ts`): Typed request dispatching with `AbortSignal` cancellation.
  - Hook & Map Layer Manager (`frontend/src/lib/use-imagery.ts`, `frontend/src/lib/imagery-map-layer.ts`):
    - Reactive state management with automatic invalidation upon AOI or scene change.
    - MapLibre GL `image` source integration with 4-corner coordinates `[[west, north], [east, north], [east, south], [west, south]]`, opacity sliders, and visibility toggles.
  - Interactive Panels:
    - `ImageryPreviewPanel` (`frontend/src/components/workspace/imagery-preview-panel.tsx`): Single-scene preview, preset selection, opacity slider, technical metadata inspector.
    - `TemporalComparisonPanel` (`frontend/src/components/workspace/temporal-comparison-panel.tsx`): Bi-temporal viewer with Swipe divider, Side-by-Side view, Opacity blend, and grid alignment status banner.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (79 source files) clean, Pytest (194 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (214 passed across 48 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 3A complete. Stopped before Phase 3B (Raster Harmonization, Reprojection and Analysis Preparation). Awaiting user confirmation.

## Phase 2B — Before/After Scene Selection and Temporal Pairing — 2026-09-20

- Implemented End-to-End Multitemporal Pairing Subsystem:
  - Pure-Python Sutherland-Hodgman Polygon Clipping Engine (`backend/src/satquery/services/temporal_pairing.py`):
    - Exact convex polygon intersection and mutual AOI coverage calculation without C-extension dependencies.
    - Returns `SpatialOverlapMetrics` including `before_aoi_coverage_percent`, `after_aoi_coverage_percent`, `mutual_aoi_coverage_percent`, `scene_overlap_percent`, and shared bounding box.
  - Authoritative Multi-Factor Compatibility Evaluation Engine:
    - 5 Factor scoring: `collection_platform` (0.25), `spatial_coverage` (0.25), `quality_atmosphere` (0.20), `temporal_suitability` (0.15), `spectral_resolution` (0.15).
    - Status classification: `compatible` (score >= 0.80), `compatible_with_warnings` (0.50 - 0.79), `incompatible` (< 0.50 or hard blocking issue).
    - Strict blocking overrides: `SAME_SCENE_SELECTED`, `TEMPORAL_ORDER_REVERSED`, `MIXED_DATA_ORIGIN`, `CROSS_SENSOR_PAIR_REQUIRES_MULTIMODAL_PIPELINE`, `NO_AOI_COVERAGE`, `POLARIZATION_MISMATCH`, `REQUIRED_BANDS_MISSING`.
  - Automatic Optimal Pair Recommendation Engine:
    - Evaluates cartesian product of candidate scenes across before/after windows and ranks top candidate pair.
  - Backend API Endpoints (`backend/src/satquery/api/routes/scenes.py`):
    - `POST /api/v1/scenes/temporal-search`: Queries catalogue for both periods and returns candidates plus recommended pair.
    - `POST /api/v1/scenes/validate-pair`: Authoritatively validates compatibility of candidate pair.
- Frontend Contract, State & UI Integration:
  - Zod Schemas & Types (`frontend/src/lib/temporal-contracts.ts`): `temporalWindowSchema`, `temporalSearchRequestSchema`, `temporalSceneCandidatesSchema`, `temporalPairValidationRequestSchema`, `temporalPairValidationResultSchema`, `pairingPreferencesSchema`.
  - Client Functions (`frontend/src/lib/temporal-client.ts`): `searchTemporalCandidates` and `validateTemporalPair` with abort signals and typed error handling.
  - Custom Hook `useTemporalPairing` (`frontend/src/lib/use-temporal-pairing.ts`): Manages candidate discovery, recommendation staging, auto-validation, and context invalidation.
  - Dual Date & Temporal UI Components:
    - `WorkflowDateFilterPanel` (`frontend/src/components/workspace/workflow-date-filter-panel.tsx`) with quick presets (30d, 90d, 180d, 1y).
    - `TemporalPairingPanel` (`frontend/src/components/workspace/temporal-pairing-panel.tsx`) with 2-period candidate columns, recommendation action banner, and compatibility factor breakdown.
    - Synchronized with `WorkspaceShell` and `SceneContainer` for footprint layer rendering.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (70 source files) clean, Pytest (172 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (181 passed across 43 test suites), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 2B complete. Stopped before Phase 3A (Pixel Download & Preprocessing Pipeline). Awaiting user confirmation.

## Phase 2A — Real Satellite Catalog Discovery Integration — 2026-09-18

- Implemented Real Satellite Imagery Discovery Subsystem:
  - Connected backend to Element 84 Earth Search STAC API v1 (`https://earth-search.aws.element84.com/v1/`) targeting `sentinel-2-c1-l2a` and `sentinel-2-l2a` collections.
  - Implemented `RealSatelliteProviderAdapter` (`backend/src/satquery/providers/satellite/real_adapter.py`):
    - STAC query mapping: AOI polygon/bbox converted to GeoJSON geometry / bounding box coordinates.
    - UTC temporal interval filtering (`datetime`).
    - Cloud cover ceiling filtering (`eo:cloud_cover <= max_cloud_cover`).
    - Normalization of STAC Items into canonical `SatelliteScene` contract with asset resolution for RGB/NIR/SWIR bands.
    - Platform resolution (`Sentinel-2A`, `Sentinel-2B`, `Sentinel-2C`) and safe thumbnail/preview URL validation against AWS S3 buckets (`e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com`).
    - In-memory bounded LRU cache (128 items, 300s TTL) for repeat query optimization.
  - Implemented `POST /api/v1/scenes/search` endpoint (`backend/src/satquery/api/routes/scenes.py`) registered in `satquery.api.router`.
  - Transparent Mock Fallback: When primary real STAC queries encounter network timeouts or errors with `allow_mock_fallback=True`, requests degrade seamlessly to synthetic `mock-scene-*` fixtures with `data_origin: "fallback"` and `MOCK_DATA_USED` warning.
- Frontend Contract & Discovery Integration:
  - Created typed Zod runtime schemas in `frontend/src/lib/scene-search-contracts.ts` (`sceneSearchRequestSchema`, `sceneSearchResponseSchema`).
  - Implemented API client `searchScenes` (`frontend/src/lib/scene-search-client.ts`) with `AbortSignal` cancellation and structured API error handling.
  - Interactive Discovery UI in `frontend/src/components/workspace/imagery-discovery-panel.tsx` with live cloud-cover filter slider, date range picker, result cards, and map footprint synchronizer.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (48 source files) clean, Pytest (151 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (165 passed across 39 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 2A complete. Stopped before Phase 2B. Awaiting user confirmation.

## Phase 1A — Existing Map Baseline & AOI Interaction Validation — 2026-09-18

- Validated Map Baseline & Drawing Infrastructure:
  - MapLibre GL JS `6.9.0` with OpenFreeMap Liberty vector basemap style (`NEXT_PUBLIC_BASEMAP_STYLE_URL` / `NEXT_PUBLIC_BASEMAP_NAME`).
  - Required legal attribution (`© OpenFreeMap © OpenStreetMap contributors`) verified and preserved.
  - Safe default center (`[77.5946, 12.9716]`, Bengaluru) and zoom levels.
  - Terra Draw integration (`@watergis/maplibre-gl-terradraw` `1.16.0`) with reactive polygon/rectangle drawing, vertex editing, bounds input, and GeoJSON import/export.
  - Single canonical `SelectedAoi` state as single source of truth in workspace.
- Implemented Authoritative Backend Validation Service (`POST /api/v1/aoi/validate`):
  - Created backend schemas in `backend/src/satquery/api/schemas/aoi.py`: `AoiValidationRequest`, `AoiValidationResponse`, `AoiValidationIssue`, `AoiValidationCode`, `AoiIssueSeverity`.
  - Implemented geometric validation engine in `backend/src/satquery/services/aoi_validator.py`:
    - Strict GeoJSON `[longitude, latitude]` (EPSG:4326) coordinate checking.
    - Longitude range $[-180, 180]$, latitude range $[-90, 90]$, finite numeric values.
    - Ring closure verification and minimum vertex count (>= 4 positions).
    - Segment self-intersection detection via linear segment crossing algorithms.
    - Geodesic polygon area on spherical WGS84 ($R = 6371.0088\text{ km}$).
    - Area threshold validation ($0.0001\text{ km}^2 \le \text{Area} \le \text{MAX\_AOI\_SQUARE\_KM}$).
    - RFC 7946 counter-clockwise exterior ring orientation normalization.
    - Bounding box extraction in standard `[minLon, minLat, maxLon, maxLat]` order.
  - Implemented API route in `backend/src/satquery/api/routes/aoi.py` registered under `/aoi` prefix in `satquery.api.router`.
- Implemented Frontend Validation Client & UI Integration:
  - Created Zod validation contracts in `frontend/src/lib/aoi-validation-contracts.ts`.
  - Implemented async client `validateAoiWithBackend` in `frontend/src/lib/aoi-validation-client.ts` with AbortSignal cancellation and graceful offline fallback.
  - Added helper converter `selectedAoiToContract` in `frontend/src/lib/aoi.ts`.
  - Enhanced workspace AOI summary panel in `frontend/src/components/workspace/scene-container.tsx` with live status badges (`Validating…`, `Authoritative Valid`, `Valid (Notice)`, `Invalid AOI`, `Editing`), structured error/warning notices, and collapsible technical details.
  - Added styling in `frontend/src/app/globals.css` for validation badges and collapsible geometry metadata.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy clean across 64 source files, Pytest (142 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (126 passed across 29 test files), Next.js 16.3.4 production build clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Phase 1A complete. Stopped before Phase 1B. Awaiting user confirmation.

## Phase 0C — Configuration, Provider Interfaces & Safe Mock Boundary — 2026-09-18

- Implemented centralized backend settings system (`backend/src/satquery/core/config.py`) using `pydantic-settings`:
  - Validated configurations for application environment, debug flag, log level, API prefix, CORS origins, PostgreSQL connection, satellite providers (Earth Search, Sentinel Hub, Copernicus Dataspace, Planetary Computer, Mock), satellite timeouts/retries, AI/VLM providers (Gemini, OpenAI, Mock, Disabled), processing parameters, and mock fallback policies.
  - Enforced strict production safety: `debug=True` rejected in production; loopback origins (`localhost`, `127.0.0.1`, `::1`) forbidden in production CORS; credentials (`SecretStr`) redacted in all summaries, logs, and public outputs.
- Established clean Provider Interfaces & Schemas (`backend/src/satquery/api/schemas/providers.py`):
  - Enums: `ProviderMode` (`mock`, `real`, `disabled`), `ProviderStatus` (`ready`, `not_configured`, `unavailable`, `degraded`, `disabled`, `unknown`), `DataOrigin` (`real`, `mock`, `fallback`, `uploaded`, `cached`), `ProviderCapability`.
  - Models: `ProviderInfo`, `ProviderExecutionMetadata`, `ProvidersStatusResponse`.
- Implemented Satellite Provider Subsystem (`backend/src/satquery/providers/satellite/`):
  - `SatelliteProvider` protocol with lifecycle and search methods.
  - `MockSatelliteProvider` returning 6 deterministic synthetic scenes (`mock-scene-*`), bounding box / date / cloud / sensor filtering, and test-only failure simulation (`timeout`, `unavailable`, `invalid_response`, `empty`).
  - `RealSatelliteProviderAdapter` for Earth Search / Sentinel-2 STAC with safe `is_configured()` checks and structured `ProviderNotConfiguredError`.
  - `SatelliteProviderRegistry` factory routing requests and applying transparent fallback when real mode fails with `allow_mock_fallback=True` (`data_origin=DataOrigin.FALLBACK`, `fallback_used=True`, `WarningCode.MOCK_DATA_USED`).
- Implemented AI / VLM Provider Subsystem (`backend/src/satquery/providers/ai/`):
  - `AIProvider` protocol with grounded analysis methods.
  - `MockAIProvider` enforcing evidence grounding rules: returns `INSUFFICIENT_EVIDENCE` warning with conservative confidence ($0.10$) if evidence is empty; generates findings referencing `evidence_ids` when evidence is provided.
  - `GeminiAIProviderAdapter` validating `GEMINI_API_KEY` configuration.
  - `AIProviderRegistry` factory managing AI provider dispatch.
- Added Read-Only Provider Status Endpoint (`backend/src/satquery/api/routes/providers.py`):
  - `GET /api/v1/providers/status` returning non-sensitive provider health, active modes, and capabilities.
- Implemented Frontend Config & Data Origin Mappings (`frontend/src/lib/`):
  - `frontend/src/lib/config.ts`: Validated public runtime configuration (`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_ENVIRONMENT`, `NEXT_PUBLIC_DEMO_MODE`, `NEXT_PUBLIC_CONTRACT_VERSION`).
  - `frontend/src/lib/provider-contracts.ts`: Zod schema parity for provider status and data origin contracts.
  - `frontend/src/lib/data-origin.ts`: Visual tokens and badges for `REAL DATA`, `DEMO DATA`, `FALLBACK DATA`, `UPLOADED DATA`, and `CACHED DATA`.
- Verification Results:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (59 source files clean), Pytest (134 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (119 passed across 27 test files), Next.js production build (`next build`) clean.
  - Full repo verification: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with repository verification passed.
- Stop boundary: Stopped before Phase 1A. Awaiting user confirmation.


- Implemented production-quality, type-safe bidirectional schemas across backend (Pydantic v2) and frontend (TypeScript + Zod):
  - Backend modules: `backend/src/satquery/api/schemas/analysis.py`, `backend/src/satquery/api/schemas/reports.py`, exported through `backend/src/satquery/api/schemas/__init__.py`.
  - Frontend modules: `frontend/src/lib/analysis-contracts.ts`, `frontend/src/lib/report-contracts.ts`.
- Enforced complete contract parity:
  - 12 Synchronized Enums: `AnalysisMode`, `AnalysisJobStatus`, `ImageryProvider`, `SensorType`, `GeometryType`, `OverlayType`, `EvidenceType`, `WarningSeverity`, `FindingSeverity`, `ReportFormat`, `APIErrorCode`, `WarningCode`.
  - 23 Core Schema Models: `AOIGeometry`, `DateRange`, `CloudCoverFilter`, `SatelliteScene`, `SceneSelection`, `AnalysisOptions`, `ClientContext`, `AnalysisRequest`, `APIFieldError`, `APIError`, `AnalysisJob`, `SpectralMeasurement`, `OverlayStyle`, `OverlayFeature`, `AnalysisWarning`, `SpectralIndexResult`, `ChangeMetrics`, `ChangeDetectionResult`, `EvidenceProvenance`, `EvidenceItem`, `Finding`, `ConfidenceFactor`, `ConfidenceBreakdown`, `ProcessingMetadata`, `AnalysisResponse`, `ReportRequest`, `ReportResponse`.
  - Mathematical & Domain Validation: Polygon ring closure check, WGS84 coordinate boundaries (`[-180, 180]`, `[-90, 90]`), bounding box order `[minX, minY, maxX, maxY]`, non-blank question with minimum 3 characters, chronological timestamp ordering, mode-aware conditional requirements (change detection requiring two distinct scenes or date range), vector/raster overlay requirements, evidence linkage for all findings, uniform `0.0 - 1.0` confidence scale.
- Verification passed:
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (44 source files clean), Pytest (116 passed, 0 failed, 1 integration deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (109 passed across 24 test files), Next.js production build (`next build`) clean.
  - End-to-end repository script: `powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1` completed with non-database repository verification passed.
- Stop boundary: Stopped before Phase 0C. Awaiting user confirmation.

## Two-date comparison maintenance — 2026-09-15

- Completed only the existing Phase 5 real-scene comparison surface. Scene A and Scene B remain distinct and chronologically normalized (earlier A, later B); their exact acquisition dates, item IDs, platforms, and cloud percentages are visible. Swipe is the default, Split renders two synchronized maps, and Blink automatically alternates the retained maps with pause/resume and manual-next controls.
- Fixed two confirmed rendering defects: comparison MapLibre canvases had collapsed to 0 px height because the library CSS won an equal-specificity cascade, and adding the AOI before imagery temporarily made the style unavailable to the existing imagery-layer synchronizer. The canvases now fill their frame; real imagery is mounted first and the AOI is then placed above it. No thumbnail, synthetic imagery, analysis, NDVI, database, or backend behavior was added.
- Live isolated Chrome/WebGL verification used real Earth Search Sentinel-2 scenes `S2B_T43PGQ_20251223T051848_L2A` (A) and `S2C_T43PGQ_20251228T052411_L2A` (B). Both reached “Imagery rendered from georeferenced raster tiles.” Swipe moved from 50% to 68%; Split showed both scenes; Blink automatically changed A to B; a trusted drag on A moved both maps and AOI outlines by the same screen displacement. Reassigning A to `S2B_T43PGQ_20251213T052354_L2A` updated the reopened comparison while B remained unchanged. Provider tile failures after the sync drag produced the existing truthful partial-warning states.
- Final focused frontend comparison/workspace tests passed 20/20, typecheck passed, focused Biome passed, the optimized build passed, and backend imagery-tile tests passed 10/10. One concurrent workspace test initially exceeded its result wait; it passed alone and the complete 20-test set then passed. The managed browser was unavailable because `sandboxPolicy` was absent, so isolated hidden Chrome supplied the live evidence. Stop before Phase 6.

## Selected-scene rendering maintenance — 2026-09-15

- Result-card selection now immediately uses the existing stable-identity imagery tile-set flow; a separate initial “Open in viewer” click is no longer required. Existing cancellation, failure, retry, expiry, layer replacement, display controls, and analysis boundaries remain unchanged.
- Live Chrome/WebGL verification used the Bengaluru bounding-box AOI and real Earth Search Sentinel-2 scenes. `S2C_T43PGQ_20251228T052411_L2A` rendered from georeferenced raster tiles, then `S2B_T43PGQ_20251223T051848_L2A` replaced it and reached ready. The AOI remained visible above imagery, the basemap remained beneath it, and Fit scene changed the scale from 5 km to 20 km.
- Frontend focused tests passed 17/17, typecheck passed, and the optimized build passed. Backend catalogue/imagery tests passed 26/26. No backend, database, map-analysis, comparison, or AI feature work was added; stop before Phase 6.

## Active phase

**Phase 5 — Original agreed title unavailable**

**User-authorized working scope:** Imagery viewer contracts, asset resolution, tiles, viewer, controls, comparison, timeline/state, and verification through tasks 5A–5H.

**Status: COMPLETE — TASKS 5A–5H COMPLETE; STOP BEFORE PHASE 6**

The original Phase 5 title remains unavailable and was not invented. The user-authorized working scope and tasks 5A–5H are in [the Phase 5 tracker](docs/PHASE_5_TASKS.md). Only task 5H was authorized in this session. All required Phase 5 viewer implementation and integration gates passed. The independent Phase 1 PostgreSQL/PostGIS migration/readiness gate remains blocked because Docker is unavailable; it is explicit and unwaived.

## Phase 3 AOI-selection verification — 2026-09-15

- A user-authorized maintenance task exercised the existing MapLibre/Terra Draw AOI flow and fixed only its imagery-search enablement gate. Rectangle and polygon controls, retained highlighted geometry, clear, RFC 7946 Polygon generation, Turf geodesic area, derived bounds, browser-draft persistence, both AOI summaries, and exact-AOI catalogue submission were already implemented and passed live verification.
- The one confirmed defect was that `Search imagery` remained enabled with no AOI and relied only on submit-time validation. It is now disabled until `selectedAoi` exists, while the request builder retains its defensive null guard.
- Live isolated Chrome drew and retained a rectangle and a four-vertex polygon, showed km² and five-decimal bounds in the AREA OF INTEREST card and imagery panel, cleared the rectangle completely, and submitted the exact polygon coordinates to the existing catalogue endpoint. The endpoint returned HTTP 200 with six real scene metadata results; no scene was opened and no imagery layer or AI behavior was added. No page exception or console error was observed.
- Final frontend typecheck passed, four focused files passed 35/35 tests, and the optimized build passed. The initial sandboxed Vitest start failed with Windows `spawn EPERM`; the permission-scoped run and final rerun passed. The in-app browser remained unavailable because `sandboxPolicy` was absent; isolated hidden Chrome supplied the browser evidence. No backend, database, environment, dependency, or phase scope changed. Stop before Phase 6.
- Follow-up visual acceptance added a compact, always-visible `AOI drawing controls` toolbar over the map with `Draw rectangle`, `Draw polygon`, and `Clear AOI`; the existing scroll-panel draw/edit controls remain available, while its duplicate clear action was removed. Both entry points share the same Terra Draw commands. Live verification confirmed the toolbar was visible without scrolling, rectangle geometry survived zoom/pan unchanged, top/AOI/imagery summaries remained synchronized, clear removed geometry and disabled search, and polygon search returned HTTP 200. Final typecheck, 36/36 focused tests, Biome, and optimized build passed. One new assertion initially failed because three intentional `No area selected` labels exist; the corrected scoped-count assertion passed. No imagery layer was opened.

## Phase 3 basemap repair verification — 2026-09-15

- A user-authorized maintenance task fixed only the existing MapLibre/OpenFreeMap basemap. The OpenFreeMap Liberty style URL and its tile, sprite, and glyph resources returned HTTP 200; no provider, backend, database, imagery, or analysis architecture changed.
- Root cause: MapLibre's `.maplibregl-map` rule won an equal-specificity cascade against `.map-canvas`, changing the intended absolute map surface to relative positioning. The map element collapsed to 0 px high although the parent stage was 859 px high and MapLibre reported ready.
- `frontend/src/app/globals.css` now uses the scoped `.map-stage > .map-canvas` selector with explicit full width/height. `MapCanvas` also marks the lifecycle ready on `style.load`, preventing the fully rendered Liberty map from later showing a false 20-second timeout while optional resources continue loading.
- Live isolated Chrome verification at `http://localhost:3000/workspace` showed the real interactive Liberty map with India centered, water, terrain/context, boundaries, roads/place labels, and correct attribution. The surface measured 972×859 px. Zoom changed the scale from 500 km to 300 km; pan changed the center from 78.96290/20.59370 to 75.85550/22.32878. The lifecycle remained `Map ready`; there were no page exceptions or console errors.
- Frontend typecheck passed, focused SceneContainer tests passed 8/8, and the optimized build passed. The in-app browser remained unavailable because its session omitted `sandboxPolicy`; isolated hidden Chrome supplied the browser evidence. Phase 5 remains complete; no new phase was started. Stop before Phase 6.

## Local startup verification — 2026-09-15

- Reused the existing SatQuery Next.js development server on `http://localhost:3000` and started the current FastAPI factory on IPv6 loopback `http://[::1]:8000`. An unrelated project already owns `127.0.0.1:8000`, so SatQuery was not allowed to replace it; `localhost` resolves to the SatQuery IPv6 listener for the configured frontend API URL.
- The repository `.venv` is present at `C:\Desktop\SatQuery\.venv` with Python 3.14.7, declared backend imports, and `pip check` passing. Frontend `node_modules`, its lock marker, Next binary, and every direct declared package/version are present. No dependency installation was needed.
- Direct backend checks passed: liveness HTTP 200 with the versioned SatQuery body, API docs/OpenAPI HTTP 200 with the expected title and versioned health paths, and frontend-origin CORS preflight HTTP 200. Readiness returned the expected retryable HTTP 503 for `database` with no-store and Retry-After because Docker/PostgreSQL/PostGIS remain unavailable.
- An isolated headless Chrome fallback rendered `/` and `/workspace` at HTTP 200. The workspace displayed `Database unavailable`, fetched liveness and real Earth Search collection metadata successfully through `http://localhost:8000/api/v1`, and retained the truthful analysis-unavailable state. Browser-observed 503 resource entries were the expected readiness probes; no page exception or console error was observed. Screenshots are in ignored local paths `tmp/startup-home.png` and `tmp/startup-workspace.png`.
- The required in-app browser connection remained unavailable because the session omitted its required `sandboxPolicy`; isolated Chrome supplied the page-level evidence. The sandboxed Uvicorn/Next launch attempts also hit Windows child-process permission errors; the documented servers were retried with the required host permission. No application code, manifest, lockfile, local environment file, database, or phase scope changed.
- Running services at handoff: the pre-existing SatQuery frontend remains on `localhost:3000`; this session's SatQuery backend remains on `[::1]:8000`. PostgreSQL/PostGIS is not running. Stop before Phase 6.

## Database-only recovery attempt — 2026-09-15

- Confirmed the frontend `Database unavailable` state is the truthful result of `GET /api/v1/health/ready` returning retryable HTTP 503 for dependency `database`. Liveness remains HTTP 200. The root `.env` loads from the intended absolute path; its PostgreSQL driver, loopback host, port, database, username, and password agree with the Compose variables without exposing the credential.
- No PostgreSQL listener, Windows PostgreSQL service/process, Docker/Podman command, Docker Desktop installation/engine pipe, or WSL installation is available. Therefore the persistent Compose database could not start, PostGIS could not be queried, revision `20260907_0001` could not be applied to a real database, and readiness/frontend-ready status could not pass. `scripts/verify-database.ps1` stopped at its deliberate Docker preflight.
- Fixed two confirmed Windows migration-runner defects in `backend/alembic/env.py`: Psycopg async now runs under `SelectorEventLoop`, and Alembic now applies `DB_CONNECT_TIMEOUT_SECONDS`. Before the fix the real command failed with a Proactor incompatibility and then hung; afterward it reached a bounded connection timeout in 4.35 seconds, proving it reached the absent database rather than failing in event-loop setup.
- Relevant backend Ruff/format/strict-mypy checks passed, and focused config/health tests passed 11/11. The declared Alembic head is `20260907_0001`. An isolated Chrome fallback confirmed the workspace still shows `Database unavailable` and not `Backend ready`; the in-app browser remained unavailable because required `sandboxPolicy` metadata was absent.
- No feature, map, schema, dependency, environment value, or phase scope changed. The remaining action is external: install/start a supported Docker Desktop Linux-container backend (including its Windows prerequisite), then run the documented Compose/Alembic/database verification workflow. Stop before Phase 6.

## Phase 5 task 5H completion checkpoint — 2026-09-15

- Passed the available end-to-end browser workflow with real Earth Search catalogue acquisitions, actual georeferenced SatQuery imagery, display/reset, chronological two-date comparison, timeline navigation, browser-local restoration, and AOI invalidation. Scene identity, exact UTC dates, bounds, attribution, and visualization-only limitations stayed visible.
- Fixed one small integration defect: comparison draft labels are now normalized to the same earlier-A/later-B ordering used by the open viewer. Focused comparison/SceneContainer tests passed 10/10 after the fix.
- Live browser/API evidence: real scene `S2B_T43PGQ_20260512T052201_L2A` restored and rendered from two z8 HTTP 200 tiles; real Apr 29/May 12 comparison rendered; display opacity changed to 55% and reset to 100%; timeline used six loaded acquisitions and warned that additional pages remained. A real live tile smoke separately confirmed 17,285 valid and 48,251 transparent pixels in a 256×256 RGBA PNG.
- Failure/security evidence passed: browser-blocked tile traffic produced the truthful partial warning; blocked metadata produced the explicit SatQuery-unreachable state; arbitrary `url`, expression preset, and internal-provider requests returned 422. Provider locations/credentials remained server-side and public-route authorization behavior did not change.
- The authoritative workflow passed backend Ruff/format/strict mypy and 102/102 selected non-database tests. Its combined frontend worker timed out before tests ran; the clean standalone frontend suite passed 98/98. Final format/lint/typecheck, post-fix focused 10/10, and optimized build passed.
- Laptop/mobile screenshots were inspected. Repeated comparison entry/exit showed no visible duplicate maps; component tests retain exact listener/map cleanup coverage. Browser console inspection found no errors, one development-only LCP warning, and expected aborted requests during reload/scene changes.
- `scripts/verify-database.ps1` remains **BLOCKED / NOT RUN** because Docker is unavailable. Readiness remains truthfully database-unavailable; this carried Phase 1 gate is not waived. Phase 5 is complete. Stop before Phase 6.

## Phase 5 task 5G completion checkpoint — 2026-09-15

- The workspace timeline is built only from actual current AOI/filter catalogue results, sorts exact UTC acquisitions chronologically with stable equal-time ordering, identifies multiple scenes on a calendar date, supports direct/previous/next viewer opening and A/B assignment, and explicitly warns when more pages remain unloaded. Stale AOI/filter contexts invalidate it immediately. Playback was not added because the roadmap/tracker does not require it.
- Version 1 browser-local viewer state now validates and stores the Phase 4 AOI geometry fingerprint, camera, stable active asset/preset/display, partial or complete comparison slots, timeline identities, and active entry. It excludes tile IDs/templates, provider URLs, access/expiry state, credentials, bytes, and render claims. A mismatched AOI or unloaded saved scene is explicit and never substituted; active imagery is re-resolved through SatQuery.
- Backend viewer-contract Ruff/format/strict-mypy and 17/17 tests passed. Frontend format/lint/typecheck, focused 19/19 tests, prior full 97/97 suite, and optimized build passed. The initial sandbox test start failed `spawn EPERM`; two later fork-worker starts timed out before tests, and a subsequent focused 8/8 run passed. These failures are retained as environment evidence.
- Live isolated Chrome/WebGL loaded six real Sentinel-2 acquisitions for the Bengaluru AOI with the incomplete-page warning, rapidly navigated Apr 17→22→27, rendered `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20260427T051531_L2A`, and after reload restored the exact scene/camera, freshly requested tile metadata, and rendered two real z8 tiles. The in-app browser remained unavailable because `sandboxPolicy` was missing; [screenshot](docs/phase-5g-restoration.png).
- No server persistence, playback, interpolation, scientific preparation, automated change, percentages, confidence, or analysis was added. This historical 5G boundary is superseded by the completed 5H checkpoint above.

## Phase 5 task 5F completion checkpoint — 2026-09-14

- Users can assign distinct catalogue selections to comparison A/B; opening comparison normalizes A to the earlier UTC acquisition and B to the later one. The view rejects duplicate identity, checks positive WGS84 bbox overlap before opening maps, and labels identity, acquisition, collection, preset, access/render state, reported resolution, cloud metadata, and processing level.
- Added synchronized swipe and side-by-side MapLibre layouts. Two controlled maps use the same projection/style parameters and a guarded camera relay for center, zoom, bearing, and pitch. A keyboard-accessible native range divider supports swipe; display-side swapping retains correct A/B labels. ResizeObserver resizes both maps and leaving comparison aborts metadata, detaches listeners, and removes both maps.
- Both sides reuse the closed 5C tile client/renderer. Nodata and uncovered areas remain transparent. Each side reports metadata/access and tile-content failure independently; `ready` is emitted only after imagery source content, not basemap load. Comparable opacity is linked by default, with visible independent A/B values and an explicit unlink option.
- The official MapLibre comparison plugin was evaluated but not added: it imperatively owns two maps/DOM, its documented example targets MapLibre 2.1.6, and it does not supply SatQuery's accessibility, typed state, independent failure, or cleanup requirements. The local adapter adds no dependency.
- Focused comparison tests passed 10/10 after correcting test/startup issues. Final frontend Biome/typecheck passed, all 91 tests passed, and the optimized `/`, `/_not-found`, `/workspace` build passed. Backend code did not change; its 5E 101-test evidence remains the current backend gate.
- Live isolated Chrome/WebGL passed for `S2B_T43PGQ_20251223T051848_L2A` (A, 2025-12-23T05:25:18.674Z, cloud 4.3%) and `S2C_T43PGQ_20251228T052411_L2A` (B, 2025-12-28T05:25:27.400Z, cloud 28.3%). Both rendered real z8 API tiles. Keyboard divider 50→51, linked opacity 1→0.95 on both, independent B 0.95→0.90, split/swap, 866→432 canvas resizing, and cleanup back to one base-map canvas passed. An earlier real May scene access failure remained explicit on B. The in-app browser could not attach because `sandboxPolicy` was missing; isolated Chrome supplied the evidence and [screenshot](docs/phase-5f-comparison.png).
- Final documentation audit passed: 24 governed Markdown files, 32 relative links, zero broken targets, 16 Phase 0–15 rows, and one active phase row.
- Visual comparison does not claim co-registration, automated change, percentage, confidence, persistence, or analysis. Tasks 5G–5H remain not started. Stop before 5G.

## Phase 5 task 5E completion checkpoint — 2026-09-14

- Added compact, keyboard-operable visibility, opacity, brightness floor/ceiling, contrast, saturation, preset, and reset controls for the active imagery layer. Updates are debounced, retain the existing MapLibre source and camera, and removal/new-scene activation restores defaults without changing AOI, catalogue results, or selected-scene identity.
- `natural-color` remains the only enabled server recipe. False colour is disabled because near-infrared is not resolved; single-band is disabled because it is not approved by the renderer. No arbitrary expression, client path, or upstream URL was added. The server validates exact RGB role/asset ordering and continues rejecting unsupported presets and extra display fields.
- The stable recipe applies each band's catalogue scale/offset and a fixed 0.00–0.30 reflectance range across the scene. MapLibre brightness/contrast/saturation/opacity are presentation-only paint changes; they do not change source values or constitute scientific processing or evidence.
- Focused backend checks passed (Ruff/format/mypy and 10/10 imagery-tile tests). Full backend verification passed with 101 non-database tests and one database test deselected. Frontend format/lint/typecheck passed; a clean standalone run passed 86/86 tests and the optimized build. The combined verification script's frontend worker timed out before running a test, so that attempt remains failed and was not called a pass.
- Live hidden Chrome/WebGL verification used `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: first open reached ready from two real z8 API tile requests; natural colour was enabled, both unsupported presets were disabled with reasons, keyboard opacity changed 1 to 0.95, all display adjustments and reset changed the real imagery while preserving camera/AOI/selection, and visibility toggled without a new metadata request. A later provider range failure was truthfully reported as partial. The in-app browser connector failed before attachment because sandbox metadata lacked `sandboxPolicy`; the isolated Chrome fallback supplied the recorded evidence.
- Final documentation audit passed across 24 governed Markdown files: 28 relative links, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.
- No comparison, timeline/saved viewer state, persistence, scientific processing, or analysis was added. Tasks 5F–5H remain not started. Stop before 5F.

## Phase 5 task 5D completion checkpoint — 2026-09-13

- The workspace now opens the selected stable scene through the 5C metadata route and mounts its exact bounded `xyz` raster source in the existing MapLibre map. The overlay shows UTC acquisition, stable identity, attribution, loading/ready/partial/failure/expired states, retry, fit imagery, fit AOI, and remove behavior. Removal preserves AOI, catalogue results, and selection.
- Imagery stays below scene/AOI overlays and distinct from the context basemap. Source/layer listeners and objects are replaced or removed across scene changes, unmounts, and style reloads. Aborted/sequence-checked requests cannot replace a newer scene. A bounded scene overview is applied before mounting the source to avoid issuing tiles for the preceding close AOI viewport.
- MapLibre's 6.9.0 module worker/shared module are served as pinned same-origin public assets. A clearly labelled synthetic background style supports reproducible local verification only; it is not imagery or analytical evidence.
- Focused frontend checks passed 9/9 after an initial sandbox `spawn EPERM` and one worker-start timeout in which no tests ran. Live Chrome/WebGL verification rendered `earth-search` / `sentinel-2-c1-l2a` scenes `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A` from real z8 API tiles. The first run's upstream failures produced the truthful partial-tile warning; retry at the bounded overview reached ready. Switching removed the first overlay before rendering the second. Hiding the assistant resized the canvas/backing buffer from 812 to 1204 pixels.
- Final repository verification passed: backend Ruff/format, strict mypy, 101 non-database tests with one database test deselected; frontend format/lint/typecheck, 85/85 tests, and optimized `/`, `/_not-found`, and `/workspace` build. The first full attempt was stopped when Biome stalled on the checksum-pinned vendor module; exact vendor assets are now excluded from formatting and their SHA-256 hashes match MapLibre's installed 6.9.0 distribution.
- Final documentation audit passed across 24 governed Markdown files: zero broken relative links, exactly 16 Phase 0–15 rows, one active phase row, and no stale current 5A–5C/5D-not-started boundary.
- No viewer display controls, comparison, timeline/saved viewer state, scientific processing, or analysis was added. Tasks 5E–5H remain not started. Stop before 5E.

## Phase 5 task 5C completion checkpoint — 2026-09-12

- Added stable-identity `POST /api/v1/imagery/tile-sets` metadata and opaque-ID `GET /api/v1/imagery/tiles/{tile_set_id}/{z}/{x}/{y}.png` delivery. Only fixed `natural-color`, 256-pixel, zoom 0–16 WebMercatorQuad rendering is accepted; arbitrary URLs, paths, expressions, and band choices are absent/rejected.
- The lifespan-managed service resolves through 5B, retains locations server-side, revalidates exact provider host/path, validates GTiff length/dimensions/CRS/transform/band headers, and requires exact bounded HTTP 206 ranges. Local/internal destinations, redirects, traversal, credentials, queries, unsupported access, expiry, and invalid matrix coordinates fail explicitly.
- Pinned rio-tiler 9.4.4, Rasterio 1.5.1/GDAL 3.12.4, and NumPy 2.5.3. COG window/overview reads and source reprojection run outside the event loop. Per-band scale/offset and combined masks produce true-colour PNGs with transparent nodata; an all-invalid or failed read is not an empty HTTP 200.
- Final dependency reconciliation records Rasterio as a direct production dependency because the tile service imports it. The regenerated lock, `pip check`, scoped Ruff/format, strict mypy, 10/10 focused tile tests, and the current 101-test non-database backend suite all passed after that manifest-only correction.
- Runtime defaults bound tile requests to 30 seconds, concurrent tile work to two, RGB readers to three per tile, range request count/bytes/deadline/cache, GDAL cache, tile-set count/TTL, and tile-byte memory. Cache keys include the applicable access scope and exact scene/recipe/tile identity.
- Focused/current backend validation passed: Ruff/format, strict mypy, and 101 non-database tests with one guarded database test deselected. Ten 5C cases cover stable-only input, fixed recipe, invalid identities/coordinates/sets, outside coverage, nodata alpha, cache identity/access scope, upstream failure, provider restriction, and hostile destinations.
- Final repository verification passed on a clean rerun: 48 backend files passed Ruff/format, 41 source/test files passed strict mypy, 100 non-database backend tests passed, frontend format/lint/typecheck and 80/80 tests passed, the optimized build passed, and `pip check` found no broken requirements. The subsequently added cache-key regression brought the current passing backend total to 101; frontend code did not change. The first full run's Vitest worker timeout occurred before any frontend test ran and remains recorded as a failed startup.
- Live FastAPI evidence passed at `2026-09-12T15:15:52.810182Z` for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: metadata/tile HTTP 200, request IDs `phase-5c-live-metadata`/`phase-5c-live-tile`, z8/x183/y118, 57,718-byte 256×256 RGBA PNG, 17,285 valid and 48,251 transparent pixels, RGB 0–255, and no database access.
- Earlier native GDAL proxy/Schannel failures and a bounded z12 504 are recorded in [the Phase 5 report](docs/PHASE_5_REPORT.md); none was claimed as success. At this historical 5C boundary browser/MapLibre rendering was not implemented and the stop was before 5D; the 5D checkpoint above supersedes only that display boundary.
- Final documentation/roadmap audit passed across 24 governed root/docs Markdown files: 28 relative links, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.

## Phase 5 task 5B completion checkpoint — 2026-09-12

- Added a closed `POST /api/v1/catalog/asset-resolutions` boundary accepting only stable provider/collection/item identity. It retrieves current metadata through the existing provider instance and returns no provider raster URL, file path, credentials, tile, database resource, or owned analytical asset.
- Earth Search resolution is limited to `sentinel-2-c1-l2a` and maps exact red/green/blue components from allow-listed STAC roles and band metadata rather than assumed asset keys. It preserves each component's ID/version, media type, scale, offset, nodata, CRS, resolution, shape, and transform; thumbnails, licence, and attribution remain separate.
- Raster locations and every redirect hop are constrained to credential-free HTTPS on the configured object host and collection path. Each selected COG must pass metadata validation plus a bounded HEAD check. `supported`, `unsupported_format`, `unavailable_asset`, and `access_credentials_required` are distinct, and every failure returns no resolved asset/components.
- Catalogue availability, asset accessibility, browser render status, and analysis readiness remain independent. Task 5B fixes render status to `not_requested` and analysis readiness to `not_assessed`; it performs no pixel download, tiling, browser rendering, persistence, scientific preparation, or analysis.
- Focused formatting/Ruff and strict mypy checks passed. The dedicated suite passed 7/7, and the adjacent asset/provider/catalogue API suite passed 34/34. The pytest cache warning reflected workspace permission limits; assertions passed.
- Final `scripts/verify.ps1` passed: Ruff/format for 43 backend files, strict mypy for 37 source files, 91 non-database backend tests with one database integration test deselected, frontend format/lint for 56 files, strict TypeScript, 80/80 frontend tests, and the optimized Next.js build.
- Final live verification passed at `2026-09-12T06:14:24.457891Z` for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`: HTTP 200 with request ID `phase-5b-live-resolution`, status `supported`, B04/B03/B02 assets `red`/`green`/`blue`, EPSG:32643, 10 m, 10980×10980, scale 0.0001, offset −0.1, nodata 0, and three HTTP 200 HEAD checks. No raster body was downloaded and the database guard was untouched.
- Documentation/roadmap audit passed across 24 governed root/docs Markdown files: 28 relative Markdown links, zero broken targets, 16 Phase 0–15 rows, and one active phase row. The first broad recursive attempt hit inaccessible generated pytest/tmp directories; its partial counts were discarded before the scoped clean rerun.
- Historical 5B stop: task 5B was complete and 5C–5H had not started. The 5C checkpoint above supersedes that boundary.

## Phase 5 task 5A completion checkpoint — 2026-09-12

- Created `docs/PHASE_5_TASKS.md` before substantial implementation. It preserves the exact repository title placeholder, assigns every authorized requirement to 5A–5H, records additional access/security/scientific boundaries, and requires a stop after each requested subtask.
- Added closed Pydantic and matching browser Zod contracts for stable `{provider, collection, item}` scene identity; resolved asset identity and visualization-only RGB/single-band presets; WGS84/zoom/size/media/attribution/access/expiry tile metadata; active layer display and render state; chronological A/B comparison; unique chronological timeline selection; and version 1 saved viewer state.
- The contracts independently represent catalogue availability, asset accessibility, rendering status, and analysis readiness. Resolved assets expose no raster URL. Tile templates must be credential-free relative `/api/v1/` paths with `{z}/{x}/{y}` and cannot appear for unavailable access. Saved state excludes tile templates/IDs, access/expiry state, credentials, bytes, and render-success claims.
- Focused backend checks passed: Ruff, Ruff format, strict mypy, and 16/16 synthetic viewer-schema tests. Focused frontend checks passed: Biome format/lint, strict TypeScript, and 6/6 runtime-contract tests on the clean permission-scoped retry.
- The first sandboxed frontend test start failed with `spawn EPERM`; the first permission-scoped execution timed out before any test ran while waiting for a fork worker. The following clean permission-scoped retry passed. These startup failures are recorded and do not establish a product defect.
- Final `scripts/verify.ps1` passed on a clean rerun: Ruff and format for 40 backend files, strict mypy for 35 source files, 84 non-database backend tests with one database integration test deselected, frontend format/lint for 56 files, strict TypeScript, all 80 frontend tests, and the optimized Next.js build.
- The first full run failed one existing Phase 4 scene-hover assertion at 79/80; it failed once more focused, then passed unchanged in isolation. Temporary diagnostic instrumentation was removed before the clean full pass. The focused frontend sandbox/worker startup failures described above and this intermittent assertion are retained as execution evidence.
- Governing API/TRD/architecture/testing/security/database/feature/roadmap/decision documentation, Phase 5 tracker/report, this checkpoint, and the session handoff are synchronized. No resolver, endpoint, provider/raster request, tile, MapLibre raster layer, viewer controls, browser persistence behavior, scientific comparison preparation, or analysis was implemented or tested.
- Final documentation/roadmap audit passed: 27 relative links across 30 Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, one active phase row, and zero stale 5A in-progress matches.
- At this historical 5A checkpoint, task 5A was complete and the required stop was before 5B; see [the Phase 5 report](docs/PHASE_5_REPORT.md).

## Carried Phase 4 checkpoint

Phase 4 tasks 4A–4G remain complete and Phase 4 remains **PARTIALLY VERIFIED**. Its live catalogue/API and automated workflow checks passed as recorded in [the Phase 4 report](docs/PHASE_4_REPORT.md). The 5D fallback browser run now adds WebGL, catalogue selection, thumbnail, network, overlay, and resize evidence; Phase 4's explicit refresh/full viewport/download-reimport set and the real database gate remain unpassed. The detailed historical checkpoints below are retained unchanged.

## Phase 4 task 4G completion checkpoint — 2026-09-11

- Live `/workspace` and liveness returned HTTP 200. Readiness correctly returned HTTP 503 `DEPENDENCY_UNAVAILABLE` for `database`, with correlated request ID, `Cache-Control: no-store`, and `Retry-After: 5`; liveness was not treated as readiness.
- Live catalogue verification through FastAPI returned the allow-listed collection, four distinct actual Sentinel-2 items across two query-bound pages with zero duplicates, current item detail/provenance, public JPEG preview metadata, and actual Polygon geometry. A valid 1900 query returned an honest empty HTTP 200 page. Controlled tests preserved `429 RATE_LIMITED`, `503 UPSTREAM_UNAVAILABLE`, and `504 UPSTREAM_TIMEOUT` rather than empty success.
- Focused workflow coverage passed 20/20 for exact AOI search, continuation, fallback metadata, selection/map synchronization, fit/clear/remount, restore/current metadata, corrupt/unavailable drafts, AOI-change invalidation, empty results, provider error, and retry.
- Final `scripts/verify.ps1` passed: Ruff and format for 38 backend files, strict mypy for 33 source files, 68 non-database backend tests with one integration test deselected, frontend format/lint for 54 files, strict TypeScript, 74 frontend tests, and the optimized Next.js build. `pip check` passed.
- Fixed two small 4G verification defects: the repository script now uses the established 15-second Vitest timeout, and the scene integration test awaits React state propagation. Earlier runs exposed one default-timeout failure and one immediate hover-state assertion; focused and complete reruns passed.
- Browser verification remains **NOT RUN** because the in-app browser failed before tab creation with missing `sandboxPolicy`. No screenshots, WebGL/thumbnail rendering, console/network inspection, refresh interaction, or laptop/mobile layout claim is made. Direct preview bytes were also blocked by the environment's unavailable loopback proxy.
- Database verification remains **BLOCKED / NOT RUN**: Docker, Podman, PostgreSQL clients, and database listeners remain unavailable; `scripts/verify-database.ps1` stopped at its deliberate Docker preflight.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, one active phase row, and zero stale 4G status matches.
- Task 4G is complete. Phase 4 remains **PARTIALLY VERIFIED**. Stop before Phase 5.

## Phase 4 task 4F completion checkpoint — 2026-09-11

- Added a versioned, runtime-validated browser draft for the selected scene and its exact originating query. Stable provider, collection, and original item identifiers; acquisition/retrieval timestamps; source record and field provenance; licence/access state; and non-secret preview role/media metadata survive refresh. The UI labels the state `Saved in this browser` and does not claim a database save.
- Durable draft serialization removes provider cursors, preview URLs, expiry timestamps, and any other temporary asset URL. Restored geometry, bbox, identity, query association, timestamps, and safe licence reference are revalidated before use; corrupt/unsupported drafts are removed without breaking the workspace.
- Refresh restoration calls the existing SatQuery item-detail route to retrieve current metadata. Missing items retain the last validated provenance as clearly unavailable/stale context; transient provider failures retain it as stale and expose retry. Selection state, advertised asset accessibility, and unsupported analysis readiness remain separate.
- Focused 4F coverage plus adjacent 4E regression coverage passed: 27 tests across 7 files; the complete frontend suite passed 74 tests. Biome format/lint, strict TypeScript, and the optimized Next.js build passed. The first sandboxed focused-suite startup failed at Vite config loading with Windows `spawn EPERM`; its permission-scoped rerun and all later gates passed.
- A real item-detail refresh through SatQuery's API returned HTTP 200 for `earth-search` / `sentinel-2-c1-l2a` / `S2C_T43PGQ_20251228T052411_L2A`, with acquisition `2025-12-28T05:25:27.400000Z`, current retrieval metadata, source-record identity, thumbnail role/type, proprietary licence, and `provider_accessible` state.
- Browser interaction verification is **NOT RUN**: the in-app browser connector failed before tab creation because sandbox metadata lacked `sandboxPolicy`. No backend/database code or migration changed, so backend and database checks are not applicable to 4F; carried database gates remain unverified.
- Final documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row.
- Historical 4F stop boundary: task 4G was not started at that checkpoint. The explicit 4G completion checkpoint above supersedes it.

## Phase 4 task 4E completion checkpoint — 2026-09-11

- Added MapLibre GeoJSON fill/line layers from each normalized catalogue scene's actual Polygon/MultiPolygon footprint. Current, stale, hovered, and selected states are visually distinct, the AOI remains a separate layer/state, and scene layers are restored after style reloads.
- Added synchronized card/map hover and selection, clear and fit-to-scene actions, and a scene-details view with real available preview/metadata plus honest fallbacks. Selection is typed workspace state keyed by provider ID, collection ID, and item ID; it is metadata context only and cannot enable raster viewing or analysis.
- AOI changes mark previous results stale, abort/disregard obsolete requests through the existing query fingerprint, clear hover, and revalidate/clear retained selection. Map listeners are removed on unmount; the existing resize observer remains responsible for panel-driven map resizing and route remounts restore current scene state.
- Phase 4E automated verification passed: 7 focused selection/layer/integration tests and all 66 frontend tests; Biome format/lint, strict TypeScript, and the optimized Next.js build passed. The first sandboxed full-suite start failed with Windows `spawn EPERM`; the first executing full suite then exposed one shared global-map-mock failure, which was corrected with an injected map component before the clean 66/66 rerun.
- Served `/workspace` returned HTTP 200. A bounded live request through SatQuery's API returned HTTP 200 with request ID `phase-4e-live-geometry`, actual item `S2C_T43PGQ_20251228T052411_L2A`, a Polygon footprint, bbox `76.8405435490709,12.560413606130458,77.86185827663547,13.561138787915565`, and a continuation cursor. The first PowerShell-built smoke body was correctly rejected with `422 VALIDATION_FAILED` after its arrays flattened; the literal valid GeoJSON rerun passed.
- Browser visual verification is **NOT RUN**: the required in-app connector again failed before tab creation because its sandbox metadata lacked `sandboxPolicy`. Unit/component coverage and HTTP/API smokes are not presented as visual/WebGL evidence. No backend code, API contract shape, database code/migration, credential, raster fetch, or analytical capability changed.
- Final documentation/roadmap audit passed: 26 relative links across 22 Markdown files, zero broken targets, exactly 16 Phase 0–15 rows, and one active phase row. An initial audit was invoked from `frontend/` and could not find the root documents; its counts were discarded and the repository-root rerun passed.
- Historical 4E stop boundary: tasks 4F–4G were not started at that checkpoint. The later 4F and 4G completion checkpoints above supersede it.

## Phase 4 task 4D completion checkpoint — 2026-09-11

- Added an imagery-discovery panel inside the existing workspace map-tool surface. It uses the selected local AOI, real collection discovery, UTC start/end dates, a provider-reported scene cloud threshold for Sentinel-2, and search/retry/load-more controls without changing map navigation or AOI editing code.
- Added a runtime-validating browser client for the 4C collection/search contracts and common request-ID error envelope. Scene cards preserve real provider/collection/acquisition/sensor/access metadata, label cloud cover as scene metadata, render provider thumbnails only when the API marks them public/temporary, and fall back honestly for missing or failed previews/metadata.
- Search pages remain associated with an exact AOI/filter fingerprint. An AOI or filter change aborts the active request, stale completions are disregarded, prior cards are explicitly marked as belonging to the prior query, and their continuation control is disabled. The UI reports only loaded scenes, never a provider total.
- Focused 4D tests passed: 9 tests across the API client and panel cover exact queries, runtime rejection, missing optional metadata, validation, stale responses, pagination, empty pages, provider errors, retries, and request correlation. The complete frontend suite passed 59 tests; format, lint, strict type checking, and the optimized build passed.
- Intermediate checks were retained rather than hidden: the first Vitest worker and first post-compile build worker hit Windows `spawn EPERM`; scoped reruns passed. The first complete suite exposed cross-file mock leakage (6 failed 4D cases), which was corrected with an injected typed client boundary before the final 59-test pass. Initial format/lint/type findings in new files were likewise corrected before the clean gate.
- A live request through the running SatQuery API returned two actual Sentinel-2 scenes (`S2B_T43PGQ_20250226T051939_L2A`, `S2C_T43PGQ_20250221T052428_L2A`), real provider cloud/MSI metadata, public preview URLs, and a continuation cursor. Following the cursor returned two distinct later-page IDs. No database access, persistence, asset selection, or raster analysis was added.
- The running `/workspace` route returned HTTP 200 and the configured frontend-origin catalogue POST preflight returned HTTP 200 with `GET, POST, OPTIONS`. Documentation/roadmap audit passed: 26 relative links across 23 governed Markdown documents, no broken targets, 16 phase rows, and one active phase row.
- Browser visual/search verification is **NOT RUN**: the required in-app browser connector failed before creating a tab because browser sandbox metadata lacked `sandboxPolicy`. A separate direct preview fetch was blocked by the environment's unavailable loopback proxy, so thumbnail pixels are not claimed as observed; failed browser loads use the tested honest fallback.
- Historical 4D stop boundary: 4E had not yet been authorized at this checkpoint. The later explicit 4E instruction and completion checkpoint above supersede it; authenticated persistence, owned asset intake, and analytical pixels remain absent.

## Phase 4 task 4C completion checkpoint — 2026-09-11

- Implemented typed public metadata routes for configured collection listing, synchronous catalogue search, and item detail. FastAPI owns validation/error translation and the lifespan-managed provider; no route depends on database storage.
- Preserved the 4A AOI, timezone/date ordering, collection/cloud/page/cursor contract and the 4B actual Earth Search token mechanism. Cursors are provider/query/filter/order bound and mismatches fail before altered upstream I/O.
- Empty search is an explicit HTTP 200 empty page. Validation, unavailable capability, missing item, rate limiting, invalid provider data, unavailable upstream service, and timeout use distinct error-envelope outcomes with correlated request IDs. No provider failure becomes empty success.
- Added 16 API tests, a POST CORS regression, and a bounded live API script. Focused API/provider/schema tests passed (49); Ruff, Ruff format (35 files), strict mypy (35 files), 68 non-database tests, and `pip check` passed. A malformed pytest marker invocation failed with zero tests before the explicit-ignore rerun passed; the guarded database integration test remains not run.
- Final live SatQuery API request passed at `2026-09-11T09:58:30.595641Z`: HTTP 200, request ID `catalog-api-live-smoke`, actual Earth Search item `S2C_T43PGQ_20251228T052411_L2A`, continuation cursor present, database guard untouched, and no raster fetched.
- Documentation/roadmap audit passed: 26 relative links across 22 governed Markdown files, no broken targets, 16 phase rows, and one active phase row.
- Public metadata access creates no owner-scoped resource and does not weaken authentication requirements for saved searches, AOIs, asset intake, provider credentials, or analysis. Existing database-backed readiness behavior and all carried gates remain unchanged.
- Stop after 4C. Task 4D is not started; its former public API portion is absorbed and any remaining authenticated/persistent scope requires explicit re-scoping.

## Phase 4 task 4B completion checkpoint — 2026-09-10

- The user explicitly redefined 4B as a real catalogue provider connector, absorbing the earlier separate initial-adapter deliverable. `docs/PHASE_4_TASKS.md` now records the current task boundary; the old 4C placeholder remains not started and requires later re-scoping.
- No repository-approved EO provider was recorded, so 4B uses the user-authorized default Earth Search STAC API. No other collection/provider is added unless required by the recorded scope.
- 4B remains backend metadata-only work: no public catalogue route, database table/migration, frontend UI, raster download, or carried-gate waiver.
- Implementation checkpoint: the provider-neutral protocol and constrained Earth Search adapter are implemented for `sentinel-2-c1-l2a`, including discovery, AOI/time/cloud/sort search, item detail, query-bound pagination, normalization, exact-origin enforcement, bounded retries/timeouts, response limits, and a bounded TTL/LRU metadata cache. A captured provider-metadata fixture is test-only and cannot become a production fallback.
- Live adapter verification passed at `2026-09-10T16:10:27.358819Z` with STAC 1.0.0, `eo:cloud_cover`, `sentinel-2-c1-l2a`, actual IDs `S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20251223T051848_L2A`, a next cursor, and detail retrieval for the second item. No raster was fetched.
- Final backend checks passed: Ruff, Ruff format (32 files), strict mypy (32 source/test/script files), 51 non-database tests, and `pip check`. The guarded database integration test was deselected and remains not run. Task 4B is complete; stop before 4C, whose former scope was absorbed into 4B and must be redefined before work begins.
- Final documentation/roadmap audit passed: 26 relative links across 24 governed Markdown documents, exactly 16 Phase 0–15 rows, and exactly one active phase row.

## Phase 4 task 4A checkpoint — 2026-09-10

- Created the required 4A–4G tracker before substantive contract implementation. It preserves the missing original Phase 4 title and records the user-authorized working scope separately.
- Added closed provider-neutral Pydantic schemas for catalogue requests, normalized scene pages, Polygon/MultiPolygon AOIs, UTC acquisition intervals, collections, provider-reported cloud filtering, bounded opaque cursors, preview/licence/access semantics, footprint-consistent bbox, unavailable fields, and field-level provenance.
- Added 22 explicitly synthetic positive/negative schema tests. No route, provider adapter, network request, database table/migration, frontend catalogue UI, asset-selection state, credential, or real scene/result was added.
- Final backend checks passed: Ruff lint, Ruff format check (26 files), strict mypy (26 source/test files), focused pytest (22 tests), and the full non-database backend suite (37 tests). The real database integration test was deselected and remains not run.
- Final documentation and roadmap checks passed: 26 relative links across 27 project documents, exactly 16 Phase 0–15 rows, and exactly one active phase row.
- Synchronized `API_CONTRACT.md`, `TRD.md`, `ARCHITECTURE.md`, `DATABASE.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, `SECURITY.md`, and `docs/DECISIONS.md`. ADR-0024 records the user-authorized working scope; ADR-0025 records contract version 1.0 decisions.
- Frontend, provider/sandbox, API route, database, and browser catalogue checks were **NOT RUN** because 4A implements none of those behaviors. Git status/diff remain unavailable because the workspace has no `.git` metadata.
- Historical 4A stop point: task 4B was next and intentionally not started in that earlier session. The 4B completion checkpoint above now supersedes this resume instruction.

## Phase 3 recovery checkpoint — 2026-09-10

- Reconstructed the interrupted work from this checkpoint, the Phase 3 report, governing contracts, implementation timestamps, source, manifests, migrations, and tests. The workspace still has no `.git` metadata, so status, diff, recent commits, and a tracked/untracked classification remain unavailable rather than inferred.
- No truncated or partially edited application file was found. Recent Phase 3 source is internally complete, all protected AOI backend surfaces remain explicitly absent, and no Phase 4 file or capability was introduced.
- The historical frontend/backend process IDs were no longer SatQuery services and no listener existed on ports 3000, 8000, 5432, or 55432. Temporary verification sessions served `/` and `/workspace` with HTTP 200, liveness with HTTP 200 and the expected versioned body, and readiness with the expected HTTP 503 plus `Cache-Control: no-store` and `Retry-After: 5`; both sessions were then stopped.
- The browser skill's required in-app connection was retried and again failed before a tab was created because the session lacked required browser sandbox metadata. Real WebGL rendering, drawing/editing, responsive screenshots, console/network inspection, and download/reimport remain **NOT RUN**.
- `scripts/verify.ps1` passed Ruff check/format, strict mypy, 15 non-database backend tests, frontend format, lint, and strict type checking. Its Vitest step failed before loading tests because the fork worker timed out, matching the recorded Windows-host issue. The isolated rerun `npm.cmd run test:run -- --testTimeout=15000` passed all 9 files and 50 tests, and `npm.cmd run build` passed with `/` and `/workspace` prerendered.
- Server-owned AOI CRUD remains blocked on the documented unresolved identity/tenant decision. No client-supplied owner, anonymous production bypass, speculative authentication scheme, domain migration, or misleading partial protected API was added. Phase 3 remains `PARTIALLY_VERIFIED`; stop before Phase 4.
- Created `SESSION_HANDOFF.md` as the concise cross-session resume record and added an `AGENTS.md` rule requiring it to be refreshed after every major task. This process-only change does not alter Phase 3 implementation or status.

## Phase 3 continuation checkpoint — 2026-09-09

- Preserved the application and existing Phase 3 files; corrected MapLibre startup types, drawing commit/cancel synchronization, import races, validation, provider configuration, and responsive controls.
- Frontend lint, typecheck, formatting and final production build passed. All 50 tests passed with `--testTimeout=15000`; the report retains the earlier worker-start and default-timeout failures. All 22 checked relative documentation links resolve.
- Windows host: `/` and `/workspace` returned 200; liveness returned 200 with the expected service/version; readiness returned 503 `DEPENDENCY_UNAVAILABLE`, dependency `database`, retryable, with no-store and Retry-After 5.
- Final Windows host recheck at 23:37 IST confirmed independent PowerShell terminals 17212/13524 and frontend 10944/backend reloader 8404/server 12396 remained running, both frontend routes returned 200, readiness 503 and subsequent liveness 200. No restart or unrelated process termination was needed.
- Browser connector failed before creating a tab (`sandboxPolicy` metadata missing). Real map rendering/drawing/editing, responsive screenshots, browser console/network inspection and refresh/download round trips remain NOT RUN.
- Required owned AOI API/PostGIS persistence remains unimplemented. Authentication integration is unresolved; browser drafts do not satisfy the ownership gate. Stop before Phase 4.

## Carried Phase 1 verification issue

Phase 1 implementation and its available non-database checks pass, but these acceptance checks remain unresolved in the currently accessible native Windows environment:

- Real PostgreSQL/PostGIS connectivity.
- Alembic migration verification against the real database.
- Database-backed readiness returning HTTP 200.

Docker/PostgreSQL/PostGIS are unavailable in the inspected environment. Do not substitute mocks or repeat unavailable-runtime attempts; resume the isolated host-side workflow described in `docs/PHASE_1_REPORT.md` when a suitable runtime is available.

## Phase 2 checklist

- [x] Implement the responsive public homepage at `/`.
- [x] Implement the responsive unified workspace shell at `/workspace`.
- [x] Preserve usable navigation, query drafting, tabs, and panels while services are unavailable.
- [x] Represent backend unreachable, backend reachable/database unavailable, and backend ready states through the real health client.
- [x] Keep map, AOI, catalogue, analysis, fabricated results, history, and reporting out of Phase 2.
- [x] Verify navigation, mobile controls, accessible tabs/dialogs, draft behavior, status retry, and unavailable-feature explanations with focused component tests.
- [x] Pass frontend formatting, linting, type checking, component tests, production build, and HTTP route checks.
- [ ] Inspect representative desktop/mobile layouts in a browser and capture screenshots when the browser connector is usable.
- [x] Synchronize feature evidence, setup guidance, testing notes, and `docs/PHASE_2_REPORT.md`.

## Phase 1 checklist

- [x] Re-inspect the Phase 0 foundation, Git state, and local runtime/tool availability.
- [x] Review official compatibility and setup guidance for the selected baseline.
- [x] Select and lock the frontend and backend dependencies; record supported runtime versions.
- [x] Implement validated backend/frontend environment conventions without exposing secrets.
- [x] Implement the FastAPI application factory, lifespan, middleware, errors, logging, database sessions, and health routes.
- [x] Add PostgreSQL/PostGIS Docker Compose and explicit Alembic migration infrastructure.
- [x] Implement the minimal Next.js shell and typed runtime-validating backend health client/status view.
- [x] Add Phase 1 backend, frontend, configuration, and guarded database integration tests.
- [x] Pass backend/frontend format, lint, type, unit, build, dependency, API degraded-state, and frontend HTTP checks.
- [ ] Pass the real Compose/PostGIS/Alembic integration and readiness-success gate (Docker unavailable).
- [x] Record the unavailable Phase 1 browser smoke accurately; it is not one of the three outstanding database acceptance checks.
- [x] Synchronize contracts, stack, setup instructions, decisions, feature evidence, and Phase 1 report.

## Inspection baseline

- The workspace began with the Phase 0 documentation/configuration foundation and no pre-existing application implementation or dependency manifests.
- `C:\Desktop\SatQuery` is still not a Git repository, so Git-aware status/diff validation is unavailable unless that external state changes.
- Locally observed runtimes: Node.js 24.19.0, npm 11.17.0, and Python 3.14.7. Docker is not installed or not on `PATH`.
- No existing local environment files were found or overwritten; only examples are tracked.

## Checkpoint revalidation — 2026-09-08

- The active shell is native x64 Windows (`Microsoft Windows 10.0.26200`) with PowerShell 5.1; it is not running inside WSL.
- `docker`, `podman`, `psql`, and `pg_isready` are not on `PATH`. Docker Desktop was not found in its documented per-user or all-users install locations or uninstall registry entries; no Docker engine pipe, Docker/PostgreSQL service, or related process is visible.
- `wsl.exe` is present, but both status and distribution listing report that Windows Subsystem for Linux is not installed.
- `.\scripts\check-prerequisites.ps1` fails only on the missing Docker command after confirming Node.js 24.19.0, npm 11.17.0, and Python 3.14.7.
- `.\scripts\verify-database.ps1` exits at its intended Docker preflight before starting or modifying any container, database, or volume.
- The focused existing health regression suite still passes: 3 tests confirm liveness and database-unavailable behavior. This does not substitute for the missing real readiness-success check.
- The user subsequently authorized Phase 2 frontend work to proceed independently under ADR-0020; the three real database checks above remain pending.

## Phase 2 implementation checkpoint — 2026-09-08

- `/` now renders the responsive SatQuery homepage with working section links, workspace actions, mobile navigation, evidence-focused content, and an explicitly illustrative code-native preview.
- `/workspace` now renders the responsive unified shell with desktop/mobile navigation, a future scene boundary, query composer, suggested-question insertion, Answer/Evidence/Activity tabs, truthful empty states, planned-feature explanations, a keyboard-managed guide dialog, and the existing real health client in compact form.
- Query and tab state remain owned by the workspace shell when panels close. No backend session persistence is implied; the draft is labeled as retained only in the current browser tab.
- Analysis remains disabled regardless of connection health. No map engine, AOI geometry, analytical imagery, catalogue, result, measurement, confidence, activity trace, or later-phase endpoint was added.
- Final frontend checks passed: Biome format and lint (31 files), Next route type generation plus strict TypeScript, Vitest (4 files, 20 tests), optimized Next.js build, and HTTP 200 checks for both implemented routes.
- Relative Markdown links resolve across 23 repository documents and ROADMAP retains exactly 16 phase rows.
- The in-app browser connector failed before creating a tab. Desktop/mobile pixel inspection, browser-console review, and screenshots are `NOT RUN`; no screenshots were created. This is the only remaining Phase 2 verification gap.
- No backend code changed, so backend regressions were not rerun. The unavailable Docker/database workflow was not retried, as explicitly requested.

## Local backend startup diagnosis — 2026-09-08

- The repository virtual environment is `C:\Desktop\SatQuery\.venv` with Python 3.14.7 and the locked FastAPI 0.141.1, Uvicorn 0.52.4, Pydantic Settings 2.15.0, SQLAlchemy 2.0.52, and Psycopg 3.3.5 dependencies installed.
- Nothing initially listened on port 8000. The exact documented factory command failed before binding with `SettingsError: Invalid backend configuration: DATABASE_URL: Field required` because the ignored root `.env` did not exist.
- Both missing ignored local files, `.env` and `frontend/.env.local`, were created from their checked-in examples without overwriting an existing value. No source, manifest, lockfile, database, or secret-bearing tracked file changed.
- Uvicorn's Windows auto-reloader initially hit a sandbox-denied multiprocessing pipe. The same documented command succeeded when granted the required local child-process permission; this was an execution-environment restriction, not an application-code defect.
- The backend was observed running on `127.0.0.1:8000` through the documented `satquery.main:create_app` factory with `--reload` during that session. Liveness was HTTP 200 with the versioned live contract; readiness was the intended retryable HTTP 503 with code `DEPENDENCY_UNAVAILABLE` and dependency `database`. This historical observation did not establish continued process availability; see the September 9 checkpoint below.
- Both preflight and live requests from origin `http://localhost:3000` receive the configured CORS allowance. The active frontend development bundle contains `http://localhost:8000/api/v1`; its status code paths map network failure to `Backend unreachable` and this readiness response to `Database unavailable`.
- Browser-level observation of the workspace label was `NOT RUN` because the in-app browser could not create a tab. A focused frontend test rerun also did not start because its Vitest worker timed out before loading tests; the previously recorded final 20-test Phase 2 run remains the latest completed UI-test evidence.
- No Docker installation or database reset/start was attempted. The three carried Phase 1 database acceptance checks remain unresolved.

## Persistent local startup checkpoint — 2026-09-09

- Windows host process inspection found no SatQuery Node/Python processes and no listeners on 3000 or 8000. All four requested URLs initially refused connections. The unrelated editor Node process and other services were left untouched.
- Both ignored local environment files already existed. The root `.venv` is Python 3.14.7 with the documented locked dependencies; backend settings validate successfully and target the local database at `127.0.0.1:5432`, where no listener was present. No configuration or dependency replacement was needed.
- The retained Next.js development log contained no crash error. No retained backend exit output was found. The observed cause of unreachable URLs was stopped server processes; the reason those earlier processes stopped is unknown. Database unavailability does not explain loss of frontend or liveness.
- Started the existing `npm.cmd run dev` script from `frontend/` and the documented `..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000` from `backend/` using two standalone host PowerShell windows (`Start-Process`, `-NoExit`). These are outside temporary verification sessions and remain open for the user.
- Actual terminal output reported Next.js 16.3.4 ready in 3.0 seconds and Uvicorn application startup complete. Windows console buffers were read directly because the open PowerShell transcripts did not yet contain native server output. No startup error appeared.
- Host HTTP verification: homepage and workspace HTTP 200 with implemented HTML; liveness HTTP 200 with `{"status":"live","service":"satquery-api","version":"0.1.0"}` on both `localhost` and `127.0.0.1`; readiness HTTP 503 with `DEPENDENCY_UNAVAILABLE`, dependency `database`, `retryable: true`, `Cache-Control: no-store`, and `Retry-After: 5`. Liveness still returned 200 after the failed readiness request.
- Observed processes: frontend PowerShell 17212 and Next server 10944 listening on port 3000 (`::`); backend PowerShell 13524, Uvicorn reloader 8404 and server 12396 on `127.0.0.1:8000`. Both terminal/process trees survived the launcher command's exit and subsequent independent host checks. These IDs are historical observations, not permanent identities.
- Final host recheck at 18:16:32 IST confirmed those five processes still running and launcher 20796 absent. Readiness 503, subsequent liveness 200, and both frontend routes 200 passed again; both health responses allowed the configured `http://localhost:3000` CORS origin. Review of all 21 relative links/anchors in the four changed documents passed.
- Changed only startup/handoff documentation: `README.md`, this checkpoint, and both phase reports. No application source, manifests, lockfiles, environment values, database, or unrelated process changed. Full build/unit suites and browser inspection were not rerun for this documentation/process task; real database readiness success remains unverified. Phase statuses are unchanged.
- Resume local use through the exact two-terminal commands in [README.md](README.md#local-setup-powershell); leave both windows open. If either URL becomes unreachable, inspect its terminal output and current port ownership before starting a replacement. Closing either window, signing out, or restarting Windows requires starting that service again.

## Phase 2 changed surfaces

- Homepage and app routes under `frontend/src/app/`.
- Shared brand/icon, homepage, workspace, dialog, status, composer, scene, and tabs components under `frontend/src/components/`.
- Centralized feature availability in `frontend/src/lib/feature-availability.ts` plus focused homepage/workspace/status tests.
- Frontend test/typecheck configuration and setup guidance; no dependency versions or lock entries changed.
- `README.md`, `ARCHITECTURE.md`, `FEATURES.md`, `ROADMAP.md`, `TESTING.md`, `docs/DECISIONS.md`, both phase reports, and this checkpoint.

## Exact resume instructions

1. Phase 5 is complete. Stop before Phase 6; its authoritative title/scope is unavailable, so do not invent or begin it without explicit authorization and source wording. Read `AGENTS.md`, this file, both phase reports, and the current manifests/contracts.
   For local UI/API use, first check the two standalone SatQuery terminals and ports 3000/8000. Reuse running services; if stopped, use the [README restart commands](README.md#local-setup-powershell) in separate host PowerShell terminals and leave both open. Readiness 503 is expected while the real database remains unavailable.
2. Retry the Phase 2 desktop/mobile browser inspection when the in-app browser connector can establish a tab. Capture the four representative viewports, fix any observed defects, rerun the frontend checks, and then mark Phase 2 complete if no acceptance issue remains.
3. Separately, on the Windows host that owns `C:\Desktop\SatQuery`, install/start Docker Desktop with a supported Linux-container backend by following the [official Windows instructions](https://docs.docker.com/desktop/setup/install/windows-install/); a restart may be required. Do not try to install it inside a hosted/sandboxed agent session.
4. In a new host PowerShell at `C:\Desktop\SatQuery`, require `docker version` and `docker compose version` to succeed, then run `.\scripts\verify-database.ps1`. The isolated script supplies and restores its own test-only environment values; it does not require or overwrite `.env` and does not touch the persistent `db` volume.
5. Require the isolated migration test, PostGIS version check, Alembic current/head check, and real readiness-success response to pass. Record actual versions/output in the Phase 1 report, then change F-CORE-01 and ROADMAP Phase 1 to `COMPLETE`.

Phase 2 frontend work does not retroactively expand Phase 1: the carried foundation still has no map/AOI, uploads, catalogue, analysis, runtime AI, reports, or complete authentication.

## Superseded sequencing checkpoint

**Phase 3 — Interactive Earth Map & AOI System**

The earlier instruction to wait before Phase 3 was superseded by the user's explicit Phase 3 request. Resume the pending Phase 3 gates in `docs/PHASE_3_REPORT.md`; stop before Phase 4. Phase 1 database verification remains separately unresolved.
