# app

The composition root and the entry point.

**Belongs here:** `container.py` (the only place that knows which adapter implements which port), paths and options, logging setup, the web server thread, the window, `main.py`.

**Does not belong here:** business rules. If `main.py` needs a decision, the decision belongs in a service.

Tests: `backend/tests/unit/app/` and `backend/tests/integration/app/`.
