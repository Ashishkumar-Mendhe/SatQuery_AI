# Technical Requirements Document (TRD)

## 1. Confirmed Technology Stack

| Domain | Selected Technology | Version | Purpose & Rationale |
|---|---|---|---|
| **Frontend Core** | Next.js (App Router), React | `16.3.4`, `19.2.8` | Modern React framework with server components and client-side workspace shell. |
| **Frontend Tooling** | TypeScript, Biome, Vitest | `6.0.3`, `2.5.12`, `5.0.0` | Strict type safety, high-performance linting/formatting, and component testing. |
| **Styling & Design** | Tailwind CSS (v4 PostCSS), Custom CSS | `4.3.3` | Clean, responsive design system with dark/light mode and geospatial layout variables. |
| **Mapping Engine** | MapLibre GL JS | `6.9.0` | High-performance WebGL-based vector and raster satellite imagery visualization. |
| **Vector Drawing & GIS** | `@watergis/maplibre-gl-terradraw`, `@turf/*` | `1.16.0`, `7.4.0` | Client-side polygon/rectangle drawing, geodesic area calculation, and geometry validation. |
| **Contract Validation** | Zod (Frontend) / Pydantic (Backend) | `zod 4.5.4`, `pydantic-settings 2.15.0` | Runtime contract enforcement and type synchronization across client and server. |
| **Backend Framework** | FastAPI, Uvicorn, Python | `0.141.1`, `0.52.4`, `3.14.7` | Asynchronous high-throughput API gateway, OpenAPI autogen, and service orchestration. |
| **Geospatial & Raster** | Rasterio, Rio-Tiler, NumPy | `1.5.1`, `9.4.4`, `2.5.3` | Windowed Cloud Optimized GeoTIFF (COG) byte-range reads, reprojection, and spectral math. |
| **Database & Spatial** | PostgreSQL, PostGIS, SQLAlchemy, Alembic | PostGIS `18-3.6`, SQLAlchemy `2.0.52`, Alembic `1.19.2` | Persistent geospatial storage, spatial indexing (GiST), and async database sessions. |
| **External Data Provider** | Element 84 Earth Search STAC v1 | Public API | Real-time metadata discovery and S3-hosted Sentinel-2 L2A COG access. |
| **AI / VLM Layer** | Google Gemini 2.0 / 1.5 Pro / Flash | Multimodal API | Multimodal remote-sensing visual question answering and grounded synthesis. |

---

## 2. System Architecture & Boundaries

```mermaid
graph TD
    subgraph Client ["Next.js Frontend Workspace"]
        UI[Workspace UI Shell]
        Map[MapLibre GL MapCanvas]
        AOI[Terra Draw & Turf Manager]
        Panel[Assistant & Discovery Panel]
        Tabs[Results & Evidence Tabs]
    end

    subgraph Gateway ["FastAPI Backend Gateway (/api/v1)"]
        Router[API Router & Middleware]
        Auth[Auth & Ownership Layer]
        CatalogRoute[/catalog/searches]
        ImageryRoute[/imagery/tiles]
        AnalysisRoute[/analysis/submit & /query]
        ReportRoute[/reports/export]
    end

    subgraph CoreEngine ["Geospatial & AI Processing Engine"]
        STACAdapter[Earth Search STAC Adapter]
        COGReader[Rasterio / Rio-Tiler Range Reader]
        SpectralEngine[Spectral Processor: NDVI / NDWI / NDBI]
        ChangeEngine[Change Detection & Diff Classifier]
        VLMEngine[Multimodal VLM Reasoning Agent]
    end

    subgraph DataPersistence ["Storage & Infrastructure"]
        Postgres[(PostgreSQL + PostGIS)]
        ObjectStore[(Private Object Storage)]
    end

    UI --> Router
    Map --> ImageryRoute
    Panel --> CatalogRoute
    Panel --> AnalysisRoute
    Tabs --> ReportRoute

    CatalogRoute --> STACAdapter
    ImageryRoute --> COGReader
    AnalysisRoute --> SpectralEngine
    AnalysisRoute --> ChangeEngine
    AnalysisRoute --> VLMEngine

    SpectralEngine --> COGReader
    ChangeEngine --> COGReader
    Router --> Postgres
    ReportRoute --> ObjectStore
```

### Responsibility Boundaries
* **Next.js Web Client:** Owns map presentation, user interaction, question drafting, local browser state, and rendering grounded overlays. Must never hold server credentials or make authoritative spatial claims without server-backed evidence.
* **FastAPI Backend Gateway:** Validates request parameters, ensures spatial geometry validity, coordinates async analysis pipelines, enforces rate limits, and signs report artifacts.
* **Geospatial Processing Engine:** Performs bounded COG window reads, calculates spectral indices, creates difference masks, and extracts vector polygons from classified rasters.
* **AI/VLM Layer:** Translates natural-language queries into structured execution plans, reviews calculated spectral statistics alongside visual crops, and formats human-interpretable answers grounded in evidence.

---

## 3. Frontend-to-Backend Communication

* **Protocol:** HTTP/2 over HTTPS, strictly RESTful JSON payloads, and standard HTTP response status codes.
* **API Versioning:** All endpoints prefixed with `/api/v1`.
* **Request Correlation:** Every request accepts or generates an `X-Request-ID` header, propagated through logs, error envelopes, and result bodies.
* **CORS:** Server allow-lists explicit origins (`http://localhost:3000` in development) with credentials enabled.
* **Contract Mirroring:** Every Pydantic model in `backend/src/satquery/api/schemas/` has an identical Zod validator in `frontend/src/lib/`.

---

## 4. Map & AOI Architecture

* **Mapping Engine:** MapLibre GL JS `6.9.0` with WebGL-accelerated vector and raster rendering.
* **Base Map Source:** OpenFreeMap Liberty vector tile style by default (`https://tiles.openfreemap.org/styles/liberty`), configurable via `NEXT_PUBLIC_BASEMAP_STYLE_URL` and `NEXT_PUBLIC_BASEMAP_NAME`.
* **Required Attribution:** Fully visible legal attribution for MapLibre, OpenFreeMap, and OpenStreetMap contributors (`© OpenFreeMap © OpenStreetMap contributors`).
* **Coordinate Reference System:** WGS 84 (EPSG:4326) for all API payloads and GeoJSON geometry storage; WebMercator (EPSG:3857) for MapLibre client rendering.
* **Coordinate Ordering:** Strictly RFC 7946 standard `[longitude, latitude]` for all positions, bounding boxes, and GeoJSON polygon rings. (Leaflet `[lat, lon]` internally inverted or avoided).
* **Bounding Box Format:** Standard 4-element array `[minimumLongitude, minimumLatitude, maximumLongitude, maximumLatitude]`.
* **Drawing & Editing Tools:** `@watergis/maplibre-gl-terradraw` (`1.16.0`) providing reactive polygon and rectangle drawing, vertex manipulation, and clear/delete workflows.
* **Area Calculation Method:** 
  * *Frontend:* Client-side geodesic approximation using `@turf/area` (`7.4.0`) displayed as $\text{km}^2$ (or $\text{ha}$ for small parcels) with formatted units.
  * *Backend (Authoritative):* Geodesic polygon area on spherical WGS84 ($R = 6371.0088\text{ km}$) computed by `satquery.services.aoi_validator.validate_aoi_geometry`. Client values are treated as hints and never trusted for system limits.
* **AOI Size Limits:** Maximum configurable AOI ceiling (`MAX_AOI_SQUARE_KM`, default $250,000\text{ km}^2$), minimum area threshold ($0.0001\text{ km}^2$), and coordinate vertex limit (500 points).
* **Validation Rules & Codes:**
  * `AOI_REQUIRED`: Geometry missing or null.
  * `AOI_EMPTY`: Coordinates array empty.
  * `INVALID_COORDINATE`: Non-numeric, non-finite, or malformed coordinate.
  * `LONGITUDE_OUT_OF_RANGE`: Longitude outside $[-180.0, 180.0]$.
  * `LATITUDE_OUT_OF_RANGE`: Latitude outside $[-90.0, 90.0]$.
  * `POLYGON_NOT_CLOSED`: First and last position do not match.
  * `INSUFFICIENT_VERTICES`: Less than 4 positions (including closure) in polygon exterior ring.
  * `AOI_SELF_INTERSECTION`: Polygon edges cross or self-intersect.
  * `AOI_TOO_SMALL`: Area below minimum processing threshold.
  * `AOI_TOO_LARGE`: Area exceeds `MAX_AOI_SQUARE_KM`.
  * `TOO_MANY_COORDINATES`: Ring contains $> 500$ vertices.
  * `UNSUPPORTED_GEOMETRY`: Unsupported geometry type (only `Polygon` and `MultiPolygon` supported).
  * `UNSUPPORTED_ANTIMERIDIAN_CROSSING`: Polygon spans the $\pm 180^\circ$ antimeridian without explicit split.
