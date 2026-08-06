import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

const drawingApi = vi.hoisted(() => ({ getTaskDetail: vi.fn() }))
vi.mock('../api/drawingApi', () => drawingApi)

const detail = {
    task_id: 'task-1', task_name: '装置图纸审查', file_names: ['A.pdf'], pdf_count: 1, file_size: 2048, page_count: 3,
    status: 2, progress: 100, current_step: '处理完成', table_count: 1, standard_count: 1, exact_match_count: 1,
    year_mismatch_count: 0, similar_count: 0, not_found_count: 0, error_message: '', created_at: null, updated_at: null,
    started_at: null, completed_at: null, description: '', processed_count: 1, pdfs: [],
    annotated_images: [{ pdf_name: 'A.pdf', page: 1, image_path: 'tasks/a.png', image_url: '' }],
    tables: [{ pdf_name: 'A.pdf', page: 1, table_index: 1, display_name: '材料表', image_path: 'tasks/table.png', image_url: '', raw_markdown_content: '  \n', markdown_content: '<table><tbody><tr><td rowspan=1 colspan=15>管 口 表</td></tr><tr><td>序号</td><td>规格</td></tr><tr><td>1</td><td>DN80</td></tr></tbody></table>', highlighted_markdown_content: '<mark>DN80</mark>', markdown_path: '', markdown_url: '' }],
    standards: [{ pdf_name: 'A.pdf', standard_no: 'GB 1', matched_standard: 'GB 1-2024', status: '完全符合', result_type: '完全符合', source_table: '材料表', confidence: 98, suggestion: '无需修改' }], overall_standard_compare: {},
}

function renderPage() {
  return render(<MemoryRouter initialEntries={['/tasks/task-1']}><Routes><Route path="/tasks/:taskId" element={<TaskDetailPage />} /></Routes></MemoryRouter>)
}

describe('TaskDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    drawingApi.getTaskDetail.mockResolvedValue(detail)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('loads the requested four result tabs and real task fields', async () => {
    renderPage()
    expect(await screen.findByText('装置图纸审查')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '图纸原始预览' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '图纸基础信息' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸标准信息审查' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸版面识别结果' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸内容解析结果' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '标准匹配分析结果' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '标准对比明细列表' })).toBeInTheDocument()
  })

  it('renders Markdown as an editable visual table and keeps edits while switching tabs', async () => {
    renderPage()
    await screen.findByText('装置图纸审查')

    fireEvent.click(screen.getByRole('tab', { name: '图纸版面识别结果' }))
    expect(screen.getByRole('heading', { name: '图纸版面识别明细' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '图纸内容解析结果' }))
    const editor = screen.getByRole('textbox', { name: 'Markdown 解析结果编辑区' })
    expect(editor).toHaveAttribute('contenteditable', 'true')
    expect(within(editor).getByRole('table')).toBeInTheDocument()
    expect(within(editor).getByText('管 口 表')).toBeInTheDocument()
    expect(within(editor).getByText('DN80')).toBeInTheDocument()
    expect(editor).not.toHaveTextContent('<table>')
    editor.innerHTML = '<table><tbody><tr><td>已编辑</td></tr></tbody></table>'
    fireEvent.input(editor)
    expect(within(editor).getByText('已编辑')).toBeInTheDocument()
    expect(screen.getByText('可直接点击表格单元格或文字修改；编辑仅保留在当前页面，不会回写服务端。')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '标准匹配分析结果' }))
    expect(screen.getByRole('heading', { name: '标准匹配分析明细' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: '图纸内容解析结果' }))
    expect(within(screen.getByRole('textbox', { name: 'Markdown 解析结果编辑区' })).getByText('已编辑')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '恢复识别结果' }))
    expect(within(screen.getByRole('textbox', { name: 'Markdown 解析结果编辑区' })).getByText('DN80')).toBeInTheDocument()
  })

  it('loads Markdown from the existing file URL when inline compatibility fields are empty', async () => {
    drawingApi.getTaskDetail.mockResolvedValue({
      ...detail,
      tables: [{ ...detail.tables[0], raw_markdown_content: '', markdown_content: '', highlighted_markdown_content: '', markdown_url: '/api/files/markdown/task-1/table-1.md' }],
    })
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/markdown/task-1/table-1.md')) {
        return Promise.resolve(new Response('<table><tr><td>远程管口表</td></tr></table>', { status: 200 }))
      }
      return Promise.reject(new Error('PDF preview unavailable in test'))
    }))

    renderPage()
    await screen.findByText('装置图纸审查')
    fireEvent.click(screen.getByRole('tab', { name: '图纸内容解析结果' }))

    const editor = await screen.findByRole('textbox', { name: 'Markdown 解析结果编辑区' })
    expect(within(editor).getByText('远程管口表')).toBeInTheDocument()
  })

  it('keeps the four-tab framework visible when detail loading fails', async () => {
    drawingApi.getTaskDetail.mockRejectedValue(new Error('任务接口不可用'))

    renderPage()

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(screen.getByText('任务接口不可用')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸标准信息审查' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸版面识别结果' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '图纸内容解析结果' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '标准匹配分析结果' })).toBeInTheDocument()
    expect(screen.getByText('任务数据暂不可用')).toBeInTheDocument()
  })
})
