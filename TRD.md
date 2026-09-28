# Technical requirements document

## Status and relationship to product requirements

This document defines the technical behavior needed to satisfy `PRD.md`; implementation evidence lives in `FEATURES.md` and phase reports. Phase 1 implements the base frontend/API/configuration/database-migration boundaries; Phases 2–3 add the workspace and local map/AOI workflow. User-authorized Phase 4 adds provider-neutral catalogue discovery, Phase 5 adds typed imagery viewing and visual comparison, Phase 6 adds bounded optical preparation, and Phase 7 adds bounded single-image inference. Phase 8 tasks 8A–8D add the typed two-date result boundary, comparable-pair preparation, a pure internal spectral-change baseline, and deterministic area/summary calculations; no change route or classification artifact exists yet. Server catalogue persistence, owned domain resources, production identity/database verification, and later analysis integration remain incomplete. Local drafts, visualization, and model prose do not satisfy server ownership or analytical measurement requirements.

Phase 8's initial result boundary requires two chronological stable same-collection scenes, the validated AOI, an identified Phase 6 preparation/common grid, explicit method/version/parameters, fixed changed/unchanged/unknown meanings, joint-valid and joint-usable coverage with named denominators, projected grid-cell area measurements, quality warnings, and checksum/software/time provenance. Unknown or unusable pixels remain unknown rather than unchanged. Counts, fractions, and areas must agree mathematically; arbitrary URLs, paths, display inputs, and confidence are rejected. This contract is not evidence that a change method has run.

The initial 8C method is versioned calibrated-RGB RMS reflectance difference with a fixed provisional 0.05 dimensionless threshold and no radiometric harmonization or per-image normalization. It can run only on the exact effective 8B pair after reliable registration and non-empty joint usability. Changed means an observed threshold-crossing spectral difference, not a detected cause or land-cover class. Clouds, shadows, missing/invalid data, unknown quality, and outside-AOI pixels remain unknown. Rejected or tampered pairs produce no classification.

Task 8D requires changed area from projected affine cells and changed percentage with joint-valid observed area as its named denominator. Joint-valid and joint-usable AOI coverage and unknown inside-AOI area are separate. CRS linear units must be converted to metres; angular degrees are invalid for square-metre measurement. Summary statements are deterministic from computed records, keep cause/land-cover undetermined, and omit vegetation direction unless calibrated required bands and a separately defensible method exist. The current RGB profile supplies no such directional vegetation method.

Task 8B requires pair preparation to recompute—not merely trust—joint masks from the effective Phase 6 scenes. Joint valid is inside the AOI and valid in every required band on both dates. Joint usable additionally requires both QA masks to be available and usable and explicitly removes cloud/cirrus, cloud/cast shadow, snow/ice, missing, unknown-quality, and outside-AOI pixels. Dates must be authoritative and increasing; bands/order and common grid dimensions/resolution must agree; spatial overlap and usable area must be non-empty; registration must be reliable with an accepted or unnecessary bounded correction. Failure produces a typed rejection reason and no classification output.

## System and responsibility boundaries

- **TRD-BND-001:** a Next.js client presents the map/viewer, inputs, job state, evidence, and results. It calls versioned FastAPI interfaces and never makes authoritative authorization decisions or receives server credentials.
- **TRD-BND-002:** FastAPI authenticates callers, checks resource ownership, validates requests, coordinates persistence and object-storage references, and orchestrates analysis/provider adapters.
- **TRD-BND-003:** spatial processing is isolated behind typed operations. Provider access, persistence, spatial computation, and UI rendering remain separate responsibilities.
- **TRD-BND-004:** long-running processing executes behind the job interface in `API_CONTRACT.md`. Task 6G uses one bounded lifespan-managed in-process dispatcher with thread-offloaded raster/CPU work; an external queue/runtime remains unresolved and is not introduced solely for this initial profile.

## Data flow

1. The backend authenticates a request and checks ownership of every referenced session, AOI, asset, query, result, and report.
2. Asset intake validates format and content, extracts metadata in a controlled environment, stores large bytes in private object storage, and writes metadata/provenance in PostgreSQL/PostGIS.
3. Query interpretation produces a validated intent/tool plan, not a geospatial fact. Orchestration verifies capability and input compatibility before creating work.
4. A worker moves the job through legal states, obtains authorized inputs, runs bounded tools, records events/parameters, and writes immutable artifacts through the storage boundary.
5. The backend validates and persists a structured result, then returns metadata plus short-lived authorized artifact access where appropriate.

