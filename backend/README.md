# Backend

The Phase 1 backend is a FastAPI application with typed settings, structured errors and logs, request IDs, asynchronous PostgreSQL/PostGIS connectivity, and explicit Alembic migrations.

From this directory, after creating the root `.env` and local `.venv` described in the project `README.md`:

```powershell
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn satquery.main:create_app --factory --app-dir src --reload --host 127.0.0.1 --port 8000
```

`GET /api/v1/health/live` checks only the application. `GET /api/v1/health/ready` checks the real database, PostGIS, and Alembic revision. A missing or stale dependency produces a safe `503`; startup itself does not hide the problem or mutate schema.

Run backend checks with:

```powershell
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format --check .
..\.venv\Scripts\python.exe -m mypy src tests
..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -m 'not integration'
```

The backend deliberately has no satellite, upload, analysis, authentication, or report endpoints yet.
