# adapters/db

Everything that knows SQLite and SQLAlchemy: the engine, the tables, the repositories and the schema migrator.

**Belongs here:** table definitions, repositories that implement ports, session handling.

**Does not belong here:** business rules. A repository stores and loads, it does not decide.

The migration files themselves are in `backend/ytmirror/migrations/`.

Tests: `backend/tests/integration/db/` and `backend/tests/migrations/`.
