# SatQuery AI — Evidence-Based Technical Q&A for Judges & Evaluators

**Document Version:** 1.0.0  
**Target Audience:** Smart India Hackathon (SIH) Technical Jury, Geospatial Experts, AI Evaluators  
**Application Candidate:** SatQuery AI RC-Phase7B  

---

### Q1: What exact problem does SatQuery AI solve?
**Answer:**  
Earth Observation (EO) satellite constellations (Copernicus Sentinel-1/2, Landsat, Planet) produce petabytes of imagery daily. However, extracting actionable operational answers from this data currently requires GIS domain experts who manually download rasters, reproject coordinate reference systems, calculate spectral indices in desktop software (QGIS/ArcGIS), and write analytical reports.  

SatQuery AI solves this accessibility and latency bottleneck. It allows non-technical decision-makers to ask plain-English questions (e.g., *"What is the vegetation and surface change in this area?"*), intelligently routes the query, executes deterministic, calibrated raster algorithms on satellite data, and produces an evidence-grounded spatial overlay alongside a cryptographically verifiable audit report.

---

### Q2: Why use a vision-language assistant instead of a traditional GIS dashboard?
**Answer:**  
Traditional GIS dashboards provide static visual layers but require the user to formulate SQL queries, select band math equations, configure thresholding algorithms, and interpret raw false-color rasters manually.  

A vision-language architecture provides:
1. **Zero-Friction Semantic Querying:** Users state their intent in natural language; the system parses the required temporal window, spatial extent, and analytical method.
2. **Dynamic Task Routing:** The assistant determines whether the query requires single-image spectral indices, multi-temporal change detection, SAR backscatter analysis, or object identification.
3. **Automated Epistemic Synthesis:** It synthesizes quantitative findings into plain language while linking every stated metric back to spatial coordinates and sensor telemetry.

---

### Q3: How does the Natural Language Router select a task, and how are hallucinated actions prevented?
**Answer:**  
We do **not** allow an unrestricted LLM to execute arbitrary code or query tools without constraints. SatQuery uses a multi-stage deterministic routing pipeline:
1. **Intent Classification:** Classifies user query into strict enumerated intents (`temporal_change_detection`, `spectral_summary`, `object_detection`, `sar_polarimetric_analysis`, `multi_sensor_fusion`).
2. **Context Snapshot Binding:** Evaluates the active workspace state (AOI bounds, selected scene modalities, available spectral bands).
3. **Sufficiency Checking:** Checks if prerequisites are met (e.g., temporal change requires at least 2 distinct scenes with valid overlapping bounds). If prerequisites are missing, it returns `NEEDS_PROCESSING` or `CLARIFICATION_REQUIRED` rather than fabricating an answer.
4. **Allow-Listed Operations:** The router constructs an execution plan using only strongly typed, server-side validated service methods.

---

### Q4: How do Optical and SAR data differ, and how does SatQuery handle both?
**Answer:**  
- **Optical Imagery (e.g., Sentinel-2 MSI):** Measures reflected solar radiation in the Visible, Near-Infrared (NIR), and Shortwave Infrared (SWIR) spectrum. Highly effective for vegetation vitality (NDVI), water bodies (NDWI), and built-up indices (NDBI), but is obstructed by clouds and night conditions.
- **SAR Imagery (e.g., Sentinel-1 C-band SAR):** Active microwave radar that penetrates clouds, smoke, and darkness. Measures surface roughness, dielectric properties, and structural volume through backscatter intensity ($\sigma^0$ in VV and VH polarizations).
- **SatQuery Integration:** SatQuery maintains distinct processing pipelines for each sensor. For optical data, it enforces BOA (Bottom-of-Atmosphere) reflectance and cloud masking. For SAR data, it applies radiometrically calibrated decibel backscatter ($\text{dB}$) conversions and dual-polarization ratio metrics ($\text{VH}/\text{VV}$). In multimodal fusion mode, SAR backscatter validates optical structural change beneath persistent cloud cover.

---

### Q5: How is before/after temporal change measured mathematically?
**Answer:**  
1. **Reprojection & Co-Registration:** Both scenes are reprojected to a common projected metric grid (e.g., UTM Zone 43N / `EPSG:32643`) and resampled to a uniform 10-meter Ground Sample Distance (GSD) using bilinear interpolation.
2. **Index Differencing:** We compute the spectral index across both rasters (e.g., $\Delta\text{NDVI} = \text{NDVI}_{\text{target}} - \text{NDVI}_{\text{baseline}}$).
3. **Thresholding Strategies:** The user or pipeline selects a thresholding method:
   - *Fixed Threshold:* Absolute delta cutoff (e.g., $|\Delta| \ge 0.15$).
   - *Percentile Cutoff:* Identifies top and bottom tails (e.g., top 5% change).
   - *Otsu Adaptive Thresholding:* Maximizes inter-class variance of the magnitude histogram.
