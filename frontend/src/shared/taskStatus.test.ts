import { describe, expect, it } from 'vitest'
import { getTaskStatusMeta } from './taskStatus'

describe('task status', () => {
  it('maps known and unknown statuses', () => {
    expect(getTaskStatusMeta(2).label).toBe('已完成')
    expect(getTaskStatusMeta(99).label).toBe('状态 99')
  })
})
