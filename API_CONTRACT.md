# API contract

## Contract status

The Phase 1 health endpoints and common error/request-correlation behavior below are **implemented**. Phase 4 tasks 4A–4F add verified catalogue schemas, a metadata-only Earth Search adapter, public stateless collection/search/item routes, a runtime-validating workspace discovery client, local footprint/selection state, and a versioned browser-local selection draft. Phase 5 tasks 5A–5H add and verify closed viewer contracts, public-provider asset resolution, bounded server-mediated imagery tiles, browser MapLibre display, presentation controls, visual comparison, acquisition timeline, and browser-local viewer-state restoration. Owned asset intake, analytical selection/readiness, and server viewer persistence remain unimplemented. All other domain resource, job, result, artifact, and authorization operations remain an **unimplemented design** for later tasks/phases. The API base is `/api/v1`; breaking changes require a new major path or an explicitly versioned media/schema strategy.

## Common conventions

Phase 3 adds local browser AOI drafts and GeoJSON export only; it does not implement the proposed `/aois` endpoints or authorize domain access. The local geometry contract is documented in [the Phase 3 report](docs/PHASE_3_REPORT.md#geometry-contract). Exported browser features have no server resource ID or owner. Future API inputs must be independently validated and owner-scoped by FastAPI.

- JSON property names use `snake_case`. Resource IDs are stable, opaque UUID strings; the UUID generation variant is selected in Phase 1.
- Timestamps are ISO 8601 UTC with a `Z` suffix. Acquisition intervals use separate start/end fields; clients must not infer local time.
- Protected operations require a verified bearer/session identity as selected later. The API checks owner/tenant access for every referenced resource and returns `404` where policy requires concealing existence.
- Create/update requests use an explicit schema and reject unknown or invalid critical fields. Content type, body size, identifier count, text length, and geometry complexity are bounded.
- List endpoints use cursor pagination: `?limit=...&cursor=...`; responses contain `items` and `next_cursor` (null at end). Cursors are opaque and ordering is stable with an ID tie-breaker.
- GeoJSON uses WGS 84 longitude/latitude order per RFC 7946. Pixel evidence declares origin/dimensions; any non-default geographic CRS is explicit in the containing field.
- Nullable/unknown values are JSON `null` or a typed `availability` field, never plausible placeholders.
- `X-Request-ID` may be accepted/generated for correlation but is not trusted as authorization or idempotency.

## Implemented Phase 1 health API

| Method and path | Success | Meaning |
|---|---|---|
| `GET /api/v1/health/live` | `200` | Application process is running; it deliberately does not query the database |
| `GET /api/v1/health/ready` | `200` or `503` | `200` only when PostgreSQL is reachable, PostGIS is installed, and Alembic is at revision `20260907_0001` |
| `GET /docs` | `200` | Development OpenAPI UI |
| `GET /openapi.json` | `200` | Generated OpenAPI document |

Health responses use `Cache-Control: no-store`. Every response has `X-Request-ID`; a caller-supplied value is accepted only when it matches the bounded correlation-ID syntax. The success readiness body also includes `request_id`. A dependency failure returns `Retry-After: 5` and the common error envelope with code `DEPENDENCY_UNAVAILABLE`, `details: {"dependency":"database"}`, and `retryable: true`.

Successful liveness:

```json
{"status":"live","service":"satquery-api","version":"0.1.0"}
```

Successful readiness:

```json
{
  "status": "ready",
  "service": "satquery-api",
  "version": "0.1.0",
  "request_id": "req_example",
  "checks": {
    "database": {
      "status": "up",
      "postgis": "available",
      "migration": "current",
      "server_version": "value_reported_by_postgresql",
      "postgis_version": "value_reported_by_pg_extension",
      "migration_revision": "20260907_0001"
    }
  }
}
```

The values above describe the schema; they are not evidence that a real database check passed in the current environment. CORS is configured from an exact server-side origin allow-list and currently permits only `GET`/`OPTIONS` plus the documented health-request headers.

## Resources and proposed operations

| Resource | Representative operations | Ownership notes |
|---|---|---|
| Assets | `POST /assets/uploads`, `POST /assets/references`, `GET /assets/{id}`, `GET /assets` | Owner-scoped; upload completion/validation is separate from mere object receipt |
| AOIs | `POST /aois`, `GET/PATCH/DELETE /aois/{id}`, `GET /aois` | Validated owned geometry; deletion respects dependent analysis lineage |
| Sessions | `POST /sessions`, `GET/PATCH/DELETE /sessions/{id}`, `GET /sessions` | Container for user workspace/history references, not an authorization shortcut |
| Public discovery/access | `GET /catalog/collections`, `POST /catalog/searches`, `GET /catalog/collections/{collection_id}/items/{item_id}`, `POST /catalog/asset-resolutions`, `POST /imagery/tile-sets`, `GET /imagery/tiles/{tile_set_id}/{z}/{x}/{y}.png` | Stateless access to the configured public provider; source locations stay server-side and tile access creates no owned or analytical asset |
| Queries | `POST /queries`, `GET /queries/{id}`, `GET /queries` | References an owned session and owned/permitted assets/AOI |
| Jobs | `GET /jobs/{id}`, `POST /jobs/{id}/cancel`, `POST /jobs/{id}/retry` | Retry creates a new attempt or successor per final implementation; never overwrites success |
| Results | `GET /results/{id}`, `GET /queries/{id}/result` | Immutable result version; authorized artifact resolution is separate/short lived |
| Evidence/artifacts | `GET /artifacts/{id}`, `POST /artifacts/{id}/access` | Metadata is durable; signed access expires and is never the durable reference |
| Reports | `POST /reports`, `GET /reports/{id}` | Generation is asynchronous and owner-scoped |

Exact endpoint inclusion and methods are proposals to validate in implementation design. Resource names align with `DATABASE.md`.

## Phase 4 catalogue contract

Task 4A implements the schema boundary in `backend/src/satquery/api/schemas/catalog.py`; task 4C exposes it through the implemented routes below. The contract is provider-neutral: `provider` is a configured adapter identifier, not a browser-supplied URL. Version 1.0 accepts only the fields below and rejects unknown fields.

### Implemented routes

- `GET /api/v1/catalog/collections?provider=earth-search` lists the allow-listed collections for the configured provider as `CatalogueCollectionsResponse`.
- `POST /api/v1/catalog/searches` validates and executes a `CatalogueSearchRequest` and returns a `CatalogueSearchResponse`. The operation is synchronous and stateless; `search_id` identifies only that returned page and is not a persisted resource.
- `GET /api/v1/catalog/collections/{collection_id}/items/{item_id}?provider=earth-search` returns one normalized `CatalogueScene`.

These three public metadata operations do not require the database or create owned resources. They are anonymous because they expose only the configured public catalogue metadata adapter. Existing and future sessions, AOIs, assets, saved searches, provider credentials, and analytical intake remain protected and deny-by-default; 4C does not introduce an authentication bypass for them. Every response carries `X-Request-ID`; errors use the common envelope and include the same request ID.

Task 4D consumes collection listing and search from the workspace through a Zod-validated browser boundary. Each search uses the exact selected local AOI, inclusive UTC day boundaries (`00:00:00.000Z` through `23:59:59.999Z`), selected server-listed collection, optional provider-reported scene cloud threshold, descending acquisition order, and a page size of six. The browser forwards `next_cursor` unchanged for load more, binds rendered pages to the originating AOI/filter fingerprint, and aborts or disregards outdated work. It displays only loaded-card count, not a catalogue total. This client behavior does not persist a search or create/select an analytical asset.

Task 4E uses each validated `CatalogueScene.footprint` directly for local map visualization and keys local selection by provider ID + collection ID + provider item ID. The selected object retains the normalized scene and originating query fingerprint. AOI/query changes mark prior results stale and revalidate or clear selection; scene selection never mutates the AOI. This is browser workspace state only: it creates no API/database resource, conveys no analytical authorization, fetches no raster, and cannot enable analysis. Provider previews remain contained preview-panel media unless a later authorized asset flow supplies verified georeferencing.

Task 4F persists that metadata context as the versioned browser key `satquery.scene-selection-draft.v1`. The durable draft contains the composite identity, exact cursor-free validated query, normalized scene metadata, acquisition and retrieval timestamps, source-record/field provenance, licence/access state, and safe preview role/media metadata. It must not contain provider cursors, credentials, raster URLs, preview URLs, or preview expiry timestamps. Restoration revalidates the complete draft and calls the implemented item-detail route for current metadata. Missing items and provider failures remain explicit unavailable/stale states with preserved provenance and retry; corrupt or unsupported drafts are discarded. `Saved in this browser` never means database persistence, ownership, asset accessibility, or analysis readiness. Task 4F adds no API route or server resource.

### Search request

`CatalogueSearchRequest` contains:

- `schema_version: "1.0"`;
- `provider`: a bounded lowercase adapter identifier;
- `aoi`: an RFC 7946 Polygon or MultiPolygon in WGS84 longitude/latitude order;
- `acquisition.start` and `acquisition.end`: timezone-aware timestamps normalized to UTC, with end not before start;
- `collections`: zero to 50 unique provider-scoped collection identifiers;
- optional `cloud_cover`: `max_percent` from 0 through 100, fixed semantics `provider_reported`, and `include_unknown` (default false);
- `limit`: 1 through 100, default 25;
- optional opaque `cursor`: 1 through 2,048 characters with no control characters; and
- `sort`: `acquired_desc` (default) or `acquired_asc`. Stable implementation ordering must add provider asset identity/version as a deterministic tie-breaker.

The 4A geometry boundary structurally validates numeric finite coordinates, longitude/latitude bounds, ring closure, distinct vertices, non-zero area, self-intersection, consecutive duplicates, and a total 500-position limit. It rejects antimeridian-crossing geometry for this contract version, consistent with the current local AOI workflow. A future API implementation must still run authoritative spatial validity/policy checks independently of browser state and provider output.

Cloud cover is never treated as a universal comparable measurement. The filter and response metadata retain provider-reported semantics; a future provider capability layer must reject or explicitly declare an unsupported filter rather than silently reinterpret it.

### Normalized scene response

`CatalogueSearchResponse` contains a UUID `search_id`, status (`succeeded` or warned `partial`), the normalized request, provider identity, a bounded page of `CatalogueScene` items, exact `returned_count`, nullable opaque `next_cursor`, UTC `searched_at`, required attribution, and warnings. A partial response requires at least one warning. Every item and the response must match the requested provider, and a page cannot exceed the requested limit.

Each normalized scene contains:

- provider identity plus provider asset ID and nullable provider version;
- provider-scoped collection identity;
- UTC acquisition interval;
- nullable platform, product type, and processing level plus bounded instrument, band, and polarization lists;
- validated Polygon/MultiPolygon footprint plus a WGS84 bbox that must match footprint-derived bounds;
- nullable provider-reported cloud-cover metadata with its source field and semantics;
- zero or more spatial-resolution values with unit, axis meaning, and source field;
- optional preview/thumbnail metadata, optional licence metadata, explicit asset-access state, and unavailable-field reasons; and
- adapter/source-record provenance, retrieval time, SHA-256 metadata digest, and field-level source mapping for every populated normalized field required by the schema.

Unknown optional values are `null`, empty only where the collection itself is known to be empty, or listed in `unavailable_fields` with a reason. Provider payloads are untrusted data and are not returned as an unrestricted raw object.

### Preview, provenance, and analytical access

A preview has purpose `thumbnail` or `preview` and access `public`, `temporary`, `backend_mediated`, or `unavailable`. Public/temporary URLs must use HTTPS without embedded credentials; temporary URLs require UTC expiry. Backend-mediated and unavailable previews expose no URL. Signed/temporary URLs remain ephemeral and must not be logged or persisted as canonical references.

`asset_access.state` distinguishes `metadata_only`, `provider_accessible`, `requires_authorization`, `requires_purchase`, `unavailable`, and `unknown`. Its method is `none`, `provider_reference`, or `backend_mediated`; inconsistent combinations are rejected. No direct analytical asset URL is part of the public scene contract. A catalogue result therefore proves only that normalized provider metadata was discovered. It does not prove that bytes were obtained, licensed, validated, georeferenced locally, selected, persisted as an owned asset, or analyzed.

### Pagination and errors

Cursors are opaque and preserve Earth Search's actual continuation token rather than translating it to offsets. The 4C public route binds each cursor to the normalized request digest, provider, collections, filters, page size, and ordering; it validates that binding before extracting the bounded provider token. A mismatch returns `422 VALIDATION_FAILED` and never runs a changed upstream search. Because these operations are anonymous and stateless, there is no owner binding. A future authenticated saved-search cursor must additionally bind owner and expiry rather than reusing this public cursor contract.

Malformed geometry, dates, timezone boundaries, provider/collection identifiers, cloud percentages, page sizes, and cursors return `422 VALIDATION_FAILED`. Unsupported filter semantics return `422 CAPABILITY_UNAVAILABLE`; missing item metadata returns `404 CATALOGUE_ITEM_NOT_FOUND`; provider throttling returns `429 RATE_LIMITED`; malformed upstream metadata returns `502 UPSTREAM_INVALID_RESPONSE`; unavailable upstream service returns `503 UPSTREAM_UNAVAILABLE`; and provider timeouts return `504 UPSTREAM_TIMEOUT`. Retryability and bounded `Retry-After` guidance are included when known. A valid search with no matches returns HTTP 200 with `items: []`, `returned_count: 0`, and no fabricated fallback. No provider failure is converted into a successful empty page.

### Internal task 4B adapter boundary

`EarthSearchCatalogueProvider` implements the internal contract for provider ID `earth-search` and the allow-listed `sentinel-2-c1-l2a` collection. It uses STAC `intersects`, a UTC `datetime` interval, `eo:cloud_cover <= max_percent`, and acquisition-time sorting with item-ID tie-breaking. `include_unknown=true` is explicitly unsupported rather than reinterpreted. Empty collection input resolves to the one configured default.

Continuation cursors contain only a bounded Earth Search token plus provider/query binding. The adapter reconstructs every page from the validated request and accepts a provider next link only when it is an exact credential-free HTTPS `POST` to Earth Search `/v1/search`; provider-supplied filters and arbitrary URLs are ignored/rejected. Task 4C exposes these cursors only for anonymous stateless search. They are not suitable for future owner-scoped saved-search resources without additional owner and expiry binding.

Collection/item metadata is cached in a bounded TTL/LRU cache. The adapter records retrieval separately from acquisition time, preserves provider nulls as unavailable, exposes only allow-listed public thumbnail references, and never returns direct raster hrefs in `CatalogueScene`. `provider_accessible` means only that STAC advertised a data reference; no bytes, licence permission, georeferencing, or analytical readiness were verified.

## Phase 5 viewer contract

Phase 5 integration verification confirmed that the implemented public imagery routes accept stable scene identity and allow-listed rendering parameters only. Requests supplying a client URL/path, arbitrary expression preset, or unconfigured/internal provider are rejected at validation/provider boundaries; raster locations and credentials do not enter browser responses. Existing authorization behavior is preserved. Successful catalogue/asset/tile responses remain separate from browser render success and from analysis readiness.

Task 5A defines contract version `1.0` in `backend/src/satquery/api/schemas/viewer.py` and matching runtime-validation schemas in `frontend/src/lib/viewer-contracts.ts`. Task 5B implements stable-identity asset resolution. Task 5C implements the closed tile-metadata request plus FastAPI-mediated PNG delivery for the configured public provider. Task 5D consumes that contract in MapLibre without adding API routes or accepting provider paths/URLs from the browser.

### Identity and resolved imagery

`ViewerSceneIdentity` is the stable tuple `{provider, collection, item}`. A resolved imagery identity adds a provider-scoped `asset` identifier and nullable `asset_version`; an expiring URL, tile-set ID, storage key, or browser layer ID is never scene or asset identity.

`ResolvedImageryAsset` carries schema version, exact scene/asset identity, UTC acquisition interval, imagery media type, validated WGS84 bounds, one or more supported render presets, the default preset, attribution, and resolution time. Every render preset declares `rgb` with exactly three distinct band asset identifiers or `single_band` with exactly one, and has fixed purpose `visualization`. Presets describe presentation only and do not establish scientific preprocessing or method validity. No raster URL appears in the resolved-asset contract.

The contract intentionally keeps these states separate:

- `catalogue_availability`: `available`, `stale`, `unavailable`, or `unknown`;
- `asset_accessibility`: `accessible`, `requires_authorization`, `requires_purchase`, `expired`, `unavailable`, or `unknown`, with `none`, `provider_reference`, or `backend_mediated` method as valid for the state;
- `render_status`: `not_requested`, `loading`, `rendered`, `failed`, or `expired`; and
- `analysis_readiness`: `not_assessed`, `not_ready`, `ready`, or `unsupported`, always with a reason.

Catalogue availability does not imply asset accessibility. Asset accessibility does not imply the browser rendered pixels. Rendering does not imply analysis readiness. Task 5A and the planned viewer flow default analysis readiness to an honest unassessed/not-ready result until a later authorized asset-intake and method-validation phase supplies evidence.

### Implemented task 5B asset resolution

`AssetResolutionRequest` accepts only schema version `1.0` and `scene: {provider, collection, item}`. It rejects extra fields, upstream URLs, file paths, credentials, and arbitrary render definitions. The provider adapter re-fetches current item metadata by the validated stable identity; selects only assets whose STAC roles are allow-listed data/reflectance roles and whose `eo:bands.common_name` identifies one red, green, and blue band; and exposes the fixed `natural-color` visualization preset only.

For every selected component, the response records the provider asset identifier/version, band and common name, band index, canonical media type, nullable scale/offset/nodata, CRS, that band's own resolution, shape, transform, bounded access-check result, and safe content length. Raster locations never enter the public schema. Thumbnail metadata remains a separate field and does not contribute to renderability. Licence metadata and provider attribution are preserved.

`status.state` is exactly `supported`, `unsupported_format`, `unavailable_asset`, or `access_credentials_required`. An expired reference uses `unavailable_asset` while the independent asset-access state is `expired` with its UTC expiry. A supported result requires three ordered RGB components, advertised Cloud Optimized GeoTIFF metadata, CRS/resolution/shape/transform for each component, and a successful server-side `HEAD` response for each configured object. All failure states return `resolved_asset: null` and an empty component list. Catalogue availability, asset accessibility, `render_status: not_requested`, and `analysis_readiness: not_assessed` are returned separately; 5B cannot claim tile availability, successful rendering, or analytical readiness.

Earth Search raster requests are limited to HTTPS on the configured Sentinel-2 object host and collection path, without credentials, query strings, arbitrary ports, traversal, or unapproved redirects. Redirects are disabled per request and each reported hop is revalidated before a bounded follow. At most three HEAD attempts occur across a redirect chain for each of the three assets; no raster response body is requested or returned. HTTP 401/403 produces `access_credentials_required`; missing/inaccessible headers or objects produce `unavailable_asset`; inconsistent TIFF headers produce `unsupported_format`. Provider metadata errors retain the existing safe request-ID error envelope.

This route is anonymous only for the already configured public Earth Search collection and does not create a database resource. A future protected provider, saved selection, owned asset, tile reference, or analytical intake operation still requires the repository's unimplemented identity/ownership boundary.

### Tile metadata and active layer

`TileMetadata` binds an opaque UUID `tile_set_id` to the exact resolved asset identity and render preset. It includes WGS84 bounds, zoom range, 256/512 tile size, PNG/JPEG/WebP media type, required attribution, expiry, and explicit access state (`available`, `expired`, `denied`, or `unavailable`). An available tile set requires an expiring, credential-free relative `/api/v1/` URL template containing `{z}`, `{x}`, and `{y}`. Non-available tile access exposes no template. This preserves FastAPI mediation and prevents provider credentials or signed provider URLs from entering the browser contract or durable state.

Task 5C implements `POST /api/v1/imagery/tile-sets` with the closed `TileMetadataRequest`: schema version `1.0`, stable `scene`, fixed `render_preset: "natural-color"`, and fixed `tile_size: 256`. Unknown fields, client URLs/paths, expressions, arbitrary band choices, and unsupported recipes are rejected. Success returns `TileMetadata` for WebMercatorQuad zooms 0–16 and an expiring relative template. The tile-set cache is access-scope-aware and bounded to 32 entries/300 seconds by default; source expiry can shorten that lifetime.

`GET /api/v1/imagery/tiles/{tile_set_id}/{z}/{x}/{y}.png` validates the UUID, access scope, expiry, zoom, and matrix coordinates before reading. Non-intersecting or all-nodata tiles return `404`; unknown sets return `404`; expired sets return `410`; unsupported access returns `403`; invalid coordinates return `422`; provider/raster failures return `502`; and the 30-second request bound returns retryable `504`. Success is a 256×256 PNG whose combined RGB validity mask makes nodata/outside-coverage pixels transparent. Tile metadata/bytes prove API delivery only, never browser rendering or analysis readiness.

`ActiveImageryLayer` binds a workspace layer ID to the exact asset, acquisition interval, preset, optional tile-set ID, display settings, and all four independent capability states. Display settings are presentation-only: visibility, opacity from 0–1, brightness minimum/maximum from 0–1, contrast from −1–1, and saturation from −1–1. A `rendered` state requires an accessible asset and tile-set ID, but it still does not imply analysis readiness.

### Comparison, timeline, and saved state

`ComparisonSelection` contains distinct `scene_a` and `scene_b`, each with stable scene identity and its UTC acquisition interval; A must precede B by acquisition start. This ordering is viewer state only. It does not satisfy the later scientific checks for CRS, resolution, transforms, nodata, alignment, valid overlap, acquisition compatibility, or quality differences in `TRD-CMP-001`.

Task 5F implements the transient browser interaction for this contract. User slot assignments are normalized into chronological A/B before opening; duplicate identity and non-overlapping WGS84 bboxes are rejected. Each side obtains separate current tile metadata and render lifecycle through 5C. Bbox overlap permits a shared visual viewport only and is not a scientific valid-overlap or co-registration result.

`TimelineSelection` contains 1–100 unique scenes in nondecreasing acquisition-start order plus a selected scene that must belong to the timeline; stable identity deterministically orders equal timestamps. `SavedViewerState` is browser-state contract version `1`; it may retain an AOI draft fingerprint, Web Mercator camera, stable active asset/preset/display, partial A/B assignments, complete ordered comparison, and timeline with `saved_at`. Its closed shape excludes tile URL templates, tile-set IDs, provider URLs, access expiry/status, render-success claims, credentials, and raster bytes. Restoration validates the AOI and resolves fresh current access; durability is browser-local rather than authenticated server persistence.

Tasks 5A–5G implement contracts, asset resolution, bounded server tile delivery, browser imagery display, client-only display controls, chronological two-scene visual comparison, actual-acquisition timeline, and browser-local restoration. Comparison reuses two independently expiring 5C tile sets and adds no API route. The server still accepts only `natural-color`; opacity, visibility, brightness, contrast, saturation, timeline, and persistence never enter tile requests. Task 5H remains subject to the common request-ID, authorization, validation, expiry, retry, and secret-handling conventions above.

## Job submission and lifecycle

Creating an asynchronous query/report requires an `Idempotency-Key` header. The key is scoped to authenticated owner, operation, and a canonical request digest for a documented retention window. Reuse with the same digest returns the original submission; reuse with a different digest returns `409 IDEMPOTENCY_CONFLICT`.

A successful query submission returns HTTP `202` with `query_id`, `job_id`, `status`, `submitted_at`, and links. Validation, ownership, unavailable capability, or quota failure occurs before returning an accepted job whenever known.

Allowed states are:

| State | Meaning |
|---|---|
| `queued` | Durably accepted, awaiting a worker |
| `running` | Claimed and executing a real attempt |
| `cancelling` | Cancellation accepted; worker stop not yet confirmed |
| `succeeded` | Result and required output references committed |
| `failed` | Terminal failure for this job, with structured safe error |
| `cancelled` | Work stopped or output quarantined after cancellation |

Legal transitions:

- `queued -> running | cancelled | failed`
- `running -> succeeded | failed | cancelling`
- `cancelling -> cancelled | failed`
- terminal states have no outgoing transitions.

A retry is an explicit authorized operation with a new attempt/successor identity and lineage; it never moves a terminal job backward. `progress` is nullable and may be emitted only when derived from real monotonic work units; otherwise clients show the state without a percentage.

## Shared result and evidence design

The result contains:

- `id`, `schema_version`, `query_id`, `job_id`, `status`, `created_at`;
- `input_assets`: internal ID, provider/source identity, provider asset ID where applicable, checksum/version, acquisition time, and role;
- `answer` and an array of supported `findings`;
- `measurements`: value or unavailable state, units, method, supporting asset IDs, denominator/exclusions for percentages, assumptions, and precision;
- `evidence`: artifact/geometry reference, evidence type, source asset ID, coordinate space (`pixel` or `geographic`), CRS when geographic, pixel dimensions/origin when pixel-based, and related finding IDs;
- `confidence`: kind (`model_score`, `heuristic_quality`, or `calibrated_probability`), value, meaning, scope, calibration metadata where applicable;
- `warnings`, `limitations`, `execution_summary`, tool/model versions, relevant parameters or sanitized parameter reference, and processing timestamps.

Unknown values are null or use `availability: "unavailable"` plus a reason. A completed response may be `supported`, `limited`, or `unsupported`; a technically successful job does not force a supported scientific claim.

### Illustrative query submission (not a working endpoint)

```http
POST /api/v1/queries
Idempotency-Key: 3b2bca0b-illustrative-only
Content-Type: application/json

{
  "session_id": "7b518b38-67d9-4f12-a23d-9e55b0d43e33",
  "question": "What fraction of the valid AOI is classified as water?",
  "asset_ids": ["ab7c48f1-28da-46d7-8fac-380d21bdbc35"],
  "aoi_id": "d3fde6d0-5e7c-4fa8-91b9-8f1ac1d952bd"
}
```

```json
{
  "query_id": "820dad1a-8c0e-433f-bcc2-8d56076d3315",
  "job_id": "26cdcf26-1bf3-429b-9e18-497c2f6d73aa",
  "status": "queued",
  "submitted_at": "2030-01-01T12:00:00Z"
}
```

All identifiers, timestamps, and content in examples are synthetic and illustrative.

### Illustrative measurement fragment

```json
{
  "id": "measurement-synthetic-01",
  "availability": "available",
  "value": 18.4,
  "units": "percent",
  "method": "example_versioned_water_classifier",
  "supporting_asset_ids": ["ab7c48f1-28da-46d7-8fac-380d21bdbc35"],
  "denominator": "valid_pixels_inside_aoi",
  "excluded_pixels": ["nodata", "cloud_masked"],
  "assumptions": ["Illustrative contract value; not a genuine product result"]
}
```

The number above is deliberately marked synthetic and must never be displayed as an actual SatQuery analysis.

## Errors

Errors use an appropriate HTTP status and a body such as:

```json
{
  "error": {
    "code": "ASSET_NOT_GEOREFERENCED",
    "message": "This operation requires a georeferenced analytical asset.",
    "request_id": "req_synthetic",
    "details": {"field": "asset_ids"},
    "retryable": false
  }
}
```

Phase 1 implements `VALIDATION_FAILED`, `HTTP_ERROR`, `INTERNAL_ERROR`, and `DEPENDENCY_UNAVAILABLE`. Planned stable domain categories include `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `CONFLICT`, `IDEMPOTENCY_CONFLICT`, `CAPABILITY_UNSUPPORTED`, `CAPABILITY_UNAVAILABLE`, `ASSET_INVALID`, `ASSET_NOT_GEOREFERENCED`, `ASSETS_INCOMPATIBLE`, `RATE_LIMITED`, `UPSTREAM_UNAVAILABLE`, `PROCESSING_FAILED`, and `ARTIFACT_EXPIRED`. `details` is allow-listed and never includes stack traces, secrets, raw provider responses, or inaccessible resource metadata.

## Artifact access and expiry

Persistent responses return artifact IDs and metadata, not permanent public URLs. `POST /artifacts/{id}/access` rechecks ownership and lifecycle, then may return a short-lived signed URL plus `expires_at`. Clients must treat expiry as normal, avoid logging/persisting URLs, and request new access. The signing TTL is configured server-side; `.env.example` uses a safe illustrative local value, not a production decision.

## Authorization, retries, and concurrency

- Resource IDs never prove access. Nested references are authorized against the caller before work or signing.
- Mutations use conditional/version fields where lost updates matter. Delete/cancel operations are idempotent from the caller's perspective.
- Automatic client retries are limited to safe/idempotent operations and honor `Retry-After`; providers and workers use bounded classified retries.
- Rate limits and quotas may apply per actor, tenant, operation, storage, and processing cost. Exact limits are unresolved.