4. **Strict Accounting:** Percentages are strictly calculated over `shared_valid_pixels` ($V$):
   $$\text{Gain}\% + \text{Loss}\% + \text{Stable}\% = 100.0\% \quad (\text{over } V)$$
   Uncertain pixels (cloud, shadow, non-overlapping extents) are isolated and reported separately as a fraction of total AOI area.

---

### Q6: How does spatial grounding work between pixels and vector map boundaries?
**Answer:**  
When change pixels are classified in raster space, contiguous clusters exceeding the minimum mapping unit (default 10 pixels / 1,000 m²) are vectorized into polygon contours using `rasterio.features.shapes`.  
The affine transform matrix maps pixel array coordinates $(r, c)$ to metric projected coordinates $(x, y)$, which are then reprojected via `pyproj` into standard WGS84 GeoJSON (`EPSG:4326`). The frontend map binds each polygon ID to the corresponding quantitative statistics (mean delta, standard deviation, peak coordinate, area in km²).

---

### Q7: How are confidence factors and warnings calculated?
**Answer:**  
SatQuery evaluates a multi-factor confidence model resulting in a score from 0.0 to 1.0:
1. **Spatial Overlap Factor:** Ratio of valid shared pixel intersection to total requested AOI.
2. **Atmospheric / Cloud Mask Factor:** Degradation penalty based on cloud probability and shadow coverage.
3. **Temporal Baseline Penalty:** Accounts for solar zenith angle differentials (e.g., winter vs summer sun angle causing seasonal reflectance shifts) and temporal gap.
4. **Sensor Resolution Factor:** Validates whether the target feature size matches the Ground Sample Distance (10m for S2, 30m for Landsat).
If any factor falls below acceptable limits, explicit warning objects (severity `low`, `medium`, `critical`) are attached to the response.

---

### Q8: How does the system prevent AI hallucinations and causal over-claims?
**Answer:**  
1. **Epistemic Classification of Claims:** Every assertion in an AI response is tagged as either `MEASUREMENT` (direct mathematical output), `INTERPRETATION` (probabilistic assessment), `BACKGROUND` (contextual data), or `LIMITATION` (caveat).
2. **Server-Side Claim Validator:** The backend verifies that every quantitative claim (e.g., "loss of 9.64 km²") exactly matches the numbers in the execution trace. Unverified claims are rejected or flagged.
3. **Causal Modesty Discipline:** The system is explicitly instructed that a reduction in NIR reflectance indicates *spectral biomass reduction*, not necessarily "illegal deforestation" or "construction". Causal explanations require ground truth or secondary multi-source validation.

---

### Q9: Which satellite imagery providers and datasets are actually integrated?
**Answer:**  
- **Element 84 Earth Search (AWS STAC API v1):** Live STAC catalog providing Sentinel-2 Level-2A (Bottom-of-Atmosphere Surface Reflectance) and Sentinel-1 GRD assets globally.
- **Local / Mock STAC Catalog:** Built-in deterministic fixtures containing multi-temporal Sentinel-2 optical bands (B02, B03, B04, B08, B11, B12) and Sentinel-1 SAR dual-pol rasters for offline resilience.
- **OpenStreetMap / CartoDB:** Tile providers used purely as visual reference basemaps (distinct from analytical raster assets).

---

### Q10: What is the difference between a visual basemap and analysis-ready surface reflectance?
**Answer:**  
- **Visual Basemaps (RGB Web Tiles):** Lossy 8-bit JPEG/PNG image tiles pre-rendered for visual display. They have no calibrated radiometry, undergo unknown contrast stretching, and cannot be used for scientific analysis.
- **Analysis-Ready Surface Reflectance (L2A Bands):** 16-bit GeoTIFF rasters with physically calibrated Bottom-of-Atmosphere (BOA) surface reflectance values ($0.0 \text{ to } 1.0$). They preserve individual electromagnetic wavelengths (Red, Green, Blue, NIR, Red Edge, SWIR) necessary to calculate biophysical equations. SatQuery strictly uses Analysis-Ready bands for all mathematical computations.

---

### Q11: How are evidence snapshots and audit reports made traceable and immutable?
**Answer:**  
When an analysis is completed, a `ReportSnapshot` data structure is compiled. It freezes:
- Exact scene acquisition IDs, timestamps, and sensor telemetry.
- Bounding geometry and coordinate reference system.
- Computed metrics, pixel counts, and threshold parameters.
- Structured AI claims and visual observations.
- Normalized UTC timestamps.

