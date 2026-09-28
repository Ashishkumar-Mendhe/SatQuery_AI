# Phase 3 — Interactive Earth Map & AOI System

Status: **PARTIALLY_VERIFIED**. Updated 2026-09-15. Basemap browser acceptance now passes; the broader responsive/AOI browser checks and server-owned AOI gate remain outstanding. Phase 4 was not changed by this repair.

## AOI-selection verification — 2026-09-15

The user reopened only the existing AOI-selection workflow. Live isolated Chrome drew and retained a rectangle and polygon on the real MapLibre map. Each became a validated, closed RFC 7946 Polygon with source/name properties and computed bbox; Turf supplied the geodesic area shown in km². The AREA OF INTEREST card and imagery-panel Selected AOI summary updated immediately, and clear removed the map highlight, stored geometry, summaries, and AOI-dependent controls. A selected polygon's exact coordinates were posted to the existing catalogue endpoint and returned six real metadata results without opening or rendering imagery.

The one confirmed defect was the imagery search control being enabled before an AOI existed, despite a defensive submit-time guard. `ImageryDiscoveryPanel` now includes `!selectedAoi` in the button's disabled condition, and its focused test asserts the unavailable state. Search becomes enabled after either valid drawing and disables again after clear.

Final verification passed: strict frontend typecheck, 35/35 focused AOI/storage/discovery/scene tests, and the optimized Next build. The first sandboxed Vitest startup failed with Windows `spawn EPERM`; the permission-scoped run and clean final rerun passed. Browser inspection found no page exception or console error. The managed browser could not initialize because its session lacked `sandboxPolicy`; isolated hidden Chrome supplied the visual and interaction evidence. No backend AOI persistence was required or added, and no database, imagery-rendering, AI, dependency, environment, or unrelated code changed. The broader authenticated-owner persistence gate remains outside this maintenance task.

A follow-up visual requirement added a compact always-visible toolbar over the map with `Draw rectangle`, `Draw polygon`, and `Clear AOI`. The scrollable tool panel retains its drawing/editing workflow but no longer duplicates clear; both drawing entry points call one shared helper. At a 1600×1000 viewport the toolbar rendered at 249×32 px beside the native MapLibre controls without covering lifecycle status. Live drawing confirmed the rectangle remained highlighted and its exact GeoJSON/area/bounds remained unchanged after zoom and pan. Clear removed the shape and local state, restored all three `No area selected` surfaces, and disabled both clear and imagery search. Polygon drawing then restored all selected states and a catalogue search returned HTTP 200. Final Biome, typecheck, 36/36 focused tests, and optimized build passed. The first new test assertion failed because the empty state is intentionally repeated in three UI surfaces; the corrected assertion and rerun passed. No imagery scene was opened and no backend, database, dependency, or AI work occurred.

## Basemap-only repair verification — 2026-09-15

The user reopened only the Phase 3 basemap foundation after the later project phases. The default remains the MapLibre GL JS 6.9.0 renderer with the public OpenFreeMap Liberty vector style at `https://tiles.openfreemap.org/styles/liberty`; it remains geographic context only. No satellite imagery, AI overlay, backend, database, dependency, or phase feature was added.

The style URL was valid and its TileJSON, sprites, glyphs, and visible resources returned HTTP 200. The actual blank-map cause was local layout: MapLibre's `.maplibregl-map` CSS rule had equal specificity and overrode `.map-canvas { position: absolute }`, leaving the map element 0 px high inside an 859 px stage. The fix scopes the project rule as `.map-stage > .map-canvas`, explicitly fills width/height, and marks lifecycle ready on `style.load` so a visibly rendered style does not later receive a false timeout while optional resources continue loading.

