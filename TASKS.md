# Antigravity Task Breakdown & Execution Plan

This document details the granular, independently executable tasks required to complete the SIH-ready vertical slice.

---

## Task Matrix Overview

| Task ID | Phase Name | Primary Scope & Objective | Deliverables | Status |
|---|---|---|---|---|
| **TASK-0A** | **Phase 0A** | Architecture & Project Control Documents | Updated `PRD.md`, `TRD.md`, `ROADMAP.md`, `TASKS.md` | **COMPLETE** |
| **TASK-0B** | **Phase 0B** | Pydantic (Backend) & Zod (Frontend) Contracts | 16 mirrored schemas in Python & TypeScript | **COMPLETE** |
| **TASK-0C** | **Phase 0C** | Configuration, Provider Interfaces & Safe Mock Boundary | Validated settings, satellite & AI provider interfaces, mock adapters, safe fallback | **COMPLETE** |
| **TASK-1A** | **Phase 1A** | Existing Map Baseline & AOI Interaction Validation | MapLibre baseline, Terra Draw tools, geodesic area, bounds, GeoJSON, authoritative backend validator endpoint (`/api/v1/aoi/validate`) | **COMPLETE** |
| **TASK-1B** | **Phase 1B** | Map Workspace UX and AOI Persistence | Complete map workspace polish, keyboard accessibility, persistent AOI sessions, and multi-mode options gating | **COMPLETE** |
| **TASK-2A** | **Phase 2A** | Real Satellite Catalog Discovery Integration | STAC Sentinel-2 L2A search (`POST /api/v1/scenes/search`), provider fallback, cards, footprint display | **COMPLETE** |
| **TASK-2B** | **Phase 2B** | Before/After Scene Selection and Temporal Pairing | Scene A & B chronological assignment, overlap check, pair validation | **COMPLETE** |
| **TASK-3A** | **Phase 3A** | Analysis-Grade Imagery Retrieval & Preview Rendering | Bounded AOI raster retrieval, RasterValidator, AssetStore caching, MapLibre preview, Swipe/Split comparison | **COMPLETE** |
| **TASK-3B** | **Phase 3B** | Raster Harmonization, Reprojection & Analysis Preparation | Scientific co-registration, reprojection, and multi-band alignment | **COMPLETE** |
| **TASK-4A** | **Phase 4A** | Spectral Indices and Evidence Generation | Spectral math (NDVI/NDWI/NDBI/EVI/SAVI/MNDWI), band math engine, statistics, evidence generation | **COMPLETE** |
| **TASK-4B** | **Phase 4B** | Pixel-Level Change Detection and Change Evidence | Bi-temporal differencing on co-registered grids, discrete classification (+1/-1/0), noise filtering, area metrics with shared valid denominator, vectorized GeoJSON regions, and continuous/discrete overlays | **COMPLETE** |
| **TASK-4C** | **Phase 4C** | Multimodal Optical and SAR Evidence Fusion | SAR radiometric differencing ($\Delta\text{dB}$), 4-role temporal tolerance, AOI coverage partition ($J = O \cap R$), 5-state joint classification, discrete 5-color overlay | **COMPLETE** |
| **TASK-5A** | **Phase 5A** | Query Routing and Evidence-Grounded AI Answers | Intent router (9 intents), context snapshot, input sufficiency checker, claim validator with strict grounding, query service orchestrator, deterministic fallback, UI assistant & result tabs | **COMPLETE** |
| **TASK-5B** | **Phase 5B** | Image VQA and Verified Spatial Grounding | Visual Question Answering with actual raster pixels, canonical coordinate normalization, exact 6-step inverse spatial transform, provider adapters, evidence overlap association, and UI observation cards | **COMPLETE** |
| **TASK-6** | **Phase 6** | Confidence, Warnings & Report Generation | Score calculation, warning codes, PDF/JSON export | **NEXT TASK** |
| **TASK-7** | **Phase 7** | End-to-End SIH Demo Validation | Full 11-step rehearsal, test suite, and audit | **PLANNED** |

---

## Detailed Task Specifications