* **Frontend AOI Source of Truth:** One canonical serializable `SelectedAoi` state stored in workspace state / localStorage. Map layers hold transient rendering handles only.
* **Backend Validation Pipeline:** `POST /api/v1/aoi/validate` implemented in `backend/src/satquery/api/routes/aoi.py` backed by `satquery.services.aoi_validator.validate_aoi_geometry`. Normalizes ring orientation (counter-clockwise exterior ring per RFC 7946), computes authoritative bounding box and area, and returns structured `AoiValidationResponse`.
* **Module Paths:**
  * Backend validator: `backend/src/satquery/services/aoi_validator.py`
  * Backend API route: `backend/src/satquery/api/routes/aoi.py`
  * Backend schemas: `backend/src/satquery/api/schemas/aoi.py`
  * Frontend contracts: `frontend/src/lib/aoi-validation-contracts.ts`
  * Frontend API client: `frontend/src/lib/aoi-validation-client.ts`
  * Frontend workspace UI: `frontend/src/components/workspace/scene-container.tsx`
* **Known Limitations:** Interior holes in polygons are rejected for MVP; antimeridian crossing requires pre-split multipolygons; offline fallback uses local Turf validation when backend service is unreachable.

---

## 5. Satellite Imagery Discovery & Retrieval Plan

* **Primary Catalogue Provider:** Element 84 Earth Search STAC API v1 (`https://earth-search.aws.element84.com/v1/`).
* **Target Collections:** `sentinel-2-c1-l2a` (Sentinel-2 Level-2A surface reflectance) and `sentinel-2-l2a`.
* **Discovery Endpoint:** `POST /api/v1/scenes/search` (routed via `satquery.api.routes.scenes.search_scenes` to `SatelliteProviderRegistry`).
* **Query Mapping & Parameter Normalization:**
  * **AOI Intersection:** Standard GeoJSON Polygon/MultiPolygon or bounding box converted into STAC `intersects` / `bbox` parameter.
  * **Temporal Interval:** ISO 8601 UTC date range formatted as `YYYY-MM-DDTHH:MM:SSZ/YYYY-MM-DDTHH:MM:SSZ` in `datetime` field.
  * **Cloud Cover Filter:** STAC query filter `eo:cloud_cover <= max_cloud_cover` (default: 20%).
  * **Sensor Type & Band Constraints:** Filtered for multispectral/optical Sentinel-2 assets (requiring `red`/`B04`, `nir`/`B08`, `green`/`B03`, `blue`/`B02`).
  * **Sorting & Pagination:** Descending chronological sort by acquisition time (`datetime desc`), with cursor/token pagination support and bounded result limit (default 20, max 100).
* **Scene Normalization Architecture (`RealSatelliteProviderAdapter`):**
  * Parses STAC Item assets into uniform `SatelliteScene` contract:
    * `id`: STAC item ID (e.g. `S2B_T43PGQ_20251223T051848_L2A`).
    * `acquisition_time`: UTC timestamp (`datetime` property).
    * `platform`: Mapped to `Sentinel-2A`, `Sentinel-2B`, or `Sentinel-2C`.
    * `cloud_cover`: Extracted from `eo:cloud_cover` or `properties.cloud_cover`.
    * `thumbnail_url` & `preview_url`: Verified against safe S3 / AWS domains (`e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com`).
    * `available_bands`: Normalized list of available spectral assets (`B02`, `B03`, `B04`, `B08`, `B11`, `B12`).
    * `resolution_meters`: 10.0m native spatial resolution.
* **Origin Attribution & Fallback Boundaries:**
  * `data_origin: "real"`: Direct live STAC search response with valid credentials/network.
  * `data_origin: "mock"`: Explicit offline mock provider (`MockSatelliteProvider`) generating synthetic `mock-scene-*` fixtures.
  * `data_origin: "fallback"`: Primary real provider failure or network disconnection with `allow_mock_fallback=True`, returning deterministic synthetic fixtures tagged with `MOCK_DATA_USED` warning.
* **Safe In-Memory Caching:**
  * Bounded LRU cache (128 entries, 300s TTL) for repeated AOI/date discovery queries to minimize upstream STAC requests.
* **Windowed Tile Delivery (Retrieval Pipeline):**
  * Raster assets are accessed via HTTP 206 partial content byte-ranges using `rio-tiler`. Full scenes ($>600\text{ MB}$) are never downloaded locally; only the specific AOI bounding window is read into memory.

---

## 6. Spectral & Change Detection Processing Plan

### A. Spectral Indices Formulas & Bands
For Sentinel-2 L2A:
* **Red (Band 4):** Central wavelength $\sim 665\text{ nm}$ (10m resolution)
* **Green (Band 3):** Central wavelength $\sim 560\text{ nm}$ (10m resolution)
* **Blue (Band 2):** Central wavelength $\sim 490\text{ nm}$ (10m resolution)
* **NIR (Band 8):** Central wavelength $\sim 842\text{ nm}$ (10m resolution)
* **SWIR-1 (Band 11):** Central wavelength $\sim 1610\text{ nm}$ (20m resolution)

$$\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}} = \frac{B08 - B04}{B08 + B04}$$

$$\text{NDWI} = \frac{\text{Green} - \text{NIR}}{\text{Green} + \text{NIR}} = \frac{B03 - B08}{B03 + B08}$$

$$\text{NDBI} = \frac{\text{SWIR} - \text{NIR}}{\text{SWIR} + \text{NIR}} = \frac{B11 - B08}{B11 + B08}$$

### B. Two-Date Change Detection Math
For before-scene $A$ and after-scene $B$:
1. Compute $\text{NDVI}_A$ and $\text{NDVI}_B$ over the mutual AOI intersection.
2. Calculate difference raster: $\Delta\text{NDVI} = \text{NDVI}_B - \text{NDVI}_A$.
3. Classify changes using dynamic thresholds:
   * **Vegetation Loss / Degradation:** $\Delta\text{NDVI} < -0.20$
   * **Stable / No Significant Change:** $-0.20 \le \Delta\text{NDVI} \le +0.20$
   * **Vegetation Gain / Regrowth:** $\Delta\text{NDVI} > +0.20$
4. Compute total changed area in $\text{km}^2$ and percentage of valid AOI pixels.

---

## 7. AI / VLM Provider Abstraction

* **Provider Interface:** `BaseVisionLanguageProvider` abstract class.
* **Primary Adapter:** Google Gemini Multimodal API (using Gemini 2.0 Flash / Pro) configured via `RUNTIME_AI_API_KEY`.
* **Prompt Engineering Strategy:**
  * **System Prompt:** Instructs the model as a Senior Remote Sensing Scientist. Strict rule: *"Never invent coordinates, percentages, or area values. Rely exclusively on the provided spectral measurement JSON and image crops."*
  * **User Payload:** Combines the user query, AOI metadata, scene acquisition dates, calculated spectral index statistics ($\text{NDVI}_{\text{mean}}$, $\Delta\text{NDVI}$, water area $\text{km}^2$), and a downsampled visual image crop.
  * **Structured Output:** Model emits a strict JSON structure containing the narrative answer, key findings, and references to supporting evidence IDs.

---

## 8. Confidence, Warning, and Uncertainty System

* **Confidence Scale:** Strictly normalized float between `0.0` and `1.0` (where `1.0` = 100% certainty).
* **Confidence Factors:**
  1. **Data Quality ($C_{\text{quality}}$):** 1.0 for Level-2A surface reflectance; 0.8 for Level-1C top-of-atmosphere.
  2. **Cloud Impact ($C_{\text{cloud}}$):** $1.0 - (\text{CloudPercent} / 100.0)$.
  3. **Spatial Resolution ($C_{\text{resolution}}$):** 1.0 for AOIs with $> 100$ pixels; penalized for tiny AOIs near sensor resolution limit.
  4. **Model Certainty ($C_{\text{model}}$):** Evaluated from VLM reasoning consistency and spectral signal clarity.
* **Overall Score Formula:**
  $$\text{Confidence} = 0.35 \cdot C_{\text{quality}} + 0.25 \cdot C_{\text{cloud}} + 0.20 \cdot C_{\text{resolution}} + 0.20 \cdot C_{\text{model}}$$
* **Standard Warning Codes:**
  * `HIGH_CLOUD_COVER`: Scene cloud coverage exceeds 20%.
  * `RESOLUTION_LIMIT_WARNING`: AOI size is small relative to the 10m Sentinel-2 pixel size.
  * `TEMPORAL_GAP_LARGE`: Before/after scenes are separated by $> 180$ days, increasing seasonal ambiguity.
  * `UNGEIGER_REFERENCED_IMAGE`: Uploaded imagery lacks georeferencing metadata.

---

## 9. Visual Overlay Architecture

* **Vector Overlays:** Emitted as standard GeoJSON `FeatureCollection` (polygons for detected change areas, bounding boxes for detected objects). Rendered as MapLibre `fill` and `line` layers with color styling.
* **Raster Overlays:** Colormapped PNG tiles (e.g., NDVI Viridis or Delta-NDVI Red-Yellow-Green) served via dynamic tile endpoints and rendered as MapLibre `raster` layers with adjustable opacity ($0.0 - 1.0$).

---

## 10. Report Generation Design

* **Format Options:** PDF (via WeasyPrint / HTML canvas export) and structured JSON.
* **Dossier Sections:**
  1. Executive Summary & User Query
  2. AOI Map Thumbnail & Coordinates
  3. Satellite Scene Provenance (Acquisition times, Platform, STAC Item IDs)
  4. Measured Spectral & Change Analytics Table
  5. Grounded AI Findings & Interpretations
  6. Confidence Score & Limitation Disclosures
  7. Audit Trace & Generation Timestamp

---

## 11. Environment Variable Plan

