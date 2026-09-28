# API contract

The existing protected single-image VQA/caption job may use the server-only xAI Responses adapter (`grok-4.3`) when `RUNTIME_AI_PROVIDER=xai`, `RUNTIME_AI_MODEL=grok-4.3`, and `XAI_API_KEY` are configured. This changes no route or client credential contract. The same trusted scientific chip, source ID, Phase 6 readiness/check outcomes and bounded JSON answer contract are used; provider/model identity is recorded and included in the answer-job cache key. The model cannot supply measured area, counts, coordinates, confidence, change, or cause from its prose. Missing key, database, verified principal, or model access remains an explicit unavailable/failed path, never a demo fallback answer.

## Contract status

The Phase 1 health endpoints and common error/request-correlation behavior below are **implemented**. Phase 4 adds verified catalogue discovery, Phase 5 adds the verified imagery-viewer scope, Phase 6 adds partially verified protected optical preparation, and Phase 7 adds partially verified protected single-image inference. Phase 8 adds the typed two-date result plus partially verified protected change jobs, result access, and categorical tiles. Phase 9 adds partially verified SAR/optical paths. Phase 10A–F add conversation contracts, deterministic routing, protected bounded execution, owner-scoped context persistence, a partially verified workspace client and a partial integration audit; backend GeoAgent map/AOI mutation remains unavailable. Owned catalogue/AOI resources and server viewer persistence remain unimplemented, and protected processing/inference still requires the unavailable production identity/database setup. Operations explicitly labelled illustrative or future below remain unimplemented. The API base is `/api/v1`; breaking changes require a new major path or an explicitly versioned media/schema strategy.

## Phase 10A+B internal GeoAgent contract and routing

`satquery.api.schemas.geoagent` schema `1.0` is an **internal** contract, not a new public endpoint. `GeoAgentMessageRequest` carries a UUID request ID, optional conversation UUID, bounded visible user text, optional validated WGS84 AOI, and at most two distinct stable selected scene identities with declared optical/SAR modality, optional UTC acquisition time, and SAR polarization. It rejects client URLs/paths, duplicate scenes, extra fields, and client-claimed readiness. A selected unsupported source, including NISAR for the current optical/SAR operation, receives an explicit unsupported routing outcome rather than being relabelled as Sentinel-1. The response echoes the request/selection and records one intended analysis, ordered source identities where required, allow-listed proposed tool, exact missing inputs, trusted dependency findings (`available`/`unavailable`/`unknown`), status, user-visible explanation, and no executed result by default. Future `completed` responses require actual tool-result UUID references bound to the selected scenes and the proposed tool; they cannot be fabricated from routing alone. No source URL, confidence, pixel measurement, model answer, or progress percentage is part of this seam.

The pure deterministic router recognizes display-only imagery viewing, single-image question/caption, referring grounding, before/after optical change, separate optical/SAR observation, and draw/zoom/clear AOI actions. It does not call any provider or analysis tool. `plan_ready` means only that input selection is structurally sufficient; runtime availability defaults to `unknown` until supplied by a trusted server-side check, and source quality is not assessed. Missing AOI/scene/date/polarization/feature yields `clarification_required`; unvalidated object counts, confidence, causes, and cross-sensor change are not sent to VQA or misrepresented as measured results. Explicit user requests to override rules or fabricate an answer/result/evidence/measurement are `unsupported` and submit no tool. Map actions are recognized but report unavailable because GeoAgent map control is not connected. The 10C executor below applies the existing FastAPI authorization and trusted service boundaries; Phase 9 remains `PARTIALLY_VERIFIED`.

### Phase 10C protected execution

`POST /api/v1/geoagent/execute` accepts `GeoAgentMessageRequest` under the existing verified `ProcessingPrincipal` dependency. It returns typed `GeoAgentExecutionResponse` schema `1.0`, not a conversationally generated answer. FastAPI checks identity first; no client owner ID, asset URL/path, tool name, confidence, or analysis output is accepted. The server computes the allow-listed intent again, validates the exact existing tool request schema and requirements, then invokes only trusted service methods: Sentinel-2 tile metadata, Phase 7 single-image VQA/caption/grounding jobs, Phase 8 optical change jobs, or Phase 9 separate optical/SAR observation jobs. Change submission additionally re-fetches trusted acquisition order. Each registry entry declares scene count, AOI need, 2–20 s bounded submission timeout and whether the underlying operation supports cooperative cancellation. Existing workers still enforce their resource and quality gates.

