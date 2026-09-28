# SatQuery session handoff

Last updated: **2026-09-22**

Read this concise resumption record with `AGENTS.md`, `CURRENT_PHASE.md`, `PRD.md`, `TRD.md`, and `ROADMAP.md`.

## Critical Recovery R4 — Imagery Identity, AOI-Specific Assets, Analysis Correctness and Workspace Stabilization — 2026-09-22

- **Scope & Objectives:**
  - Resolved all critical correctness, hydration, asset identity, cache key isolation, and visual QA grounding issues:
    1. **Next.js Hydration Mismatch Fixed**: Synchronized SSR default basemap and client mount preference application in `map-canvas.tsx` and `scene-container.tsx`. Zero hydration warnings/errors.
    2. **Single Immutable Imagery Identity Manifest**: Extended `ImageManifest` with `provider`, `collection`, `platform`, `sensor`, `media_type`, `scene_bbox`, `aoi_id`, `aoi_revision`, `crop_bounds`, `resolution_meters`, and `preview_type`. Scoped asset generation prevents asset collision across different AOIs.
    3. **Three Explicit Image Products**: Full-scene provider thumbnail (labeled `"Full-scene preview (100×100 km)"`), Selected-area preview (labeled `"Selected-area preview"`), and Analysis asset.
    4. **Area-Specific VQA Grounding & Prerequisite Guidance**: Grounded visual observations trace strictly through the selected AOI crop. Replaced pre-validation error cards with compact inline guidance.
    5. **Clean Acquisition Timeline & Mode-Aware Comparison**: Redesigned comparison labels to explicit `"Before acquisition"` and `"After acquisition"` and mode-aware timeline assignment buttons without raw oversized clutter.
- **Verification Evidence:**
  - `verify.ps1`: All backend (302 Pytest, Ruff format/lint clean, strict Mypy clean) and frontend (303 Vitest across 69 files, strict TypeScript, Biome format/lint clean, Next.js build clean) checks **PASSED**.
  - Browser CDP & Visual Evidence: Verified measurements at 1920×1080 and 1366×768 with zero hydration errors, distinct AOI crops and answers, and 8 PNG screenshots captured.
- **Next Action**: Rerun Phase 7A validation before Phase 7B.

## UI Correction R3 — Map-First Layout, Compact Controls and Hybrid Map Labels — 2026-09-22

- **Scope & Objectives:**
  - Full implementation and verification of UI Correction R3:
    1. **Map-First Layout**: Grid adjusted to `14.5rem 1fr 22.5rem` on large desktops, `13.5rem 1fr 21.5rem` on medium desktops, and floating overlay on `<980px` screens. Sidebar expanded to ~232px, collapsible to ~68px with centered accessible icons. Assistant collapsible to `0` width with instant map expansion.
    2. **Compact Step Toolbar & Draw AOI Action**: Replaced tall banner with single-row toolbar (~48px) displaying mode-aware step chips (4 for single-image, 5 for bi-temporal) and a compact primary button (`height: 2.15rem`, ~36px) without split lines.
    3. **Compact AOI Summary Card**: Compact card (~18.5rem, ~295px) with collapsible area, bounds, and quick "Edit", "Fit AOI", and "Remove" actions.
    4. **Hierarchical Place Labels & Hybrid Satellite View**:
       - Multi-level place labels and contours enabled on Default and Terrain.
       - Satellite basemap provides a true **Hybrid View** combining Esri World Imagery raster tiles with an Esri Reference transparent vector labels and administrative boundaries overlay (`satellite-hybrid-labels-layer`).
       - Added compact "Labels: On/Off" toggle adjacent to basemap switcher.
       - Synchronized and preserved AOI and analysis vector layers over basemap style changes without duplicate layers or canvas flashes.
    5. **Correct Dynamic Attribution & Status**: Active basemap text and attribution accurately reflect active source (OpenTopoMap on Terrain, Esri on Satellite Hybrid, OpenFreeMap on Default).
    6. **Slimmer Assistant & Elimination of SVG Overflow**: Compact tabs, bounded question textarea (`5.5rem–8.5rem`), bounded decorative empty state icons (`.result-empty-icon` / `.selected-assets-notice svg` max 1.15rem), eliminating oversized SVG overflow.
- **Verification Evidence:**
  - `verify.ps1`: All backend (298 Pytest) and frontend (303 Vitest across 69 files, TypeScript, Biome, Next.js build) checks **PASSED**.
  - Browser CDP & Visual Evidence: Verified measurements at 1920×1080 and 1366×768 with zero horizontal overflow, dominant map canvas, clear place labels, and compact controls.
- **Next Action**: Rerun Phase 7A validation before Phase 7B.

## Feature Correction R2 — Basemap Modes, Analysis-Type Selection and AOI-Only Processing — 2026-09-21