## Asset metadata and validation

**TRD-AST-001** supports PRD-AST-001 and requires:

- provider/source type, provider asset identifier where applicable, original filename for uploads, immutable internal ID, media type, byte size, checksum, storage reference, ingestion status, and timestamps;
- acquisition start/end time in UTC when known, platform, sensor/instrument, product/processing level, bands or SAR polarizations, raster width/height, ground sample distance/resolution with units, and applicable orbit/look information;
- CRS identifier/WKT as needed, affine/georeferencing status, bounds geometry, pixel-to-world transform, nodata semantics, and footprint derived only when valid;
- cloud cover and provider/image quality fields with their source and semantics, never normalized into false equivalence without an explicit method.

**TRD-SEC-002** requires intake to enforce allow-listed types, configured byte and pixel/dimension limits, bounded archive expansion if archives are ever accepted, filename sanitization, content-signature inspection, raster parser isolation/resource limits, checksum computation, malware scanning where deployment risk requires it, and rejection before the asset becomes available. Exact formats and limits are unresolved and must become configuration plus tests before upload ships.

Remote asset fetching must satisfy `SECURITY.md`: allow-listed schemes/providers, DNS/IP and redirect checks, time/byte limits, and no arbitrary server-side URL fetch.

Task 5B implements only a remote visualization-reference subset of this boundary. FastAPI accepts the stable configured scene identity, retrieves current provider metadata, maps allow-listed STAC data/reflectance roles and red/green/blue common names, retains each band's advertised scale, offset, nodata, CRS, resolution, shape, and transform, and performs bounded HEAD checks against exact configured HTTPS destinations. Only advertised COG components that all pass become a resolved natural-colour visualization asset. Missing metadata/object access, unsupported format, and credential-required access remain distinct states and yield no usable asset. No pixels are downloaded, parsed, stored, tiled, rendered, or made analysis-ready.

Task 5C adds visualization-only raster reads after 5B succeeds. A closed FastAPI route issues an access-scoped, expiring tile-set ID; a second route serves fixed 256-pixel PNG WebMercatorQuad tiles for zooms 0–16 and the fixed natural-colour RGB recipe. rio-tiler/Rasterio use the COG geotransform, CRS, overviews, nodata, masks, and per-band scale/offset. Provider bytes are obtained by bounded HTTP range requests through an exact-host/path opener; raster header dimensions, CRS, transform, driver, and band index must match trusted catalogue metadata before reads proceed. This is tile visualization, not owned intake or analytical preparation.

## Catalogue discovery contract

Phase 4 task 4A defines the executable contract in `backend/src/satquery/api/schemas/catalog.py` and the public semantics in `API_CONTRACT.md`. Task 4B implements the typed adapter boundary and a restricted Earth Search STAC connector for current Sentinel-2 Collection 1 Level-2A metadata. Task 4C exposes public stateless collection listing, synchronous search, and item-detail routes. Task 4D consumes listing/search through a Zod-validated client in the existing workspace, preserving exact AOI/date/filter state, request cancellation, query-result association, and provider continuation. Task 4E renders actual normalized footprints and keeps local selection as provider/collection/item-keyed metadata context associated with the originating query. Task 4F serializes a closed versioned browser draft without cursor or temporary asset URLs, revalidates it on restoration, and refreshes current metadata through item detail while retaining explicit stale/unavailable states. These operations do not access the database, create an owned resource, or obtain analytical pixels.

