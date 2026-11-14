# fakes

One fake per port of `ytmirror.ports`. Fakes live only here (docs/TESTING.md rule 8).

A fake must pass the same contract test as the real adapter of its port. The contract tests are in `backend/tests/integration/test_*_contract.py`. When a port changes, change the fake and the contract test in the same commit.

Two ports have no fake here, on purpose:

- **CatalogueRepository.** What it does is the database: the transaction of a check, the order of a catalogue, the totals. Tests of the services use the real repository on a migrated database in a temp folder (`tests/fixtures/database.py`), which docs/TESTING.md section 1 allows for the service layer. Its tests are in `backend/tests/integration/db/`.
- **YouTubeGateway.** Its fake is part of the app, because the app itself can start with it: `backend/ytmirror/adapters/fixture_youtube.py` (docs/DECISIONS.md D-062). It passes the same contract test as the real gateway.

