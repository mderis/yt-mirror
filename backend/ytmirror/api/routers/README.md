# api/routers

One module per resource. Each module has a `build_router(...)` function that receives the services it needs and returns a router. Nothing here reads global state.

Tests: `backend/tests/api/`.
