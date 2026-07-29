import { describe, expect, it } from 'vitest'
import { ApiError, resolveApiFileUrl, unwrapEnvelope } from './client'

describe('API contract helpers', () => {
  it('returns data from a successful envelope', () => {
    expect(unwrapEnvelope({ code: 200, msg: 'ok', data: { value: 1 } })).toEqual({ value: 1 })
  })

  it('throws the backend business message when code is not 200', () => {
    expect(() => unwrapEnvelope({ code: 400, msg: '仅支持PDF文件', data: null })).toThrowError(ApiError)
    expect(() => unwrapEnvelope({ code: 400, msg: '仅支持PDF文件', data: null })).toThrow('仅支持PDF文件')
  })

  it('normalizes file paths through the API base', () => {
    expect(resolveApiFileUrl('files/task/image.png')).toBe('/api/files/task/image.png')
    expect(resolveApiFileUrl('/api/files/task/image.png')).toBe('/api/files/task/image.png')
    expect(resolveApiFileUrl('https://example.com/image.png')).toBe('https://example.com/image.png')
  })
})