Results distinguish `submitted`, `completed`, `result_pending`, `failed`, `unavailable`, `clarification_required`, `unsupported`, and `submission_unknown`. A queued job returns its real job ID, actual job status and an existing owner-protected cancel path, with null result ID. Completed imagery returns an actual tile-set ID and display-only metadata; cached completed analysis returns its real committed artifact/result ID and service output. A timed-out submission may have uncertain state, so clients must retry **the same request UUID**; the service idempotency key derives from that UUID and the tool, and the existing repository rejects a conflicting digest. Failure never creates an invented answer/result. The concise execution summary contains only selected intent, tool, stable source IDs, a SHA-256 of the validated AOI serialization when present, state, job ID and result ID. Map/AOI controls remain `unavailable`: current map navigation/editing is browser-local and no authorized GeoAgent bridge exists before 10E. The route adds no conversation persistence, new worker, or source-data bypass.

Task 10D adds protected `POST /api/v1/geoagent/conversations/{conversation_id}/turns`, `GET /api/v1/geoagent/conversations/{conversation_id}` and `DELETE /api/v1/geoagent/conversations/{conversation_id}`. A turn accepts UUID `request_id`, required `expected_selection_revision` (start at `0`; use the revision returned by the previous turn or GET), ≤1,000 visible characters and optional `ConversationSelection` (validated WGS84 AOI and ≤2 stable dated scene identities). Omission inherits the conversation selection; an explicit empty selection clears it. Only the server-derived verified owner/access scope can read or modify a conversation; an absent/cross-owner row is `404`, missing identity or durable storage is `503`, and a stale revision/optimistic write conflict is `409 CONVERSATION_CHANGED`. `GET` returns bounded selection, revision, earlier-scene candidates, latest committed analysis reference and at most eight recent tool references. `DELETE` removes only that state, not existing owned jobs/artifacts or their cancellation paths. An AOI/scene change clears dependent analysis/tool references. A follow-up resolves only unambiguous context; otherwise it returns `clarification_required` with a specific missing reference. A late result after selection change returns `stale` without the result body. Queued jobs become verified references only after owner-authorized succeeded status and committed artifact/result retrieval. Task 10E adds a browser client that reads this route and may open a source-validated committed change reference through existing authorized tiles; this does not add a backend map/AOI mutation tool. No client owner, arbitrary asset URL/path, confidence or fabricated answer is accepted; raw user text and model output are not persisted in this table. Production database/identity and retention policy remain unverified/unresolved.
Task 10D adds protected `POST /api/v1/geoagent/conversations/{conversation_id}/turns`, `GET /api/v1/geoagent/conversations/{conversation_id}` and `DELETE /api/v1/geoagent/conversations/{conversation_id}`. A turn accepts UUID `request_id`, required `expected_selection_revision` (start at `0`; use the revision returned by the previous turn or GET), ≤1,000 visible characters and optional `ConversationSelection` (validated WGS84 AOI and ≤2 stable dated scene identities). Omission inherits the conversation selection; an explicit empty selection clears it. Only the server-derived verified owner/access scope can read or modify a conversation; an absent/cross-owner row is `404`, missing identity or durable storage is `503`, and a stale revision/optimistic write conflict is `409 CONVERSATION_CHANGED`. `GET` returns bounded selection, revision, earlier-scene candidates, latest committed analysis reference and at most eight recent tool references. `DELETE` removes only that state, not existing owned jobs/artifacts or their cancellation paths. An AOI/scene change clears dependent analysis/tool references. A follow-up resolves only unambiguous context; a same-AOI follow-up may reuse a prior supported single-image, change or optical/SAR intent when its selected sources are unchanged. Otherwise it returns `clarification_required` with a specific missing reference. A late result after selection change returns `stale` without the result body. Queued jobs become verified references only after owner-authorized succeeded status and committed artifact/result retrieval. Task 10E adds a browser client that reads this route and may open a source-validated committed change reference through existing authorized tiles; this does not add a backend map/AOI mutation tool. No client owner, arbitrary asset URL/path, confidence or fabricated answer is accepted; raw user text and model output are not persisted in this table. Production database/identity and retention policy remain unverified/unresolved.