### Antigravity Phase 1A — Existing Map Baseline and AOI Interaction Validation
* **Objective:** Establish a robust interactive map baseline (MapLibre GL JS `6.9.0`) with Terra Draw AOI polygon/rectangle creation, coordinate bounding box input, GeoJSON import/export, client-side Turf area calculations, and authoritative backend geometric validation via `POST /api/v1/aoi/validate`.
* **Backend Target:** `backend/src/satquery/api/schemas/aoi.py`, `backend/src/satquery/services/aoi_validator.py`, `backend/src/satquery/api/routes/aoi.py`.
* **Frontend Target:** `frontend/src/lib/aoi-validation-contracts.ts`, `frontend/src/lib/aoi-validation-client.ts`, `frontend/src/components/workspace/scene-container.tsx`, `frontend/src/lib/aoi.ts`.
* **Verification:** Full automated test suite passed: 142 backend pytest tests, strict Mypy (64 source files), Ruff checks; 126 frontend vitest tests (29 files), Biome lint/format, TypeScript typecheck, Next.js 16.3.4 production build. Non-database repository verification passed via `scripts/verify.ps1`.

### Antigravity Phase 1B — Map Workspace UX and AOI Persistence
* **Objective:** Refine map workspace user experience, responsive panel transitions, keyboard shortcuts, multi-tab persistent drafts, and analysis mode gating based on validated AOI properties.
* **Verification:** 165 vitest unit/component tests passing, Biome linting/formatting clean.

### Antigravity Phase 2A — Real Satellite Catalog Discovery Integration
* **Objective:** Implement real end-to-end satellite imagery discovery workflow: Validated AOI $\to$ Date and filter selection $\to$ Backend scene search (`POST /api/v1/scenes/search`) $\to$ Element 84 Earth Search STAC v1 $\to$ Normalized `SatelliteScene` items $\to$ Frontend discovery panel & footprints.
* **Backend Target:** `backend/src/satquery/providers/satellite/real_adapter.py`, `backend/src/satquery/api/routes/scenes.py`, `backend/src/satquery/api/router.py`.
* **Frontend Target:** `frontend/src/lib/scene-search-contracts.ts`, `frontend/src/lib/scene-search-client.ts`, `frontend/src/components/workspace/imagery-discovery-panel.tsx`.
* **Verification:** Pytest 151 passed, Mypy strict clean across 48 source files, Vitest 165 passed across 39 files, Next.js 16.3.4 production build clean.

### Phase 2B: Before/After Scene Selection and Temporal Pairing
* **Objective:** Enable multi-scene selection for two-date temporal analysis, enforcing chronological ordering ($T_A < T_B$) and spatial bounding box overlap verification.
* **Backend Target:** `backend/src/satquery/api/schemas/temporal.py`, `backend/src/satquery/services/temporal_service.py`, `backend/src/satquery/api/routes/temporal.py`.
* **Frontend Target:** `frontend/src/components/workspace/temporal-pairing-panel.tsx`, `frontend/src/lib/use-temporal-pairing.ts`, `frontend/src/lib/temporal-client.ts`.
* **Verification:** Pytest 169 passed, Vitest 192 passed across 44 files.

### Antigravity Phase 3A — Analysis-Grade Imagery Retrieval and Preview Rendering
* **Objective:** Implement secure, bounded raster retrieval, validation, and multitemporal preview rendering for single scenes and temporal pairs.
* **Backend Target:** `backend/src/satquery/api/schemas/imagery.py`, `backend/src/satquery/services/raster_validator.py`, `backend/src/satquery/services/asset_store.py`, `backend/src/satquery/services/imagery_service.py`, `backend/src/satquery/api/routes/imagery.py`.
* **Frontend Target:** `frontend/src/lib/imagery-contracts.ts`, `frontend/src/lib/imagery-client.ts`, `frontend/src/lib/use-imagery.ts`, `frontend/src/lib/imagery-map-layer.ts`, `frontend/src/components/workspace/imagery-preview-panel.tsx`, `frontend/src/components/workspace/temporal-comparison-panel.tsx`.
* **Verification:** Pytest 194 passed (100%), Ruff check & format clean, Mypy strict (79 files) clean, Vitest 214 passed across 48 files (100%), Next.js 16.3.4 production build clean. Full repository verification passed via `scripts/verify.ps1`.
* **Live Validation & Limitations:** Verified deterministic offline mock and STAC asset resolution paths. Full multi-gigabyte scene downloads strictly prevented in favor of bounded AOI requests. Scientific co-registration and index math deferred to Phase 3B/4.

