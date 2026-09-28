# Local data conventions

This directory is not production storage. Local raw imagery, uploads, caches, generated artifacts, and model weights belong in the ignored subpaths defined by `.gitignore`. Only this convention file and deliberately small, clearly identified test fixtures should be committed.

Production raster assets and generated artifacts will live in private object storage, with provenance and metadata referenced from PostgreSQL/PostGIS. The provider and retention implementation are unresolved.

