import { apiRequest } from '../../../shared/api/client'
import type {
  AnnotatedImage,
  ProcessFileResult,
  RecognitionTable,
  StandardMatch,
  TaskDetail,
  TaskSummary,
  UploadResult,
} from '../types'

type RawTask = Omit<Partial<TaskDetail>, 'tables'> & { task_id?: unknown; tables?: unknown }

const numberValue = (value: unknown): number => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const textValue = (value: unknown): string => (value == null ? '' : String(value))
const textArray = (value: unknown): string[] => Array.isArray(value) ? value.map(textValue).filter(Boolean) : []
const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const firstNonBlankText = (...values: unknown[]): string => {
  for (const value of values) {
    if (typeof value !== 'string' && typeof value !== 'number') continue
    const text = String(value)
    if (text.trim()) return text
  }
  return ''
}
const firstNumber = (...values: unknown[]): number => {
  for (const value of values) {
    if (value == null || value === '') continue
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}
const statusValue = (value: unknown): TaskSummary['status'] => {
  if (value == null || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : String(value)
}

export function normalizeTask(raw: RawTask): TaskSummary {
  const taskId = textValue(raw.task_id)
  const originalFilename = textValue(raw.original_filename)
  const fileNames = textArray(raw.file_names)
  return {
    id: raw.id == null ? undefined : numberValue(raw.id),
    task_id: taskId,
    task_name: textValue(raw.task_name) || originalFilename || taskId || '未命名任务',
    original_filename: originalFilename,
    file_names: fileNames.length ? fileNames : originalFilename ? [originalFilename] : [],
    pdf_count: numberValue(raw.pdf_count) || fileNames.length || (originalFilename ? 1 : 0),
    file_size: numberValue(raw.file_size),
    page_count: numberValue(raw.page_count),
    status: statusValue(raw.status),
    progress: numberValue(raw.progress),
    current_step: textValue(raw.current_step),
    table_count: numberValue(raw.table_count),
    standard_count: numberValue(raw.standard_count),
    exact_match_count: numberValue(raw.exact_match_count),
    year_mismatch_count: numberValue(raw.year_mismatch_count),
    similar_count: numberValue(raw.similar_count),
    not_found_count: numberValue(raw.not_found_count),
    error_message: textValue(raw.error_message),
    created_at: raw.created_at ? textValue(raw.created_at) : null,
    updated_at: raw.updated_at ? textValue(raw.updated_at) : null,
    started_at: raw.started_at ? textValue(raw.started_at) : null,
    completed_at: raw.completed_at ? textValue(raw.completed_at) : null,
  }
}

export function normalizeRecognitionTable(value: unknown, index = 0): RecognitionTable {
  const raw = isRecord(value) ? value : {}
  const tableIndex = firstNumber(raw.table_index, raw.source_table_index, index + 1)
  const rawMarkdown = firstNonBlankText(
    raw.qwen_fixed_md_content,
    raw.raw_markdown_content,
    raw.md_content,
    raw.original_md_content,
    raw.markdown_content,
    raw.highlighted_markdown_content,
  )
  const renderedMarkdown = firstNonBlankText(
    raw.markdown_content,
    raw.highlighted_markdown_content,
    raw.md_content,
    raw.qwen_fixed_md_content,
    raw.raw_markdown_content,
    raw.original_md_content,
  )
  return {
    pdf_name: firstNonBlankText(raw.pdf_name, raw.file_name, raw.original_filename),
    page: firstNumber(raw.page, raw.page_number),
    table_index: tableIndex,
    display_name: firstNonBlankText(raw.display_name, raw.table_name, raw.name) || `表格${tableIndex || index + 1}`,
    image_path: firstNonBlankText(raw.image_path, raw.source_image, raw.table_image_path),
    image_url: firstNonBlankText(raw.image_url, raw.source_image_url, raw.table_image_url),
    raw_markdown_content: rawMarkdown,
    markdown_content: renderedMarkdown,
    highlighted_markdown_content: firstNonBlankText(raw.highlighted_markdown_content, renderedMarkdown),
    markdown_path: firstNonBlankText(raw.markdown_path, raw.md_file, raw.qwen_fixed_md_file, raw.original_md_file),
    markdown_url: firstNonBlankText(raw.markdown_url, raw.md_url, raw.qwen_fixed_md_url, raw.original_md_url),
  }
}

export function normalizeTaskDetail(raw: RawTask): TaskDetail {
  return {
    ...normalizeTask(raw),
    description: textValue(raw.description),
    processed_count: numberValue(raw.processed_count),
    pdfs: Array.isArray(raw.pdfs) ? raw.pdfs : [],
    tables: (Array.isArray(raw.tables) ? raw.tables : []).map(normalizeRecognitionTable),
    standards: (Array.isArray(raw.standards) ? raw.standards : []) as StandardMatch[],
    annotated_images: (Array.isArray(raw.annotated_images) ? raw.annotated_images : []) as AnnotatedImage[],
    overall_standard_compare: raw.overall_standard_compare || {},
    raw_json: raw.raw_json,
  }
}

export async function uploadPdfs(files: File[], taskName?: string, description?: string): Promise<UploadResult> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  const normalizedTaskName = taskName?.trim()
  const normalizedDescription = description?.trim()
  const params = normalizedTaskName || normalizedDescription ? {
    ...(normalizedTaskName ? { task_name: normalizedTaskName } : {}),
    ...(normalizedDescription ? { description: normalizedDescription } : {}),
  } : undefined
  return apiRequest<UploadResult>({
    method: 'POST',
    url: '/drawing/upload-pdf',
    data: formData,
    params,
    timeout: 3_600_000,
  })
}

export function processSinglePdf(taskId: string, fileIndex: number): Promise<ProcessFileResult> {
  return apiRequest<ProcessFileResult>({
    method: 'POST',
    url: '/drawing/process-single-pdf-full',
    params: { task_id: taskId, file_index: fileIndex },
    timeout: 3_600_000,
  })
}

export async function listTasks(limit = 100): Promise<TaskSummary[]> {
  const data = await apiRequest<RawTask[]>({ method: 'GET', url: '/drawing/tasks', params: { limit } })
  return (Array.isArray(data) ? data : []).map(normalizeTask)
}

export async function getTaskDetail(taskId: string): Promise<TaskDetail> {
  const data = await apiRequest<RawTask>({ method: 'GET', url: `/drawing/task/${encodeURIComponent(taskId)}` })
  return normalizeTaskDetail(data || {})
}