Isolated hidden Chrome rendered `/workspace` with a 972×859 real Liberty map centered on India, visible water, terrain/context, boundaries, roads/place labels, correct attribution, and `Map ready`. Clicking zoom changed the scale from 500 km to 300 km; dragging changed the center from 78.96290/20.59370 to 75.85550/22.32878. No page exception or console error was recorded. Frontend typecheck passed, focused SceneContainer tests passed 8/8, and the optimized Next build passed. The in-app browser could not initialize because its session lacked `sandboxPolicy`; this time the isolated-browser evidence closes the basemap rendering/interaction portion only. The server-owned AOI/authentication/persistence and other carried Phase 3 gates remain outside this repair and keep the overall Phase 3 report partially verified.

## Scope and continuation

The user authorized Phase 3 while the Phase 1 database and earlier browser gates remained pending, then asked to finish incomplete files without rewriting completed work. The existing Next.js/FastAPI application, dark/cyan presentation, two persistent local terminals, npm lock and Python dependency workflow were preserved. No backend implementation, local secret configuration, database, or unrelated process was changed during this continuation. The workspace is not a Git repository, so Git status/diff checks are unavailable.

Plan executed: inspect existing work and running services; finish map/AOI integration and validation; add failure-path tests; run frontend checks and host HTTP verification; record external gates and exact resume instructions.

## Recovery verification — 2026-09-10

The continuation audit inspected the governing documents, implementation, manifests, migrations, tests, timestamps, and runtime state. `C:\Desktop\SatQuery` still has no `.git` metadata, so Git status, diff, recent commits, and a reliable tracked/untracked classification are unavailable. No truncated or partially edited source file was found, and no Phase 4 work exists.

The historical service PIDs were no longer SatQuery processes; ports 3000, 8000, 5432, and 55432 had no listeners. Temporary verification sessions were started with the existing documented commands (the frontend required permission to create its normal child process), used for HTTP checks, and stopped afterward. `/` and `/workspace` returned 200; liveness returned 200 with `{"status":"live","service":"satquery-api","version":"0.1.0"}`; readiness returned the expected 503 with `Cache-Control: no-store` and `Retry-After: 5` while PostgreSQL remained unavailable.

The required in-app browser workflow was retried. It failed before creating a tab because the browser session lacked required sandbox metadata, so no WebGL/map interaction, responsive viewport, console/network, or screenshot claim was made. Standalone HTTP success is not substituted for browser evidence.

`scripts/verify.ps1` passed backend Ruff check/format, strict mypy, all 15 selected non-database backend tests, frontend format/lint, and strict type checking. The script then encountered the already documented Vitest fork-worker startup timeout before loading any test. A separate `npm.cmd run test:run -- --testTimeout=15000` run passed all 9 files and 50 tests; the expected jsdom canvas notices do not establish WebGL behavior. `npm.cmd run build` passed and prerendered `/` and `/workspace`. No application source, manifest, lockfile, migration, environment value, or database was changed in this recovery. `SESSION_HANDOFF.md` was subsequently created as the concise cross-session resume record, and `AGENTS.md` now requires it to be refreshed after every major task.

The remaining server-owned AOI work cannot safely begin by inventing identity: the PRD, TRD, architecture, security requirements, decision register, and this report all leave the identity/tenant provider and owner mapping unresolved and prohibit client-supplied ownership or a production anonymous bypass. The authenticated-owner decision is therefore the implementation prerequisite for protected AOI CRUD and two-owner tests. Phase 3 remains in progress, and Phase 4 remains out of scope.

## Implemented local workflow