## Phase 8E computed change operations

`POST /api/v1/processing/changes` accepts only the bounded `PreparationRequest` with exactly two trusted Sentinel-2 scenes and an AOI, plus `Idempotency-Key`. `GET /api/v1/processing/change-jobs/{job_id}` returns stage status, `POST .../cancel` requests cancellation, and `GET .../result` returns the persisted computed result only after successful commit. `GET /api/v1/processing/artifacts/{artifact_id}/tiles/change/{z}/{x}/{y}.png` renders an authorized committed categorical artifact. Owner/access-scope checks apply throughout; clients cannot supply asset URLs or paths. Unknown remains distinct from unchanged, and summary prose is deterministic computed output rather than model evidence.

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
| `GET /api/v1/health/ready` | `200` or `503` | `200` only when PostgreSQL is reachable, PostGIS is installed, and Alembic is at revision `20260926_0003` |
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
      "migration_revision": "20260926_0003"
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

## Processing preparation contract

Phase 6 task 6A defines schema version `1.0` in `satquery.api.schemas.processing`; 6A itself exposed no endpoint, while 6G later connected the same contract to the protected operations below. `PreparationRequest` accepts one or two distinct stable `{provider, collection, item}` scenes, a validated RFC 7946 WGS 84 Polygon/MultiPolygon AOI, unique required optical bands, an explicit single-scene or pair task, the initial `sentinel-2-l2a-surface-reflectance-v1` profile, and bounded options. The initial profile accepts only the existing `earth-search` / `sentinel-2-c1-l2a` collection. Options require original preservation, AOI clipping, metadata calibration, explicit continuous/mask resampling, resolution, grid policy, and a bounded output-pixel ceiling; client URLs, paths, credentials, and arbitrary operations are rejected by the closed schema.

`OutputGrid` declares a north-up metre-based UTM EPSG CRS, six-term affine transform, dimensions, two-axis resolution, bounds, and area-pixel interpretation. Validators require finite values, no rotation/shear, consistent transform/resolution/bounds, and at most 100 million pixels. A `PreparedRaster` identifies its source scene and bands, uses an opaque checksum-bound raster artifact, and carries separate validity and quality-mask artifacts on the same declared grid. Validity defines exact invalid/valid classes; quality masks retain their own typed class meanings rather than being folded into nodata.

`SourceCalibration` records the exact resolved source asset, band role, method, coefficients, units, status, and explanation. Unavailable calibration retains null coefficients. `ProcessingProvenance` binds a canonical request digest to source identities/checksum availability, calibration records, contiguous processing steps and parameter digests, software versions, and UTC execution bounds. Artifact references contain opaque UUIDs, kind, media type, checksum, byte size, and access state only—never object keys, server paths, provider locations, or signed URLs.

Each `QualityCheck` contains a metric, scope, finite measured value or explicit unknown, units, threshold/operator, outcome, and explanation. Passed/failed outcomes require matching measurement and threshold units and must agree mathematically; unresolved measurements remain null. `TaskReadiness` separately declares `ready`, `limited`, `not_ready`, `unresolved`, or `unsupported`, references its exact checks, and lists unresolved checks. A `PreparationResult` may therefore report processing `succeeded` while readiness is `limited`, `not_ready`, or `unresolved`; success never forces suitability. Failed processing exposes no prepared outputs and cannot be ready.

`ProcessingJobStatus` follows the existing `queued`, `running`, `cancelling`, `succeeded`, `failed`, and `cancelled` lifecycle. Timestamps, attempts, optional measured work units, safe errors, and artifacts are state-consistent. Only succeeded jobs expose available committed artifact references, and no percentage is guessed.

Task 6B adds an internal service boundary, not a direct raster-input HTTP endpoint. It accepts only the closed single-scene request, resolves RGB assets from stable scene identity through the existing server-side adapter, and returns an in-memory source-aligned calibrated input with CRS, transform, bounds, dimensions, ordered source identities, dimensionless reflectance units, native resolutions, calibration coefficients/methods, a separate inside-AOI mask, and per-band validity. Client locations and filesystem paths remain absent. Task 6G is the only HTTP orchestration path for this service; it requires durable persistence and verified authorization before processing.

