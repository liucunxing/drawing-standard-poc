# API 设计草案

## 1. 上传与任务

### POST /api/tasks/upload

上传 PDF 文件并创建审查任务。

输入：

- files: PDF 文件列表。

输出：

```json
{
  "task_id": "task_001",
  "status": "pending"
}
```

### GET /api/tasks/{task_id}

查询任务状态和总体进度。

### GET /api/tasks

查询任务列表。

## 2. 分步骤结果查询

### GET /api/tasks/{task_id}/tables

查询表格区域识别结果。

### GET /api/tasks/{task_id}/parsed-tables

查询表格解析结果，包括 Markdown 和 JSON。

### GET /api/tasks/{task_id}/standards

查询标准编号提取结果。

### GET /api/tasks/{task_id}/review-results

查询标准库比对和审查结果。

## 3. 人工复核

### POST /api/tasks/{task_id}/manual-review

提交人工复核结果。

建议输入：

```json
{
  "result_id": "result_001",
  "manual_result_type": "完全符合",
  "manual_comment": "经人工确认标准引用正确"
}
```

## 4. 标准库

### GET /api/standards

查询标准库。

### POST /api/standards/import

导入标准库文件。