- A search targets one configured provider adapter and carries a bounded WGS84 Polygon/MultiPolygon AOI, ordered UTC acquisition interval, provider-scoped collection identifiers, optional explicitly provider-reported cloud-cover threshold, fixed stable ordering, page limit, and opaque cursor.
- Normalized scenes retain provider/collection/asset identity, acquisition interval, footprint and derived bbox, optional platform/instrument/product/band/polarization/resolution/cloud metadata, preview/licence/access state, unavailable-field reasons, and field-level adapter provenance.
- Every populated provider-derived normalized field identifies its source record field or adapter-derived method. Raw provider payloads do not cross the public boundary unrestricted.
- Cloud-cover values retain provider field and semantics; providers may declare the filter unavailable. Adapters must not imply comparable cloud methods across collections/providers without an explicit normalization method.
- Thumbnail/preview availability is independent of analytical access. Public or expiring preview references are display aids; no preview or basemap becomes an analytical asset.
- Analytical access state distinguishes metadata-only discovery, mediated provider access, additional authorization/purchase, unavailable, and unknown. A separate authorized intake/reference operation is required before a discovered item becomes an owned usable asset.
- Pagination cursors are opaque and bound to actor, request digest, provider, ordering, and expiry by the future API implementation. Adapter/provider cursors must not be exposed in a way that bypasses authorization or request consistency.
- Validation, unavailable capability, rate limiting, and upstream failure return structured errors and never fabricated scenes. Cached responses, if introduced later, require explicit age/provenance semantics.

The 4A Pydantic geometry checks are a bounded input/schema layer, not a replacement for authoritative PostGIS/spatial validity checks in the future endpoint. Provider calls, retry policy, capability reporting, and error translation belong to 4B or later.

## Imagery viewer contract

Phase 5 task 5A defines closed Pydantic and Zod contracts with stable `{provider, collection, item}` scene identity. A resolved imagery identity additionally carries a provider-scoped asset identifier/version, while tile-set IDs, layer IDs, URLs, and expiry are explicitly non-identity delivery/display values.

A resolved imagery asset describes current catalogue state, asset accessibility, visualization-only render presets, acquisition interval, imagery media type, WGS84 bounds, attribution, resolution time, and an independent analysis-readiness assessment. It exposes no raster URL. Tile metadata is separately bound to the exact asset and preset and permits only expiring relative FastAPI-mediated tile templates with explicit bounds, zoom, tile size, media type, attribution, and access status. Provider credentials, unrestricted remote URLs, and durable signed URLs remain outside browser state.

Active layer state includes explicit display settings and render lifecycle. Catalogue availability, asset accessibility, successful rendering, and analysis readiness are separate typed states; no transition between them is inferred. Rendering controls are presentation operations and cannot create measured evidence or scientific preprocessing.

Comparison viewer state contains distinct chronological A/B scene identities and acquisition intervals. Timeline state contains unique, chronological scene entries and an in-set selection. These prepare UI state only: `TRD-CMP-001` compatibility, reprojection, alignment, overlap/mask, and quality checks remain required in their later scientific phase. Version 1 saved viewer state retains only an AOI draft fingerprint, camera, stable identities, acquisition, preset, display, partial/complete comparison slots, and timeline selection; it excludes tile templates/IDs, provider locations, expiry/access status, credentials, raster bytes, and render-success claims, so restoration must resolve access afresh.

Tasks 5B–5C implement provider resolution plus bounded tile delivery. Raster work runs outside the event loop with two tile slots and three bounded RGB component readers per tile; source-range reads are limited by deadline, count, bytes, and cache, while tile-set/tile-byte caches are bounded and access-scoped. Task 5D mounts one runtime-validated raster source/layer in the existing map; 5E adds validated presentation controls. Task 5F adds chronological A/B assignment, overlap gating, synchronized swipe/split maps, linked or explicit independent opacity, and per-side lifecycle/cleanup. It does not establish pixel co-registration, resolution equivalence, valid scientific overlap, preprocessing, or analysis. Task 5G implements timeline/state; 5H owns final verification.

## Processing preparation contract

Phase 6 task 6A defines a closed Pydantic contract for future backend-owned preparation. It reuses stable scene identity and validated WGS 84 AOI geometry, accepts only the existing Earth Search Sentinel-2 L2A optical collection/profile initially, and requires explicit bands, intended single-scene/pair task, clipping, grid policy/resolution, calibration source, resampling, original preservation, and pixel ceiling. Output grids must be finite, north-up, metre-based UTM grids whose affine transform, dimensions, resolution, and bounds agree.