Task 6C remains internal and adds no route. Given a 6B raster input, it resolves the actual Sentinel-2 `scl` quality asset through the trusted provider adapter and returns separate boolean masks for outside AOI, missing/invalid, cloud/cirrus, cloud shadow, cast shadow, snow/ice, unknown quality, usable pixels, and the union of all exclusions. It also retains nearest-neighbour-resampled categorical SCL labels, product processing baseline, QA source identity, and separate catalogue scene-cloud metadata. Every coverage value includes pixel count, denominator name/count, and nullable percentage. Missing QA makes all inside-AOI quality unknown and none usable; it never means clear. This is an in-memory scientific boundary, not a persisted API response.

Task 6D also remains internal and adds no endpoint. It accepts only request-matched 6B/6C inputs and returns one in-memory AOI-derived UTM grid shared by every requested band and scene. Per-band validity and quality masks remain separate, pair outputs add joint-valid and joint-usable masks, and coverage records explicit pixel/area denominators. The result states that feature registration was not assessed and radiometric harmonization is absent. It exposes no provider URL, filesystem path, artifact, or new client-controlled fetch surface.

Task 6E adds no endpoint and accepts only an in-memory 6D same-sensor pair. Its internal result records the comparable band, moving-to-reference row/column convention, pixel/projected-map translation, per-patch diagnostics and spatial distribution, consensus agreement, held-out residual evidence, and a reliable/inconclusive/unsupported state. A correction, when independently validated, is an integer translation record plus corrected in-memory moving scene and recomputed overlap; the original pair remains present. Missing measurements are null-equivalent `None`, and no provider location, artifact reference, readiness decision, or accuracy claim is exposed.

Task 6F adds deterministic internal scientific-validity and geofeasibility reports. Each task profile emits pass, warning, fail, unknown, or not-applicable checks with evidence, measured values and denominators when available, provisional versioned thresholds, reasons, and corrective actions. Required unknown evidence blocks a positive task-readiness result without disabling catalogue search or map viewing. No aggregate accuracy, AI confidence, or LLM interpretation is produced.

Task 6G exposes the following protected operations. They are deny-by-default when no verified principal resolver or durable PostgreSQL service is configured:

| Operation | Success | Contract |
|---|---:|---|
| `POST /api/v1/processing/preparations` | `202` | Requires `Idempotency-Key`; validates limits and trusted source-version evidence before durable acceptance; returns `ProcessingJobStatus`. |
| `GET /api/v1/processing/jobs/{job_id}` | `200` | Owner/access-scope constrained status with actual completed/total stage units and no invented percentage. |
| `POST /api/v1/processing/jobs/{job_id}/cancel` | `200` | Idempotent cooperative cancellation; running work becomes `cancelling` until a stage boundary confirms stop. |
| `GET /api/v1/processing/jobs/{job_id}/quality-report` | `200` | Returns the persisted 6F report only for a succeeded authorized job; otherwise `409` or non-disclosing `404`. |
| `GET /api/v1/processing/artifacts/{artifact_id}` | `200` | Streams an owner/access-scope-authorized committed artifact with private/no-store caching and checksum metadata. |
| `GET /api/v1/processing/artifacts/{artifact_id}/tiles/{mask}/{z}/{x}/{y}.png` | `200` | Renders `usable` or unioned quality-`exclusions` from an owner/access-scope-authorized committed quality-mask artifact. Categorical reprojection is nearest-neighbour; responses are private/no-store. Other artifact kinds, mask names, and invalid WebMercatorQuad coordinates are rejected. |

The cache digest includes owner/access scope, trusted source asset/version evidence, canonical AOI rings and holes, band order, target-grid and processing options, task/profile, and code/configuration versions. Provider locations, signed URLs, and credentials are excluded. Only a succeeded database row with committed artifact rows and present private files is reusable. Raster, validity, categorical quality, pair masks, and JSON provenance manifest are atomically renamed before the success transaction; incomplete files or rows are never exposed as successful cache entries.

Task 6I confirmed the operational failure boundary: catalogue routes remain available without the processing database, while processing returns `503 CAPABILITY_UNAVAILABLE` when no verified identity resolver exists and readiness returns `503 DEPENDENCY_UNAVAILABLE` when PostgreSQL is unavailable. These responses are not accepted jobs, cache hits, readiness evidence, or authorization. Real protected job/artifact behavior remains unverified until both dependencies are configured.

