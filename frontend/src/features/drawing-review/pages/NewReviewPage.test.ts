import { describe, expect, it } from 'vitest'
import { composeDescription, validateTaskName } from './newReviewForm'

describe('new review form helpers', () => {
  it('validates the frozen task-name restrictions', () => {
    expect(validateTaskName('  检查任务')).toBeNull()
    expect(validateTaskName('.')).not.toBeNull()
    expect(validateTaskName('任务/名称')).toBe('任务名称包含不支持的字符')
    expect(validateTaskName('任务\u0001名称')).toBe('任务名称不能包含控制字符')
    expect(validateTaskName('任务名称.')).toBe('任务名称不能以空格或点结尾')
    expect(validateTaskName('a'.repeat(48))).toBeNull()
    expect(validateTaskName('a'.repeat(49))).toBe('任务名称长度应为 1-48 个字符')
    expect(validateTaskName('有效任务名称')).toBeNull()
  })

  it('composes the exact description without changing task name content', () => {
    expect(composeDescription({
      remark: '  补充说明  ',
      professional: '未知专业',
      equipment: '未知设备',
      drawingType: '未知类型',
      recognitionTaskType: '未知识别任务类型',
    })).toBe('补充说明\n未知专业-未知设备-未知类型-未知识别任务类型')
    expect(composeDescription({
      professional: '未知专业', equipment: '未知设备', drawingType: '未知类型', recognitionTaskType: '未知识别任务类型',
    })).toBe('未知专业-未知设备-未知类型-未知识别任务类型')
  })
})