Prepared raster data, validity masks, and quality masks are separate checksum-bound opaque artifacts. Calibration records distinguish applied, unnecessary, and unavailable coefficients/units. Provenance retains source identity/checksum availability, request/parameter digests, ordered steps, software versions, and UTC bounds. Quality checks require an actual measured value, units, threshold, mathematically consistent outcome, and explanation, or retain the measurement as null and unresolved. Task readiness references those checks and remains independent of processing success. Job status conforms to `TRD-JOB-001` state semantics but 6A implements no durable job, route, worker, storage, database persistence, raster operation, or analysis.

Task 6B implements only the calibrated native-grid input stage for one supported optical scene. The service resolves assets through the trusted provider adapter, requires the source-aligned policy and native resolution, revalidates raster headers, transforms the RFC 7946 AOI from EPSG:4326 into the source CRS, uses a windowed read, rasterizes the exact Polygon/MultiPolygon including holes into a separate mask, and retains per-band source validity. Its hard ceiling is 4,000,000 AOI-window pixels, further reduced by the request ceiling; existing per-band range request/byte/deadline limits also remain in force. Empty overlap, missing georeferencing, grid disagreement, unavailable/expired sources, unsupported bands/policies, and limit excess are explicit failures. Scale/offset is applied exactly once only to valid pixels; identity coefficients preserve already-calibrated values. There is no display stretch, clipping, date-wise normalization, model normalization, reprojection, resampling, artifact write, quality mask, readiness evaluation, or analysis.