### Phase 7A VQA/caption contract seam

Task 7A adds no HTTP operation. Internal schema version 1.0 defines a bounded model image chip by authorized prepared-raster UUID/checksum, fixed RGB rendering parameters, dimensions, source scene, explicit pixel-edge coordinate convention, projected CRS/affine transform, and the complete referenced Phase 6 quality context. Arbitrary client URLs, paths, bytes, display state, and per-image normalization are outside the contract.

VQA and caption requests are distinct. Results expose an explicit `available`, `unavailable`, or `unknown` state, pinned provider/model/version/adapter identity, image-specific evidence references, retained Phase 6 warnings/checks, and optional separately sourced grounding geometry with declared `image_pixel` or `projected_map` coordinates. `calibrated_confidence` is always null; extra confidence fields are invalid.

Task 7B implements these schemas as an internal service only. A source may be an authorized prepared artifact or an explicitly labelled trusted ephemeral extraction; the latter cannot claim a committed artifact/manifest. The checksum-bound chip records source assets, acquisition, fixed rendering, dimensions, AOI footprint, CRS/transform, and quality gate. Provider results additionally record strict inference parameters, provider response ID, and measured latency. Quality/unsupported questions may return `unavailable` without a provider response or latency. There is still no HTTP operation: public authorization, jobs, artifact access, and workspace integration remain outside 7B.

Task 7C adds a separate internal referring-grounding request/result. It binds short referring text and an optional user-selected integer pixel-edge crop to the exact checksum-bound chip. The selection remains request input and is never model evidence. Results identify the pinned detector/revision and preprocessing, distinguish detected/no-detection/ambiguous/unsupported/unavailable/failed states, retain model-output boxes in visual-prompt pixels, map them through crop offsets into chip pixels, and provide a projected map footprint from the chip affine. Candidate scores are labelled raw uncalibrated model relevance. The supported geometry is a rectangular bounding box only; mask or polygon requests fail explicitly. There is still no public HTTP operation, durable job, or artifact contract in 7C.

Task 7D exposes only stable scene/AOI inputs through protected `/api/v1/inference` operations. `InferenceSubmissionRequest` accepts a request UUID, one supported Earth Search Sentinel-2 L2A scene identity, validated AOI, a closed VQA/caption/grounding operation, bounded task text, and an optional normalized user-selected grounding crop. It has no URL, path, image-byte, provider-credential, readiness, answer, confidence, or model-geometry input. The server re-fetches catalogue identity and resolves scientific RGB and SCL assets through the trusted provider adapter before building the exact checksum-bound chip.

| Method and path | Success | Contract |
|---|---:|---|
| `POST /api/v1/inference/jobs` | `202` | Requires verified processing principal and `Idempotency-Key`; starts or reuses one operation-scoped durable job. |
| `GET /api/v1/inference/jobs/{job_id}` | `200` | Owner/scope-constrained state, actual completed/total stages, committed artifact reference, and result only after success. |
| `GET /api/v1/inference/jobs/{job_id}/result` | `200` | Returns the typed evidence record after success; otherwise `409` or non-disclosing `404`. |
| `POST /api/v1/inference/jobs/{job_id}/cancel` | `200` | Uses the existing durable cooperative-cancellation state machine. |
| `GET /api/v1/inference/artifacts/{artifact_id}` | `200` | Streams an authorized committed `inference_evidence` JSON record or its exact `inference_chip` PNG with checksum and private/no-store caching. Other artifact kinds are rejected. |

The evidence record retains source scene and acquisition, exact chip checksum/dimensions/assets/rendering/footprint/transform, Phase 6 checks, an explicit `proceed`, `proceed_with_warning`, `blocked`, or `unknown` decision, execution state, answer model/version/parameters where actually run, and validated grounding only where actually produced. Failed required quality blocks model execution; unresolved required quality produces `unknown`; missing runtime is `unavailable`, never clear/ready. Its disclaimer states that pixel/geometry provenance does not prove the model interpretation. No progress percentage or numerical answer confidence exists.

