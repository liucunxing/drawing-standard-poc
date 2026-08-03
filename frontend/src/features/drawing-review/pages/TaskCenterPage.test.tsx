import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listTasks } from '../api/drawingApi'
import { TaskCenterPage } from './TaskCenterPage'

vi.mock('../api/drawingApi', () => ({ listTasks: vi.fn() }))

describe('TaskCenterPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('applies draft filters only after the filter button is clicked and refreshes the existing task endpoint', async () => {
    const tasks = [
      task({ task_id: 'task-a', task_name: '泵房图纸识别' }),
      task({ task_id: 'task-b', task_name: '阀门历史审查' }),
    ]
    vi.mocked(listTasks).mockResolvedValue(tasks)

    render(<MemoryRouter><TaskCenterPage /></MemoryRouter>)

    expect(await screen.findByText('泵房图纸识别')).toBeInTheDocument()
    expect(screen.getByText('阀门历史审查')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('搜索任务或文件名称'), { target: { value: '阀门' } })
    expect(screen.getByText('泵房图纸识别')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /筛选/ }))
    await waitFor(() => expect(listTasks).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByText('泵房图纸识别')).not.toBeInTheDocument())
    expect(screen.getByText('阀门历史审查')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /重置/ }))
    await waitFor(() => expect(listTasks).toHaveBeenCalledTimes(3))
    expect(await screen.findByText('泵房图纸识别')).toBeInTheDocument()
  })

  it('shows separated filtering, bordered task list and selectable page sizes', async () => {
    vi.mocked(listTasks).mockResolvedValue(Array.from({ length: 12 }, (_, index) => task({ task_id: `task-${index}`, task_name: `任务 ${index + 1}` })))

    render(<MemoryRouter><TaskCenterPage /></MemoryRouter>)

    expect(await screen.findByText('任务筛选条件')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '任务列表' })).toBeInTheDocument()
    expect(screen.getByText('共 12 条数据')).toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: '每页显示条数' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '10' })).toBeChecked()
    expect(screen.getByRole('radio', { name: '20' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: '50' })).toBeInTheDocument()
  })

  it('keeps filters and table columns visible when loading fails', async () => {
    vi.mocked(listTasks).mockRejectedValue(new Error('服务暂不可用'))

    render(<MemoryRouter><TaskCenterPage /></MemoryRouter>)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('搜索任务或文件名称')).toBeInTheDocument()
    expect(screen.getByText('任务筛选条件')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '任务名称' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '审查统计' })).toBeInTheDocument()
    expect(screen.getByText('任务数据暂不可用')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重新加载/ })).toBeInTheDocument()
  })
})

function task(overrides: Partial<ReturnType<typeof baseTask>>): ReturnType<typeof baseTask> {
  return { ...baseTask(), ...overrides }
}

function baseTask() {
  return {
    id: 1,
    task_id: 'task-0',
    task_name: '任务',
    original_filename: 'drawing.pdf',
    file_names: ['drawing.pdf'],
    pdf_count: 1,
    file_size: 0,
    page_count: 1,
    status: 0,
    progress: 0,
    current_step: '',
    table_count: 0,
    standard_count: 0,
    exact_match_count: 0,
    year_mismatch_count: 0,
    similar_count: 0,
    not_found_count: 0,
    error_message: '',
    created_at: '2026-07-01 09:00:00',
    updated_at: null,
    started_at: null,
    completed_at: null,
  }
}
