# SatQuery AI — Official SIH Live Demonstration Script

**Document Version:** 1.0.0  
**Target Stage:** Smart India Hackathon (SIH) Grand Finale Demonstration  
**Applicable Release:** Candidate RC-Phase7B  
**Primary Dataset:** Live Sentinel-2 L2A via Element 84 Earth Search STAC + Surface Reflectance Bands  
**Fallback Dataset:** Pre-staged Deterministic Sentinel-2 Mock Fixtures  

---

## 1. Timing Overview & Structure

| Section | Target Window | Theme / Core Message |
|---|---|---|
| **Act 1** | `0:00 – 0:40` | The Remote Sensing Accessibility Problem & SatQuery AI Thesis |
| **Act 2** | `0:40 – 1:20` | Dynamic Area of Interest (AOI) Definition & Geodesic Validation |
| **Act 3** | `1:20 – 2:10` | STAC Temporal Scene Discovery & Multi-Band Metadata Verification |
| **Act 4** | `2:10 – 3:10` | Natural Language Query Processing & Task-Specific Routing |
| **Act 5** | `3:10 – 4:30` | Rigorous Raster Harmonization, NDVI Differencing & Grounded Map Overlays |
| **Act 6** | `4:30 – 5:20` | Transparent Epistemic Accounting: Confidence Factors, Warnings & Limitations |
| **Act 7** | `5:20 – 6:10` | Immutable Evidence Dossier: Multi-Format PDF/JSON Export & SHA-256 Verification |
| **Act 8** | `6:10 – 7:00` | SIH Innovation Summary, Scalability & Competitive Moat |

---

## 2. Full 5–7 Minute Primary Demonstration Script

### Act 1: Problem Statement & Value Proposition (`0:00 – 0:40`)
* **Visual State:** Browser open to SatQuery AI Landing / Workspace Hub (`http://localhost:3000`). Clean dark UI visible.
* **Presenter Action:** Mouse cursor over the interactive map viewport.

> **Presenter Speaks:**  
> *"Good morning, esteemed jury. Earth observation satellites capture terabytes of spectral and radar data daily. Yet, extracting actionable insights today requires deep GIS domain expertise, complex desktop software like QGIS, and manual script authoring. When decision-makers ask simple operational questions—such as 'Did urban development encroach onto green corridors between 2025 and 2026?'—they wait days for geospatial analysts.*  
>  
> *SatQuery AI solves this bottleneck. We combine modern vision-language query understanding with a scientifically rigorous, deterministic geospatial processing pipeline. Let's see it live on a real-world scenario."*

* **Transition Sentence:** *"Let's begin by defining our Area of Interest on the map."*

---

### Act 2: Dynamic AOI Selection & Geodesic Validation (`0:40 – 1:20`)
* **Visual State:** Interactive Leaflet map centered over Bengaluru Urban / Bellandur corridor.
* **Presenter Action:** Click the Polygon tool on the map toolbar. Draw a bounding polygon over coordinates `[77.65, 12.93]` to `[77.69, 12.95]`.
* **Expected UI Response:** Polygon snaps with crisp green boundary; the right-hand panel immediately validates the geometry via the backend geodesic calculator, displaying: `Area: 9.64 km² | EPSG:4326 | Status: Valid`.

> **Presenter Speaks:**  
> *"We select a 9.64 square kilometer corridor in East Bengaluru. Notice that our backend immediately validates the geometry against geodesic ellipsoidal models (WGS84) and enforces strict bounding constraints. The application rejects degenerate self-intersecting polygons or excessive extents, ensuring all subsequent raster operations have mathematical integrity."*

* **Transition Sentence:** *"Now, let's discover the available multi-temporal satellite scenes for this exact bounding box."*

---

### Act 3: STAC Scene Discovery & Sensor Compatibility (`1:20 – 2:10`)
* **Visual State:** Date picker and Scene Discovery panel.
* **Presenter Action:** Set **Before Window** to `Dec 2025` and **After Window** to `May 2026`. Max cloud cover filter set to `30%`. Click **"Search STAC Catalog"**.
* **Expected UI Response:** A loading indicator pulses for ~1.1s. Two scenes are retrieved directly from Element 84 Earth Search:
  - Baseline: `S2C_T43PGQ_20251228T052411_L2A` (Sentinel-2C, Cloud: 0.12%)
  - Target: `S2B_T43PGQ_20260512T052201_L2A` (Sentinel-2B, Cloud: 4.8%)
  - Data origin tag displays: `[REAL STAC PROVIDER: AWS Element 84]`.