| Variable Name | Environment | Required? | Purpose |
|---|---|---|---|
| `SATQUERY_ENV` | Server | Yes | Environment mode (`development`, `staging`, `production`) |
| `SATQUERY_API_PREFIX` | Server | Yes | Base route prefix (default: `/api/v1`) |
| `FRONTEND_CORS_ORIGINS` | Server | Yes | Allowed client origins (e.g., `["http://localhost:3000"]`) |
| `CATALOGUE_PROVIDER` | Server | Yes | Default STAC provider (`earth-search`) |
| `EARTH_SEARCH_BASE_URL` | Server | Yes | Base URL for STAC catalogue (`https://earth-search.aws.element84.com/v1/`) |
| `RUNTIME_AI_PROVIDER` | Server | Optional | AI provider identifier (`gemini`, `openai`, `mock`) |
| `RUNTIME_AI_API_KEY` | Server | Optional | Secret API key for runtime VLM service |
| `RUNTIME_AI_MODEL` | Server | Optional | Model identifier (e.g., `gemini-2.0-flash`) |
| `DATABASE_URL` | Server | Yes | PostgreSQL connection string |
| `NEXT_PUBLIC_API_BASE_URL` | Browser | Yes | Public API base URL (`http://localhost:8000/api/v1`) |
| `NEXT_PUBLIC_BASEMAP_STYLE_URL` | Browser | Yes | Vector basemap style URL (`https://tiles.openfreemap.org/styles/liberty`) |

---

## 12. Planned Contracts & Schema Specifications

Below are the 16 core field-level draft schemas governing the SIH vertical slice.

### Schema 1: `AOIGeometry`
*GeoJSON geometry representation of the user-selected Area of Interest.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `type` | `string` | Required | Fixed `"Polygon"` or `"MultiPolygon"` | GeoJSON geometry type | `"Polygon"` |
| `coordinates` | `array` | Required | Valid RFC 7946 coordinates; longitude in `[-180, 180]`, latitude in `[-90, 90]` | Closed ring of longitude/latitude pairs | `[[[77.58, 12.96], [77.62, 12.96], [77.62, 13.01], [77.58, 13.01], [77.58, 12.96]]]` |
| `area_km2` | `float` | Required | Float $> 0.0$ | Calculated geodesic area in square kilometers | `21.45` |
| `bbox` | `array[float]` | Required | Exactly 4 floats `[minX, minY, maxX, maxY]` | Bounding box of the AOI | `[77.58, 12.96, 77.62, 13.01]` |

---

### Schema 2: `SatelliteScene`
*Normalized satellite imagery scene discovery descriptor.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `scene_id` | `string` | Required | Non-empty string; unique provider scene ID | Unique identifier of the scene | `"S2B_T43PGQ_20251223T051848_L2A"` |
| `provider` | `string` | Required | Allow-listed provider (e.g. `"earth-search"`) | Upstream data provider | `"earth-search"` |
| `collection` | `string` | Required | Valid collection ID | STAC collection name | `"sentinel-2-c1-l2a"` |
| `acquired_at` | `string` | Required | ISO 8601 UTC timestamp format | UTC timestamp of satellite acquisition | `"2025-12-23T05:25:18.674Z"` |
| `cloud_cover_percent` | `float` | Required | Float in range `[0.0, 100.0]` | Provider-reported cloud percentage | `4.3` |
| `thumbnail_url` | `string` | Optional | Valid HTTPS URL or null | Public preview thumbnail image | `"https://earth-search.../thumbnail.jpg"` |
| `footprint` | `object` | Required | Valid GeoJSON Polygon | Spatial boundary of the satellite scene | `{"type": "Polygon", "coordinates": [...]}` |

---

### Schema 3: `AnalysisRequest`
*Client payload submitted when initiating an AI analysis.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `query` | `string` | Required | Length between 3 and 1000 chars | Natural language question from the user | `"What changed in vegetation and water coverage?"` |
| `mode` | `AnalysisMode` | Required | Enum value | Target analysis workflow mode | `"change_detection"` |
| `aoi` | `AOIGeometry` | Required | Valid `AOIGeometry` schema | The geographic boundary to analyze | `{ "type": "Polygon", "coordinates": [...] }` |
| `scene_a` | `SatelliteScene` | Required | Valid `SatelliteScene` | Baseline / earlier scene | `{ "scene_id": "S2B_...20251223..." }` |
| `scene_b` | `SatelliteScene` | Optional | Required if `mode == "change_detection"` | Comparison / later scene | `{ "scene_id": "S2C_...20251228..." }` |
| `parameters` | `object` | Optional | Key-value dictionary | Optional configuration parameters | `{"sensitivity": "medium"}` |

---

### Schema 4: `AnalysisMode`
*Enum representing supported analysis types.*

| Field Name / Value | Data Type | Purpose | Example |
|---|---|---|---|
| `"single_scene_inspection"` | `string` | Spectral & visual analysis of a single acquisition date | `"single_scene_inspection"` |
| `"change_detection"` | `string` | Two-date comparative change analysis | `"change_detection"` |
| `"vegetation_health"` | `string` | Focused NDVI & agricultural vigor analysis | `"vegetation_health"` |
| `"water_body_monitoring"` | `string` | Focused NDWI & hydrological flood/drought analysis | `"water_body_monitoring"` |

---

### Schema 5: `AnalysisJobStatus`
*Enum representing the execution state of an analysis job.*

| Status Value | Meaning |
|---|---|
| `"queued"` | Job received and waiting for worker dispatch |
| `"processing"` | Actively computing spectral rasters and querying VLM |
| `"succeeded"` | Analysis successfully completed with full results |
| `"failed"` | Execution terminated due to a handled error |

---

### Schema 6: `SpectralIndexResult`
*Quantitative summary of computed spectral index metrics.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `index_name` | `string` | Required | One of `"NDVI"`, `"NDWI"`, `"NDBI"` | Name of the calculated spectral index | `"NDVI"` |
| `mean` | `float` | Required | Value in `[-1.0, 1.0]` | Mean index value over AOI | `0.48` |
| `min` | `float` | Required | Value in `[-1.0, 1.0]` | Minimum index value over AOI | `-0.12` |
| `max` | `float` | Required | Value in `[-1.0, 1.0]` | Maximum index value over AOI | `0.82` |
| `std_dev` | `float` | Required | Value $\ge 0.0$ | Standard deviation of index values | `0.18` |
| `classified_area_km2` | `object` | Optional | Map of class names to area floats | Area breakdown by classified threshold | `{"dense_vegetation": 8.4, "sparse": 5.2}` |

---

### Schema 7: `ChangeDetectionResult`
*Quantitative change metrics between two acquisition dates.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `metric_name` | `string` | Required | E.g. `"delta_ndvi"`, `"delta_ndwi"` | Metric used to measure change | `"delta_ndvi"` |
| `loss_area_km2` | `float` | Required | Float $\ge 0.0$ | Area experiencing significant negative change | `2.84` |
| `gain_area_km2` | `float` | Required | Float $\ge 0.0$ | Area experiencing significant positive change | `0.92` |
| `unchanged_area_km2` | `float` | Required | Float $\ge 0.0$ | Stable area without significant change | `17.69` |
| `net_change_percent` | `float` | Required | Float percentage value | Overall net change percentage over AOI | `-8.95` |
| `method` | `string` | Required | Non-empty description | Algorithm / formula used | `"thresholded_ndvi_differencing"` |

---

### Schema 8: `Finding`
*Individual structured insight grounded in measured evidence.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `id` | `string` | Required | Unique identifier string | Finding identity key | `"fnd_veg_loss_01"` |
| `title` | `string` | Required | 5–100 characters | Brief descriptive title | `"Significant Vegetation Loss in Northern Sector"` |
| `description` | `string` | Required | Detailed statement | Narrative explanation of the finding | `"A 2.84 km² reduction in NDVI (>0.20 decrease) was detected."` |
| `category` | `string` | Required | `"vegetation"`, `"water"`, `"urban"`, `"general"` | Category of the finding | `"vegetation"` |
| `evidence_ids` | `array[string]` | Required | Non-empty list of referenced evidence IDs | Links to supporting evidence items | `["evd_spectral_01", "evd_overlay_02"]` |

---

### Schema 9: `EvidenceItem`
*Atomic piece of measured evidence backing an analysis finding.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `id` | `string` | Required | Unique identifier string | Evidence identity key | `"evd_spectral_01"` |
| `type` | `string` | Required | `"spectral_metric"`, `"change_stat"`, `"image_crop"`, `"vector_feature"` | Type of the evidence | `"change_stat"` |
| `source_scene_id` | `string` | Required | Valid `scene_id` | Source satellite scene | `"S2C_T43PGQ_20251228T052411_L2A"` |
| `metric_value` | `string` | Optional | Formatted measurement string | Human-readable metric value | `"-8.95% Net Vegetation Change"` |
| `parameters` | `object` | Optional | Key-value dictionary | Underlying calculation parameters | `{"threshold": 0.20, "bands": ["B08", "B04"]}` |

---