The backend computes a deterministic **SHA-256 cryptographic digest** of the serialized snapshot. Both the generated multi-page ReportLab PDF and the machine-readable JSON export embed this exact SHA-256 checksum.

---

### Q12: What runs live versus what runs via cached or mock fixtures?
**Answer:**  
- **Live in Primary Demo:** Live STAC temporal scene discovery from AWS Element 84, geodesic AOI validation, UTM reprojection and co-registration, band math (NDVI/NDWI/NDBI differencing), polygon vectorization, and ReportLab Platypus PDF compilation.
- **Offline / Mock in Fallback Demo:** Scene discovery reads from deterministic local STAC fixtures, and the query synthesis operates in deterministic template mode. All raster mathematics, vectorization, and report generation execute the exact same live Python engine.

---

### Q13: What is the current evaluation and accuracy verification status?
**Answer:**  
- **Unit & Integration Suite:** 295 backend tests (Pytest) and 297 frontend tests (Vitest) passing with strict TypeScript and Mypy validation.
- **Scientific Verification:** Pixel accounting equations are verified against synthetic test rasters with known geometric ground truth (100% pixel conservation).
- **Operational Rehearsals:** Phase 7B automated rehearsal suite demonstrated 100% pass rate across 6 consecutive end-to-end executions (3 Primary, 3 Fallback) with average end-to-end processing latencies under 2.5 seconds.
- *Note:* Large-scale empirical validation against government ground truth datasets (e.g., NRSC Bhuvan land use maps) is slated for Phase 10 of the long-term roadmap.

---

### Q14: What are the current known technical and scientific limitations?
**Answer:**  
1. **Spatial Resolution:** Sentinel-2 optical is limited to 10-meter GSD; individual vehicles or small residential buildings cannot be resolved.
2. **Atmospheric Occlusion:** Severe cloud cover obscures optical measurements, necessitating SAR fallback or multi-day compositing.
3. **Topographic Distortion:** In steep mountainous terrain, terrain shadows and layover can distort reflectance and backscatter without high-resolution DEM orthorectification.
4. **Processing Limits:** Single-node synchronous execution is tuned for AOIs up to 100 km²; regional or national-scale processing requires asynchronous distributed workers.

---

### Q15: What are the production scalability and cloud deployment requirements?
**Answer:**  
- **Architecture:** The backend is stateless and horizontally scalable behind a load balancer.
- **Raster Processing:** Heavy compute jobs (large AOIs, multi-temporal cubes) transition to asynchronous task queues (Celery / Redis / AWS SQS) executing on GPU/CPU worker pools.
- **Cloud-Optimized Rasters:** Direct reading of Cloud Optimized GeoTIFFs (COGs) via HTTP Range requests using GDAL `vsis3` eliminates the need to download entire 500MB satellite granules.

---

### Q16: How does SatQuery protect security, privacy, and token boundaries?
**Answer:**  
- **No Client-Side Secrets:** Provider credentials and API keys remain exclusively on the server.
- **Strict Boundary Validation:** All user inputs (GeoJSON coordinates, query text, date ranges) are strictly validated by Pydantic models with extra fields forbidden.
- **No Data Poisoning:** Retrieved STAC metadata and user uploads are treated strictly as data, never as executable instructions or agent prompts.

---

### Q17: What distinguishes SatQuery AI from Google Earth Engine (GEE)?
**Answer:**  
- **Google Earth Engine** is a developer platform requiring knowledge of JavaScript/Python APIs and complex geospatial functions. It provides no natural language understanding or automated epistemic claim verification.
- **SatQuery AI** is an end-to-end intelligent assistant for operators, analysts, and decision-makers. It interprets high-level operational intent, selects appropriate algorithms automatically, executes the workflow, and provides grounded explanations with tamper-evident audit dossiers.

---

### Q18: What is the remaining scope across the 16-phase roadmap?
**Answer:**  
Phase 7B successfully concludes the **SIH Demo-Readiness Sprint** (Phases 0 through 7B).  
The broader 16-phase product roadmap (Phases 8–15) outlines subsequent engineering milestones:
- **Phases 8–9:** Advanced SAR interferometry (InSAR coherence loss), multi-sensor fusion algorithms, and multi-temporal time-series forecasting.
- **Phases 10–11:** Distributed asynchronous worker architecture, large-scale COG streaming, and multi-tenant enterprise RBAC.
- **Phases 12–15:** External GIS plugin integrations (QGIS/ArcGIS connectors), automated satellite tasking triggers, and production cloud deployment.