- **Scope & Objectives:**
  - Full implementation and verification of Feature Correction R2:
    1. **Basemap Switcher**: Implemented compact switcher supporting **Default** (OpenFreeMap Liberty), **Terrain** (OpenTopoMap), and **Satellite** (ESRI World Imagery) backgrounds. Basemap switches preserve map center, zoom, AOI, analysis overlays, and footprints without re-running analysis.
    2. **Analysis-Type Selection (Mode-First Workflow)**: Mode selection is the real first step in the workspace workflow with three primary choices: **Single Image Analysis** (1 scene VQA/grounding), **Change Detection** (bi-temporal pair ΔNDVI/ΔNDWI), and **Optical + SAR Analysis** (Sentinel-2 + Sentinel-1 multimodal fusion).
    3. **Strict AOI-Only Processing**: Verified exact polygon masking via `geometry_mask(..., invert=True)` sets outside pixels to nodata, and downstream metric calculations isolate the AOI domain so outer pixels cannot influence change or spectral percentages. Added deterministic test suite `backend/tests/test_aoi_masking.py`.
    4. **Cloud-Cover Scoping**: Renamed to *"Maximum scene cloud cover — optical only"* with contextual tooltip; disabled automatically with clear explanation when SAR sensor is selected.
- **Verification Evidence:**
  - `verify.ps1`: All backend (298 Pytest) and frontend (303 Vitest across 69 files, TypeScript, Biome, Next.js build) checks **PASSED**.
  - Browser Subagent: Visual evidence confirmed distinct mode cards, working Default/Terrain/Satellite basemap switching, single-image workflow execution, and cloud cover scoping.
- **Next Action**: Rerun Phase 7A validation before Phase 7B.

## Recovery R1 — Database Readiness, Map Canvas, Workspace UI and Feature Connectivity — 2026-09-21

- **Scope & Objectives:**
  - Full repair of workspace layout, database readiness badge, MapLibre canvas rendering, operation controls, and navigation.
  - Added zero-Docker local persistence (`aiosqlite` SQLite adapter) auto-initializing database tables while keeping PostgreSQL/PostGIS foundation ready.
  - Fixed CSS grid column displacement caused by unplaced draft banner.
  - Implemented segmented operation buttons (`Describe`, `Locate Feature`, `Compare Pair`).
  - Added dedicated connected pages for `/history`, `/saved-aois`, and `/reports`, with `Missions` honest Phase 12 indicator.
- **Verification Evidence:**
  - `verify.ps1`: All backend (296 Pytest) and frontend (297 Vitest across 68 files, TypeScript, Biome, Next.js build) checks **PASSED**.
  - Browser Subagent: Visual evidence confirmed green `Backend ready` status, `REAL DATA` origin badge, rendered OpenFreeMap tiles, separate operation pills, and responsive layout across 1920x1080 and 1366x768.

## Phase 7B — SIH Demo Rehearsal, Contingency Pack and Final Handoff — 2026-09-21

- **Scope & Objectives:**
  - Executed end-to-end automated rehearsal suite for the Smart India Hackathon (SIH) live demonstration.
  - Frozen candidate profile: Python 3.14 / FastAPI / GDAL / Rasterio / Next.js 16.3.4 Turbopack.
  - Verified 100% pass rate across 6 consecutive end-to-end rehearsal passes (3 Primary live STAC runs, 3 Fallback offline runs).
  - Target AOI: Bengaluru Urban / Bellandur Green Corridor (9.64 km² WGS84 geodesic area).
  - Primary workflow: Live Element 84 Earth Search STAC Sentinel-2 L2A pair (`S2C_T43PGQ_20251228T052411_L2A` and `S2B_T43PGQ_20260512T052201_L2A`) $\to$ 10m UTM grid co-registration (95,630 valid pixels) $\to$ NDVI differencing $\to$ WGS84 GeoJSON change vectorization $\to$ Grounded question answering $\to$ ReportLab Platypus PDF & JSON dossier export with SHA-256 integrity hash.
  - Fallback workflow: Pre-staged deterministic mock Sentinel-2 L2A optical scenes executing the identical downstream raster math and PDF/JSON dossier export completely offline.
- **Blocker Fixes Applied During Rehearsal:**
  - `backend/src/satquery/services/raster_harmonizer.py`: Propagated band descriptions to output GeoTIFFs preserving optical band identities (`B02, B03, B04, B08, B11, B12`).
  - `backend/src/satquery/services/change_engine.py`: Reprojected change vector polygons from projected metric CRS (`EPSG:32643`) to WGS84 (`EPSG:4326`) GeoJSON.
