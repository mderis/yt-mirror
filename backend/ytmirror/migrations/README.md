# migrations

The Alembic environment and the database migrations (docs/RELEASE-AND-UPDATE.md section 7).

Rules:

- Forward only. A migration has an `upgrade` function and no `downgrade`.
- One migration per schema change, named `NNNN_short_description.py`. The revision ID is the number.
- Each migration has a test in `backend/tests/migrations/`.
- Migrations are run by the app at start (`adapters/db/schema.py`), not with the `alembic` command.
- A migration imports only Alembic and SQLAlchemy, never the table classes of the app: it must keep working after those classes change.
