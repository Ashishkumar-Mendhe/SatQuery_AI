# Security requirements

## Status and threat posture

Phase 1 implements only the development/runtime baseline described below; the remaining sections are requirements for the phases that introduce protected resources. Satellite imagery, AOIs, prompts, results, and provider metadata may reveal sensitive interests or locations, so default access is private and least privilege. Exact compliance classification, jurisdictions, and retention policy remain unresolved.

Implemented now: validated server settings; `SecretStr` handling for the database URL; safe public error envelopes; bounded request IDs; structured request logs; exact-origin CORS; local-only database port bindings; server-side database access; frontend runtime validation; ignored local environment files; the restricted Earth Search metadata/RGB resolver; bounded public-collection imagery tiles; and a same-origin-template-only MapLibre consumer described below. Authentication, protected-resource authorization, uploads, analytical provider access, runtime AI, security headers, rate limits, and production hardening are not implemented.

## Authentication and authorization

- A future verified identity provider authenticates users. FastAPI validates issuer, audience, signature, time claims, and tenant context; production has no anonymous development bypass.
- Authorization is backend-owned and deny-by-default. Every session, AOI, asset, query, job, result, evidence artifact, catalogue search, and report reference receives an owner/tenant check, including nested IDs and signed-link issuance.
- Opaque IDs are not capabilities. The browser cannot bypass the API to access protected database rows, object keys, provider assets, or administrative operations.
- Service identities and workers receive only the database, queue, object prefix, provider, and key operations they need. Privileged administrative and deletion actions require separate authorization and audit.

## Secrets and configuration

- Secrets remain server-side in an approved environment/secret store and are never committed, placed in `NEXT_PUBLIC_*`, bundled to the browser, embedded in URLs, copied into test fixtures, or printed in logs/reports.
- `.env.example` uses explicit non-production placeholders for the local database and blank later-phase provider fields; it documents consumers and is never a deployable secret source. `.env*` is ignored except examples. The backend resolves only the repository-root `.env`; the frontend loads its separate `.env.local`. Existing local files must not be overwritten. Rotate credentials after suspected disclosure and avoid long-lived provider keys where workload identity is available.
- Signed URLs are short-lived, owner-authorized delivery artifacts. Do not persist or log them; constrain method/object/content disposition where the storage service supports it.

## Upload and parsing controls

- Enforce allow-listed content types and actual file signatures, filename normalization, byte/pixel/dimension limits, upload timeouts, per-owner quotas, and checksum verification. Store uploads outside executable/static-web roots with server-selected object keys.
- Treat metadata parsers and native raster libraries as attack surfaces. Process untrusted files with patched libraries, least privilege, CPU/memory/time/scratch limits, and isolation appropriate to deployment risk.
- If archives are supported later, bound entry count, recursion, expanded bytes, path traversal, symlinks, and compression ratio. Malware scanning requirements depend on deployment risk but must be decided before broad upload support.
- A file is not an analytical asset until validation succeeds. Failed/quarantined uploads cannot be rendered or sent to tools and are deleted according to policy.

## Remote fetching and external providers