Inference uses operation-scoped rows in the existing processing tables. Cache identity includes owner/scope, canonical bounded request, stable provider item/version/acquisition evidence, and code/operation version; provider URLs and credentials are absent. The exact PNG input and JSON evidence record are atomically published before the success transaction, and both committed rows/files are required for cache reuse. Interrupted attempts are reconciled as failed and queued inference workers claim only `infer_single_image`, so they cannot execute preparation jobs.

Task 7E consumes these operations from the workspace. The browser submits only the current stable scene/AOI identity and bounded task text, polls actual job state, and renders only committed response fields. Results retain their source-scene binding; a changed selection marks an old result stale and suppresses its map overlay. Validated image-pixel boxes are drawn over the exact protected chip. Projected map footprints are displayed only after supported CRS conversion and geometry validation, and overlay visibility never changes the AOI. UI labels distinguish model interpretation from measurement, quality readiness, and unavailable capabilities; stage counts are not converted to progress percentages.

Task 7F verified one real QA-ready chip and local grounding result, but not a hosted answer/caption response or production-persisted job. Missing model configuration remains an explicit unavailable result; upstream bounded extraction failure remains a terminal failed job with no successful artifact. Browser callers must use an origin listed exactly in `FRONTEND_CORS_ORIGINS`; `localhost` and `127.0.0.1` are different origins. Phase 7 remains partially verified until the pinned hosted model, durable PostgreSQL/verified principal, successful real workspace question/caption, and annotated evaluation gates pass.

## Two-date change result contract

Phase 8's result contract is schema version `1.1` in `satquery.api.schemas.change`; tasks through 8D still add no HTTP operation. `TwoDateChangeResult` requires exactly two distinct stable source scenes labelled `before` and `after`, strictly ordered UTC acquisitions, the validated WGS 84 AOI, and the same initial provider/collection. It binds the result to a Phase 6 preparation job, one common `OutputGrid`, method/version, unique required band roles, explicit parameters and digest, no radiometric harmonization, the effective Phase 6 registration disposition, and a policy that treats pixels outside joint usability or unresolved quality as unknown.

The categorical raster meanings are fixed as `unchanged=0`, `changed=1`, and `unknown=255`; outside-AOI cells are not part of these inside-AOI measurements. Coverage explicitly uses `inside_aoi` as its denominator and records both joint-valid and joint-usable support. The contract validates that joint usable does not exceed joint valid, changed plus unchanged equals joint-usable pixels, unknown equals the remaining inside-AOI pixels, and every fraction and projected grid-cell area agrees with its pixel counts and pixel area. Schema 1.1 records changed/unchanged fractions against joint-valid observed pixels separately from fractions within joint usability. Zero joint-usable coverage remains all unknown. These area values use counted projected grid cells and do not claim exact vector-polygon area.

Quality limitations contain source Phase 6 check IDs, reasons, and corrective actions. Unknown evidence forces a `limited` result. Reproducible provenance binds the preparation job and manifest checksum, both prepared scene raster/validity/quality checksums, the exact parameter digest, software versions, and UTC execution bounds. The output is an opaque, available, checksum-bound `change_classification` GeoTIFF artifact reference; provider URLs, signed URLs, storage paths, arbitrary confidence, and extra inputs are invalid. Change-specific jobs/API operations, artifact creation, and UI remain unimplemented after the user revised 8D to measurement/summary work.

Task 8B adds no public operation. For an `optical_pair`, the existing protected `POST /api/v1/processing/preparations` job now runs an internal `pair_comparability_assessed` stage after Phase 6 validity. It consumes the exact common-grid/registration/acquisition evidence, verifies chronological sources, identical required band order, common grid shape/resolution, actual QA on both dates, spatial overlap, and reliable registration. It recomputes joint validity from both dates and the AOI, then joint usability by applying both dates' cloud/cirrus, cloud-shadow, cast-shadow, snow/ice, missing, unknown-quality, and outside-AOI masks.

The preparation manifest contains `comparison_preparation` with `comparable` or `rejected`, `comparison_allowed`, processing version/policies, source IDs and UTC dates, band order, exact grid, registration/correction state, inside-AOI valid/usable pixels, percentages and projected-cell areas, stable reasons/actions, and the existing atomic joint-mask artifact ID. A rejected pair retains diagnostics but sets `change_classification_artifact_id` to null. Processing/configuration versions changed for cache separation. No classifier, result route, new job operation, storage bypass, or map output exists in 8B.