Task 6C uses the Sentinel-2 Level-2A Scene Classification Layer described by the [official Sentinel-2 processing documentation](https://sentiwiki.copernicus.eu/web/s2-processing). The supported Collection-1 product uses these byte classes: 0 no-data, 1 saturated/defective, 2 cast shadow, 3 cloud shadow, 4 vegetation, 5 not vegetated, 6 water, 7 unclassified, 8 medium-probability cloud, 9 high-probability cloud, 10 thin cirrus, and 11 snow/ice. The applicable baseline is retained from `s2:processing_baseline`; the verified real product is baseline 05.11. Official product guidance notes that Collection-1 products benefit from defective-pixel reporting in SCL class 1 and documents remaining classification limitations.

For `sentinel-2-l2a-surface-reflectance-v1`, classes 4/5/6 are usable when all requested source bands are valid. Classes 0/1 are missing/invalid; 8/9/10 are cloud/cirrus; 3 is cloud shadow; 2 is retained separately as cast shadow; 11 is snow/ice; 7, unrecognized codes, and areas without usable QA are unknown. Every non-usable category is excluded, but their union is counted once. Water and dark reflectance remain valid when SCL and source validity permit; darkness alone is never nodata. Missing SCL makes quality unavailable/unknown, not clear.

SCL is categorical and is resized/reprojected only with nearest-neighbour. Following [Rasterio mask documentation](https://rasterio.readthedocs.io/en/stable/topics/masks.html), GDAL/RFC 15 nonzero values mean valid while `numpy.ma` mask `True` means invalid; 6C reads both and rejects disagreement. Coverage includes explicit output-window, inside-AOI, or quality-assessed denominators. Scene-wide `eo:cloud_cover` remains separate from measured AOI cloud/cirrus coverage.

Task 6D selects one AOI-derived UTM CRS only when the AOI lies within 80°S–84°N, one UTM zone, and one hemisphere. The requested metre resolution defines a deterministic outward-snapped origin, extent, affine transform, width, and height once for all inputs. Rasterio reprojection uses the request-recorded nearest/bilinear/cubic method for continuous calibrated data with invalid pixels supplied as nodata; all validity and quality categories use nearest-neighbour. Outputs preserve source calibration and native resolution, disclose upsampling as interpolation without new detail, and apply no cross-sensor harmonization. Pair coverage includes joint all-band validity and joint quality usability with named AOI/overlap denominators and projected pixel area. Common CRS/transform/dimensions do not establish feature registration.

Task 6E supports only same-provider Sentinel-2 L2A pairs with actual quality masks and a comparable red band. It partitions the common AOI into a deterministic 3×3 layout and uses bounded ±6-pixel masked zero-normalized cross-correlation, rejecting insufficient valid coverage, low texture, weak/ambiguous peaks, and search-boundary estimates. Five alternating patches estimate translation; at least three spatially distributed inliers and 60% agreement within 0.75 pixel are required. Four held-out patches provide independent residual evidence. Nonzero correction requires at least two held-out patches, residual median correlation ≥0.55, median improvement ≥0.03, and improvement in at least 60% of those patches. Only integer copying is permitted; all masks use the same translation, exposed borders become missing, overlap is recomputed, and original arrays are retained. Correlation, matching grids, or missing/NaN diagnostics alone never establish registration.

Task 6F defines versioned single-scene and pair profiles for a deterministic Scientific Validity Engine and GeoFeasibility Guard. Checks retain pass/warning/fail/unknown/not-applicable outcome, requiredness, measurements and denominators, threshold description, reason, evidence source, and corrective action. Threshold version `provisional-engineering-v1` is configurable engineering policy, not a universal scientific limit. Required failures or unknown evidence prevent positive task readiness; unrelated catalogue and map operations remain available. Requested spatial scale is not inferred from pixel size, and no overall accuracy or AI-confidence percentage is created.

Task 6G durably accepts only a request whose stable source/version evidence was resolved through the trusted adapter. Cache identity hashes owner/access scope, that safe evidence, a canonical AOI preserving holes, required band order, grid/options/profile, and code/config versions; it excludes locations, expiring URLs, and credentials. PostgreSQL revision `20260923_0002` stores the narrow preparation job, artifact metadata, and stage-event subset. Real completed/total stage units replace guessed percentages. Running/cancelling attempts present at restart fail explicitly as interrupted; durable queued work is dispatched again. Cancellation is cooperative between stages and never declares cancellation while an uninterruptible raster call is still running.

The current private artifact backend is a server-owned filesystem root with per-job byte limits and temporary-file/atomic-rename publication. Prepared calibrated GeoTIFFs, per-band/combined validity and AOI masks, categorical SCL/exclusion masks, pair joint masks, and a JSON manifest are published only with a successful database transaction. The manifest retains safe source provenance, calibration, grid, resampling, native/output resolution, registration/transformation evidence, explicit absence of normalization and cross-sensor harmonization, validity report, and artifact checksums where non-recursive. Missing files or incomplete metadata cannot satisfy a cache hit or artifact request. A configured verified principal is mandatory at the protected FastAPI boundary; absent identity or database capability returns unavailable without affecting public viewing/search.

## Geospatial correctness

- **TRD-GEO-001:** API geometries use GeoJSON `[longitude, latitude]` in WGS 84 (EPSG:4326) unless a field explicitly declares another CRS. AOIs must be valid, within coordinate bounds, and under configured vertex/area complexity limits. Database geometry type and indexes are defined in `DATABASE.md`.
- **TRD-GEO-002:** evidence records either pixel space tied to a source raster and dimensions, or geographic space with an explicit CRS and source asset. No geographic geometry is derived from an ungeoreferenced image.
- Real-world distance/area uses a documented projected/equal-area or geodesic method appropriate to extent; output records method, CRS/ellipsoid, units, exclusions, and assumptions.
- Percentage results record numerator, denominator, units, valid-pixel mask, nodata/cloud/quality exclusions, and rounding. Unknown values remain null.

## Comparison and multimodal preparation

**TRD-CMP-001** requires comparison validation to establish acquisition order, footprint overlap, CRS, transforms, resolution, nodata/valid masks, bands, processing levels, and relevant cloud/illumination/seasonal or sensor differences. The selected reference grid, reprojection method, resampling method (categorical vs continuous), co-registration approach and quality, valid-overlap mask, and exclusions must be recorded. An analysis is rejected or limited if alignment cannot support its claim.

**TRD-MOD-001** requires optical/SAR tools to declare accepted sensors/products, bands or polarizations, radiometric/geometric calibration assumptions, terrain correction/speckle or atmospheric preprocessing where relevant, acquisition compatibility, resolution tolerance, and validation domain. Fusion is never implied merely because both modalities are present.

## Query orchestration and result design

**TRD-ORC-001:** interpretation maps a question to a versioned, allow-listed capability plus typed arguments and required inputs. The server validates authorization, compatibility, cost/resource policy, and tool availability independently of model output. Retrieved text and uploaded content cannot add permissions or tool capabilities.

**TRD-RSL-002:** every stored result follows the shared design in `API_CONTRACT.md`:

- analysis/query and job identity;
- immutable input asset references and provenance snapshots;
- answer and supported findings;
- measurements with value/unavailable state, units, method, denominator/exclusions, assumptions, and supporting assets;
- evidence/artifact references with source image and coordinate space;
- confidence/quality fields with type, meaning, scope, and calibration status;
- warnings, limitations, execution summary, relevant tool/model versions, processing parameters, and timestamps.

Measured claims must come from the suitable data/tool output. A language model may interpret a question and explain validated outputs, but cannot invent a measurement, trace, progress value, or unsupported class attribution.

## Job execution and recovery

**TRD-JOB-001** adopts the lifecycle and transitions in `API_CONTRACT.md`. Submission uses an idempotency key scoped to owner and operation. Workers claim jobs atomically, emit append-only execution events, heartbeat when appropriate, and finalize results/artifact references transactionally enough to prevent a “succeeded” job without a retrievable result.

Retries are bounded and limited to classified retryable failures. An attempt records its number and error; it never rewrites a prior completed result. Cancellation is cooperative and ends in `cancelled` only after processing stops or output is quarantined. Stalled work is reconciled to `failed` or safely requeued according to a future queue design. Progress is null unless a tool provides truthful, monotonic, well-defined work units.

## Persistence and reports

- **TRD-PER-001:** PostgreSQL/PostGIS stores ownership, metadata, AOIs, state, lineage, results, and events. Large raster bytes and artifacts live in private object storage referenced by immutable keys/checksums. See `DATABASE.md`.
- **TRD-RPT-001:** report generation is a job/capability that snapshots the result version and disclosed provenance. Report artifacts inherit owner authorization, retention, and signed-access rules; missing/expired evidence is stated.

## Integrations and configuration

**TRD-INT-001:** each adapter has a typed internal interface, timeouts, bounded retries with jitter for safe operations, response validation, rate-limit handling, health/capability reporting, and provider-specific provenance. Missing credentials mark that capability `unavailable`; they never select fabricated or silent fallback data.

| Integration | Purpose | Required configuration | Failure behavior | Status |
|---|---|---|---|---|
| EO catalogue/access provider | Discover metadata and resolve supported visualization assets; later obtain authorized analytical assets | Exact Earth Search v1 base URL, metadata/raster host and collection allow-lists, timeout/retry/cache policy; credentials for future protected providers | Explicit unsupported/unavailable/credentials-required resolution; structured upstream/rate-limit/licensing errors | Earth Search metadata discovery and RGB COG visualization resolution implemented for `sentinel-2-c1-l2a`; tile delivery and analytical asset acquisition unresolved |
| Private object storage | Store uploads, source rasters, overlays, and reports | Endpoint/provider, private bucket, region, workload identity or credentials, signing policy | Intake/job fails safely; no public fallback | Vendor unresolved; architecture confirmed |
| Runtime AI service/model | Interpret questions and optionally ground a referring phrase | Explicit provider/model, server credential where applicable, safety/cost/time limits | Interpretation or grounding unavailable/failed; never fabricate tool results or geometry | Phase 7 implements protected jobs/workspace presentation for the pinned hosted answer adapter and local box detector. One real-chip detector run passes; hosted VQA/caption and production persistence remain unverified; Codex is not implied |
| Job backend | Dispatch and recover asynchronous work | Broker/service URL or managed identity, queue names, retry/visibility settings | Submission fails atomically or remains recoverable; no false progress | Implementation unresolved |
| Identity provider | Authenticate users and issue verifiable claims | Issuer, audience, keys/discovery, tenant policy | Protected endpoints deny access; no development bypass in production | Scheme/provider unresolved |
| Basemap/style provider | Visual context only | Public restricted style URL or backend-mediated config and attribution | Map context unavailable; analytical assets unaffected | Provider unresolved |

Phase 7A narrows the initial single-image answer/caption candidate to hosted, version-pinned `gpt-4.1-mini-2025-04-14`. Tasks 7B–7E implement a bounded Responses API transport, fixed scientific-chip processor, protected durable inference routes/artifacts, and workspace controls. No credential or successful live hosted response exists, so the capability remains explicitly unavailable at runtime. Input is server-created from trusted calibrated imagery and quality masks or an authorized prepared artifact. General-VLM prose is non-measured and its spatial output is not accepted as grounding. GeoChat-7B remains only a separately gated research candidate.

Task 7C selects pinned `IDEA-Research/grounding-dino-tiny` revision `a2bb814dd30d776dcf7e30523b00659f4f141c71` for text-conditioned rectangular boxes. It records preprocessing/crop transforms, clips invalid output, preserves prompt and predicted regions separately, converts chip boxes through the exact affine, and labels detector scores as uncalibrated relevance. The checkpoint does not produce segmentation masks and is not remote-sensing-specific. Task 7F ran it on one real QA-ready Sentinel-2 chip; the returned near-whole-chip box verified placement but was over-broad and supplies no accuracy claim.

**TRD-CFG-001:** configuration is environment-driven, typed, validated at startup, and separated into public browser configuration and server-only secrets. Phase 1 loads the root server `.env` through validated Pydantic settings and the separate frontend `.env.local` through Next.js; examples document the contract and local files remain ignored. Production secrets come from an approved secret store, not committed files.

## Failure handling and observability

- **TRD-SEC-001:** authenticate and authorize protected operations at the FastAPI boundary; keep secrets and protected object/provider access server-side; apply the upload, remote-fetch, logging, lifecycle, and agent/tool controls in `SECURITY.md`.
- **TRD-RSL-001:** use stable machine-readable errors from `API_CONTRACT.md`; disclose safe remediation without stack traces or sensitive provider details. Partial results stay explicitly incomplete.
- **TRD-OBS-001:** structured logs and traces correlate request ID, owner-safe actor ID, session/query/job IDs, capability, attempt, duration, and error code. Do not log tokens, credentials, signed URLs, raw sensitive prompts/assets, or unrestricted geometry. Metrics cover state latency, failure class, queue delay, tool duration, and storage/provider availability.
- Execution events are an auditable technical trace summary, not hidden chain-of-thought. Store tool name/version, sanitized parameters or their digest, input/output references, state, duration, and error code as policy permits.

**TRD-PERF-001:** instrument interaction, API, queue, provider, storage, and processing latency separately; establish baselines before enforcing budgets. Long processing remains asynchronous, resource/geometry/upload limits prevent unbounded work, and PRD performance figures remain targets until measured.

## UI technical requirements

**TRD-UI-001:** the frontend uses one workspace and renders server state defensively. The implemented discovery panel distinguishes basemap context from catalogue metadata, validates API responses at runtime, identifies cloud as provider-reported scene metadata, preserves honest null/thumbnail/error states, and never treats loaded-card count as a catalogue total. Catalogue footprints use actual normalized geometry in layers independent of the AOI; hover/selection synchronize with cards, stale query context is explicit, and provider previews remain in the details panel rather than masquerading as georeferenced raster layers. Future analytical UI must distinguish analytical layers, source assets, and derived evidence; provide a non-map representation for core evidence; never infer job completion locally; and handle expired signed URLs by requesting a newly authorized reference rather than persisting them.

## Deployment considerations

**TRD-DEP-001:** deploy frontend, API, workers, PostgreSQL/PostGIS, and private object storage as separate responsibility boundaries. Use TLS, least-privilege identities, private service paths where feasible, health/readiness checks, backups and restore tests, migration gates, resource quotas, and separate development/staging/production configuration. Processing environments must account for native geospatial libraries, CPU/memory/scratch-disk limits, and possibly distinct GPU pools only after a model requires them.

No platform, cloud, region, container base, queue product, storage vendor, or GPU requirement is confirmed in Phase 0.

## Compatibility and version policy

Phase 1 dependency versions are selected and locked from official compatibility documentation and a working minimal scaffold; `TECH_STACK.md` and generated lockfiles are authoritative. Future Python/PostGIS/GDAL-family and map/analysis combinations still require explicit compatibility checks. APIs are versioned under `/api/v1`; stored result/tool schema versions are explicit so readers can migrate or reject incompatible data.
