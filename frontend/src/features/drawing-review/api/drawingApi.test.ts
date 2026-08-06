import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiRequestMock = vi.hoisted(() => vi.fn())

vi.mock('../../../shared/api/client', () => ({ apiRequest: apiRequestMock }))

import { normalizeRecognitionTable, normalizeTask, normalizeTaskDetail, uploadPdfs } from './drawingApi'

beforeEach(() => apiRequestMock.mockReset())

describe('normalizeTask status compatibility', () => {
  it('preserves unknown status text and does not treat a missing status as pending', () => {
    expect(normalizeTask({ task_id: 'T-1', status: 'queued-by-new-backend' } as never).status).toBe('queued-by-new-backend')
    expect(normalizeTask({ task_id: 'T-2' }).status).toBeNull()
  })

  it('normalizes numeric status strings to the current numeric contract', () => {
    expect(normalizeTask({ task_id: 'T-3', status: '2' } as never).status).toBe(2)
  })
})

describe('normalizeTaskDetail Markdown compatibility', () => {
  it('uses non-blank backend Markdown aliases instead of preserving an empty editor value', () => {
    const markdown = '<table><tr><td rowspan=1 colspan=15>管 口 表</td></tr><tr><td>N1</td></tr></table>'
    const detail = normalizeTaskDetail({
      task_id: 'T-MD',
      tables: [{
        table_index: 2,
        page_number: 1,
        source_image: 'table_blocks/T-MD/table_2.png',
        raw_markdown_content: '  \n',
        md_content: markdown,
        md_url: '/api/files/markdown/T-MD/table_2.md',
      }],
    } as never)

    expect(detail.tables[0]).toMatchObject({
      table_index: 2,
      page: 1,
      display_name: '表格2',
      image_path: 'table_blocks/T-MD/table_2.png',
      raw_markdown_content: markdown,
      markdown_content: markdown,
      markdown_url: '/api/files/markdown/T-MD/table_2.md',
    })
  })

  it('falls back across highlighted and Qwen content fields', () => {
    expect(normalizeRecognitionTable({ highlighted_markdown_content: '<table><tr><td>高亮结果</td></tr></table>' }).raw_markdown_content).toContain('高亮结果')
    expect(normalizeRecognitionTable({ qwen_fixed_md_content: '<table><tr><td>修复结果</td></tr></table>' }).raw_markdown_content).toContain('修复结果')
  })
})

describe('uploadPdfs metadata transport', () => {
  it('keeps repeated multipart files and sends trimmed task metadata as query parameters', async () => {
    const first = new File(['%PDF-1'], 'A.pdf', { type: 'application/pdf' })
    const second = new File(['%PDF-2'], 'B.pdf', { type: 'application/pdf' })
    apiRequestMock.mockResolvedValue({ task_id: 'task-1', file_names: ['A.pdf', 'B.pdf'] })

    await uploadPdfs(
      [first, second],
      '  装置图纸审查  ',
      '  人工备注\n未知专业-未知设备-未知类型-未知识别任务类型  ',
    )

    const request = apiRequestMock.mock.calls[0][0]
    expect(request.params).toEqual({
      task_name: '装置图纸审查',
      description: '人工备注\n未知专业-未知设备-未知类型-未知识别任务类型',
    })
    expect(request.data).toBeInstanceOf(FormData)
    expect(request.data.getAll('files')).toEqual([first, second])
  })

  it('omits metadata params when both values are blank', async () => {
    apiRequestMock.mockResolvedValue({ task_id: 'task-2', file_names: ['A.pdf'] })

    await uploadPdfs([new File(['%PDF'], 'A.pdf', { type: 'application/pdf' })], '  ', '  ')

    expect(apiRequestMock.mock.calls[0][0].params).toBeUndefined()
  })
})