### Schema 10: `OverlayFeature`
*Map overlay layer specification for visualizing findings.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `id` | `string` | Required | Unique overlay ID | Unique layer identifier | `"ovl_change_mask_01"` |
| `title` | `string` | Required | Non-empty string | Human-readable layer label | `"Vegetation Loss Mask"` |
| `layer_type` | `string` | Required | `"geojson_vector"` or `"raster_tiles"` | MapLibre rendering layer type | `"geojson_vector"` |
| `geojson_data` | `object` | Optional | Required if `layer_type == "geojson_vector"` | GeoJSON FeatureCollection | `{"type": "FeatureCollection", "features": [...]}` |
| `tile_url_template` | `string` | Optional | Required if `layer_type == "raster_tiles"` | Tile URL template for MapLibre raster source | `"/api/v1/imagery/tiles/{id}/{z}/{x}/{y}.png"` |
| `style` | `object` | Required | Color, opacity, and line properties | Presentation styling | `{"fill_color": "#ef4444", "fill_opacity": 0.5}` |

---

### Schema 11: `ConfidenceBreakdown`
*Transparent confidence score and contributing factor breakdown.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `overall_score` | `float` | Required | Float in range `[0.0, 1.0]` | Overall calibrated confidence score | `0.87` |
| `data_quality` | `float` | Required | Float in range `[0.0, 1.0]` | Sensor and calibration quality factor | `1.00` |
| `cloud_impact` | `float` | Required | Float in range `[0.0, 1.0]` | Impact of cloud cover on visibility | `0.95` |
| `spatial_resolution` | `float` | Required | Float in range `[0.0, 1.0]` | Suitability of pixel resolution for AOI | `0.85` |
| `model_certainty` | `float` | Required | Float in range `[0.0, 1.0]` | AI model reasoning certainty score | `0.80` |
| `explanation` | `string` | Required | Brief summary text | Plain English explanation of confidence | `"High confidence based on cloud-free Sentinel-2 L2A data."` |

---

### Schema 12: `AnalysisWarning`
*Standardized machine-readable warning or limitation disclosure.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `code` | `string` | Required | Uppercase snake_case string | Standardized machine-readable warning code | `"HIGH_CLOUD_COVER"` |
| `message` | `string` | Required | 10–250 characters | User-facing explanation of the limitation | `"Cloud cover exceeds 15%, which may obscure some ground pixels."` |
| `severity` | `string` | Required | One of `"info"`, `"warning"`, `"critical"` | Warning severity level | `"warning"` |

---

### Schema 13: `AnalysisResponse`
*Complete envelope returned to the frontend upon analysis completion.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `analysis_id` | `string` | Required | UUIDv4 string | Unique identifier of this analysis run | `"anl_820dad1a-8c0e-433f-bcc2-8d56076d3315"` |
| `query` | `string` | Required | Matching request query | User query that was processed | `"What changed between these images?"` |
| `status` | `AnalysisJobStatus` | Required | `"succeeded"` or `"failed"` | Final completion status | `"succeeded"` |
| `answer` | `string` | Required | Synthesized answer from VLM | Comprehensive natural-language answer | `"Between Dec 23 and Dec 28, 2025, a net vegetation decrease of 8.95% was observed..."` |
| `findings` | `array[Finding]` | Required | List of structured findings | Key individual grounded findings | `[{ "id": "fnd_01", ... }]` |
| `spectral_results` | `array[SpectralIndexResult]` | Optional | List of computed spectral indices | Detailed spectral measurements | `[{ "index_name": "NDVI", "mean": 0.48 }]` |
| `change_results` | `ChangeDetectionResult` | Optional | Present for change detection mode | Measured change metrics | `{ "loss_area_km2": 2.84, ... }` |
| `overlays` | `array[OverlayFeature]` | Required | List of visual map overlay layers | Overlays to render on MapLibre | `[{ "id": "ovl_01", ... }]` |
| `confidence` | `ConfidenceBreakdown` | Required | Calibrated confidence breakdown | Confidence and factor metrics | `{ "overall_score": 0.87, ... }` |
| `warnings` | `array[AnalysisWarning]` | Required | List of warnings and caveats | Operational limitations | `[{ "code": "HIGH_CLOUD_COVER", ... }]` |
| `created_at` | `string` | Required | ISO 8601 UTC timestamp | Time analysis was generated | `"2026-09-18T13:40:00.000Z"` |

---

### Schema 14: `ReportRequest`
*Client request to generate a downloadable analysis dossier.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `analysis_id` | `string` | Required | Valid existing `analysis_id` | Reference to completed analysis | `"anl_820dad1a-8c0e-433f-bcc2-8d56076d3315"` |
| `format` | `string` | Required | One of `"pdf"`, `"json"`, `"markdown"` | Target export document format | `"pdf"` |
| `include_map_snapshot` | `boolean` | Optional | Default `true` | Whether to embed visual map crop | `true` |

---

### Schema 15: `ReportResponse`
*Metadata and download access for a generated report.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `report_id` | `string` | Required | UUIDv4 string | Unique report identifier | `"rep_91bc38d1-72ef-466a-bc12-98402ac34012"` |
| `analysis_id` | `string` | Required | Valid `analysis_id` | Associated analysis run ID | `"anl_820dad1a-8c0e-433f-bcc2-8d56076d3315"` |
| `format` | `string` | Required | Matching requested format | Report media format | `"pdf"` |
| `download_url` | `string` | Required | Relative or pre-signed download path | URL to download the report document | `"/api/v1/reports/download/rep_91bc38d1.pdf"` |
| `generated_at` | `string` | Required | ISO 8601 UTC timestamp | Timestamp of report generation | `"2026-09-18T13:40:15.000Z"` |
| `file_size_bytes` | `integer` | Required | Integer $> 0$ | Size of the report document | `248102` |

---

### Schema 16: `APIError`
*Standard error envelope returned on validation or processing failure.*

| Field Name | Data Type | Req/Opt | Validation Rule | Short Purpose | Example Value |
|---|---|---|---|---|---|
| `error.code` | `string` | Required | Standardized uppercase error code | Machine-readable error code | `"VALIDATION_FAILED"` |
| `error.message` | `string` | Required | Plain language explanation | User-friendly error message | `"The submitted AOI polygon has self-intersecting rings."` |
| `error.request_id` | `string` | Required | Request correlation ID | ID for tracing in backend logs | `"req_d892ba1409ac"` |
| `error.details` | `object` | Optional | Key-value dictionary | Specific field or parameter errors | `{"field": "aoi.coordinates"}` |
| `error.retryable` | `boolean` | Required | Boolean flag | Whether client should retry | `false` |

---

## 13. Configuration Architecture & Validation

The backend configuration is centralized in `backend/src/satquery/core/config.py` using `pydantic-settings` (`Settings` class inheriting from `BaseSettings`).

### Validation & Security Rules
1. **Secret Masking:** All database passwords, API keys, and client secrets use `pydantic.SecretStr` types. `Settings.get_safe_summary()` returns a public-safe dictionary redacting all credentials.
2. **Environment Validation:** Production mode strictly forbids `debug=True` and rejects loopback hosts (`localhost`, `127.0.0.1`, `::1`) in `FRONTEND_CORS_ORIGINS`.
3. **Database URL Validation:** Enforces `postgresql+psycopg` driver scheme with explicit host and database names.
4. **Offline Resilience:** Missing provider credentials never crash application startup or offline development. If a real provider is selected without credentials, it reports `ProviderStatus.NOT_CONFIGURED` gracefully.

---

## 14. Provider Abstraction & Safe Mock-to-Real Boundary

### A. Satellite Provider Subsystem (`backend/src/satquery/providers/satellite/`)
* **Interface Protocol (`SatelliteProvider` in `base.py`):**
  * `provider_id`, `display_name`, `mode`, `capabilities`
  * `is_configured() -> bool`
  * `health_check() -> ProviderInfo`
  * `search_scenes(request: SceneSearchRequest) -> SceneSearchResponse`
  * `get_scene(scene_id: str) -> SatelliteScene`
* **Implementations:**
  1. `MockSatelliteProvider` (`mock.py`): Returns deterministic synthetic scenes (`mock-scene-*`), validates bbox/date/cloud/sensor filters, and simulates test failures (`timeout`, `unavailable`, etc.) without calling external networks.
  2. `RealSatelliteProviderAdapter` (`real_adapter.py`): Validates STAC / Earth Search credentials and endpoints, raising structured `ProviderNotConfiguredError` when unconfigured without making live billable network calls.
  3. `SatelliteProviderRegistry` (`registry.py`): Selects providers based on configuration. When real mode fails and `allow_mock_fallback=True`, explicitly marks the response with `data_origin=DataOrigin.FALLBACK`, `fallback_used=True`, and attaches `WarningCode.MOCK_DATA_USED`.

### B. AI / VLM Provider Subsystem (`backend/src/satquery/providers/ai/`)
* **Interface Protocol (`AIProvider` in `base.py`):**
  * `provider_id`, `display_name`, `mode`, `capabilities`
  * `is_configured() -> bool`
  * `health_check() -> ProviderInfo`
  * `analyze(request: AIInterpretationRequest) -> AIInterpretationResponse`
* **Implementations:**
  1. `MockAIProvider` (`mock.py`): Refuses ungrounded hallucination if input evidence is missing (emitting `INSUFFICIENT_EVIDENCE` warning with conservative confidence); generates deterministic interpretations citing exact `evidence_ids` when evidence is provided.
  2. `GeminiAIProviderAdapter` (`real_adapter.py`): Validates `GEMINI_API_KEY` configuration.
  3. `AIProviderRegistry` (`registry.py`): Centralized registry routing mock/real/disabled AI workflows.

