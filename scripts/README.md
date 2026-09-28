# Scripts

- `check-prerequisites.ps1` validates the supported Node.js, npm, Python, and Docker prerequisites without changing the machine.
- `verify.ps1` runs the locked backend and frontend checks; `-IncludeDatabase` also invokes the isolated database verification.
- `verify-database.ps1` starts only the disposable `db-test` Compose service, applies/tests migrations, inspects Alembic revisions, and removes only that test container.

All scripts resolve paths from their own location, preserve environment files and persistent development data, and return nonzero when a required step fails.

Docker/Compose is required only for the real database path, but that path is a required Phase 1 completion gate. `verify.ps1` without `-IncludeDatabase` does not imply a successful PostGIS check.