> **Presenter Speaks:**  
> *"With one click, SatQuery queries the live AWS Element 84 STAC catalog. In approximately 1.1 seconds, it discovers optimal acquisition pairs from Sentinel-2C and Sentinel-2B. Notice the data origin badge: SatQuery never obscures data provenance. It explicitly confirms that these are calibrated Level-2A bottom-of-atmosphere surface reflectance assets."*

* **Transition Sentence:** *"With our imagery pairs staged, let's ask a natural-language operational question."*

---

### Act 4: Natural-Language Question & Task-Specific Routing (`2:10 – 3:10`)
* **Visual State:** Chat / Query Input drawer at the bottom of the viewport.
* **Presenter Action:** Type into the prompt box:  
  `"What is the vegetation and surface change in this area?"`  
  Click **"Analyze"** (or press Enter).
* **Expected UI Response:** Router badge flashes `Routing Intent: temporal_change_detection | Strategy: Bidirectional Differencing`. The processing pipeline runs asynchronously, showing step progress (Harmonization $\to$ Index Computation $\to$ Vector Masking).

> **Presenter Speaks:**  
> *"We submit an unstructured natural-language question. Unlike standard LLMs that hallucinate facts from their training weights, SatQuery uses a multi-intent router. It parses the semantic intent, determines that this question requires multi-temporal optical comparison, verifies that our input assets satisfy the spatial and band requirements, and constructs a deterministic execution plan. The AI does not guess the change—it delegates to our verified geospatial engine."*

* **Transition Sentence:** *"Let's inspect the calculated change metrics and spatial overlays."*

---

### Act 5: Raster Harmonization, NDVI Differencing & Map Grounding (`3:10 – 4:30`)
* **Visual State:** Dual-layer map with Split/Swipe slider active. Overlay displays classified vegetation loss/gain masks (Red = Loss, Green = Gain, Grey = Stable).
* **Presenter Action:** Drag the swipe comparison slider back and forth across the AOI. Click on a highlighted red polygon in the change layer.
* **Expected UI Response:** Inspection drawer opens displaying:
  - `Region ID: reg-001 | Area: 9.64 km² | Classification: Significant Vegetative Reduction`
  - `Band Radiometry: B08 (NIR) vs B04 (Red) | Delta-NDVI: -0.28`
  - Strict denominator accounting: `Gain: 0.0% (0.00 km²) | Loss: 100.0% (9.64 km²) | Stable: 0.0% (0.00 km²) | Denominator: Shared Valid Pixels (95,630 px)`.

> **Presenter Speaks:**  
> *"Under the hood, SatQuery reprojected and co-registered both scenes onto a unified UTM grid at 10-meter Ground Sample Distance, harmonizing 95,630 valid overlapping pixels. It computed Normalized Difference Vegetation Index (NDVI) rasters across both dates and applied bidirectional thresholding.*  
>  
> *Notice our strict scientific accounting: the percentage breakdown is calculated strictly over the shared valid pixel denominator, avoiding misleading land cover claims. Furthermore, every vectorized boundary on the map is spatially grounded in WGS84 GeoJSON."*

* **Transition Sentence:** *"Equally vital is what SatQuery chooses NOT to claim—let's review the confidence breakdown."*

---

### Act 6: Confidence Breakdown, Warnings & Causal Discipline (`4:30 – 5:20`)
* **Visual State:** "Confidence & Evidence Breakdown" accordion panel expanded.
* **Presenter Action:** Highlight the Confidence Card (`Overall Quality Score: 0.88 / 1.00`) and the Warning Badges.

> **Presenter Speaks:**  
> *"In remote sensing, a drop in NIR reflectance could indicate seasonal crop harvesting, drought stress, or actual construction clearing. SatQuery enforces strict causal discipline: it refuses to assert 'illegal demolition' or 'building construction' from optical reflectance alone.*  
>  
> *Our sufficiency checker outputs calibrated confidence factors, accounting for solar zenith angle differentials (32° vs 58°), sub-pixel cloud shadows, and temporal gap (135 days). When evidence is insufficient, it explicitly issues a caveat rather than fabricating certainty."*

* **Transition Sentence:** *"Finally, let's export an immutable evidence package for auditing and executive briefing."*

---

