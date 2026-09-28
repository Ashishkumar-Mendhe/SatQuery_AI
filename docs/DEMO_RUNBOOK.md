# SatQuery AI — Presenter Preflight & Fast Recovery Runbook

**Document Version:** 1.0.0  
**Target Environment:** Windows 10/11 x64 (PowerShell 7 / 5.1)  
**Applicable Candidate:** SatQuery AI RC-Phase7B  
**Target Ports:** Backend `8000` (`http://[::1]:8000` or `http://127.0.0.1:8000`), Frontend `3000` (`http://localhost:3000`)

---

## 1. Environment & Runtime Prerequisites

Ensure the following tools and runtimes are present on the presentation workstation:

| Component | Verified Version | Verification Command |
|---|---|---|
| **Python** | 3.12+ / 3.14.0rc1 x64 | `python --version` |
| **Node.js** | v20.x or v22.x LTS | `node -v` |
| **npm** | 10.x+ | `npm -v` |
| **GDAL / Rasterio** | 3.10+ / 1.4.3 | `..\.venv\Scripts\python.exe -c "import rasterio; print(rasterio.__version__)"` |
| **Browser** | Google Chrome or Microsoft Edge | Standard Chromium viewport (1920x1080 @ 100% zoom) |

---

## 2. Configuration Variables Reference

All configurations are defined in `backend/.env` (or environment variables). **Never hardcode or expose API keys during screen sharing.**

| Variable Name | Production / Live Demo Value | Offline Fallback Value |
|---|---|---|
| `SATQUERY_ENV` | `production` or `test` | `test` |
| `SATQUERY_STAC_URL` | `https://earth-search.aws.element84.com/v1` | `""` (disables remote STAC) |
| `SATQUERY_AI_PROVIDER` | `gemini` / `openai` / `mock` | `mock` |
| `SATQUERY_STORAGE_DIR` | `backend/data/imagery` | `backend/data/imagery` |
| `SATQUERY_ASSET_TTL` | `86400` | `86400` |

---

## 3. Standard Startup Procedure (PowerShell)

Open two distinct PowerShell terminal windows inside `c:\Desktop\SatQuery -AG`.

### Terminal 1: Backend Service (FastAPI + Uvicorn)
```powershell
# 1. Navigate to backend directory
cd "c:\Desktop\SatQuery -AG\backend"

# 2. Activate virtual environment
..\.venv\Scripts\Activate.ps1

# 3. Launch Uvicorn server on port 8000
python -m uvicorn satquery.main:app --host 0.0.0.0 --port 8000 --reload
```
*Expected Terminal Output:*
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     application_started
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### Terminal 2: Frontend Service (Next.js 16 App Router)
```powershell
# 1. Navigate to frontend directory
cd "c:\Desktop\SatQuery -AG\frontend"

# 2. Launch Next.js dev server with Turbopack
npm run dev
```
*Expected Terminal Output:*
```
  ▲ Next.js 16.3.4 (Turbopack)
  - Local:        http://localhost:3000
  - Network:      http://192.168.x.x:3000

 ✓ Starting...
 ✓ Ready in 950ms
```

### Terminal 3 (Optional Verification): Health Check
```powershell
# Verify Backend Health
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/liveness"
# Expected: @{status="alive"; timestamp="..."; environment="test"}

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health/readiness"
# Expected: @{status="ready"; services=...}
```

---

## 4. Multi-Stage Preflight Checklists

### 60 Minutes Before Presentation (T-60)
- [ ] Connect presentation laptop to dedicated AC power (disable battery-saver sleep timers).
- [ ] Verify internet connectivity (ping `https://earth-search.aws.element84.com/v1`).
- [ ] Pull latest verified git reference: `git status` should be clean.
- [ ] Run backend automated rehearsal suite:
  ```powershell
  cd "c:\Desktop\SatQuery -AG\backend"
  ..\.venv\Scripts\python.exe scripts\rehearse_demo.py
  ```
  *(Verify output shows `ALL 6 REHEARSALS COMPLETED SUCCESSFULLY (100% PASS RATE)`).*

### 15 Minutes Before Presentation (T-15)
- [ ] Start Backend (Port 8000) and Frontend (Port 3000).
- [ ] Open Chrome/Edge to `http://localhost:3000`.
- [ ] Set browser zoom to **100%** (Ctrl+0). Maximize window or press F11 for presentation mode.
- [ ] Verify dark theme contrast and side panel dimensions (min 1280px horizontal width).
- [ ] Pre-load default demo workspace (`Bengaluru Urban - Bellandur Corridor`).
- [ ] Ensure PDF download viewer is functional (Chrome default PDF reader or Edge PDF).
- [ ] Close all personal messaging apps (Slack, WhatsApp, Teams, Discord, email clients).

