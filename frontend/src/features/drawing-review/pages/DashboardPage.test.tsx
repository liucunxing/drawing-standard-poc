import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { listTasks } from '../api/drawingApi'
import { DashboardPage } from './DashboardPage'

vi.mock('../api/drawingApi', () => ({ listTasks: vi.fn() }))

beforeAll(() => {
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
})

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the latest 100 tasks and derives task status metrics', async () => {
    vi.mocked(listTasks).mockResolvedValue([
      task({ task_id: 'task-1', task_name: '处理中的任务', status: 1 }),
      task({ task_id: 'task-2', task_name: '完成的任务', status: 2 }),
      task({ task_id: 'task-3', task_name: '异常的任务', status: 3 }),
    ])

    render(<DashboardPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('处理中的任务')).toBeInTheDocument()
    expect(listTasks).toHaveBeenCalledWith(100)
    const metrics = within(screen.getByLabelText('数据统计总览'))
    expect(metrics.getByText('所有任务数量').parentElement).toHaveTextContent('3')
    expect(metrics.getByText('进行中任务数量').parentElement).toHaveTextContent('1')
    expect(metrics.getByText('审核确认任务数量').parentElement).toHaveTextContent('1')
    expect(metrics.getByText('报错任务数量').parentElement).toHaveTextContent('1')
  })

  it('provides working quick actions without adding backend contracts', async () => {
    vi.mocked(listTasks).mockResolvedValue([])

    render(<DashboardPage />, { wrapper: MemoryRouter })

    await waitFor(() => expect(listTasks).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('button', { name: /创建识别任务/ })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /查询历史识别任务/ }))
    await waitFor(() => expect(listTasks).toHaveBeenCalledTimes(2))
    expect(listTasks).toHaveBeenLastCalledWith(100)

    fireEvent.click(screen.getByRole('button', { name: /配置识别规则/ }))
    expect(await screen.findByText('暂不可配置识别规则')).toBeInTheDocument()
  })

  it('keeps the dashboard framework visible when the backend is unavailable', async () => {
    vi.mocked(listTasks).mockRejectedValue(new Error('后端连接失败'))

    render(<DashboardPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(screen.getByText('后端连接失败')).toBeInTheDocument()
    expect(screen.getByLabelText('数据统计总览')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '任务名称' })).toBeInTheDocument()
    expect(screen.getByText('近期任务数据暂不可用')).toBeInTheDocument()
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
    original_filename: '',
    file_names: [],
    pdf_count: 1,
    file_size: 0,
    page_count: 0,
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
    created_at: null,
    updated_at: null,
    started_at: null,
    completed_at: null,
  }
}
