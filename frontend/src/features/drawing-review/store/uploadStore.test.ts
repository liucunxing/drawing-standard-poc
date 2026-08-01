import { beforeEach, describe, expect, it, vi } from 'vitest'
import { processSinglePdf, uploadPdfs } from '../api/drawingApi'
import { useUploadStore } from './uploadStore'

vi.mock('../api/drawingApi', () => ({ uploadPdfs: vi.fn(), processSinglePdf: vi.fn() }))

const file = (name: string) => new File(['pdf'], name, { type: 'application/pdf', lastModified: 1 })

describe('uploadStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useUploadStore.setState({ files: [], status: 'idle', taskId: null, currentFileIndex: 0, currentFileName: '', errorMessage: null })
  })

  it('forwards metadata once then processes selected files in order', async () => {
    const first = file('first.pdf')
    const second = file('second.pdf')
    vi.mocked(uploadPdfs).mockResolvedValue({
      task_id: 'task/a', filename: 'first.pdf', original_filename: 'first.pdf', file_path: '', file_size: 6, uploaded_at: '', pdf_count: 2,
      file_names: ['服务端一.pdf', '服务端二.pdf'], files: [],
    })
    vi.mocked(processSinglePdf).mockResolvedValue({} as never)
    useUploadStore.getState().addFiles([first, second])

    await expect(useUploadStore.getState().run('纯任务名', '说明\n配置')).resolves.toBe('task/a')

    expect(uploadPdfs).toHaveBeenCalledWith([first, second], '纯任务名', '说明\n配置')
    expect(processSinglePdf).toHaveBeenNthCalledWith(1, 'task/a', 1)
    expect(processSinglePdf).toHaveBeenNthCalledWith(2, 'task/a', 2)
    expect(useUploadStore.getState()).toMatchObject({ status: 'completed', currentFileIndex: 2, currentFileName: '服务端二.pdf' })
  })
})