### Antigravity Phase 3B — Raster Harmonization, Reprojection & Analysis Preparation
* **Objective:** Implement a scientifically defensible raster preparation engine converting Phase 3A imagery assets into strictly co-registered, analysis-ready rasters for single-scene or multitemporal analysis.
* **Backend Target:** `backend/src/satquery/api/schemas/preparation.py`, `backend/src/satquery/services/raster_harmonizer.py`, `backend/src/satquery/services/preparation_service.py`, `backend/src/satquery/api/routes/preparation.py`.
* **Frontend Target:** `frontend/src/lib/preparation-contracts.ts`, `frontend/src/lib/preparation-client.ts`, `frontend/src/lib/use-raster-preparation.ts`, `frontend/src/components/workspace/raster-preparation-panel.tsx`.
* **Verification:** Pytest 209 passed (100%), Ruff check & format clean, Mypy strict (87 files) clean, Vitest 226 passed across 52 test files (100%), Next.js 16.3.4 production build clean. Non-database verification passed via `scripts/verify.ps1`.
* **Live Validation & Limitations:** Verified polygon clipping, UTM auto-selection, resolution harmonization strategies, rigid temporal grid alignment ($<10^{-6}$ transform delta), shared validity mask generation, and readiness scoring. Spectral indices (NDVI/NDWI) and differencing deferred to Phase 4A.

### Phase 4A: Spectral Indices and Evidence Generation
* **Objective:** Implement rigorous mathematical calculation of spectral indices ($\text{NDVI}$, $\text{NDWI}$, $\text{NDBI}$, $\text{EVI}$, $\text{SAVI}$, $\text{MNDWI}$), physical thresholding, pixel difference classification, and evidence layer packaging.
* **Backend & Frontend Targets:** `backend/src/satquery/api/schemas/spectral.py`, `backend/src/satquery/services/spectral_registry.py`, `backend/src/satquery/services/spectral_engine.py`, `backend/src/satquery/services/spectral_service.py`, `backend/src/satquery/api/routes/spectral.py`.
* **Verification:** 229 backend pytest tests passed (100%), strict mathematical tests on synthetic Float32 GeoTIFF arrays, boundary checks for $[-1.0, 1.0]$ ranges, edge case tests for division by zero.

### Phase 4B: Pixel-Level Change Detection and Change Evidence
* **Objective:** Implement a transparent, scientifically defensible pixel-level change-detection pipeline using Phase 3B co-registered rasters and Phase 4A spectral measurements.
* **Backend Target:** `backend/src/satquery/api/schemas/change.py`, `backend/src/satquery/services/change_registry.py`, `backend/src/satquery/services/change_engine.py`, `backend/src/satquery/services/change_service.py`, `backend/src/satquery/api/routes/change.py`.
* **Frontend Target:** `frontend/src/lib/change-contracts.ts`, `frontend/src/lib/change-client.ts`, `frontend/src/lib/use-change-detection.ts`, `frontend/src/components/workspace/change-detection-panel.tsx`.
* **Verification:** Pytest 245 passed (100%), Mypy strict (105 files) clean with 0 errors, Ruff lint & format check clean, Vitest 251 passed across 56 test files (100%), Biome lint & format clean, Next.js 16.3.4 production build clean. Full verification passed via `scripts/verify.ps1`.

### Phase 4C: Multimodal Optical and SAR Evidence Fusion
* **Objective:** Implement an explainable multimodal evidence fusion subsystem combining optical change results with calibrated SAR backscatter pairs ($\Delta\text{dB}$), evaluating 4-role temporal offsets, partitioning AOI coverage ($J = O \cap R$), and classifying 5 joint observation states.
* **Backend Target:** `backend/src/satquery/api/schemas/fusion.py`, `backend/src/satquery/services/sar_engine.py`, `backend/src/satquery/services/fusion_engine.py`, `backend/src/satquery/services/fusion_service.py`, `backend/src/satquery/api/routes/fusion.py`.
* **Frontend Target:** `frontend/src/lib/fusion-contracts.ts`, `frontend/src/lib/fusion-client.ts`, `frontend/src/lib/use-multimodal-fusion.ts`, `frontend/src/components/workspace/multimodal-fusion-panel.tsx`.
* **Verification:** Pytest 260 passed (100%), Vitest 12/12 fusion tests passed (100%), Biome lint/format clean.

