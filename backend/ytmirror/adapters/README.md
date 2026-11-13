# adapters

Implementations of the ports: the database, the system clock, the operating system. Later: yt-dlp, ffmpeg, the macOS file system, GitHub.

**Belongs here:** code that talks to something outside the process, behind a port.

**Does not belong here:** business rules, and imports of `services`, `api`, `app` or of another adapter.

Tests: `backend/tests/integration/`.