### C. Data Origin Semantics & Frontend Parity
* **Data Origin States:**
  * `real`: Authenticated, verified real satellite data or live AI model response.
  * `mock`: Deterministic synthetic fixture used during offline development/testing.
  * `fallback`: Real provider was requested but failed; system degraded safely to mock data with explicit warnings.
  * `uploaded`: User-supplied local imagery or vector asset.
  * `cached`: Verified cached result from prior execution.
* **Frontend Visual Mapping (`frontend/src/lib/data-origin.ts`):** Clear badges and UI tokens preventing mock or fallback data from being misrepresented as verified real imagery.
* **Provider Status Endpoint (`GET /api/v1/providers/status`):** Public-safe endpoint exposing provider readiness, capabilities, and data origin without leaking credentials or internal filesystem paths.

---

## 15. Analysis-Grade Imagery Retrieval & Preview Rendering (Phase 3A)

### A. Retrieval Strategy & Architecture
* **Strategy:** Bounded AOI Window Retrieval. The system never downloads full multi-gigabyte satellite scenes. All imagery requests are bounded by the user's validated AOI polygon and target pixel dimensions.
* **Product Type Distinction:**
  * `catalogue_thumbnail`: Low-resolution visual scene card thumbnail (from catalogue STAC discovery). Never rendered as analytical evidence.
  * `map_preview`: Bounded RGB display PNG/JPEG with 2%–98% percentile linear contrast stretching for fast map overlay.
  * `analysis_raster`: Multi-band lossless 32-bit Float32 GeoTIFF or Cloud Optimized GeoTIFF (COG) preserving raw physical reflectance values, georeferencing transform, CRS, and band metadata for downstream scientific processing.
* **Supported Formats:** `png`, `jpeg`, `geotiff`, `cog`.

### B. Visualization Presets & Band Mappings
1. **Optical Presets (Sentinel-2 L2A / Landsat-8/9):**
   * `true_color`: Red (`B04`), Green (`B03`), Blue (`B02`)
   * `false_color`: NIR (`B08`), Red (`B04`), Green (`B03`)
   * `vegetation`: NIR (`B08`), Red (`B04`), Green (`B03`) (visual contrast stretching; not an NDVI index)
   * `water`: Green (`B03`), NIR (`B08`), SWIR1 (`B11`) (visual water enhancement; not an NDWI index)
   * `urban`: SWIR2 (`B12`), SWIR1 (`B11`), Red (`B04`) (built-up contrast; not an NDBI classification)
2. **SAR Presets (Sentinel-1 GRD / Radar):**
   * `sar_grayscale`: Calibrated amplitude intensity
   * `sar_vv`: Vertical-Transmit Vertical-Receive amplitude
   * `sar_vh`: Vertical-Transmit Horizontal-Receive amplitude

### C. Resource Limits & Safety Envelope
* **Preview Dimensions:** Maximum 2048 × 2048 px (`IMAGERY_MAX_PREVIEW_PIXELS = 4,194,304`).
* **Analysis Raster Dimensions:** Maximum 4096 × 4096 px (`IMAGERY_MAX_ANALYSIS_RASTER_PIXELS = 16,777,216`).
* **Maximum File Size:** 50 MB (`IMAGERY_MAX_FILE_SIZE_BYTES = 52,428,800`).
* **Resolution Range:** 1.0 m to 1000.0 m per pixel.
* **Cache TTL:** 1800 seconds (30 minutes) with SHA-256 fingerprint deduplication.

### D. Raster Validation Pipeline (`RasterValidator`)
Every retrieved or generated raster passes strict validation before being stored or served:
1. **Magic Signature & MIME Check:** Validates GeoTIFF (`II*\0` / `MM\0*`), PNG (`\x89PNG\r\n\x1a\n`), or JPEG (`\xff\xd8\xff`) magic bytes. Rejects HTML/JSON error documents.
2. **Dataset Structure Check:** Opens dataset with Rasterio in memory; verifies width, height, band count, and data type against schema boundaries.
3. **Geospatial Integrity:** Ensures valid CRS exists, Affine transform is non-degenerate, and spatial bounding box is finite and intersects the requested AOI.
4. **Sample Readability:** Reads a safe 16×16 window sample to ensure pixel arrays are decodable and non-corrupted.

### E. Storage & Secure Delivery (`AssetStore`)
* **Opaque Asset IDs:** Assets are referenced exclusively by random UUIDv4 identifiers (`ast-` prefix); raw filesystem paths are never returned to clients.
* **Path Traversal Prevention:** Enforces storage within `data/imagery_cache` using `Path.resolve()` and strict prefix verification.
* **Atomic Writes:** Saves data to temporary filenames before atomically replacing the target asset file.
* **Endpoints:**
  * `POST /api/v1/imagery/request`: Request single-scene bounded preview or analysis raster.
  * `POST /api/v1/imagery/temporal-request`: Request bi-temporal imagery pair.
  * `GET /api/v1/imagery/assets/{asset_id}`: Stream binary raster with strict `Content-Type` headers and cache control.
  * `GET /api/v1/imagery/assets/{asset_id}/metadata`: Inspect non-binary geospatial and processing metadata.

### F. Temporal Grid Alignment Evaluation (`AlignmentStatus`)
Bi-temporal imagery pairs are analyzed across spatial parameters to evaluate co-registration suitability:
* `aligned`: Identical CRS, resolution difference $< 1\%$, matching pixel dimensions ($< 2$ px delta), and sub-pixel affine transform offset.
* `approximately_aligned`: Identical CRS and overlapping bounds, but slight resolution or grid shift requiring resampling.
* `requires_alignment`: Differing projections, resolution, or non-matching grids requiring formal reprojection in Phase 3B.
* `incompatible`: Non-overlapping footprints or incompatible spatial reference systems.
* `unknown`: Incomplete spatial metadata.

### G. Map Rendering & Comparison Modes
* **Single Scene Overlay:** Synchronizes MapLibre `image` source with exact 4-corner coordinates `[[west, north], [east, north], [east, south], [west, south]]` and configurable raster opacity/visibility.
* **Multitemporal Comparison Modes:**
  1. **Swipe Comparison:** Draggable split-divider slider displaying before scene on the left and after scene on the right with synchronized positioning.
  2. **Side-by-Side Comparison:** Dual synchronized geographic viewports for direct side-by-side inspection.
  3. **Opacity Blend:** Single-viewport interactive cross-fading of before/after layers.

---

## 16. Raster Harmonization, Reprojection & Analysis Preparation (Phase 3B)

### A. Core Workflow & Scope
Phase 3B implements a scientifically defensible raster preparation engine that transforms Phase 3A analysis assets into strictly co-registered, analysis-ready rasters for single-scene or multitemporal analysis.
* **End-to-End Pipeline:** Validated Imagery Assets $\to$ Raster Inspection $\to$ AOI Polygon Clipping $\to$ Metric Target CRS Selection $\to$ Reprojection & Resampling $\to$ Resolution Harmonization $\to$ Strict Grid Alignment $\to$ No-Data & Shared Validity Masking $\to$ Output Quality Validation $\to$ Derived GeoTIFF & Preview PNG in `AssetStore` with Explainable Readiness Metrics.
* **Strict Phase Boundary:** Prepares imagery grids and validity masks only. Does not compute NDVI/NDWI/NDBI or spectral indices, perform pixel differencing/change classification, call AI/VLM models, or produce reports.

### B. Target CRS Selection & Metric Grids
* **Deterministic UTM Selection:** Automatic determination of the optimal Universal Transverse Mercator (UTM) projection (EPSG:32601–32660 for North, EPSG:32701–32760 for South) based on the geometric centroid of the validated AOI.
* **Existing Projected CRS Preservation:** If an AOI or input raster is already in a valid projected metric CRS (e.g., local state plane or national grid), it is preserved.
* **Geographic CRS Constraint:** EPSG:4326 (WGS84 degrees) is rejected or converted to metric UTM for analysis rasters to prevent degree-to-meter distortion in spatial resolution.
* **Warnings Emitted:** `TARGET_CRS_SELECTED_AUTOMATICALLY`, `AOI_SPANS_MULTIPLE_ZONES`, `GEOGRAPHIC_CRS_NOT_SUITABLE_FOR_METRIC_GRID`.

### C. Resolution Harmonization & Resampling Semantics
* **Target Grid Strategies (`TargetGridStrategy`):**
  * `reference_before`: Snaps common grid to the before-scene resolution and bounds.
  * `reference_after`: Snaps common grid to the after-scene resolution and bounds.
  * `highest_resolution`: Adopts the minimum pixel size ($\min(\Delta x_A, \Delta x_B)$), subject to memory/pixel limits.
  * `lowest_resolution`: Adopts the maximum pixel size ($\max(\Delta x_A, \Delta x_B)$) to avoid artificial upsampling.
  * `configured_resolution`: Explicit user-specified pixel size in meters.
  * `common_intersection`: Snaps to the shared spatial extent at native sensor resolution.
* **Resampling Methods (`ResamplingMethod`):**
  * `bilinear` (default) & `cubic`: Used for continuous optical surface reflectance and SAR intensity values.
  * `average`: Used for continuous downsampling.
  * `nearest`: Strictly required for categorical classifications, binary masks, and provider quality flags.
* **Warnings Emitted:** `UPSAMPLING_APPLIED`, `DOWNSAMPLING_APPLIED`, `SOURCE_RESOLUTION_MISMATCH`.

