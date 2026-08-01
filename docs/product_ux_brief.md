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

## New-review metadata continuation (2026-08-01)

- Information hierarchy: three separate containers in order: task name and remark; recognition configuration; PDF upload.
- Task name: required after trim, 1–48 characters, and safe for the backend-generated task ID/upload directory.
- Remark: optional, maximum 200 characters after trim.
- Recognition configuration: four required, initially unselected fields with the exact placeholders and only options requested by the user.
- Configuration order: 专业分类 → 设备分类 → 图纸类型 → 识别任务类型.
- Final description: `trimmedRemark + "\n" + configText` when a remark exists, otherwise `configText`; `configText` joins the four values with `-`.
- Actions: centered `提交识别任务`, `重置表单`, `退出页面`; reset clears form/files/run state, exit returns to 工作台 without submitting, and the existing running-task leave warning remains.
- Content truth: `description` is sent by the frontend for forward compatibility, but the current backend does not persist or return it.
