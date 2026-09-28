# Roadmap & Implementation Plan

## 1. Urgent SIH Vertical-Slice Path (Fast-Track)

To fulfill the Smart India Hackathon (SIH) live working prototype requirement, this fast-track path connects existing geospatial foundations directly to the AI analysis and reporting engine:

```
[Interactive Map] ──> [AOI Drawing & Selection] ──> [Real Imagery Discovery (Sentinel-2)]
                                                                  │
                                                                  ▼
[Analysis Report Export] ◄── [Confidence & Warnings] ◄── [Before/After Date Selection]
         ▲                                                        │
         │                                                        ▼
[Grounded Map Overlays] ◄── [Processing & AI VLM] ◄── [Typed Analysis Request]
```

### Fast-Track Phase Sequence:
* **Antigravity Phase 0A (Active):** Project Control Documents & Architecture Definition.
* **Antigravity Phase 0B:** Pydantic (Backend) & Zod (Frontend) Contract Generation for the 16 Planned Schemas.
* **Antigravity Phase 0C:** API & Provider Configuration Baseline (Gemini / Multimodal VLM settings, CORS, Error handling).
* **Antigravity Phase 1:** Verify Map, AOI Drawing & Coordinate Ingestion Workflow.
* **Antigravity Phase 2:** Real Satellite Imagery Discovery & Metadata Integration (Element 84 Earth Search).
* **Antigravity Phase 3:** Before/After Imagery Selection, Temporal Ordering, & Overlap Validation.
* **Antigravity Phase 4:** Analysis-Pipeline Implementation (Spectral math: NDVI/NDWI + VLM reasoning).
* **Antigravity Phase 5:** Map Overlays & Grounded Evidence Visualization (GeoJSON masks & colormaps on MapLibre).
* **Antigravity Phase 6:** Confidence Scoring, Warning Codes, and Report Generation (PDF/JSON Export).
* **Antigravity Phase 7:** End-to-End SIH Demo Validation & Rehearsal.

---

## 2. Long-Term Repository Roadmap (Phases 0–15)

### Integrity Rule
SatQuery AI maintains 16 governed phases (Phase 0 through Phase 15). The original long-term titles and scope are preserved below:

| Phase | Title / Scope | Dependencies | Outputs / Deliverables | Completion Criteria | Status |
|---|---|---|---|---|---|
| **0** | Project Foundation & AI-Agent Rules | None | Requirements, rules, architecture, contracts, repository structure, handoff | Consistent docs and approved rules | **COMPLETE** |
| **1** | Core Repository, Environment & Base Backend | Phase 0 | Runtime scaffolding, manifests, locks, base FastAPI backend, health endpoints | Startup and unit tests pass; PostGIS container integration pending | **PARTIALLY_VERIFIED** |
| **2** | Premium Homepage + Main Workspace UI | Phase 1 | Homepage, responsive workspace shell, topbar, sidebar, assistant panel, results tabs | UI renders cleanly; static build passes | **PARTIALLY_VERIFIED** |
| **3** | Interactive Earth Map & AOI System | Phases 1–2 | MapLibre basemap, Terra Draw rectangle/polygon tools, bounds entry, GeoJSON import/export | AOI creation/editing passes automated tests | **PARTIALLY_VERIFIED** |
| **4** | EO Catalogue Discovery & Scene Selection | Phase 3 | STAC catalogue search, Sentinel-2 L2A integration, footprint overlays, scene selection draft | Live Earth Search STAC query passes | **PARTIALLY_VERIFIED** |
| **5** | High-Resolution Imagery Viewer & Visual Comparison | Phase 4 | Bounded server-mediated COG tile delivery (rio-tiler), Swipe/Split/Blink two-date comparison | Real S2 tiles render in MapLibre | **COMPLETE** |
| **6** | Spectral & Change Analysis Engine | Phase 5 | Bounded pixel window extraction, NDVI/NDWI/NDBI computation, difference masks | Spectral algorithms pass unit test suite | **IN PROGRESS (Phase 0A Plan)** |
| **7** | Grounded Multimodal AI & VLM Integration | Phase 6 | VLM provider adapter (Gemini), prompt engineering, evidence-grounded reasoning | AI responses reference verified metrics | **PLANNED** |
| **8** | Grounded Map Overlays & Spatial Evidence | Phase 7 | Vector GeoJSON masks, colormapped raster layers, toggleable overlay controls | Overlays align on MapLibre map | **PLANNED** |
| **9** | Calibrated Confidence & Warning System | Phase 8 | Multi-factor confidence calculation ($0.0-1.0$), standardized warning codes | Transparent scores displayed in UI | **PLANNED** |
| **10** | Analysis Dossier & Report Generation | Phase 9 | PDF/JSON report generation with provenance, charts, maps, and findings | Downloadable report validated | **PLANNED** |
| **11** | User Authentication & Multi-Tenancy | Phase 10 | Auth0 / OIDC authentication, user session management, tenant isolation | Protected routes require auth | **PLANNED** |
| **12** | Asynchronous Distributed Task Queue | Phase 11 | Celery / Redis background worker pool, job progress streaming | Long jobs execute asynchronously | **PLANNED** |
| **13** | Multimodal Optical & SAR Fusion | Phase 12 | Sentinel-1 SAR ingestion, speckle filtering, dual-pol cross-comparison | Optical/SAR joint queries supported | **PLANNED** |
| **14** | Advanced Object Detection & Segmentation | Phase 13 | Specialized remote-sensing vision models (Segment Anything for EO) | Semantic segmentation masks | **PLANNED** |
| **15** | Production Hardening, Multi-Region & Scalability | Phase 14 | Kubernetes Helm charts, autoscaling, CDN caching, security audits | Production staging sign-off | **PLANNED** |