### Immediately Before Screen Sharing (T-0)
- [ ] In the screen-sharing prompt, select **Application Window** (`SatQuery AI - Chrome`) rather than Entire Desktop to prevent unintended desktop notifications.
- [ ] Confirm microphone audio levels.
- [ ] Take a deep breath; start with Act 1 of `DEMO_SCRIPT.md`.

---

## 5. Symptom-Based Fast Recovery Runbook

> **The 20-Second Rule:**  
> If an unexpected network or hardware hiccup occurs on stage, make **one fast recovery attempt (< 10 seconds)**. If unresolved, smoothly transition to the **Verified Fallback Mode** within 20–30 seconds. Never debug deep stack traces in front of judges.

### Symptom 1: Port Collision on Startup (`Address already in use: 8000` or `3000`)
* **Observation:** Uvicorn or Next.js crashes with `EADDRINUSE` error.
* **Fast Diagnostic:**
  ```powershell
  Get-NetTCPConnection -LocalPort 8000,3000 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess
  ```
* **Recovery Action:** Terminate the orphaned process:
  ```powershell
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess -Force
  ```
  Restart the service.

---

### Symptom 2: Frontend Displays "Backend Unreachable" or Network Error Banner
* **Observation:** Red error toast appears: *"Failed to connect to SatQuery API service"*.
* **Recovery Action (10s):**
  1. Check Terminal 1 to ensure Uvicorn is active.
  2. If crashed, hit `Up-Arrow` + `Enter` in Terminal 1 to restart.
  3. In browser, refresh page (F5).

---

### Symptom 3: Interactive Map Renders Blank Tiles or Gray Canvas
* **Observation:** Leaflet map background is solid grey or grid lines fail to load.
* **Cause:** External OpenStreetMap / CartoDB tile server connectivity blip.
* **Recovery Action (5s):**
  1. Toggle the basemap selector in the map controls (switch from *Carto Dark* to *Carto Light* or *OSM Standard*).
  2. The analytical raster layers and vector GeoJSON masks remain 100% locally rendered and will display regardless of basemap tile availability.
* **Presenter Line:** *"The background basemap visualizer is reconnecting, but as you can see, our analytical raster and vector change calculations are computed locally."*

---

### Symptom 4: Remote STAC Catalog Search Times Out or Throws 504 / 429
* **Observation:** STAC scene discovery spinner runs > 5 seconds, or toast says *"Provider rate limit exceeded"*.
* **Recovery Action (Immediate Transition to Fallback):**
  1. In the Scene Selection toolbar, toggle the data source switch from **"Live STAC (AWS)"** to **"Cached / Mock Demo Fixtures"**.
  2. Click **"Load Scenes"** (instantly populates verified Sentinel-2 L2A optical scenes).
* **Presenter Line:** *"The live commercial STAC endpoint is experiencing high latency, so I will switch to our cached Sentinel-2 Level-2A verification pair to demonstrate the exact same downstream processing workflow."*

---

### Symptom 5: Change Computation Fails or Returns Alignment Mismatch
* **Observation:** Alert displays *"Coordinate Reference System mismatch or insufficient overlapping valid pixels"*.
* **Recovery Action:**
  1. Open the **Preset AOI** dropdown on the map toolbar.
  2. Select **"Bengaluru Bellandur Standard AOI (9.64 km²)"**.
  3. Re-click **"Calculate Change"**.

---

### Symptom 6: Browser Tab Crashed or Accidental Page Close
* **Observation:** Browser closed or navigated away.
* **Recovery Action (10s):**
  1. Re-open browser to `http://localhost:3000`.
  2. The frontend automatically re-hydrates the latest workspace state from `localStorage` / backend session cache.

---

## 6. Controlled Fallback Mode Activation

To force offline mode prior to presenting in low-connectivity auditoriums:

```powershell
# Set backend environment to deterministic test/mock mode
$env:SATQUERY_ENV="test"
$env:SATQUERY_AI_PROVIDER="mock"
python -m uvicorn satquery.main:app --host 0.0.0.0 --port 8000
```
This guarantees 100% offline operation:
- Geodesic AOI validation runs via local shapely / pyproj.
- Scene discovery serves deterministic Sentinel-2 L2A pairs from mock catalog.
- Co-registration and NDVI differencing run via local rasterio / numpy.
- Grounded query router uses deterministic rule-based template generation with verified claims.
- ReportLab Platypus compiles multi-page PDF & JSON with complete cryptographic hash.
