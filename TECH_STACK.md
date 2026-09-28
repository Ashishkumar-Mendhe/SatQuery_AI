# Technical stack and decision status

## Status vocabulary

- **Confirmed:** selected, implemented, and represented in the current manifests/contracts.
- **Proposed:** useful starting choice, pending an explicit Phase 1+ decision and validation.
- **Unresolved:** no choice should be inferred.

## Confirmed Phase 1 baseline

| Area | Technology/direction | Responsibility and constraints |
|---|---|---|
| Runtime/package manager | Node.js 24.x LTS + npm 11.x; Python 3.13–3.14 + pip/pip-tools | `.nvmrc` prefers Node 24.20.0; `.python-version` prefers Python 3.14; npm and pip-generated locks are authoritative |
| Frontend | Next.js 16.3.4, React 19.2.8, TypeScript 6.0.3, Tailwind CSS 4.3.3, Zod 4.5.4 | Accessible presentation and strict runtime validation; no server credentials or authoritative computation |
| Frontend quality | Biome 2.5.12, Vitest 5.0.0, Testing Library | Formatting/lint and component/client contract tests; single-worker test configuration is stable on Windows |
| Application API | FastAPI 0.141.1, Pydantic Settings 2.15.0, Uvicorn 0.52.4 | Validated settings, application lifecycle, versioned APIs, safe errors, request correlation, orchestration boundary |
| Database access | PostgreSQL 18/PostGIS 3.6 container line, SQLAlchemy 2.0.52 async, Psycopg 3.3.5, Alembic 1.19.2 | Explicit async sessions and migrations; no ORM auto-create; real readiness verifies PostGIS and migration revision |
| Long-running work | Background workers behind a documented job interface | Durable asynchronous execution; implementation not selected |
| Raster/artifact persistence | Private object storage with database references | Large bytes outside relational rows; vendor not selected |
| EO and AI access | Backend-controlled adapters | Server-side credentials, schema validation, explicit capability availability |
| Visualization tile rendering | rio-tiler 9.4.4, Rasterio 1.5.1/GDAL 3.12.4, NumPy 2.5.3 | Fixed natural-colour WebMercatorQuad PNG tiles from allow-listed COG range reads; not an analysis stack |

Phase 4 task 4B promotes `httpx2` 2.12.0 to a backend runtime dependency and implements the first EO metadata adapter against Earth Search STAC v1. The adapter is deliberately limited to `sentinel-2-c1-l2a`, uses no credential, and performs no raster download. This does not select an analytical imagery delivery/storage strategy or a runtime AI provider.

Phase 5 task 5C pins rio-tiler 9.4.4 and direct application dependencies Rasterio 1.5.1 and NumPy 2.5.3 for bounded visualization tiles. The implementation uses rio-tiler's WebMercatorQuad window/overview path behind SatQuery routes instead of mounting TiTiler's generic STAC URL/expression surface. Rasterio's Python opener is backed by validated `httpx2` range requests because the local Windows GDAL Schannel path could not complete the live HTTPS read. This choice does not select scientific preprocessing, analytical raster intake, object storage, or a deployment tiling service.

Phase 5 task 5D continues the existing MapLibre GL JS 6.9.0 integration and serves its pinned module worker/shared module from the frontend origin. It adds no second map framework or rendering dependency. The background-only verification style is a labelled synthetic browser fixture, not the product basemap default or an imagery substitute.

Phase 5 task 5E uses MapLibre's existing raster layout/paint properties for debounced presentation-only controls and adds no dependency. The server's natural-colour recipe remains a fixed red/green/blue mapping with catalogue scale/offset and a scene-stable 0.00–0.30 reflectance range.

Phase 5 task 5F adds no package. The official MapLibre comparison plugin was evaluated; its documented example uses MapLibre 2.1.6 and imperative dual-map/DOM ownership. SatQuery instead uses two existing MapLibre 6.9.0 instances behind a small React-owned synchronization/swipe adapter with native range accessibility and typed per-side failure/cleanup.

The PostGIS image is pinned to `postgis/postgis:18-3.6`; reproducible production deployment requires pinning an immutable image digest in a later deployment decision. shadcn/ui remains product direction; MapLibre is installed in Phase 3 as recorded below.

