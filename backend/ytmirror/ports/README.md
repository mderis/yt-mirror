# ports

The interfaces between the use cases and the outside world, one file per port, each a `typing.Protocol`.

**Belongs here:** interfaces, written with data types from `core`.

**Does not belong here:** any implementation, any I/O, any import other than `core` and the standard library.

Every port has a fake in `backend/tests/fixtures/fakes/`, and a contract test in `backend/tests/integration/` that runs against both the fake and the real adapter, so the fake cannot drift from reality (docs/TESTING.md rule 8).