- **Documentation Package Created:**
  - [`docs/DEMO_SCRIPT.md`](file:///c:/Desktop/SatQuery%20-AG/docs/DEMO_SCRIPT.md): 5–7 min full script, 3 min compressed script, 90 sec emergency path, and judge interruption safe points.
  - [`docs/DEMO_RUNBOOK.md`](file:///c:/Desktop/SatQuery%20-AG/docs/DEMO_RUNBOOK.md): PowerShell startup commands, preflight checklists (T-60, T-15, T-0), and symptom-based fast recovery guide with 20-second rule.
  - [`docs/JUDGE_QA.md`](file:///c:/Desktop/SatQuery%20-AG/docs/JUDGE_QA.md): 18 evidence-based answers covering remote sensing fundamentals, optical vs SAR, grounding, and hallucination prevention.
  - [`docs/FINAL_DEMO_HANDOFF.md`](file:///c:/Desktop/SatQuery%20-AG/docs/FINAL_DEMO_HANDOFF.md): Candidate freeze reference, readiness verdict, and startup commands.
- **Verification Evidence:**
  - Automated Rehearsals (`backend/scripts/rehearse_demo.py`): **6/6 passed (100%)**, telemetry in `backend/tmp/rehearsal_output/rehearsal_summary.json`.
  - Full repo verification (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED** (`Non-database repository verification passed.`).
  - Backend: 295 Pytests passed, 0 failed, strict Mypy (137 source files) clean, Ruff clean.
  - Frontend: 297 Vitests passed across 68 test files, strict TypeScript (`tsc --noEmit`) clean, Next.js 16.3.4 production build clean.
- **Current State & Sprint Closure:**
  - Final Readiness Verdict: **GO (SIH DEMONSTRATION READY)**.
  - Phase 7B officially concludes the **SIH Demo-Readiness Sprint**. Zero prompts remain in this sprint.
  - The broader 16-phase SatQuery product roadmap (Phases 0–15 in `ROADMAP.md`) remains preserved. Post-hackathon work resumes from Phase 8.

## Phase 7A — Final Validation, Stability and Release-Candidate Hardening — 2026-09-21

- **Scope & Objectives:**
  - Hardened full application stack for SIH demo readiness, validating user journeys across all 5 analysis modes (`change_detection`, `multimodal_analysis`, `spectral_analysis`, `visual_question_answering`, `query`).
  - Resolved report format union typing in `ReportExportDialog` (`hasFormat` type guard).
  - Verified scientific accounting (percentage denominator $V = \text{shared\_valid\_pixels}$, coverage denominator $A = \text{total\_aoi\_area}$), epistemic segregation (visual model predictions segregated and never added to measured change totals), and transparent mock/fallback flags.
- **Backend Architecture & Quality:**
  - Preserved all 295 unit/integration tests with 0 failures (`test_database_integration.py` deselected due to no local PostGIS container).
  - Ruff check & format clean, strict Mypy (137 source files) clean.
- **Frontend Architecture & Quality:**
  - TypeScript typecheck (`tsc --noEmit`), Biome lint & format, and Next.js 16.3.4 production build clean.
  - All 297 Vitest unit tests across 68 test files passed cleanly.
- **Verification Evidence:**
  - Full repo verification (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED** (`Non-database repository verification passed.`).
- **Current State & Stop Boundary:** Phase 7A is **COMPLETE**. Stopped before Phase 7B (Demo Rehearsal and Handoff).
- **Exact Next Recommended Task:** `Phase 7B — Demo Rehearsal and Handoff`.

## Phase 6B — Full Workflow Integration and Blocker Fixes — 2026-09-21

- **Scope & Objectives:**
  - Integrated end-to-end user experience across all analysis modes (`change_detection`, `multimodal_analysis`, `spectral_analysis`, `visual_question_answering`, `query`), connecting previously isolated panels into a reactive, step-by-step pipeline.
  - Extended workflow state machine (`workspace-workflow.ts`) to manage 5 sequential stages: `awaiting_aoi` -> `awaiting_date_range` -> `ready_for_pairing` / `ready_for_scene_discovery` -> `ready_for_raster_prep` -> `ready_for_analysis` -> `analysis_completed` / `ready_for_export`.
  - Built interactive `WorkflowReadinessBanner` with dynamic readiness pills (Mode, AOI, Dates, Scenes, Analysis, Dossier) and quick action triggers.
  - Synchronized active change detection and fusion results into query assistant context snapshots and report export dossiers.
  - Resolved routine blocker issues in `SceneContainer`, `RasterPreparationPanel`, `MultimodalFusionPanel`, and backend `ReportService`.
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/services/report_service.py`: Fixed `ReportStatus.PARTIALLY_COMPLETED` typing and resolved upstream snapshots cleanly from `change_service` and `fusion_service` cache with proper `AOIGeometry`.
  - Preserved all 295 backend unit tests.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/workspace-workflow.ts`: Extended `WorkflowStep`, `WorkflowAction`, and `WorkflowContext` to cover all 5 pipeline stages.
  - `frontend/src/lib/workspace-workflow.test.ts`: Added unit tests covering all multi-step transitions across single-scene and temporal pairing modes (9/9 passed).
  - `frontend/src/components/workspace/workflow-readiness-banner.tsx`: Updated banner with dynamic readiness pills and enabled action triggers via `onTriggerAction`.
  - `frontend/src/components/workspace/scene-container.tsx`: Properly wired scene ID references (`.id`), destructured workflow notification callbacks, and corrected `MultimodalFusionPanel` callback props.
  - `frontend/src/components/workspace/workspace-shell.tsx`: Full reactive integration between state, assistant, and report export dialog.
- **Verification Evidence:**
  - Full repo verification (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED** (`Non-database repository verification passed.`).
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (297 passed across 68 test files), Next.js 16.3.4 production build clean.
- **Current State & Stop Boundary:** Phase 6B is **COMPLETE**. Stopped before Phase 7A (Final Validation and Stability).
- **Exact Next Recommended Task:** `Phase 7A — Final Validation and Stability`.

## Phase 6A — Evidence-Based Reports and Export — 2026-09-21

- **Scope & Objectives:**
  - Implemented immutable analysis snapshot capture, print-ready PDF rendering via ReportLab Platypus, standards-compliant portable JSON export, and full frontend export workflow.
  - Snapshot Capture & Epistemic Segregation: Server captures an immutable `ReportSnapshot` versioned with schema `"1.0.0"` and computes a deterministic SHA-256 integrity hash.
  - Epistemic Category Discipline: Computed physical measurements, model predictions (visual bounding boxes segregated and never added to measured change totals), AI interpretations, and limitations are kept distinct.
  - Scientific Area & Denominator Accounting: Class percentages strictly use valid observed comparison area as denominator ($V$), and coverage uses total AOI area ($A$).
  - Prominent Mock / Fallback Labelling: Synthetic and mock demo data are prominently disclaimed in both PDF banner and JSON properties (`is_mock_data: true`, `data_origin: "mock"`).
  - Security & Sanitization: Safe HTML entity escaping of user titles and questions in PDF flowable paragraphs.
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/api/schemas/reports.py`: Strict Pydantic models for snapshots, figures, requests, format statuses, and responses.
  - `backend/src/satquery/services/report_builder.py`: Snapshot assembly engine resolving AOI, scenes, metrics, answers, observations, and figure manifests.
  - `backend/src/satquery/services/pdf_renderer.py`: ReportLab Platypus renderer with custom `NumberedCanvas` ("Page X of Y"), dark slate typography, quantitative tables with explicit denominators, disclaimed model predictions, warnings, and provenance register.
  - `backend/src/satquery/services/report_service.py`: Orchestrates snapshot lifecycle, PDF/JSON generation, caching, and stream downloads.
  - `POST /api/v1/reports/request`, `POST /api/v1/reports/snapshot-export`, `GET /api/v1/reports/{report_id}`, `GET /api/v1/reports/{report_id}/snapshot`, `GET /api/v1/reports/{report_id}/download/{format}`.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/report-contracts.ts` & `frontend/src/lib/report-client.ts`: Zod schemas and typed API client.
  - `frontend/src/lib/use-report-export.ts`: Custom hook managing dialog state, format toggles, section customization, generation progress, and download actions.
  - `frontend/src/components/workspace/report-export-dialog.tsx`: Accessible dialog with target context card, format chips, section checkboxes, progress spinner, completed download buttons with SHA-256 digest, and retry alerts.
  - `frontend/src/components/workspace/results-tabs.tsx`: "Export Dossier" trigger in results header.
  - `frontend/src/components/workspace/workspace-shell.tsx`: Full integration with active analysis context.
- **Verification Evidence:**
  - Full repo verification (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED** (`Non-database repository verification passed.`).
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (137 source files) clean, Pytest (295 passed, 0 failed, 1 deselected).
  - Backend Known-Answer Fixture Test: Verified 2.00 km² AOI, 1.00 km² valid comparison area (50% coverage), 0.20 km² gain (20%), 0.10 km² loss (10%), 0.65 km² stable (65%), 0.05 km² uncertain (5%), 1.00 km² excluded (50%), and 0.03 km² model box strictly NOT added to change totals.
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck (`tsc --noEmit`) clean, Vitest (296 passed across 68 test files), Next.js 16.3.4 production build clean.
  - Sample Demo Artifacts: Generated `backend/tmp/reports_demo/satquery_report_known_answer.pdf`, `satquery_report_known_answer.json`, `satquery_report_synthetic_mock.pdf`, `satquery_report_synthetic_mock.json`.
- **Current State & Stop Boundary:** Phase 6A is **COMPLETE**. Stopped before Phase 6B (Full Workflow Integration and Blocker Fixes).
- **Exact Next Recommended Task:** `Phase 6B — Full Workflow Integration and Blocker Fixes`.

## Phase 5B — Image VQA and Verified Spatial Grounding — 2026-09-20

- **Scope & Objectives:**
  - Implemented Visual Question Answering (VQA) from actual satellite imagery pixels and mathematically verified, traceable placement of visual model observations onto the geospatial map.
  - Epistemic Separation: Model visual observations (`observation_source`: `model_prediction`, `semantic_status`: `unverified`) are kept strictly distinct from computed evidence (spectral/change/fusion metrics). Spatial overlap indicates candidate co-occurrence, not verified ground truth.
  - Canonical Coordinate Normalization: Continuous pixel-edge coordinates $[xmin, ymin, xmax, ymax]$ on $[0.0, 1.0]$ with top-left origin $(0, 0)$.
  - Exact 6-Step Inverse Transformation Pipeline:
    1. Denormalize to submitted pixel dimensions: $px = x \cdot W_{\text{sub}}, py = y \cdot H_{\text{sub}}$.
    2. Undo recorded padding: $cx = px - \text{pad\_left}, cy = py - \text{pad\_top}$. Wholly-in-padding boxes flagged as `invalid_padding_only`.
    3. Undo resizing: scale factor $\frac{W_{\text{crop}}}{W_{\text{resize}}}, \frac{H_{\text{crop}}}{H_{\text{resize}}}$.
    4. Undo cropping: add column offset $col_0$, row offset $row_0$.
    5. Apply raster affine transform matrix to compute projected coordinates $(X_{\text{crs}}, Y_{\text{crs}})$.
    6. Reproject projected coordinates to WGS84 (EPSG:4326) GeoJSON using `pyproj.Transformer.from_crs(manifest.crs, "EPSG:4326", always_xy=True)` with RFC 7946 $[lon, lat]$ ordering.
  - Evidence Overlap Association: Computes spatial intersection between grounded visual observation polygon and computed change/spectral/fusion regions (`compute_evidence_overlap`).
  - Non-Georeferenced Image Discipline: Sets `image_only_no_georeference` when CRS is missing or unverified, without guessing coordinates.
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/api/schemas/visual.py`: Comprehensive Pydantic v2 schemas and enums.
  - `backend/src/satquery/services/spatial_grounding.py`: Inverse transformation engine, provider convention adapters, overlap analyzer.
  - `backend/src/satquery/services/visual_image_preparer.py`: Clean visual PNG renderer, SHA-256 digest computer, immutable `ImageManifest` creator.
  - `backend/src/satquery/services/visual_query_service.py`: Main visual Q&A orchestrator.
  - `backend/src/satquery/providers/ai/`: Added `VisualQARequest`/`VisualQAResponse` and `generate_visual_qa` across protocol, Mock, and Gemini adapters.
  - `GET /api/v1/query/visual/capabilities`, `POST /api/v1/query/visual`, `GET /api/v1/query/manifests/{manifest_id}`.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/visual-contracts.ts` & `frontend/src/lib/visual-client.ts`: Zod schemas and typed API client.
  - `frontend/src/lib/use-visual-qa.ts`: Custom hook managing visual queries, operation modes (`describe`, `locate_feature`, `compare_pair`), manifest caching, and highlighted map overlays.
  - `frontend/src/components/workspace/assistant-panel.tsx`: VQA mode toggle, operation selector, image count notice, grounded visual observation cards with confidence badges.
  - `frontend/src/components/workspace/results-tabs.tsx`: Visual prediction cards with canonical boxes, grounding badges, and "Highlight on Map" triggers.
  - `frontend/src/components/workspace/workspace-shell.tsx`: Full integration with scene selection and MapLibre overlay layers.
- **Verification Evidence:**
  - Full repo script (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED**.
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (132 source files) clean, Pytest (287 passed, 0 failed, 1 deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck clean, Vitest (287 passed across 66 test files), Next.js 16.3.4 production build clean.
- **Current State & Stop Boundary:** Phase 5B is **COMPLETE**. Stopped before Phase 6 (Confidence, Warnings & Report Generation).
- **Exact Next Recommended Task:** `Antigravity Phase 6A — Confidence Calculation, Warning Codes and Dossier Export (PDF/JSON)`.

## Phase 5A — Query Routing and Evidence-Grounded AI Answers — 2026-09-20

- **Scope & Objectives:**
  - Implemented end-to-end natural-language query routing, multi-factor input sufficiency checking, evidence retrieval across optical/spectral/change/fusion results, server-side claim validation, zero-causal-hallucination grounding, and bidirectional map linking.
  - Deterministic Intent Routing: regex-backed rule hierarchies for 9 intents (`evidence_summary`, `spectral_summary`, `change_summary`, `multimodal_summary`, `locate_evidence`, `explain_quality`, `needs_processing`, `clarification_required`, `unsupported`).
  - Strict Causal Grounding: Positive NDBI is mapped to "Built-up-related spectral increase" (never "confirmed construction"); NDVI decrease to "Vegetation-related spectral decrease" (never "confirmed deforestation"); SAR delta to "backscatter response change" (never "confirmed flooding").
  - Scientific Percentage & Area Denominators: Percentages divide strictly by `shared_valid_pixels` ($V$) or `jointly_observable_area_km2` ($J$). Total AOI percentages are never conflated with valid comparison subsets.
  - Deterministic Fallback Mode: When AI provider keys are missing/unavailable/disabled or model outputs fail validation, the system automatically degrades to `deterministic_summary` ("Evidence summary — AI explanation unavailable") with verified claim cards and map references.
  - Bidirectional Map Grounding: Interactive citation chips and candidate spatial region cards link directly to map geometry and coordinate bounds.
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/api/schemas/query.py`: Comprehensive Pydantic v2 models.
  - `backend/src/satquery/services/query_router.py`: Intent classifier and query plan generator.
  - `backend/src/satquery/services/evidence_retriever.py`: Multi-source evidence aggregator with lineage deduplication.
  - `backend/src/satquery/services/sufficiency_checker.py`: Input sufficiency evaluator with actionable `SuggestedNextAction` targets.
  - `backend/src/satquery/services/claim_validator.py`: Grounding enforcer, denominator validator, and claim card formatter.
  - `backend/src/satquery/services/query_service.py`: Main workflow orchestrator with execution trace recording.
  - `GET /api/v1/query/capabilities`, `POST /api/v1/query/ask`.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/query-contracts.ts` & `frontend/src/lib/query-client.ts`: Zod schemas and typed client.
  - `frontend/src/lib/use-query-assistant.ts`: Custom hook managing context snapshots, fingerprinting, query lifecycle, stale invalidation, and highlight state.
  - `frontend/src/components/workspace/assistant-panel.tsx`: Query input, 500-char counter, loading stages, stale context warning, error retry, suggestion chips.
  - `frontend/src/components/workspace/results-tabs.tsx`: Enhanced Answer tab (claims, metrics, limitations, actions), Evidence tab (items, regions, warnings), and Activity tab (execution trace timeline).
  - `frontend/src/components/workspace/workspace-shell.tsx`: Full integration with workspace state and AOI contracts.
- **Verification Evidence:**
  - Full repo script (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`): **PASSED**.
  - Backend: Ruff check clean, Ruff format clean, strict Mypy (126 source files) clean, Pytest (276 passed, 0 failed, 1 deselected).
  - Frontend: Biome format clean, Biome lint clean, TypeScript typecheck clean, Vitest (275 passed across 63 test files), Next.js 16.3.4 production build clean.
- **Current State & Stop Boundary:** Phase 5A is **COMPLETE**. Stopped before Phase 5B (Image VQA and Verified Spatial Grounding).

## Phase 4C — Multimodal Optical and SAR Evidence Fusion — 2026-09-20

- **Scope & Objectives:**
  - Implemented multimodal evidence fusion combining optical change results (from Phase 4B) and calibrated SAR backscatter change pairs (from Phase 3B prepared SAR rasters).
  - SAR differencing: calibrated linear power converted to decibels $\text{dB} = 10 \cdot \log_{10}(\text{power})$, computing $\Delta\text{dB} = 10 \cdot \log_{10}(\text{power}_{\text{after}} / \text{power}_{\text{before}})$ without artificial epsilon clamping.
  - 4-Role Temporal Analysis: tracks acquisition timestamps across `optical_before`, `optical_after`, `sar_before`, `sar_after`, calculating before/after offsets and interval overlap ratios against temporal tolerance (default 30 days).
  - AOI Coverage Partitioning: strictly partitions total AOI into Jointly Observable ($J = O \cap R$), Optical Coverage Only, SAR Coverage Only, and Neither Sensor Available.
  - 5-State Joint Observation Classification within $J$: `both_detect_change` (amber), `optical_response_only` (emerald), `sar_response_only` (blue), `neither_above_threshold` (slate), `uncertain` (purple).
  - Percentage Denominator Discipline: All joint state percentages strictly use $J = \text{jointly\_observable\_area\_km2}$ as the denominator; percentages are `null` when $J = 0$.
  - Vectorized Candidate Regions extracted with `rasterio.features.shapes` into GeoJSON polygons with calibrated confidence and explainable rules.
  - Discrete 5-color RGBA preview PNG overlays.
  - Scientific Grounding Disclaimer: Co-observed response change is strictly sensor response co-occurrence, *not* verified physical ground truth (e.g. flood inundation or building demolition).
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/api/schemas/fusion.py`: Pydantic v2 schemas and enums.
  - `backend/src/satquery/services/sar_engine.py`: SAR radiometric differencing and unit validation engine.
  - `backend/src/satquery/services/fusion_engine.py`: Multimodal fusion, coverage partitioning, joint classification, metrics calculation, and region vectorization engine.
  - `backend/src/satquery/services/fusion_service.py`: Service orchestration and `AssetStore` integration (`ast-fusprv-*`).
  - `GET /api/v1/fusion/capabilities`, `POST /api/v1/fusion/analyze`, `GET /api/v1/fusion/results/{result_id}`, `GET /api/v1/fusion/results/{result_id}/overlay`.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/fusion-contracts.ts` & `frontend/src/lib/fusion-client.ts`: Zod validators and typed API client.
  - `frontend/src/lib/use-multimodal-fusion.ts`: Custom hook managing observation inputs, tolerances, thresholds, and result caching.
  - `frontend/src/components/workspace/multimodal-fusion-panel.tsx`: Interactive panel with observation stream selector, 4-role timeline, coverage partitioning cards, joint state breakdown table, scientific grounding disclaimer, candidate fused regions list, and map overlay controls.
- **Verification Evidence:**
  - Backend: 260 Pytest passed (0 failed, 1 deselected), strict Mypy clean, Ruff check & format clean.
  - Frontend: 12/12 fusion tests passed (contracts, client, hook, UI panel).
- **Current State & Stop Boundary:** Phase 4C is **COMPLETE**. Stopped before Phase 5A (Multimodal Agent & VLM Reasoning).

## Phase 4B — Pixel-Level Change Detection and Change Evidence — 2026-09-20

- **Scope & Objectives:**
  - Implemented end-to-end pixel-level change detection pipeline on Phase 3B co-registered raster pairs.
  - Implemented 5 registered change methods: `ndvi_difference`, `ndwi_difference`, `ndbi_difference`, `absolute_index_difference`, and `multiband_change_magnitude`.
  - Enforced strict percentage calculation discipline: all change percentages strictly divide by `shared_valid_pixels` (never total AOI or bounding box).
  - Enforced strict semantic separation: positive NDBI difference is labeled as *“Built-up-related spectral increase”* and never as *“confirmed construction”*.
  - Implemented threshold strategies (`fixed`, `standard_deviation`, `percentile`, `otsu`, `manual`) and noise filtering (`min_cluster_size_pixels`).
  - Implemented vectorized GeoJSON change regions, multi-factor confidence breakdown, Float32 GeoTIFF difference rasters, and continuous/discrete (3-class mask) PNG overlays.
- **Backend Architecture & Endpoints:**
  - `backend/src/satquery/api/schemas/change.py`: Strict Pydantic v2 contracts.
  - `backend/src/satquery/services/change_registry.py`: Authoritative registry with mathematical formulas, ranges, sensors, and limitations.
  - `backend/src/satquery/services/change_engine.py`: Grid alignment validator, difference array computer, threshold segmenter, metrics calculator, and polygon vectorizer.
  - `backend/src/satquery/services/change_service.py`: Orchestration & `AssetStore` integration (`ast-chg-*`, `ast-chgprv-*`, `ast-chgcls-*`).
  - `GET /api/v1/change/methods`, `POST /api/v1/change/calculate`, `GET /api/v1/change/results/{result_id}`, `GET /api/v1/change/results/{result_id}/overlay`.
- **Frontend Architecture & Components:**
  - `frontend/src/lib/change-contracts.ts` & `frontend/src/lib/change-client.ts`: Zod validators and typed API client.
  - `frontend/src/lib/use-change-detection.ts`: Custom hook managing method selection, thresholds, overlay mode, and automatic input invalidation.
  - `frontend/src/components/workspace/change-detection-panel.tsx`: Interactive panel with method selector, threshold controls, metrics cards, scientific disclaimer banner, candidate regions table, overlay mode controls, and provenance details.
- **Verification Evidence:**
  - Full repository test script (`powershell.exe -ExecutionPolicy Bypass -File .\scripts\verify.ps1`) PASSED cleanly.
  - Backend: 245 Pytest passed (0 failed, 1 deselected), strict Mypy (105 source files) clean, Ruff check & format clean.
  - Frontend: 251 Vitest passed across 56 test files (100%), Biome lint & format clean, Next.js 16.3.4 production build clean.
- **Current State & Stop Boundary:** Phase 4B is **COMPLETE**. Stopped before Phase 5. Awaiting user confirmation before proceeding to Phase 5.


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

## Current state

- **Active phase:** Phase 3B is **COMPLETE**. Phase 4A is **READY FOR EXECUTION**.
- **Status:** Phase 0A through Phase 3B are 100% complete and verified.
- **Stop boundary:** Stop before Phase 4A. Await user confirmation before beginning Phase 4A.
- **Exact next recommended task:** `Antigravity Phase 4A — Spectral Indices and Evidence Generation`.
- **Carried gates:** Phase 1 real PostGIS/migration/readiness, Phase 2 browser, and Phase 3 browser/authenticated-owner/persistence evidence remain unwaived and unpassed.
- **Repository state:** Non-database repository verification script (`scripts/verify.ps1`) passes completely.
- **Local verification services:** frontend is running on `http://localhost:3000`; backend factory is on `http://[::1]:8000`. PostgreSQL/PostGIS is verified via Docker container when launched.
- **Carried gates:** Phase 1 real PostGIS/migration/readiness, Phase 2 browser, and Phase 3 browser/authenticated-owner/persistence evidence remain unwaived and unpassed.
- **Repository state:** Git metadata is unavailable to the workspace. Task 5G adds browser-local viewer draft state only: no database migration, server persistence, provider secret, scientific processing, or runtime model.
- **Local verification services:** the SatQuery frontend is running on `http://localhost:3000`; the current backend factory is running on IPv6 loopback `http://[::1]:8000`. An unrelated project owns `127.0.0.1:8000`, so do not use or stop that IPv4 service. PostgreSQL/PostGIS remains unavailable.

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
2. Preserve completed Phase 4 tasks 4A–4G and Phase 5 tasks 5A–5H, including the stable-ID provider boundary and scientific-analysis exclusions.
3. Stop before Phase 6. Its authoritative title/scope is unavailable; do not invent or start it without explicit authorization and source wording.
4. When Docker is available, run `scripts/verify-database.ps1`; require the integration test, exact Alembic head, and readiness HTTP 200 before closing the carried Phase 1 database gate.
5. Never reinterpret browser rendering, catalogue availability, or asset access as database readiness or scientific analysis evidence.

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

## Files changed by Phase 2B

- Backend Schemas, Routes & Services:
  - `backend/src/satquery/api/schemas/temporal.py` (authoritative Pydantic v2 temporal models)
  - `backend/src/satquery/api/schemas/__init__.py` (schema exports)
  - `backend/src/satquery/services/temporal_pairing.py` (Sutherland-Hodgman clipping engine, multi-factor compatibility evaluation, and recommendation algorithm)
  - `backend/src/satquery/api/routes/scenes.py` (`POST /scenes/temporal-search` and `POST /scenes/validate-pair` endpoints)
- Backend Tests:
  - `backend/tests/test_temporal_pairing.py` (18 deterministic unit tests for clipping, scoring, blocking rules, and recommendations)
  - `backend/tests/test_temporal_api.py` (3 API route integration tests)
- Frontend Contracts, Clients & State:
  - `frontend/src/lib/analysis-contracts.ts` (exported `boundingBoxSchema`)
  - `frontend/src/lib/temporal-contracts.ts` (Zod schemas and TypeScript types)
  - `frontend/src/lib/temporal-contracts.test.ts` (7 contract tests)
  - `frontend/src/lib/temporal-client.ts` (API client functions with abort signals)
  - `frontend/src/lib/temporal-client.test.ts` (2 client tests)
  - `frontend/src/lib/use-temporal-pairing.ts` (reactive temporal hook)
  - `frontend/src/lib/use-temporal-pairing.test.tsx` (4 hook tests)
  - `frontend/src/lib/use-workspace-draft.ts` (dual date and scene draft persistence)
- Frontend UI Components:
  - `frontend/src/components/workspace/workflow-date-filter-panel.tsx` (dual date pickers & presets)
  - `frontend/src/components/workspace/workflow-date-filter-panel.test.tsx` (3 tests)
  - `frontend/src/components/workspace/temporal-pairing-panel.tsx` (2-period candidate UI, recommendation banner, factor breakdown)
  - `frontend/src/components/workspace/temporal-pairing-panel.test.tsx` (3 component tests)
  - `frontend/src/components/workspace/scene-container.tsx` (wired temporal pairing panel)
  - `frontend/src/components/workspace/workspace-shell.tsx` (wired bi-temporal state)
- Governing Documentation & Checkpoints:
  - `CURRENT_PHASE.md`
  - `SESSION_HANDOFF.md`

## Handoff maintenance rule

After every major task, refresh this file with exact status, changed files, checks, errors/blockers, decisions, remaining work, and the precise resume action. Include no secrets or fabricated/unverified evidence.
