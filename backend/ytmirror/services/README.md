# services

The use cases of the app. A service receives ports in its constructor and uses `core` for the rules.

**Belongs here:** one module per use case area, logging at the start and end of each use case with event names from docs/LOGGING.md.

**Does not belong here:** imports of an adapter, of FastAPI, or of `app`. Direct calls to the system clock: time comes from the Clock port.

Tests: `backend/tests/unit/services/`, with the fakes from `backend/tests/fixtures/fakes/`.
