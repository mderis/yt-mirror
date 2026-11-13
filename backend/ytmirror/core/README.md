# core

Pure domain code: data types, rules and the status machines.

**Belongs here:** frozen dataclasses and enums, functions that turn values into values, error codes.

**Does not belong here:** anything that reads a file, a clock, a database, the network or the environment, and any import of a framework or of another yt-mirror package. `core` must be testable with plain values (docs/ARCHITECTURE.md section 4, rule 1).

Tests: `backend/tests/unit/core/`.
