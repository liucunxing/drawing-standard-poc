# Controlled Delivery Task Plan

| Ticket | Owner | Dependency | Acceptance |
|---|---|---|---|
| BASE-001 baseline/contract | Explorer | none | API, Docker, fields, risks confirmed read-only |
| CORE-001 React foundation | Orchestrator | BASE-001 | package, routing, API/types, theme and tests build |
| UI-001 shell/dashboard | Frontend shell worker | CORE-001 | navigation and recent metrics conform to UX brief |
| FLOW-001 upload/tasks | Frontend workflow worker | CORE-001 | sequential multi-PDF workflow and task center |
| DETAIL-001 task detail | Frontend results worker | CORE-001 | four tabs, safe Markdown and images/results |
| STD-001 standards/deploy | Frontend/deploy worker | CORE-001 | CRUD plus Nginx/Docker rollback arrangement |
| QA-001 independent QA | QA | integration | reproducible findings and severity |
| GATE-001 delivery review | Final reviewer | QA pass | release verdict and residual risks |

Integration order: foundation → shell/workflow/results/standards → deployment → UX review → QA → repairs → final gate.

## New-review metadata continuation (2026-08-01)

| Ticket | Owner | Dependency | Acceptance |
|---|---|---|---|
| DRMVP-20260801-EXP-01 | Explorer | latest `origin/master` fetched | upload contract and persistence facts confirmed read-only |
| DRMVP-20260801-PLAN-01 | Planner / Conflict Reviewer | exploration | transport-only metadata rule and exact description composition frozen |
| DRMVP-20260801-FE-01 | Frontend workflow | contract freeze | three containers, validation, configuration, request state and centered actions |
| DRMVP-20260801-QA-01 | QA | integration and UX repair | independent contract, functional and visual regression |
| DRMVP-20260801-GATE-01 | Final reviewer | QA pass | local candidate verdict with real-backend limitations retained |

Status: all continuation tickets complete; local frontend candidate `PASS WITH FINDINGS`.