Phase 3 installs exact npm pins: MapLibre GL 6.9.0, `@watergis/maplibre-gl-terradraw` 1.16.0 (Terra Draw integration), and `@turf/area`, `@turf/bbox`, `@turf/kinks` 7.4.0. The npm lock captures transitive drawing dependencies. MapLibre 6 requires WebGL2; the client handles unsupported contexts. OpenFreeMap Liberty is the no-key basemap default. Optional geocoding requires a configured browser-safe provider; public Nominatim is not used without application-wide controls. See `docs/PHASE_3_REPORT.md` for provider and geometry limitations.

The Codex model used to develop this repository is not automatically SatQuery's runtime AI provider.

## Proposed evaluation set, not selected dependencies

These names identify candidates to evaluate against actual tasks; they are not installed, pinned, or approved:

- Scientific raster/vector processing: pyproj, Shapely, GeoPandas, xarray/rioxarray, or task-specific alternatives; the visualization-only rio-tiler path does not settle this choice.
- Production-scale raster delivery: the current bounded in-process COG tile path, a dedicated tile service, or pre-generated artifacts depending on authorization, scale, deployment, and caching evidence.
- Job execution: a PostgreSQL-backed job library, Redis-backed worker, managed queue, or workflow engine depending on durability and deployment needs.
- Object storage: an S3-compatible interface or cloud-native equivalent with private buckets and signed access.
- API schema sharing: OpenAPI-derived TypeScript client/types after FastAPI contracts stabilize.
- Model/runtime AI: no provider, checkpoint, framework, embedding store, or GPU runtime has been chosen.

## Source and compatibility review

- Versions were reviewed on 2026-09-07/08 against the official [Next.js installation guidance](https://nextjs.org/docs/app/getting-started/installation), [Node.js release information](https://nodejs.org/en/about/previous-releases), [FastAPI releases](https://fastapi.tiangolo.com/release-notes/), [SQLAlchemy releases](https://www.sqlalchemy.org/blog/), [Alembic documentation](https://alembic.sqlalchemy.org/), [Psycopg installation guidance](https://www.psycopg.org/psycopg3/docs/basic/install.html), [Tailwind PostCSS guidance](https://tailwindcss.com/docs/installation/using-postcss), and the [PostGIS image documentation](https://hub.docker.com/r/postgis/postgis).
- Local verification used Node.js 24.19.0, npm 11.17.0, and Python 3.14.7. The supported ranges permit patch upgrades within Node 24 and Python 3.13–3.14.
- TypeScript 6 was selected instead of the newer 7.x line because the current lint ecosystem showed compatibility warnings during implementation. Biome is the single formatter/linter, avoiding overlapping tool ownership.
- The current Python/Rasterio/GDAL set is verified only for Phase 5 visualization tiles; analytical geospatial packages still require selection and scientific regression evidence when analysis work begins.
- Verify browser support for WebGL, large raster strategy, coordinate precision, and memory limits before choosing client-side rendering paths.
- Confirm PostGIS extension availability and migration tooling before database code; confirm object-store signing semantics before embedding artifact access in API responses.
- Keep API schema, stored result schema, and tool/capability versions explicit and independently evolvable.

## Version-selection policy

`frontend/package-lock.json` is generated by npm and installed with `npm ci`. `backend/requirements.lock` is generated from `backend/requirements.in` and `backend/pyproject.toml` with pip-tools under Python 3.14. Direct requirements are exact pins; transitive changes require lock regeneration and verification, not hand editing.

Security updates follow tested dependency updates. Model/tool version changes that can affect scientific results require regression evidence and result provenance, not only a package upgrade check.

## Outstanding decisions

- Production deployment target, immutable container-image digests, monorepo/CI automation, and release packaging.
- Authentication/tenant provider and authorization model details.
- Object storage vendor, queue/worker technology, additional/protected EO providers and analytical-access strategy, basemap provider, and runtime AI provider/model.
- Analytical raster/vector library subset, upload formats and limits, production-scale tiling/deployment strategy, model serving approach, and observability platform.
- Phase 4–15 roadmap titles/scope, which determine when these choices are needed.

Decisions and rationale are tracked in `docs/DECISIONS.md`. Phase 1 configuration names and consumers are documented in the root and frontend `.env.example` files.
