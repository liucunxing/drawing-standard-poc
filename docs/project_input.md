# Project Input

## Objective

Rebuild the existing Streamlit drawing-standard POC as a simple, clear React MVP for internal trial use while minimizing backend changes and keeping future integration with a parallel React application manageable.

## Frozen scope

- Dashboard based on the latest 100 tasks.
- Multi-PDF upload followed by sequential per-file processing.
- Task list with client-side filters and pagination.
- Task detail with overview, layout images, table/Markdown content, and standard review.
- Standard library CRUD using existing endpoints.
- Nginx static delivery and same-origin `/api` proxy, with Streamlit retained as rollback.

## Non-goals

No authentication, RBAC, SSE, backend job queue, chat entry, rich text editing, client PDF parsing, export/reporting, microfrontend, mobile layout, or production-readiness claim.

## Constraints

- Source priority: actual API/runtime fields > current Streamlit behavior > Feishu information architecture > screenshot example fields.
- Trial is internal-network only because no authentication exists.
- Existing sample/customer files and backend recognition logic are protected.
- Unknown or absent API fields must not be invented in the UI.

## Baseline

- Remote baseline: `bce80a06bb16f0a77327cc38924f4bc0ba056937`.
- Backend: FastAPI + MySQL + GPU recognition services.
- Existing frontend: root `streamlit_app.py` on port 8501.
- Formal automated backend tests were not found; four sample PDFs exist under `data/samples/pdf`.

## Known risks

- Browser-driven synchronous processing is interrupted before remaining files are submitted when the user closes or refreshes the page.
- The task list is limited to recent rows and does not support server-side aggregate metrics.
- Example/backend configuration previously contained unsafe credential defaults.
- `/api/files/{filepath}` requires containment validation before trial deployment.
