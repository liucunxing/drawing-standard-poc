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
