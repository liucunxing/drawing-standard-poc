import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { TaskDetailPage } from './TaskDetailPage'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
})

vi.mock('../api/drawingApi', () => ({
  getTaskDetail: vi.fn().mockResolvedValue({
    task_id: 'task-1', task_name: '装置图纸审查', file_names: ['A.pdf'], pdf_count: 1, file_size: 2048, page_count: 3,
    status: 2, progress: 100, current_step: '处理完成', table_count: 1, standard_count: 1, exact_match_count: 1,
    year_mismatch_count: 0, similar_count: 0, not_found_count: 0, error_message: '', created_at: null, updated_at: null,
    started_at: null, completed_at: null, description: '', processed_count: 1, pdfs: [],
    annotated_images: [{ pdf_name: 'A.pdf', page: 1, image_path: 'tasks/a.png', image_url: '' }],
    tables: [{ pdf_name: 'A.pdf', page: 1, table_index: 1, display_name: '材料表', image_path: 'tasks/table.png', image_url: '', raw_markdown_content: '| A |', markdown_content: '| A |', highlighted_markdown_content: '<mark>A</mark>' }],
    standards: [{ pdf_name: 'A.pdf', standard_no: 'GB 1', matched_standard: 'GB 1-2024', status: '完全符合', result_type: '完全符合', source_table: '材料表', confidence: 98, suggestion: '无需修改' }], overall_standard_compare: {},
  }),
}))

describe('TaskDetailPage', () => {
  it('loads the fixed four tabs and real task fields', async () => {
    render(<MemoryRouter initialEntries={['/tasks/task-1']}><Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes></MemoryRouter>)
    expect(await screen.findByText('装置图纸审查')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '任务概览' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '版面识别' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '内容识别' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '标准审查' })).toBeInTheDocument()
    expect(screen.getByText('处理完成')).toBeInTheDocument()
  })
})