- `MapCanvas` dynamically imports MapLibre and Terra Draw after mount. It provides pan/zoom, compass/north, metric scale, pointer/center coordinates, coordinate and bounds navigation, fit AOI, loading timeout, provider failure/retry, and an explicit unsupported-WebGL2 state.
- Map effects own the renderer, draw control, listeners, timers and ResizeObserver. Cleanup removes them; retries create a fresh renderer. React owns drawing modes; the library's global mode shortcuts are disabled to prevent bypassing draft/commit state. Native drawing keyboard events belong to the map canvas, not the assistant composer.
- Rectangle/polygon drawing and vertex selection/editing are integrated. Finish commits validated geometry; cancel restores the previous AOI. Edit previews update measurements separately from the committed source of truth. Invalid imports/bounds preserve the current selection, and delayed imports cannot resurrect a cleared or replaced selection.
- `WorkspaceShell` owns `SelectedAoi` through `useAoiDraft`, passed explicitly to `SceneContainer`. The summary shows name, source, derived bounds and approximate area. An AOI does not select imagery or enable analysis.
- GeoJSON import/export and bounds entry remain usable without database readiness or map tiles. Map navigation/drawing require the map's own resources. Browser drafts are read after mount, versioned, validated on restoration, and can be cleared. Quota/denied-storage failures retain in-tab geometry and report persistence limits.
- Tools collapse according to the actual map container width. The assistant starts closed on mobile. Hidden tools are removed from visual/focus access with CSS visibility. Real responsive inspection is still pending.

Important changed files: `frontend/src/components/workspace/map-canvas.tsx`, `scene-container.tsx`, `workspace-shell.tsx`; `frontend/src/lib/aoi.ts`, `aoi-storage.ts`, `use-aoi-draft.ts`, `geocoder.ts`, `feature-availability.ts`; focused tests alongside these files; `frontend/src/app/globals.css`, `.env.example`, `package.json` and `package-lock.json`. Current phase, roadmap, setup, architecture, stack, feature, API/database status, testing, and decision documents were synchronized with this report.

## Providers and dependencies

Exact direct pins: `maplibre-gl@6.9.0`, `@watergis/maplibre-gl-terradraw@1.16.0`, `@turf/area@7.4.0`, `@turf/bbox@7.4.0`, `@turf/kinks@7.4.0`. The initial dependency addition used:

```powershell
npm.cmd install --save-exact maplibre-gl@6.9.0 @watergis/maplibre-gl-terradraw@1.16.0 @turf/area@7.4.0 @turf/bbox@7.4.0 @turf/kinks@7.4.0
```

It added 30 packages; npm reported 175 audited packages and zero vulnerabilities at that invocation. Dependencies were not reinstalled during continuation. Python dependencies were untouched.

Default basemap: `https://tiles.openfreemap.org/styles/liberty`, following [OpenFreeMap quick start](https://openfreemap.org/quick_start/). MapLibre displays source attribution (including OpenMapTiles/OSM); the default adds OpenFreeMap/OSM links. Custom providers must carry their own required attribution in the style sources. Configure public `NEXT_PUBLIC_BASEMAP_STYLE_URL` and `NEXT_PUBLIC_BASEMAP_NAME`; no secret-bearing URLs or credentials belong here. The basemap is geographic context, never an analytical asset. Drawing integration follows the [MapLibre Terra Draw example](https://maplibre.org/maplibre-gl-js/docs/examples/draw-geometries-with-terra-draw/).

Optional geocoding is disabled until `NEXT_PUBLIC_GEOCODER_URL` names an HTTPS, CORS-enabled Nominatim-compatible provider that permits direct browser queries. `NEXT_PUBLIC_GEOCODER_NAME` supplies its label. The adapter uses explicit submits, an eight-second timeout, at most five results, a bounded 50-entry per-tab cache, and a per-tab one-second request interval. These are not application-wide controls. The public Nominatim endpoint is rejected because its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) requires application-wide throttling and identification; a suitable proxy/service would need a separate implementation. No autocomplete, fabricated fallback results, or live geocoder success is claimed. Coordinate navigation remains available without a geocoder.

## Geometry contract

