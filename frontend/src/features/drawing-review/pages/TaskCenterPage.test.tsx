import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { listTasks } from '../api/drawingApi'
import { TaskCenterPage } from './TaskCenterPage'

vi.mock('../api/drawingApi', () => ({ listTasks: vi.fn() }))

describe('TaskCenterPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('keeps filters and table columns visible when loading fails', async () => {
    vi.mocked(listTasks).mockRejectedValue(new Error('服务暂不可用'))

    render(<MemoryRouter><TaskCenterPage /></MemoryRouter>)

    expect(await screen.findByText('数据加载失败')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('搜索任务或文件名称')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '任务名称' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '审查统计' })).toBeInTheDocument()
    expect(screen.getByText('任务数据暂不可用')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重新加载/ })).toBeInTheDocument()
  })
})
