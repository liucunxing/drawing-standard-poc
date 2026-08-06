export type TaskStatus = 0 | 1 | 2 | 3 | number | string | null

export interface TaskSummary {
  id?: number
  task_id: string
  task_name: string
  original_filename: string
  file_names: string[]
  pdf_count: number
  file_size: number
  page_count: number
  status: TaskStatus
  progress: number
  current_step: string
  table_count: number
  standard_count: number
  exact_match_count: number
  year_mismatch_count: number
  similar_count: number
  not_found_count: number
  error_message: string
  created_at: string | null
  updated_at: string | null
  started_at: string | null
  completed_at: string | null
}

export interface PdfSummary {
  pdf_name: string
  status: string
  table_count: number
  standard_count: number
}

export interface RecognitionTable {
  pdf_name: string
  page: number
  table_index: number
  display_name: string
  image_path: string
  image_url: string
  raw_markdown_content: string
  markdown_content: string
  highlighted_markdown_content: string
  markdown_path: string
  markdown_url: string
}

export interface AnnotatedImage {
  pdf_name?: string
  page: number
  image_path: string
  image_url: string
}

export type StandardResult = '完全符合' | '年份不一致' | '较为相似' | '不存在' | '解析错误' | '待识别' | string

export interface StandardMatch {
  pdf_name: string
  standard_no: string
  matched_standard: string
  status: StandardResult
  result_type: StandardResult
  source_table: string
  confidence: number
  suggestion: string
}

export interface OverallStandardCompare {
  results?: Array<Record<string, unknown>>
  [key: string]: unknown
}

export interface TaskDetail extends TaskSummary {
  description: string
  processed_count: number
  pdfs: PdfSummary[]
  tables: RecognitionTable[]
  standards: StandardMatch[]
  annotated_images: AnnotatedImage[]
  overall_standard_compare: OverallStandardCompare
  raw_json?: Record<string, unknown>
}

export interface UploadResult {
  task_id: string
  filename: string
  original_filename: string
  file_path: string
  file_size: number
  uploaded_at: string
  pdf_count: number
  file_names: string[]
  files: Array<{
    index: number
    original_filename: string
    saved_filename: string
    file_path: string
    file_size: number
  }>
}

export interface ProcessFileResult {
  task_id: string
  pdf_name: string
  file_index: number
  file_count: number
  processed_files: number
  total_pages: number
  total_tables: number
  tables: RecognitionTable[]
  summary?: Record<string, number>
}

export interface StandardRecord {
  id: number
  standard_no: string
  standard_type: string
  standard_prefix: string
  create_time: string | null
  update_time: string | null
  create_user: string
  update_user: string
}

export interface StandardListResult {
  total: number
  page: number
  page_size: number
  items: StandardRecord[]
}

export interface StandardInput {
  standard_no: string
  standard_type: string
  standard_prefix: string
  operator?: string
}