### D. Strict Temporal Grid Alignment
Bi-temporal change detection requires exact mathematical equivalence across both rasters:
1. **Common Spatial Extent:** Intersection of the validated AOI bounding box and both scene footprints.
2. **Grid Snapping:** Bounding box coordinates snapped to integer multiples of the target resolution:
   $$\text{minX}_{\text{snap}} = \lfloor \text{minX} / \text{res} \rfloor \cdot \text{res}, \quad \text{maxY}_{\text{snap}} = \lceil \text{maxY} / \text{res} \rceil \cdot \text{res}$$
3. **Rigid Equivalence Check:** Outputs must have $100\%$ identical `(crs, transform, width, height, pixel_size_x, pixel_size_y)`. Transform delta tolerance is verified to $< 10^{-6}$.

### E. No-Data & Shared Validity Masking
* **Zero Value Preservation:** Legitimate zero reflectance values are preserved and never conflated with nodata.
* **Numeric Sanitization:** Non-finite values (`NaN`, `+Inf`, `-Inf`) are masked out as nodata.
* **Shared Validity Mask:** For temporal pairs, a combined boolean validity mask is computed:
  $$\text{Mask}_{\text{shared}} = \text{Mask}_{\text{before}} \land \text{Mask}_{\text{after}} \land \text{AOI}_{\text{inside}}$$
* **Metrics Reported:** `valid_pixel_count`, `invalid_pixel_count`, `valid_data_percent`, `shared_valid_pixel_count`, `shared_valid_percent`.
* **Warnings Emitted:** `LOW_VALID_DATA_COVERAGE` ($< 50\%$), `NO_SHARED_VALID_PIXELS` (blocking).

### F. Optical, SAR & Multimodal Boundaries
* **Optical Bands:** Preserves canonical band names (`blue`, `green`, `red`, `nir`, `swir1`, `swir2`) and underlying physical reflectance. Scales/offsets are preserved without double-application.
* **SAR Boundaries:** Supports polarizations (`VV`, `VH`, `HH`, `HV`) and acquisition modes. Does not claim unperformed speckle filtering or terrain correction without metadata. Emits `SAR_PREPROCESSING_REQUIRED` and `SAR_SPECKLE_FILTER_NOT_APPLIED`.
* **Multimodal Inputs:** Harmonizes optical and SAR inputs to a common metric CRS and AOI footprint while retaining separate assets. Strictly forbids automated uncalibrated pixel differencing.

### G. Readiness & Quality Assessment (`RasterQualityMetrics`)
* **Multi-Factor Score ($0.0 - 1.0$):** Combines metadata completeness ($0.25$), valid data coverage ($0.30$), AOI coverage ($0.25$), and grid alignment ($0.20$).
* **Readiness Classifications:**
  * `ready`: Quality score $\ge 0.80$, $100\%$ grid alignment, shared valid pixels $> 50\%$, zero blocking issues.
  * `ready_with_warnings`: Quality score between $0.50$ and $0.79$, minor warnings present (e.g. upsampling or low valid coverage), but scientifically usable.
  * `not_ready`: Quality score $< 0.50$ or hard blocking issue present (`NO_SHARED_VALID_PIXELS`, `GRID_MISMATCH`, `CORRUPT_SOURCE`, `MIXED_DATA_ORIGIN`).

### H. Module Paths & Endpoints
* **Backend Models:** `backend/src/satquery/api/schemas/preparation.py`
* **Harmonization Engine:** `backend/src/satquery/services/raster_harmonizer.py`
* **Preparation Service:** `backend/src/satquery/services/preparation_service.py`
* **API Endpoints:**
  * `POST /api/v1/processing/prepare-raster`: Prepares single-scene analysis raster.
  * `POST /api/v1/processing/prepare-temporal-pair`: Prepares co-registered bi-temporal pair.
* **Frontend Contracts & Clients:** `frontend/src/lib/preparation-contracts.ts`, `frontend/src/lib/preparation-client.ts`, `frontend/src/lib/use-raster-preparation.ts`
* **Frontend UI Component:** `frontend/src/components/workspace/raster-preparation-panel.tsx`

---

## 18. Pixel-Level Change Detection Engine & Evidence Architecture (Phase 4B)

### A. Core Mathematical Change Pipeline
The pixel-level change detection pipeline executes strictly upon verified, co-registered temporal raster pairs prepared in Phase 3B. The calculation is governed by the following sequence:

$$\text{Validated Temporal Pair} \xrightarrow{\text{Rigid Alignment Check}} \text{Shared Valid Mask} \xrightarrow{\text{Pixel Differencing}} \Delta \text{ Array} \xrightarrow{\text{Thresholding}} \text{Discrete 3-Class Mask} \xrightarrow{\text{Cluster Filtering}} \text{Vectorized Polygons} \xrightarrow{\text{Spatial Area Metrics}} \text{Evidence Records}$$

### B. Supported Change Detection Methods (`ChangeDetectionMethod`)
1. **Spectral Index Differencing ($\Delta = \text{Index}_{\text{after}} - \text{Index}_{\text{before}}$):**
   * `ndvi_difference`: Detects bidirectional vegetation vigor changes (Range: $[-2.0, +2.0]$, default colormap: `RdYlGn`).
   * `ndwi_difference`: Detects bidirectional surface water and moisture changes (Range: $[-2.0, +2.0]$, default colormap: `RdBu_r`).
   * `ndbi_difference`: Detects bidirectional built-up/bare ground spectral changes (Range: $[-2.0, +2.0]$, default colormap: `YlOrRd`).
2. **Absolute Index Differencing ($|\Delta| = |\text{Index}_{\text{after}} - \text{Index}_{\text{before}}|$):**
   * `absolute_index_difference`: Measures magnitude of spectral change regardless of polarity (Range: $[0.0, 2.0]$, default colormap: `viridis`).
3. **Multiband Change Magnitude ($M = \sqrt{\sum (\text{Band}_{i, \text{after}} - \text{Band}_{i, \text{before}})^2}$):**
   * `multiband_change_magnitude`: Euclidean radiometric distance across mutual bands `(B02, B03, B04, B08)` on harmonized surface reflectance (Range: $[0.0, 2.0]$, default colormap: `magma`).

### C. Threshold Strategies & Classification (`ThresholdStrategy`)
* `fixed`: Discrete cutoffs where $\text{Gain} \iff \Delta > T_{\text{pos}}$, $\text{Loss} \iff \Delta < T_{\text{neg}}$, $\text{Stable} \iff T_{\text{neg}} \le \Delta \le T_{\text{pos}}$.
* `standard_deviation`: Empirical statistical cutoff where $T_{\text{pos}} = \mu + k\cdot\sigma$ and $T_{\text{neg}} = \mu - k\cdot\sigma$ with $k \in [0.5, 5.0]$.
* `percentile`: Magnitude screening cutoff using the upper $P$-th percentile of absolute differences ($P \in [50.0, 99.9]$).
* `otsu`: Automatic bimodal histogram clustering finding the threshold $T^*$ that maximizes inter-class variance $\sigma_B^2(T)$.
* `manual`: User-customized explicit numerical cutoffs with validated ordering ($T_{\text{pos}} \ge T_{\text{neg}}$).

### D. Scientific Area & Percentage Denominator Discipline
* **Percentage Denominator:** All change percentage statistics ($\text{gain\_percent}$, $\text{loss\_percent}$, $\text{stable\_percent}$) **strictly** divide by `shared_valid_pixels`, never the bounding box or entire AOI.
  $$\text{Gain \%} = \frac{N_{\text{gain}}}{N_{\text{shared\_valid}}} \times 100, \quad \text{Loss \%} = \frac{N_{\text{loss}}}{N_{\text{shared\_valid}}} \times 100$$
* **Spatial Area Calculation:** Computed using metric pixel dimensions ($\Delta x \cdot \Delta y \times 10^{-6} \text{ km}^2$) on projected metric grids. Longitude/latitude degrees are never treated as metric meters.

### E. Noise Filtering & Vectorized Regions (`ChangeRegion`)
* **Cluster Filtering:** Connected component filtering removes isolated noisy pixel clusters smaller than `min_cluster_size_pixels` (default: 5 px).
* **Polygon Extraction:** Vectorized using `rasterio.features.shapes` into valid GeoJSON polygons, simplified with geodesic/projected tolerance in meters, sorted by spatial area descending, and bounded to `max_regions`.

### F. Scientific Disclaimers & Ground Truth Boundaries
* **Strict Semantic Separation:** Positive NDBI change is explicitly labeled as *“Built-up-related spectral increase”* and never proclaimed as *“confirmed new building construction”* (dry soil, cleared land, and tarmac exhibit identical NDBI responses). Negative NDVI change is labeled as *“Vegetation-related spectral decrease”* and never *“confirmed deforestation”*.
* **Explainable Multi-Factor Confidence:** Combines data quality, temporal baseline, spatial grid consistency, and index validity ($0.0 - 1.0$).

### G. Module Paths & Endpoints
* **Backend Models:** `backend/src/satquery/api/schemas/change.py`
* **Change Registry:** `backend/src/satquery/services/change_registry.py`
* **Change Engine:** `backend/src/satquery/services/change_engine.py`
* **Change Service:** `backend/src/satquery/services/change_service.py`
* **API Routes:**
  * `GET /api/v1/change/methods`: List registered methods and mathematical specifications.
  * `POST /api/v1/change/calculate`: Calculate pixel differencing, metrics, regions, and overlays.
  * `GET /api/v1/change/results/{result_id}`: Retrieve calculated change result.
  * `GET /api/v1/change/results/{result_id}/overlay`: Retrieve continuous or discrete classified PNG.
