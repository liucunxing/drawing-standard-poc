# Frozen API Contract for React MVP

All business responses use `ApiEnvelope<T> = { code: number; msg: string; data: T | null }`. HTTP 200 with `code != 200` is an application error.

## Routes

| Purpose | Contract |
|---|---|
| Upload | `POST /api/drawing/upload-pdf`, multipart field `files` repeated, optional query `task_name` |
| Process one PDF | `POST /api/drawing/process-single-pdf-full`, query `task_id`, `file_index` (1-based) |
| Recent tasks | `GET /api/drawing/tasks?limit=100` |
| Task detail | `GET /api/drawing/task/{task_id}` |
| Parse status | `GET /api/drawing/task/{task_id}/parse-status` |
| Standards list | `GET /api/standard-data?keyword=&page=1&page_size=20` |
| Standard create | `POST /api/standard-data` with `standard_no`, `standard_type`, `standard_prefix`, optional `operator` |
| Standard update | `PUT /api/standard-data/{id}` with the create fields |
| Standard delete | `DELETE /api/standard-data/{id}` |
| Files | `GET /api/files/{relative-path}` |

## Frontend-only metadata compatibility

- The new-review client sends trimmed `task_name` through the existing optional upload query parameter.
- The client also sends a forward-compatible `description` query parameter containing the user remark and selected recognition configuration.
- `origin/master` at `1676ff2` does not declare, persist, or return `description`; this transport-only parameter must not be reported as stored data until a separately approved backend/database contract exists.
- Remarks and recognition configuration must never be encoded into `task_name`, because the backend uses that value in the task ID and upload directory.

## Status semantics

- Task status: `0` pending, `1` processing, `2` complete, `3` failed. Unknown values are shown verbatim/neutrally.
- Standard result values: `完全符合`, `年份不一致`, `较为相似`, `不存在`, plus compatible fallback labels such as `解析错误` and `待识别`.

## Required frontend models

- Task: id/name/file fields, counts, numeric status, progress/current step, error, timestamps.
- Detail additions: `file_names`, `pdfs`, `tables`, `standards`, `annotated_images`, `overall_standard_compare`.
- Table: PDF name, page, table index/display name, image URL/path, raw and highlighted Markdown.
- Standard match: PDF name, standard number, matched standard, result/status, source table, confidence, suggestion.
- Standard record: id, standard number/type/prefix, create/update timestamps and users.

## Compatibility rules

- Normalize missing arrays to `[]`, missing counts to `0`, and invalid display values to `—`.
- Preserve backend messages; do not convert business failure into a success state.
- Image URLs may be relative or absolute and must be normalized through one helper.
- No backend business endpoint may change without explicit Orchestrator approval.