Task 8C implements only the internal detector expected by the result contract: `calibrated_rgb_rms_reflectance_difference` version `8c-calibrated-rgb-rms-v1`, RGB inputs, fixed provisional threshold `0.05` in dimensionless surface-reflectance RMS units, `>=` comparison, no per-image normalization, and no radiometric harmonization. It emits no contract result or artifact until later protected integration. A detector outcome distinguishes completed, insufficient evidence, and failed; only completed outcomes contain arrays and class measurements.

The explicit task 8D request superseded that earlier integration placeholder. Internal `ChangeSummaryService` computes changed m² and percent of `joint_valid_observed_area`, plus separate observed/usable coverage and inside-AOI unknown area. Pixel area is the affine determinant converted using the projected CRS linear-unit factor; angular CRSs fail. Its deterministic statements retain dates, AOI, method, measured extent/coverage, QA cloud-shadow exclusions, alignment, and date-gap context. Directional vegetation measurement is absent for RGB-only input and cause/land-cover is `not_determined`. This remains an internal contract with no route or browser access.

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

## Phase 9A shared optical/SAR scene metadata contract

Task 9A adds internal schema version `1.0` in `satquery.api.schemas.scene_metadata`; it does not add a public route. `SceneMetadataResponse` has a discriminated `available` or `unavailable` outcome. An available record binds stable provider/collection/item source identity and optional source version to provider identity, mission, UTC acquisition interval, bounded WGS84 footprint, native x/y resolution in metres, authority-qualified native CRS, processing level, explicit product maturity, calibration semantics, and valid-data-mask semantics.

The scientific modality is closed and discriminated:

- `optical` requires one or more unique ordered optical bands and rejects polarization fields;
- `sar` requires one or more unique ordered polarization channels and rejects optical-band fields.

Calibration distinguishes source values that require a finite scale/offset or named provider algorithm, source values already calibrated with identity conversion, and unavailable calibration evidence. Mask evidence is separately `available` with a GDAL, categorical, or finite/nodata convention, or `unavailable` with a reason. Neither model accepts source URLs, filesystem paths, readiness claims, or extra fields.

An unavailable result retains the stable source/provider, expected modality, stable reason code, explicit missing fields, retryability, reason, and corrective action. Only transient provider failure is retryable. `SceneCombinationResponse` separately represents a supported or unsupported ordered two-scene combination, validates distinct source identities and modality order, and carries a policy version or stable rejection reason. It contains no confidence or implicit analytical-readiness claim.

Task 9A alone added no provider. Task 9B below now populates the SAR branch for one explicit product; existing optical catalogue, viewer, preparation, change, inference, and artifact APIs retain their prior schemas and behavior.

## Phase 9B Sentinel-1 RTC discovery and preparation

`POST /api/v1/sar/search` accepts only `provider: "inpe-bdc"`, a validated WGS84 AOI, UTC interval, and bounded limit. It searches fixed INPE collection `sentinel-1-rtc-1` and returns stable identity, time, footprint, actual HH/HV/VH/VV assets, mode, nominal resolution, and the populated Phase 9 metadata contract. It accepts no URL, path, credential, calibration claim, or client-authored readiness.

`POST /api/v1/sar/preparations` accepts one returned scene, AOI, one available polarization, and at most 1,000,000 pixels. The server re-fetches the item and resolves only allow-listed INPE RTC GeoTIFFs. Success records grid/bounds, gamma-0 power units, identity calibration, RTC/DEM evidence, nodata and layover/shadow counts, checksum, processing version, warnings, and an opaque relative preview URL.

`GET /api/v1/sar/preparations/{preparation_id}/preview.png` returns the cached AOI rendering. It uses `10*log10(linear gamma0 power)`, fixed -25 to 0 dB, and transparent invalid pixels. Analytical memory remains float32 linear gamma-0; preview colours are not analytical input. Preparations are bounded memory entries, not durable jobs/artifacts. Missing IDs and polarization, coverage, georeferencing, mask-grid, resource, access, and provider failures return explicit safe errors.

## Phase 9C NISAR PROVISIONAL GCOV discovery and ingestion

