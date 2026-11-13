# api

Translates HTTP into service calls and back.

**Belongs here:** routers, request and response models, the security checks of docs/ARCHITECTURE.md section 9, the mapping from error codes to HTTP responses.

**Does not belong here:** business logic and database access.

The OpenAPI schema produced here is the contract with the frontend. After changing a route or a model, run `npm --prefix frontend run gen:api`.

Tests: `backend/tests/api/`.