* **Frontend Contracts & Client:** `frontend/src/lib/change-contracts.ts`, `frontend/src/lib/change-client.ts`, `frontend/src/lib/use-change-detection.ts`
* **Frontend UI Component:** `frontend/src/components/workspace/change-detection-panel.tsx`

---

## 19. Multimodal Optical and SAR Evidence Fusion Architecture (Phase 4C)

### A. Problem Formulation & Scope Boundaries
Multimodal evidence fusion combines measured optical spectral change evidence (from Phase 4B) and calibrated SAR backscatter change evidence (from Phase 3B prepared SAR temporal pairs) across a shared AOI and comparable time periods.
* **Deterministic Rule-Based Fusion:** Operates strictly through deterministic, auditable rules without machine learning / black-box fusion models.
* **No Speculative Event Claims:** Spatial-temporal co-occurrence of spectral differencing and backscatter delta ($\Delta\text{dB}$) is reported strictly as *co-observed sensor response change*. It does *not* claim confirmed flood inundation, building destruction, or crop loss.
* **No Raw SAR Focusing:** Operates on calibrated Level-1 Ground Range Detected (GRD) linear power or decibel ($\text{dB}$) rasters.

### B. Calibrated SAR Backscatter Differencing ($\Delta\text{dB}$)
* **Power-to-Decibel Transformation:** For linear power rasters ($\sigma^0, \gamma^0, \beta^0$), decibels are calculated as:
  $$\text{dB} = 10 \cdot \log_{10}(\text{power}), \quad \Delta\text{dB} = 10 \cdot \log_{10}\left(\frac{\text{power}_{\text{after}}}{\text{power}_{\text{before}}}\right)$$
* **Strict Unit Handling:** Values $\le 0.0$ linear power are masked as invalid (no artificial epsilon floor). Unknown units or polarization mismatches (`VV` vs `VH`) produce explicit warnings or rejections.
* **Discrete Thresholding:** Classifies SAR delta into:
  * `increase`: $\Delta\text{dB} \ge T_{\text{inc}}$ (default $+2.0\text{ dB}$)
  * `decrease`: $\Delta\text{dB} \le T_{\text{dec}}$ (default $-2.0\text{ dB}$)
  * `stable`: $T_{\text{dec}} < \Delta\text{dB} < T_{\text{inc}}$

### C. 4-Role Temporal Observation System & Compatibility Matrix
The system tracks four distinct acquisition timestamps:
1. `optical_before`: Optical pre-event baseline timestamp $t_{O,b}$
2. `optical_after`: Optical post-event baseline timestamp $t_{O,a}$
3. `sar_before`: SAR pre-event baseline timestamp $t_{R,b}$
4. `sar_after`: SAR post-event baseline timestamp $t_{R,a}$

* **Timing Metrics:**
  * $\text{Before Offset} = |t_{O,b} - t_{R,b}|$
  * $\text{After Offset} = |t_{O,a} - t_{R,a}|$
  * $\text{Interval Overlap Ratio} = \frac{\max(0, \min(t_{O,a}, t_{R,a}) - \max(t_{O,b}, t_{R,b}))}{\max(t_{O,a}, t_{R,a}) - \min(t_{O,b}, t_{R,b})}$
* **Compatibility Statuses (`FusionCompatibilityStatus`):**
  * `valid`: Offsets $\le \text{tolerance}$ (default $30$ days), intervals overlap $> 0\%$, temporal order valid.
  * `compatible_with_warnings`: Offsets exceed tolerance or reverse ordering detected between before/after across sensors.
  * `incompatible`: Grid misalignment, CRS incompatibility, or disjoint bounding extents.

### D. Spatial Alignment & AOI Coverage Partitioning ($J = O \cap R$)
Total AOI area ($A_{\text{AOI}}$) is strictly partitioned into 4 mutually exclusive subsets:
1. **Jointly Observable Area ($J = O \cap R$):** Valid data in both Optical and SAR pairs ($N_J$ pixels).
2. **Optical Coverage Only:** Valid optical pair data, missing/nodata in SAR ($N_{O\setminus R}$ pixels).
3. **SAR Coverage Only:** Valid SAR pair data, missing/nodata in Optical ($N_{R\setminus O}$ pixels).
4. **Neither Sensor Available:** Missing/nodata in both pairs ($N_{\emptyset}$ pixels).
$$\sum \text{Partitions} = A_{\text{AOI}} \quad (100.0\%)$$

### E. 5-State Joint Observation Model
Within the jointly observable area ($J$), each pixel $(r, c)$ is classified into exactly one joint observation state:
1. `both_detect_change` (Amber): Both optical and SAR detected change above their respective thresholds.
2. `optical_response_only` (Green): Optical change detected; SAR response remained stable / below threshold.
3. `sar_response_only` (Blue): SAR delta exceeded threshold; optical response remained stable / below threshold.
4. `neither_above_threshold` (Slate): Both sensors have valid data with response below change cutoffs.
5. `uncertain` (Purple): Noise-filtered, high-uncertainty, or ambiguous boundary pixels.

### F. Area & Percentage Denominator Discipline
* **Joint State Percentages:** Evaluated strictly with denominator $J = \text{jointly\_observable\_area\_km2}$:
  $$\text{State \%} = \frac{\text{State Area (km}^2)}{J\text{ (km}^2)} \times 100$$
* If $J = 0.0\text{ km}^2$, all joint state percentages are strictly `null` (never $0.0\%$).

### G. Fused Vector Candidate Regions (`FusionRegion`)
* Contiguous clusters of joint state pixels are vectorized into standard GeoJSON polygons using `rasterio.features.shapes`.
* Filtered by minimum cluster size, sorted by metric area descending, and tagged with calibrated confidence, pixel count, and explainable rule descriptions.

### H. Multi-Factor Quality Score & Scientific Disclaimers
* **Composite Quality ($0.0 - 1.0$):**
  $$\text{Quality} = w_t \cdot Q_{\text{temporal}} + w_s \cdot Q_{\text{spatial}} + w_c \cdot Q_{\text{calib}} + w_v \cdot Q_{\text{coverage}}$$
* **Scientific Grounding Disclaimer:** "Evidence-level fusion reports spatial-temporal co-occurrence of measured optical spectral differences and calibrated SAR backscatter delta ($\Delta\text{dB}$). It does not establish a confirmed physical cause. Physical causes remain unverified hypotheses."

### I. Module Paths & Endpoints
* **Backend Models:** `backend/src/satquery/api/schemas/fusion.py`
* **SAR Engine:** `backend/src/satquery/services/sar_engine.py`
* **Fusion Engine:** `backend/src/satquery/services/fusion_engine.py`
* **Fusion Service:** `backend/src/satquery/services/fusion_service.py`
* **API Endpoints:**
  * `GET /api/v1/fusion/capabilities`: List supported rules, sensors, polarization modes, and default tolerances.
  * `POST /api/v1/fusion/analyze`: Execute multimodal fusion across optical change and SAR pairs.
  * `GET /api/v1/fusion/results/{result_id}`: Retrieve calculated fusion result and vector regions.
  * `GET /api/v1/fusion/results/{result_id}/overlay`: Retrieve 5-color discrete preview PNG overlay.
* **Frontend Contracts & Client:** `frontend/src/lib/fusion-contracts.ts`, `frontend/src/lib/fusion-client.ts`, `frontend/src/lib/use-multimodal-fusion.ts`
* **Frontend UI Component:** `frontend/src/components/workspace/multimodal-fusion-panel.tsx`

---

## 20. Natural-Language Query Routing and Evidence-Grounded AI Answers (Phase 5A)

### A. Core Architectural Principles & Grounding Rules
1. **Server-Owned Context Snapshot:** Context is constructed exclusively from authorized workspace and result records (`WorkspaceContextSnapshot`). Client-provided IDs are treated strictly as unverified references and resolved server-side against authorized state.
2. **Deterministic Intent Routing:** Queries are classified into 9 typed intents (`QueryIntent`) using regex-backed rule hierarchies, recording chosen intent, context fingerprint, required evidence types, missing inputs, approved operations, and routing reason.
3. **Multi-Factor Input Sufficiency Evaluation:** Prior to LLM generation, the system authoritatively checks input sufficiency (`SufficiencyStatus`), categorizing queries as `answerable`, `partially_answerable`, `clarification_required`, `needs_processing`, `insufficient_evidence`, or `unsupported`. If computation is missing, actionable `SuggestedNextAction` triggers are emitted without executing expensive raster pipelines synchronously.
4. **Zero Causal Hallucinations:** Claims are strictly separated into `measurement`, `interpretation`, `background`, and `limitation`. Spectral differences are never mapped to physical causes (e.g. positive NDBI is "Built-up-related spectral increase", never "confirmed construction"; NDVI decrease is "Vegetation-related spectral decrease", never "confirmed deforestation"; SAR $\Delta\text{dB}$ is "backscatter response change", never "confirmed flooding").
5. **Rigid Denominator & Metric Verification:** Every proposed measured claim must identify its `evidence_id`, `metric_field`, direction predicate, and denominator. Numerical values and percentages are computed server-side against authorized metrics (e.g., $V = \text{shared\_valid\_pixels}$ or $J = \text{jointly\_observable\_area\_km2}$).
6. **Bidirectional Map Linking:** Evidence references (`evidence_references`) and spatial region IDs (`spatial_references`) resolve backend GeoJSON bounds/polygons, enabling interactive UI highlighting and coordinate inspection without exposing raw raster arrays.
7. **Safe Deterministic Fallback Mode:** When AI provider keys are missing, disabled, rate-limited, or return invalid model schemas, the system automatically degrades to `deterministic_summary` mode with full measured fact cards, evidence links, and quality warnings, labeled as "Evidence summary — AI explanation unavailable."

