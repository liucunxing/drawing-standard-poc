import { describe, expect, it } from 'vitest'
import { normalizeTask } from './drawingApi'

describe('normalizeTask status compatibility', () => {
  it('preserves unknown status text and does not treat a missing status as pending', () => {
    expect(normalizeTask({ task_id: 'T-1', status: 'queued-by-new-backend' } as never).status).toBe('queued-by-new-backend')
    expect(normalizeTask({ task_id: 'T-2' }).status).toBeNull()
  })

  it('normalizes numeric status strings to the current numeric contract', () => {
    expect(normalizeTask({ task_id: 'T-3', status: '2' } as never).status).toBe(2)
  })
})
