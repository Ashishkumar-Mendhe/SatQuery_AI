# SatQuery presentation demo handoff — 2026-09-27

## Resume verification — 2026-09-28

**Result remains BLOCKED for a complete evidence-linked browser answer; Phase 11 was not started.** The partial browser path was rerun from map through question without redoing implementation work. The repository root has no `.git` directory, so `git status` could not be used to distinguish tracked changes; recent implementation and handoff files were inspected directly. No API key value was printed, logged, copied into the browser, or committed.

- Docker Desktop was restored, `satquery-db-1` became healthy, and Alembic upgraded the persisted database from `20260907_0001` through `20260923_0002` to required head `20260926_0003`.
- On Windows/Python 3.14, the documented plain Uvicorn command selected `ProactorEventLoop`, which Psycopg async rejects. That run kept readiness at 503 and disabled all durable processing services even though PostGIS was healthy. Starting Uvicorn through `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)` removed the startup warnings; `/api/v1/health/ready` then returned HTTP 200 with PostgreSQL 18.6, PostGIS 3.6.4, and migration `20260926_0003`. Use the selector-loop command below for this local environment until the launcher is made permanent:

  ```powershell
  cd C:\Desktop\SatQuery\backend
  ..\.venv\Scripts\python.exe -c "import asyncio, uvicorn; config=uvicorn.Config('satquery.main:create_app', factory=True, host='127.0.0.1', port=8000); server=uvicorn.Server(config); asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)"
  ```

- Root `.env` already contained a non-placeholder server-only `RUNTIME_AI_API_KEY`. Only the matching selectors `RUNTIME_AI_PROVIDER=openai` and `RUNTIME_AI_MODEL=gpt-4.1-mini-2025-04-14` were filled; the key itself remained secret. `backend/scripts/verify_demo_question.py` again created the same real `110 × 113` source chip with checksum `4fbf8bda6eb648d297d7c9ed3c781ffdcd8d2f4a08e711215b990ad425f05680` and Phase 6 readiness `ready`, but the live provider request returned safe `MODEL_UPSTREAM_ERROR`; no model answer or account/access claim is made. `XAI_API_KEY` remains absent.
- The in-app browser connector again failed at its sandbox-policy setup step, so the existing isolated local Chrome/CDP fallback was used. With backend readiness 200, the browser showed **Backend ready**, accepted bounds `77.585, 12.965, 77.605, 12.985` (4.82 km²), returned six real Sentinel-2 L2A scenes, selected `S2B_T43PGQ_20260422T052413_L2A`, and submitted **“What surface types are visible?”**. The protected turn failed safely with **“Protected processing requires a configured identity provider.”** No answer/evidence overlay appeared. The imagery overlay still reported **“Loading georeferenced imagery tiles…”**; the catalogue thumbnail remained explicitly labelled provider preview only. [Resume screenshot](docs/demo-blocked-question-2026-09-28.png).
- Current live gate: database/readiness **passed**; public map/AOI/catalogue/scene/question submission **passed**; verified identity **missing**; provider answer **failed**; rendered scientific imagery tiles **not verified**; committed evidence-linked answer **not produced**. The backend and frontend were left running at `127.0.0.1:8000` and `localhost:3000` for continuation.

**First unfinished action:** configure a real verified processing-principal resolver (the identity-provider decision remains unresolved) and restore usable hosted-model access. Then restart with the Windows selector loop, rerun `backend/scripts/verify_demo_question.py` until it returns an available real-chip answer, and repeat the exact browser path through a committed result and authorized source-chip/map evidence. Do not add a fixed development principal, expose a browser credential, substitute the provider thumbnail/basemap, or start Phase 11.

**Result: BLOCKED for the requested complete question-to-answer browser demo.** The partial map/AOI/public-catalogue path works; no live protected model answer or source-bound answer overlay was produced. Do not present the basemap, catalogue thumbnail, a fixture, or the direct chip verifier as an AI answer.

## Server-only xAI configuration

