# Product and UX Brief

- Primary user: internal engineering reviewer trialing drawing recognition and standard comparison.
- Job: upload one or more drawing PDFs, see progress, inspect recognized tables/content, review standard matches, and maintain the standard library.
- Happy path: 新建审查 → 上传 → 顺序处理 → 任务详情 → 检查四页签。
- Exception path: upload/process error stops remaining browser submissions, keeps persisted results, and offers task detail or restart.
- Navigation: 工作台、新建审查、任务中心、标准库。
- Real content: all tasks, counts, images, Markdown, standard matches, and standard records come from existing APIs. No fake user/project/department fields.
- Derived content: dashboard metrics are computed from the latest 100 tasks and labeled `近期`.
- Visual direction: white/light gray background, restrained enterprise blue, 14px Chinese body, 36px controls, 4px radius, 1px borders, one primary action per view.
- Prohibited: gradients, glass, glow, heavy shadows, decorative charts, hero art, complex animation.
- Required states: loading, empty, business error, HTTP error, partial completion, unknown status, missing images/content.
- Trial viewport: modern Edge/Chrome, minimum 1366×768; mobile and IE are out of scope.
- Post-build evidence: route-by-route visual review plus 1366×768 and 1920×1080 screenshots when browser execution is available.
