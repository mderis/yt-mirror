# fakes

One fake per port of `ytmirror.ports`. Fakes live only here (docs/TESTING.md rule 8).

A fake must pass the same contract test as the real adapter of its port. The contract tests are in `backend/tests/integration/test_*_contract.py`. When a port changes, change the fake and the contract test in the same commit.