### Phase 5A: Query Routing and Evidence-Grounded AI Answers
* **Objective:** Implement a natural-language query routing and evidence-grounded answer workflow connecting user questions to active workspace evidence, enforcing zero causal hallucinations, deterministic input sufficiency checks, server-validated quantitative claims, and bidirectional map references.
* **Backend Target:** `backend/src/satquery/api/schemas/query.py`, `backend/src/satquery/services/query_router.py`, `backend/src/satquery/services/evidence_retriever.py`, `backend/src/satquery/services/sufficiency_checker.py`, `backend/src/satquery/services/claim_validator.py`, `backend/src/satquery/services/query_service.py`, `backend/src/satquery/api/routes/query.py`.
* **Frontend Target:** `frontend/src/lib/query-contracts.ts`, `frontend/src/lib/query-client.ts`, `frontend/src/lib/use-query-assistant.ts`, `frontend/src/components/workspace/assistant-panel.tsx`, `frontend/src/components/workspace/results-tabs.tsx`, `frontend/src/components/workspace/workspace-shell.tsx`.
* **Verification:** Pytest 276 passed (100%), strict Mypy (126 source files) clean, Ruff check/format clean, Vitest 275 passed across 63 test files (100%), Biome format/lint clean, Next.js 16.3.4 production build clean.

### Phase 5B: Image VQA and Verified Spatial Grounding
* **Objective:** Implement visual question answering directly on actual satellite imagery pixels, with continuous normalized coordinate bounding boxes, an exact 6-step inverse transformation pipeline mapping pixels to WGS84 GeoJSON polygons, provider adapters (Gemini & Mock), candidate evidence overlap association, and interactive map observation cards.
* **Backend Target:** `backend/src/satquery/api/schemas/visual.py`, `backend/src/satquery/services/spatial_grounding.py`, `backend/src/satquery/services/visual_image_preparer.py`, `backend/src/satquery/services/visual_query_service.py`, `backend/src/satquery/providers/ai/`, `backend/src/satquery/api/routes/query.py`.
* **Frontend Target:** `frontend/src/lib/visual-contracts.ts`, `frontend/src/lib/visual-client.ts`, `frontend/src/lib/use-visual-qa.ts`, `frontend/src/components/workspace/assistant-panel.tsx`, `frontend/src/components/workspace/results-tabs.tsx`, `frontend/src/components/workspace/workspace-shell.tsx`.
* **Verification:** Pytest 287 passed (100%), strict Mypy (132 source files) clean, Ruff check/format clean, Vitest 287 passed across 66 test files (100%), Biome format/lint clean, Next.js 16.3.4 production build clean. Full repo verification passed via `scripts/verify.ps1`.

### Phase 6: Confidence, Warnings, and Report Generation
* **Objective:** Implement the multi-factor confidence calculation ($0.0 - 1.0$), standardized warning code emission (`HIGH_CLOUD_COVER`, `RESOLUTION_LIMIT_WARNING`), and the downloadable analysis dossier generator (PDF / formatted JSON).
* **Backend & Frontend Targets:** `backend/src/satquery/analysis/confidence.py`, `backend/src/satquery/reports/generator.py`, `frontend/src/components/workspace/assistant-panel.tsx`.
* **Verification:** Report PDF generation check, JSON schema export check, confidence math test suite.

### Phase 7: End-to-End SIH Demo Validation
* **Objective:** Execute the complete 11-step demo workflow continuously: AOI draw $\to$ STAC discovery $\to$ 2-date selection $\to$ natural language question $\to$ spectral/AI analysis $\to$ map overlay rendering $\to$ report download.
* **Verification:** Run complete test suite (`verify.ps1`), verify zero ungrounded statements, and measure execution performance ($< 15\text{s}$ response time).
