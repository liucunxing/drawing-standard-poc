import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App as AntApp, ConfigProvider } from 'antd'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StandardsPage } from './StandardsPage'

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

const standardApi = vi.hoisted(() => ({
  createStandard: vi.fn(),
  deleteStandard: vi.fn(),
  listStandards: vi.fn(),
  updateStandard: vi.fn(),
}))

vi.mock('../api/standardApi', () => standardApi)

function renderPage() {
  return render(<ConfigProvider><AntApp><StandardsPage /></AntApp></ConfigProvider>)
}

describe('StandardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    standardApi.listStandards.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 20,
      items: [{ id: 1, standard_no: 'GB 50016-2014', standard_type: '国家标准', standard_prefix: 'GB', create_time: null, update_time: null, create_user: '', update_user: '' }],
    })
  })

  it('loads standards and sends server-side keyword query', async () => {
    renderPage()
    expect(await screen.findByText('GB 50016-2014')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('按关键词搜索标准库'), { target: { value: '50016' } })
    fireEvent.click(screen.getByRole('button', { name: 'search' }))

    await waitFor(() => expect(standardApi.listStandards).toHaveBeenLastCalledWith({ keyword: '50016', page: 1, pageSize: 20 }))
  })

  it('shows a retryable business or HTTP error', async () => {
    standardApi.listStandards.mockRejectedValueOnce(new Error('网络不可用'))
    renderPage()
    expect(await screen.findByText('标准库加载失败')).toBeInTheDocument()
    expect(screen.getByText('网络不可用')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => expect(standardApi.listStandards).toHaveBeenCalledTimes(2))
  })
})