- Phase 4 task 4B adds metadata-only outbound requests to the exact configured Earth Search HTTPS v1 origin and internally constructed discovery/search/item paths. Redirects are disabled; timeouts, retry count, response bytes, cache entries/TTL, item identifiers, and continuation tokens are bounded. Provider next links must resolve to the exact approved `POST /v1/search`; their filter bodies are not trusted. No credential or general URL fetcher is introduced.
- Phase 4 task 4C exposes only the configured public metadata adapter. Its stateless routes create no owned object and do not access the database. This narrow anonymous boundary does not apply to saved searches, protected providers, provider credentials, AOIs, asset references/intake, or analysis; those remain deny-by-default pending verified identity and ownership checks.
- Phase 4 task 4F stores only a closed, versioned browser-local metadata draft. It excludes provider cursors, credentials, raster references, preview URLs, and expiry timestamps, and is revalidated before restoration. `Saved in this browser` is not an authenticated server/database save and does not confer asset access or analytical authorization.
- Phase 5 task 5A permits only credential-free relative `/api/v1/` tile templates in transient tile metadata. Resolved-asset contracts expose no raster URL. Versioned saved viewer state excludes tile templates/IDs, access expiry/status, credentials, raster bytes, and rendering claims; restoration must obtain fresh authorized access. These schemas add no route or access grant.
- Phase 5 task 5B accepts only the stable configured provider/collection/item identity and returns no provider raster URL. Earth Search RGB locations must use HTTPS, the exact allow-listed object host and collection path, no embedded credentials/query/fragment, no traversal, and no unapproved port. Redirect following is disabled on each request; every location header is revalidated before a bounded next HEAD. Three required COG components must each expose CRS/resolution/shape/transform metadata and pass HEAD before the response contains a usable resolved asset. HTTP 401/403, missing objects/metadata, and unsupported formats produce distinct no-asset states. Thumbnails remain separate and raster bodies are not requested.
- Phase 5 task 5C accepts only stable scene identity plus fixed `natural-color`/256-pixel render parameters. It issues opaque, expiring, access-scope-bound tile-set IDs and exposes no generic URL/path/expression route. Source URLs remain server-only and are revalidated against the exact HTTPS object host/collection path; local, loopback, private/internal, credential-bearing, queried, traversal, and redirect responses are rejected. Raster response bodies must be exact HTTP 206 ranges matching the HEAD length. Per-component deadline/request/byte/cache bounds, two tile slots, a 30-second API bound, fixed GTiff driver, and header-to-catalogue dimension/CRS/transform checks constrain native parsing. Tile caches are bounded and access-scoped; signed URLs remain prohibited from persistence/logging.
- Phase 5 task 5D sends only stable scene identity and the fixed recipe, validates the response against the requested scene, and accepts only credential-free same-origin SatQuery tile templates. Abort/sequence guards prevent stale metadata from activating another scene. Provider locations and credentials never enter the browser, and active tile-set IDs are transient rather than persisted viewer state.
- Phase 5 task 5G stores only runtime-validated browser-local AOI/camera/display and stable scene/asset/preset identities. It excludes tile templates/IDs, provider URLs, expiry/access state, credentials, raster bytes, and render claims. Restore validates the AOI binding, never substitutes an acquisition, and requests fresh tile metadata.
- Phase 5 task 5E changes only validated MapLibre layer layout/paint values. Display parameters are not sent to the tile API, arbitrary expressions remain unavailable, and unsupported presets stay disabled; this adds no fetch destination, credential surface, persistence, or scientific claim.
- Phase 5 task 5F resolves each stable comparison scene independently through the same closed tile API. It introduces no URL/path input or provider credential surface; request aborts and map/listener removal apply on exit. Comparison assignments and display values remain transient and do not claim ownership, persistence, compatibility, or analysis.
- Public/temporary preview references remain HTTPS-only and reject embedded URL credentials. The adapter exposes only thumbnails on its explicit preview-host allow-list and never fetches them. It inspects data-asset references only to classify advertised access, does not return raster URLs in the normalized scene, and never downloads raster bytes.
- Do not expose a general URL fetcher. Allow only necessary HTTPS schemes and configured providers/hosts; validate URL, DNS resolution, resolved IP ranges, redirects at every hop, content type, byte limits, timeout, and response checksum. Block loopback, link-local, private/internal, cloud metadata, and disallowed ports unless an explicit trusted deployment route requires them.
- Provider credentials, licensing, rate limits, attribution, and permitted caching are adapter policy. Validate provider responses as untrusted input and separate catalogue discovery from possession of analyzable pixels.
- Missing configuration yields `CAPABILITY_UNAVAILABLE`; upstream failure yields an explicit safe error. Neither may produce synthetic provider data outside clearly labeled tests.

## Agent, model, and tool restrictions

- Query text, uploads, OCR/captions, catalogue metadata, web content, and retrieved documents are untrusted data. Instructions within them cannot change identity, permissions, allowed tools, destinations, or security policy.
- Runtime AI receives the minimum context and cannot directly authorize resources, execute arbitrary code/shell/SQL, choose unrestricted URLs, or access raw credentials. Use an allow-listed capability registry with typed schemas, backend validation, ownership checks, cost/time/resource bounds, and auditable invocation/output references.
- Tool output is validated before persistence or narration. Language-model text is not geospatial measurement, and no model may invent results, coordinates, scores, progress, or traces.
- Record externally useful execution metadata, not hidden chain-of-thought. Apply prompt/content retention controls and provider data-use settings once a runtime AI provider is selected.

## Storage, logging, and lifecycle

- Buckets/containers are private, encrypted in transit and at rest, versioning/retention aligned to policy, and separated by environment. Object keys must not contain secrets or unnecessary personal/location labels.
- Structured logs use safe IDs and error codes. Redact tokens, cookies, authorization headers, credentials, signed URLs, raw uploads, sensitive query text/AOIs, provider payloads, and stack details at public boundaries.
- Audit security-relevant access, export, permission, provider configuration, and deletion events with tamper-resistant retention appropriate to policy.
- Define retention/quotas/legal holds before production data. Deletion must cover relational data, object storage, caches, replicas/backups according to policy, while retaining only authorized minimal audit evidence. Show pending and failed deletion states.

## Web and API baseline

Use TLS; secure cookies where applicable; strict CORS origin allow-lists; CSRF protection for cookie-authenticated mutations; CSP and output encoding; rate/size limits; dependency and container scanning; safe error messages; and security headers. Validate GeoJSON complexity to prevent computational denial of service. Avoid rendering untrusted HTML/markup and prevent object/file content sniffing.

For local Phase 1, CORS permits only configured origins and only `GET`/`OPTIONS` with the small health-request header set. Docker publishes database ports to loopback. The browser receives only `NEXT_PUBLIC_API_BASE_URL`; database and future provider credentials remain server-side. These development controls are not a production security claim.

Threat modeling and tests must cover horizontal authorization (IDOR), cross-tenant references, signed-link replay/expiry, upload parser abuse, SSRF/redirect rebinding, prompt/tool injection, job duplication/cancellation races, malicious geometry, log leakage, and deletion/backup behavior before affected features ship.

## Incident and disclosure readiness

Before production, identify security ownership, vulnerability-reporting path, credential rotation/runbook, audit access, dependency response process, backup/restore responsibility, and user notification obligations. The repository must not claim compliance certification; operational ownership and the controls above remain required before production.