The local boundary is `frontend/src/lib/aoi.ts`, following [RFC 7946](https://datatracker.ietf.org/doc/html/rfc7946).

- Input: a Polygon, a Polygon Feature, or a one-feature FeatureCollection. One exterior ring only; holes, MultiPolygon, other geometry, and legacy CRS metadata are rejected with explanations.
- Positions contain exactly two finite numbers: WGS84 `[longitude, latitude]`, longitude within ±180 and latitude within ±90. Ring closure is exact. At least three distinct vertices are required; repeated nonclosing vertices, zero area, self-intersections and collinear overlapping/touching edges are rejected.
- Limits: 1,000,000 input bytes and 500 ring positions including closure. Antimeridian-crossing edges and extents wider than 180 degrees are rejected; split the source into separately selectable supported polygons. Parts are never silently discarded.
- Exterior winding is normalized counterclockwise. Bounds are recomputed as `[west, south, east, north]`; imported bbox/area metadata is not trusted.
- [Turf area](https://turfjs.org/docs/api/area) supplies approximate spherical geographic area in square metres; display uses m², hectares or km². This is not projected-degree arithmetic, survey accuracy, or an analysis finding. Tiny nonzero areas display `<1 m²`.
- Geographic validity is separate from Web Mercator display support. Geometry outside ±85.051129 latitude may be geographically valid; the current map workflow declines that selection with a specific display-limit explanation and preserves the previous AOI. It never silently clamps the exported geometry.
- The editor uses 15 decimal places of coordinate precision; the committed import/export model preserves the validated numeric coordinates. Renderer insertion failures are reported rather than represented as successful display.
- Export: actual selected Feature with geometry, recomputed bbox, name/source properties, filename `satquery-selected-aoi.geojson`. No invented server ID, owner, imagery, findings, or evidence.

## Persistence and ownership gate

Browser storage key: `satquery.aoi-draft.v1`. The envelope has version 1, saved timestamp and typed AOI. Restoration validates version/source/geometry and recomputes derived values. Labels say “Saved in this browser” or “Restored from this browser.” Failed writes warn that refresh may restore an older draft; failed clears distinguish current-tab state from storage state.

The roadmap explicitly requires backend ownership/geometry checks and PRD AC-AOI-02 requires owned persistence. **That requirement is not satisfied by this implementation.** Server Saved AOIs, `/aois` routes, domain table/migration, authenticated owner binding, and two-owner tests are unimplemented. Authentication integration remains unresolved in the existing architecture, and no client-supplied owner or fabricated identity was introduced. Real PostGIS is also unavailable for verification. This is an implementation gap plus an external verification gap, not merely an unrun database test. The target database MultiPolygon design is unchanged; the local Polygon subset does not redefine the server contract.

## Verification evidence

| Check | Result |
|---|---|
| Frontend `npm.cmd run lint` | PASSED after correcting unfinished hook, accessibility and CSS issues |
| Frontend `npm.cmd run typecheck` | PASSED; invalid `maplibre.supported()` API and nullable-container errors corrected |
| Frontend `npm.cmd run format:check` | PASSED; formatting was limited to touched Phase 3 files |
| Frontend tests | Final `npm.cmd run test:run -- --testTimeout=15000` PASSED: 9 files, 50 tests in 7.71 seconds. An earlier default-timeout run also passed all 50. Other attempts FAILED on worker startup timeout and a five-second timeout in the existing typing test (49 passed). No assertions were removed or dependencies reinstalled. |
| Frontend `npm.cmd run build` | PASSED: optimized Next.js build, strict types and prerendered `/` and `/workspace` |
| Windows host `/` and `/workspace` | PASSED: HTTP 200 with HTML |
| Windows host liveness | PASSED: HTTP 200, `{"status":"live","service":"satquery-api","version":"0.1.0"}` |
| Windows host readiness failure | PASSED: HTTP 503, `DEPENDENCY_UNAVAILABLE`, details dependency `database`, `retryable: true`, `Cache-Control: no-store`, `Retry-After: 5` |
| Persistent service processes | PASSED: existing standalone terminal/process trees still running after their launcher exited |
| Browser/WebGL, screenshots, console/network | NOT RUN: browser tool failed before a tab could be created, reporting missing `sandboxPolicy` metadata |
| Real geocoder/provider rendering | NOT RUN; no configured geocoder or real rendered-map evidence |
| PostgreSQL/PostGIS migration/readiness success | NOT RUN; carried unavailable-runtime gate; no port 5432 listener in current host inspection |
| Owned AOI API/database/authorization | NOT IMPLEMENTED / NOT RUN |
| Backend suites | NOT RUN during continuation because backend code/configuration did not change; existing HTTP health behavior was checked |
| Git status/diff | Git status FAILED because the workspace is not a Git repository; Git diff unavailable |

Final host recheck at 23:37 IST on 2026-09-09, after the final successful build: both frontend routes returned 200, readiness returned the expected 503 body/headers, subsequent liveness returned 200, and all five listed service/terminal PIDs remained alive. A documentation audit found all 22 relative links in the updated documents resolve to existing files; formatting passed for all 41 frontend files.

Tests use explicitly synthetic geometry/provider/storage fixtures. They cover bounds/axis order, geometry rejection, area units, round trips, corrupt drafts, denied/quota storage, provider errors, invalid import/bounds preservation, and delayed import cancellation. jsdom reports unavailable canvas contexts; that is not real WebGL testing. The scene integration test mocks the map boundary. These results cannot establish real rendering, drawing, edit cancellation, lifecycle behavior, downloaded-file round trips, or responsive quality.

## Local startup and observed process state

The prior startup repair established two standalone PowerShell windows. This continuation verified and reused them; it did not start temporary replacement servers or stop unrelated processes. Frontend terminal PID 17212, Next PID 10944 listening on `::3000`; backend terminal PID 13524, Uvicorn reloader 8404/server 12396 on `127.0.0.1:8000`. PIDs are observations, not permanent configuration. The earlier disappearance of both services had no recoverable exit-error evidence; it must not be attributed to database failure. This continuation found actual unfinished map-code defects, not a dead frontend/backend process.

**Frontend terminal**

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\frontend'
npm.cmd run dev
```

**Backend terminal**

```powershell
Set-Location -LiteralPath 'C:\Desktop\SatQuery\backend'
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000
```

Leave both terminals open. Reuse them while they are running; do not start duplicate listeners. Closing a terminal or signing out/restarting Windows requires restarting its service. URLs: `http://localhost:3000/`, `http://localhost:3000/workspace`, `http://127.0.0.1:8000/api/v1/health/live`, `http://127.0.0.1:8000/api/v1/health/ready`. A 503 readiness response is intentional while the database is unavailable.

## Exact resume instructions

1. Preserve these files and inspect current terminal output/ports before any service restart. Use the two commands above only for a stopped service.
2. Once the browser connector works, inspect `/` and `/workspace` at desktop/laptop/mobile sizes. Verify real provider rendering, rectangle/polygon drawing, vertex editing and finish/cancel, invalid import preservation, actual export/reimport, refresh restoration/clear, pan/zoom/north/fit, and sidebar/assistant resizing. Capture actual map/AOI screenshots and inspect console/network. Repeat with readiness 503, failed tiles, missing WebGL, retry and remount. Correct observed defects and rerun relevant checks.
3. Resolve the authentication/owner integration before implementing protected AOI CRUD. Add the owned PostGIS schema/migration, independent FastAPI geometry validation and tests across at least two owners. Do not accept an owner ID supplied by the browser as authorization.
4. When a suitable host database runtime is available, follow `scripts/verify-database.ps1` and the Phase 1 report for the isolated migration/PostGIS/readiness-success gate. Then verify real owned AOI persistence and degraded behavior. Browser storage cannot substitute for it.
5. Record remaining Phase 2 responsive/browser evidence separately. Mark Phase 3 COMPLETE only after its local browser and backend ownership/persistence criteria pass. Stop before Phase 4.