### Act 7: Immutable Report Dossier & SHA-256 Verification (`5:20 – 6:10`)
* **Visual State:** Report Export modal open.
* **Presenter Action:** Click **"Generate Audit Report"** $\to$ Click **"Download PDF"** and **"Download JSON"**. Open the generated PDF in the browser viewer.
* **Expected UI Response:** A multi-page ReportLab Platypus PDF opens with high-resolution vector tables, sensor provenance metadata, spatial extent diagrams, and a cryptographic checksum banner: `SHA-256: 78436af0c5dd...`.

> **Presenter Speaks:**  
> *"With a single click, SatQuery compiles an immutable analytical snapshot. This is not a superficial screenshot printout. It is an authoritative engineering dossier built with ReportLab Platypus. It includes full sensor calibration parameters, exact band descriptions, quantitative area tables with explicit units (km²), and a SHA-256 cryptographic digest.*  
>  
> *Any auditor can ingest the accompanying machine-readable JSON snapshot or recalculate the SHA-256 checksum to verify that the report has not been tampered with."*

* **Transition Sentence:** *"To wrap up, let's reflect on what makes SatQuery AI a production-grade solution."*

---

### Act 8: Innovation, Impact & Conclusion (`6:10 – 7:00`)
* **Visual State:** Return to map view with full telemetry dashboard.

> **Presenter Speaks:**  
> *"SatQuery AI bridges the gap between massive geospatial satellite archives and real-time operational decision-making. By uniting natural-language interfaces with mathematically grounded, deterministic raster processing, we eliminate both the complexity of traditional GIS and the dangerous hallucinations of generic AI models.*  
>  
> *The entire system is modular, horizontally scalable, operates across optical and SAR modalities, and is built to open OGC/STAC standards. Thank you, and we look forward to your questions."*

---

## 3. Compressed 3-Minute Demonstration Path

When presenting in tight preliminary rounds or rapid evaluation slots:

| Time | Action | Speaking Core |
|---|---|---|
| `0:00 – 0:30` | Draw AOI on map & click "Search" | State the problem: manual GIS takes hours. Draw Bengaluru AOI (9.64 km²). Live STAC search retrieves Sentinel-2 pair. |
| `0:30 – 1:30` | Ask question: *"What is the vegetation change?"* | Router identifies temporal differencing. System co-registers 95,630 pixels at 10m GSD and computes NDVI delta. |
| `1:30 – 2:15` | Swipe comparison slider & inspect region | Show red/green change masks. Emphasize strict scientific accounting (loss % over valid pixels) and causal modesty (no guessing reasons). |
| `2:15 – 3:00` | Open & show PDF Report | Highlight immutable snapshot, exact band provenance, and SHA-256 checksum for audit compliance. |

---

## 4. Emergency 90-Second Demonstration Path

For unexpected time cuts or lightning judging rounds:

1. **`0:00 – 0:20`**: Load pre-staged Bengaluru Demo Workspace. Show 9.64 km² validated AOI and Sentinel-2 L2A acquisition pair.
2. **`0:20 – 0:50`**: Execute Question: *"Vegetation change between Dec 2025 and May 2026"*. Show instantaneous grounded response with NDVI change mask overlay.
3. **`0:50 – 1:20`**: Drag swipe slider to demonstrate pixel-aligned visual evidence. Point to the Confidence & Warning breakdown (solar angle caveat).
4. **`1:20 – 1:30`**: Pop up the verified PDF report showing SHA-256 integrity hash. Conclude: *"Zero hallucination, 100% deterministic geospatial grounding."*

---

## 5. Judge Interruption Strategy & Safe Pause Points

If judges interrupt with questions during the live walkthrough:

### Safe Pause Point A: During STAC Scene Selection (`~1:45`)
* **Safe State:** Scene list rendered, no active computation running.
* **Resume Line:** *"Now that we have verified both Level-2A acquisition dates and cloud cover, let's submit our operational question to the AI router."*

### Safe Pause Point B: During Swipe Overlay Inspection (`~3:45`)
* **Safe State:** Map rendered with change vectors, drawer open.
* **Resume Line:** *"As we observe these grounded change polygons, let's examine the confidence metrics that quantify our observation quality."*

### Safe Pause Point C: During PDF Report Display (`~5:40`)
* **Safe State:** PDF viewer modal open.
* **Resume Line:** *"This immutable report encapsulates all raw data, processed rasters, and audit hashes, allowing full reproducibility."*