The backend previously supported only OpenAI. A minimal xAI Responses adapter now uses the existing Phase 7 scientific-chip VQA/caption service and protected job path, with pinned `grok-4.3` (official [model capabilities](https://docs.x.ai/developers/models/grok-4.3), [image input](https://docs.x.ai/developers/model-capabilities/images/understanding), [structured output](https://docs.x.ai/developers/model-capabilities/text/structured-outputs)). It sends the source chip ID, stable Sentinel-2 source ID, acquisition time, fixed RGB recipe, actual PNG pixels and measured Phase 6 quality checks; it records the model and response ID. It does not use basemap/thumbnail pixels or provider URLs, and no client key is accepted. Model prose is interpretation, not measured area, location, count, cause or confidence. No new satellite-data credential is required for public Earth Search.

Set these three lines **only in `C:\Desktop\SatQuery\.env`**, an ignored local file loaded by the backend, or as backend-process environment variables:

```dotenv
RUNTIME_AI_PROVIDER=xai
RUNTIME_AI_MODEL=grok-4.3
XAI_API_KEY=<set locally; never paste into chat or commit>
```

Do **not** use `frontend/.env.local`, `NEXT_PUBLIC_*`, logs, screenshots or source code for the key. At handoff, `XAI_API_KEY` was absent from the checked process/user/machine environments and root `.env`; account credits, model entitlement and an actual xAI request therefore remain **not tested**. The adapter returns safe 401/402/403/404 error classes without reflecting upstream response bodies. Restart the backend after adding the settings. A configured key alone does **not** restore database/identity or prove a browser answer.

## Exact local startup and tested click path

From `C:\Desktop\SatQuery`, with two terminals:

```powershell
cd C:\Desktop\SatQuery\backend
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --host 127.0.0.1 --port 8000
```

```powershell
cd C:\Desktop\SatQuery\frontend
npm.cmd run dev -- --hostname localhost --port 3000
```

Open **`http://localhost:3000/workspace`** (not `http://127.0.0.1:3000`: backend CORS currently allows the localhost origin). On this host, the frontend dev server needed an approved worker-process launch; `npm.cmd run build` passed. The backend was started and later restarted after the adapter change; liveness returned HTTP 200, readiness returned HTTP 503 for database. Docker Desktop was launched but its engine did not become available; `127.0.0.1:5432` was closed. The protected identity resolver is not configured.

Observed browser sequence in a separate local headless Chrome session (the in-app browser connector failed before opening a tab):

1. Open the workspace map; the public catalogue collection loads after using the documented `localhost` origin. The first `127.0.0.1:3000` attempt showed “Backend unreachable” because the browser origin did not match CORS; retesting on `localhost:3000` correctly showed “Database unavailable” while public catalogue discovery continued.
2. Open **Workspace tools → Enter bounding box**; set west `77.585`, south `12.965`, east `77.605`, north `12.985`; click **Use bounds**. The UI showed a 4.82 km² Bengaluru-area AOI, coordinates and map outline.
3. Click **Search imagery** with the existing date range/cloud ceiling. Earth Search returned six actual Sentinel-2 L2A scenes. Select `S2B_T43PGQ_20260422T052413_L2A` (acquired `2026-04-22T05:25:15.650Z`, catalogue scene cloud 0.0%). The backend returned HTTP 200 for its georeferenced tile-set metadata after trusted B04/B03/B02 HEAD checks. The browser still said “Loading georeferenced imagery tiles…” at final inspection, so visible satellite raster tiles were **not verified**; the basemap and provider thumbnail are not scientific evidence.
4. In Assistant, choose the suggested **“What surface types are visible?”** and click **Ask question**. The draft remained visible, the selected scene/date stayed linked, and the answer panel showed **“Inference failed — Protected processing requires a configured identity provider.”** No model answer, fabricated evidence, numeric confidence or overlay appeared. [Blocked-question screenshot](docs/demo-blocked-question.png) records this state; [initial map screenshot](docs/demo-map-before-selection.png) records the starting UI.

Separately, `backend/scripts/verify_demo_question.py` read **actual scientific raster assets** for `S2B_T43PGQ_20251223T051848_L2A` over a 0.01° × 0.01° AOI, calibrated/masked them, and built a source-bound `110 × 113` PNG chip with checksum `4fbf8bda6eb648d297d7c9ed3c781ffdcd8d2f4a08e711215b990ad425f05680`; Phase 6 readiness was `ready`. This is **direct backend preparation only**, not an authorized conversation result. It reported `model_not_configured`; the final script exits nonzero unless an available model answer is returned.

## Verification and precise resume

- `cd backend; ..\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_vqa_inference.py tests/test_inference_api.py tests/test_geoagent_phase10.py tests/test_geoagent_execution_phase10c.py tests/test_geoagent_conversation_phase10d.py tests/test_geoagent_phase10f.py -q` — **76 passed** (synthetic xAI transport/shape/error tests included).
- `cd backend; ..\.venv\Scripts\python.exe -m pytest -q -m "not integration"` — **307 passed, 1 PostgreSQL integration test deselected**. `..\.venv\Scripts\python.exe -m ruff format --check src tests scripts/verify_demo_question.py`, `..\.venv\Scripts\python.exe -m ruff check src tests scripts/verify_demo_question.py`, `..\.venv\Scripts\python.exe -m mypy src tests scripts/verify_demo_question.py` — **passed**, 111 files.
- `cd frontend; npm.cmd run format:check; npm.cmd run lint; npm.cmd run typecheck; npm.cmd run build` — **passed**. Focused `npm.cmd test -- --run src/components/workspace/assistant-panel.test.tsx --pool=threads --reporter=dot --testTimeout=15000` — **9 passed**.
- `cd backend; ..\.venv\Scripts\python.exe scripts/verify_demo_question.py` — **real chip preparation passed, full question check BLOCKED** (`model_not_configured`, nonzero exit); the second run reproduced the same source-chip checksum.
- Live catalogue search, tile-set metadata, scientific chip extraction and browser selection were **observed**. Live xAI request, PostgreSQL migration/readiness, verified identity, successful protected inference, fully rendered satellite tiles and answer-to-map evidence were **not verified**. The in-app browser connector failed at its sandbox metadata check; fallback local Chrome was used only for the observations above.

**Next action for a true PASS:** locally set the three backend xAI variables; bring up the documented PostGIS service (`docker compose up -d db`), migrate to Alembic head `20260926_0003`, and configure a real verified processing principal. Then run `cd backend; ..\.venv\Scripts\python.exe scripts/verify_demo_question.py` to check xAI model/account access with a real chip; restart both servers; repeat the exact browser sequence through a committed answer and authorized source-chip/map evidence. If the key is rejected, billing is unavailable, raster tiles fail, or identity remains unconfigured, keep **BLOCKED** and show the partial map/catalogue demo only. Do not substitute a fabricated answer or begin Phase 11.