### B. Module Structure & Endpoints
* **Backend Models & Contracts:** `backend/src/satquery/api/schemas/query.py`
* **Query Router:** `backend/src/satquery/services/query_router.py`
* **Evidence Retriever:** `backend/src/satquery/services/evidence_retriever.py`
* **Sufficiency Checker:** `backend/src/satquery/services/sufficiency_checker.py`
* **Claim Validator & Formatter:** `backend/src/satquery/services/claim_validator.py`
* **Query Service (Orchestrator):** `backend/src/satquery/services/query_service.py`
* **FastAPI Routes:** `backend/src/satquery/api/routes/query.py`
  * `GET /api/v1/query/capabilities`: List supported intents, sufficiency statuses, generation modes, max question length (500 chars), and active provider info.
  * `POST /api/v1/query/ask`: Process user natural-language question against active workspace snapshot.
* **Frontend Contracts & Client:** `frontend/src/lib/query-contracts.ts`, `frontend/src/lib/query-client.ts`
* **Frontend Hook & UI:** `frontend/src/lib/use-query-assistant.ts`, `frontend/src/components/workspace/assistant-panel.tsx`, `frontend/src/components/workspace/results-tabs.tsx`

---

## 21. Image VQA and Verified Spatial Grounding Architecture (Phase 5B)

### A. Problem Formulation & Visual Grounding Semantics
Visual Question Answering (VQA) enables users to ask natural-language questions directly about actual satellite imagery pixels, producing structured visual observations and mathematically verified, traceable placement of model-predicted bounding boxes onto the geospatial map.
* **Epistemic Separation:** Visual model observations (`observation_source: "model_prediction"`, `semantic_status: "unverified"`) are kept strictly distinct from computed evidence (spectral/change/fusion metrics). Spatial overlap between a visual observation and computed change regions indicates candidate spatial co-occurrence, never verified physical ground truth or physical causation.
* **Single & Bi-Temporal Operations:**
  * `describe`: Comprehensive scene description and feature identification.
  * `locate_feature`: Identification and bounding-box localization of specific ground features.
  * `compare_pair`: Bi-temporal comparative analysis between before and after acquisitions.

### B. Canonical Coordinate System & Provider Transformations
* **Continuous Pixel-Edge Coordinates:** Canonical normalized coordinates $[xmin, ymin, xmax, ymax]$ on $[0.0, 1.0]$.
  * Origin $(0.0, 0.0)$ is defined as the top-left edge of the image submitted to the vision model; $(1.0, 1.0)$ is defined as the bottom-right edge.
  * $X$ increases monotonically rightward; $Y$ increases monotonically downward.
* **Provider Adapters:**
  * Gemini VLM outputs $[ymin, xmin, ymax, xmax]$ on integer scale $[0, 1000]$. The adapter converts these to canonical $[xmin, ymin, xmax, ymax]$ on $[0.0, 1.0]$.
  * Invalid ordering ($xmin \ge xmax$ or $ymin \ge ymax$) or out-of-range values ($< 0.0$ or $> 1.0$) are rejected with `CoordinateStatus.OUT_OF_RANGE`.

### C. Exact Inverse Transformation Pipeline
To map a model-predicted canonical bounding box back to ground coordinates, the system performs an exact 6-step inverse transformation:
1. **Denormalize to Submitted Pixels:**
   $$px_{\min} = x_{\min} \cdot W_{\text{sub}}, \quad py_{\min} = y_{\min} \cdot H_{\text{sub}}$$
   $$px_{\max} = x_{\max} \cdot W_{\text{sub}}, \quad py_{\max} = y_{\max} \cdot H_{\text{sub}}$$
2. **Undo Recorded Padding:**
   $$cx_{\min} = px_{\min} - \text{pad}_{\text{left}}, \quad cy_{\min} = py_{\min} - \text{pad}_{\text{top}}$$
   $$cx_{\max} = px_{\max} - \text{pad}_{\text{left}}, \quad cy_{\max} = py_{\max} - \text{pad}_{\text{top}}$$
   *If the box lies entirely within the padded margin, it is flagged as `invalid_padding_only` and rejected from map projection.*
3. **Undo Resizing:**
   $$sx_{\min} = cx_{\min} \cdot \frac{W_{\text{crop}}}{W_{\text{resized}}}, \quad sy_{\min} = cy_{\min} \cdot \frac{H_{\text{crop}}}{H_{\text{resized}}}$$
   $$sx_{\max} = cx_{\max} \cdot \frac{W_{\text{crop}}}{W_{\text{resized}}}, \quad sy_{\max} = cy_{\max} \cdot \frac{H_{\text{crop}}}{H_{\text{resized}}}$$
4. **Undo Cropping (Offset to Native Raster):**
   $$\text{col}_{\min} = \text{col}_0 + sx_{\min}, \quad \text{row}_{\min} = \text{row}_0 + sy_{\min}$$
   $$\text{col}_{\max} = \text{col}_0 + sx_{\max}, \quad \text{row}_{\max} = \text{row}_0 + sy_{\max}$$
5. **Apply Raster Affine Transform:**
   Using the raster transform matrix $\begin{bmatrix} a & b & c \\ d & e & f \\ 0 & 0 & 1 \end{bmatrix}$:
   $$X_{\text{crs}} = a \cdot \text{col} + b \cdot \text{row} + c, \quad Y_{\text{crs}} = d \cdot \text{col} + e \cdot \text{row} + f$$
   for all 4 box corners $[(\text{col}_{\min}, \text{row}_{\min}), (\text{col}_{\max}, \text{row}_{\min}), (\text{col}_{\max}, \text{row}_{\max}), (\text{col}_{\min}, \text{row}_{\max})]$.
6. **Reproject to WGS84 GeoJSON:**
   Reproject projected metric coordinates $(X_{\text{crs}}, Y_{\text{crs}})$ to WGS84 (EPSG:4326) using `pyproj.Transformer.from_crs(manifest.crs, "EPSG:4326", always_xy=True)`, constructing an RFC 7946 Polygon with $[lon, lat]$ ordering and computing spherical geodesic bounding box and area.

### D. Image Manifest Schema & Immutable Lineage
Each image submitted to the vision model is paired with an immutable `ImageManifest` (`imf-*`):
* `manifest_id`, `asset_id`, `scene_id`, `image_role` (`single_image`, `before_image`, `after_image`).
* `sha256`: Cryptographic digest of the submitted image bytes.
* `submitted_dimensions`: Width and height in pixels as sent to the vision model.
* `original_dimensions`: Width and height of the source raster.
* `crop_window`: Offsets and dimensions $(col_0, row_0, W_{\text{crop}}, H_{\text{crop}})$.
* `padding`: Top, left, bottom, and right padding added during preparation.
* `crs`: Coordinate Reference System string (e.g., `EPSG:32643`).
* `affine_transform`: 6-element affine transform tuple $(a, b, c, d, e, f)$.
* `georeferencing_status`: `verified_georeferenced`, `unverified_metadata`, or `non_georeferenced`.

### E. Evidence Overlap & Verification Engine
* **Candidate Overlap Calculation:** Computes spatial intersection between the grounded visual observation polygon and computed change/spectral/fusion regions (`compute_evidence_overlap`).
* **Association Metadata:** Emits `overlapping_evidence_ids`, `evidence_overlap_fraction`, and `associated_change_magnitude` to assist user cross-examination without claiming physical causality.

### F. Non-Georeferenced Imagery Discipline
* If source imagery lacks valid georeferencing metadata (missing CRS or non-invertible affine transform), the grounding engine assigns `MapGroundingStatus.IMAGE_ONLY_NO_GEOREFERENCE`.
* Geographic coordinates $[lon, lat]$ are strictly `null` and never fabricated or interpolated.

### G. Module Structure & Endpoints
* **Backend Models:** `backend/src/satquery/api/schemas/visual.py`
* **Spatial Grounding Engine:** `backend/src/satquery/services/spatial_grounding.py`
* **Visual Image Preparer:** `backend/src/satquery/services/visual_image_preparer.py`
* **Visual Query Service:** `backend/src/satquery/services/visual_query_service.py`
* **API Endpoints:**
  * `POST /api/v1/query/visual`: Submit visual question answering query with image manifests.
  * `GET /api/v1/query/visual/capabilities`: List supported visual operations, provider information, and grounding statuses.
  * `GET /api/v1/query/manifests/{manifest_id}`: Retrieve immutable image manifest record.
* **Frontend Contracts & Client:** `frontend/src/lib/visual-contracts.ts`, `frontend/src/lib/visual-client.ts`
* **Frontend Hook & UI:** `frontend/src/lib/use-visual-qa.ts`, `frontend/src/components/workspace/assistant-panel.tsx`, `frontend/src/components/workspace/results-tabs.tsx`, `frontend/src/components/workspace/workspace-shell.tsx`
