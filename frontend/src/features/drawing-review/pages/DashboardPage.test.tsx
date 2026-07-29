import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, describe, expect, it, vi } from 'vitest'
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
  it('loads the latest 100 tasks and derives recent status metrics', async () => {
    vi.mocked(listTasks).mockResolvedValue([
      task({ task_id: 'task-1', task_name: '处理中的任务', status: 1 }),
      task({ task_id: 'task-2', task_name: '完成的任务', status: 2 }),
      task({ task_id: 'task-3', task_name: '异常的任务', status: 3 }),
    ])

    render(<DashboardPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('处理中的任务')).toBeInTheDocument()
    expect(listTasks).toHaveBeenCalledWith(100)
    const metrics = within(screen.getByLabelText('近期任务统计'))
    expect(metrics.getByText('近期任务').parentElement).toHaveTextContent('3')
    expect(metrics.getByText('处理中').parentElement).toHaveTextContent('1')
    expect(metrics.getByText('已完成').parentElement).toHaveTextContent('1')
    expect(metrics.getByText('异常').parentElement).toHaveTextContent('1')
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