`POST /api/v1/nisar/search` accepts a validated WGS84 AOI, UTC interval, and limit 1–25 for the fixed public NASA CMR/ASF collection `NISAR_L2_GCOV_PROVISIONAL_V1`. Results contain the stable CMR concept ID, granule name, acquisition/footprint, L-SAR frequency and actual polarization metadata, provisional CRID/product/PGE versions, QA-link and acquisition flags, and known limitations. Granule CRS remains explicitly unavailable until HDF5 ingestion.

`POST /api/v1/nisar/ingestions` accepts only a returned scene identity, AOI, available frequency/real-valued diagonal covariance term, and a maximum of 1,000,000 pixels. The server re-resolves the granule through CMR and reads only its operator-staged HDF5 under `NISAR_PRODUCT_CACHE_ROOT/<concept-id>/<granule-ur>.h5`; arbitrary client URLs and paths are not accepted. Pinned `h5py` reads and checks the source projection, coordinate axes, mask, units, and fill value. The typed `ingested` outcome records native projected metre grid, affine, bounds, size, actual spacing, linear RTC gamma-0 power calibration, AOI/product-mask/nodata counts, QA flags and warnings, source/version, and processing version. The separate `unavailable` outcome records a stable reason and action for missing authenticated staging, unavailable layer, malformed product, no intersection, or resource limit. The analytical float32 raster stays server-side in a bounded in-memory cache; no map preview, durable artifact, analysis, or public raster download is offered in 9C.

## Errors

## Phase 9D internal optical/SAR pair result

9D adds no public route. `OpticalSarPairOutcome` is an internal, versioned scientific-preparation record for one selected Sentinel-2 L2A scene and one INPE Sentinel-1 RTC C-band scene over the identical AOI. It binds both stable source identities, acquisition UTC times and absolute time gap, the single projected grid, optical source bands/calibration and units, SAR selected polarization/native resolution/gamma-0 units and preparation checksum/version, separately resampled SAR values and masks, joint valid/usable masks, area/coverage with `inside_aoi` denominator, and explicit alignment evidence/reasons. States are `analysis_ready` or `insufficient_evidence`; without independent distributed feature correspondences, the latter is mandatory even when CRS/grid and overlap match. Neither result authorizes numerical optical-versus-SAR comparison, a change label, or use of display pixels. Production API/job/artifact integration is left for authorized 9E.

## Phase 9E bounded optical/SAR observations

Protected `POST /api/v1/optical-sar/jobs` accepts `OpticalSarAnalysisRequest` schema `1.0` with UUID request ID, stable Earth Search Sentinel-2 L2A and INPE Sentinel-1 RTC scene identities, validated AOI, selected real HH/HV/VH/VV polarization, 20 or 30 m target cells, and bounded question (500 characters). `Idempotency-Key` is required. No client asset URL/path, calibration override, display stretch, model score, or cross-sensor threshold is accepted. The only supported question is `Summarize the separate optical and SAR observations.` Other text produces an explicit insufficient-evidence answer, not an invented analysis. Provider resolution and version evidence enter the owner/scope-bound cache key; credentials and expiring asset URLs do not.

`GET /api/v1/optical-sar/jobs/{job_id}` returns the actual queued/running/cancelling/succeeded/failed/cancelled state and completed stage units. `GET /jobs/{job_id}/result` returns `OpticalSarAnalysisResult` only after a complete committed artifact. `POST /jobs/{job_id}/cancel` requests cancellation. `GET /api/v1/optical-sar/artifacts/{artifact_id}` streams the private JSON evidence record only for its owner/access scope. Requests fail closed without durable processing service or verified principal; unknown jobs/artifacts return 404 to other owners. The record is atomic and carries source IDs/times and available source-version/checksum/preparation-version evidence, separate calibrated reflectance and gamma-0 medians with units and valid-cell counts, source evidence bounding rectangles in the common grid CRS, AOI-denominator joint coverage/area, time gap, alignment state, limitations, request/job/artifact IDs, and processing version. Bounding rectangles locate measured pixels but do not assert every enclosed pixel is usable. `limited` permits separate-source summary only; missing QA, low/no joint coverage, or unsupported text yields `insufficient_evidence`. Neither state establishes optical/SAR agreement, registration accuracy, flood extent, buildings, cause, or confidence.

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
