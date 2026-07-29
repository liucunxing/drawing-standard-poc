# Project Agent Rules

## Goal and current phase

- Goal: 将 Streamlit POC 重构为 React 19 + TypeScript 的内部 MVP 试用版，并保持现有 FastAPI 业务契约。
- Current phase: Controlled delivery，React MVP implementation。
- Explicit non-goals: 登录/RBAC、SSE、异步队列、聊天入口、客户端 PDF 解析、富文本编辑、报表导出、微前端、移动端、生产级高可用。

## Authority

- Orchestrator owns dispatch, integration, shared contracts, state, and defect routing.
- Planner is used only for consequential product, architecture, scope, or contract changes.
- Explorer is read-only.
- Workers modify only assigned scope and must not revert other work.
- QA and Final Reviewer review independently and do not repair their own findings.

## Frozen decisions

- Scope: 工作台、新建审查、任务中心、任务详情四页签、标准库。
- API: keep the existing `/api` routes and `{code,msg,data}` envelope; prefer frontend adapters over backend changes.
- UX terminology: 工作台、新建审查、任务中心、标准库；任务详情页签为任务概览、版面识别、内容识别、标准审查。
- Visual direction: restrained SOE enterprise UI, white/light gray/enterprise blue, no gradients, glow, glass, heavy shadows, or decorative animation.
- Runtime: React 19, TypeScript, Vite 7, Ant Design 5, React Router DOM 7, Zustand, Axios, CSS Modules, markdown-it, DOMPurify, dayjs, pnpm.

## Protected paths and outputs

- Treat `data/`, customer/sample source files, `streamlit_app.py`, database schema, and backend recognition algorithms as read-only unless the Orchestrator assigns a specific fix.
- Never commit `.env`, real credentials, generated OCR outputs, database files, logs, models, or customer documents.
- `frontend/` is the React candidate implementation. The existing Streamlit app remains the rollback implementation.

## File ownership

- Orchestrator only: root package/deployment integration decisions, `frontend/package.json`, route root, API client, shared API types, global theme, project state files.
- Shell worker: application shell, navigation, shared presentational components, dashboard.
- Workflow worker: upload workflow, Zustand run state, task center.
- Results worker: task detail, annotated images, markdown rendering, standards review result UI.
- Standards/deploy worker: standard library feature plus Docker/Nginx deployment files explicitly assigned by ticket.
- A worker needing a shared-file change must report it to the Orchestrator instead of editing outside ownership.

## Delivery loop

- Required states: BASELINE → CONTRACT_FREEZE → DISPATCH → INTEGRATE → UX_REVIEW → QA → FIX/RE_QA as needed → FINAL_GATE → DELIVERY_DECISION → CLOSE.
- P0/P1 findings return to the accountable worker and require independent regression.
- Contract or scope changes stop and route to Planner.

## Required evidence

- `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`.
- Playwright smoke coverage for standalone and `/drawing-review` base paths.
- UI screenshots at 1366×768 and 1920×1080 when browser execution is available.
- Real-backend verification must be reported separately from mock/unit verification.
