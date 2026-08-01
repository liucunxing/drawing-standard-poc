export interface NewReviewFormValues {
  taskName: string
  remark?: string
  professional: string
  equipment: string
  drawingType: string
  recognitionTaskType: string
}

const containsControlCharacter = (value: string) => Array.from(value).some((character) => {
  const code = character.charCodeAt(0)
  return code <= 31 || (code >= 127 && code <= 159)
})

export const validateTaskName = (value: unknown): string | null => {
  if (typeof value !== 'string' || !value.trim()) return '请填写任务名称'
  const normalized = value.trim()
  if (value.endsWith(' ') || normalized.endsWith('.')) return '任务名称不能以空格或点结尾'
  if (normalized.length > 48) return '任务名称长度应为 1-48 个字符'
  if (containsControlCharacter(normalized)) return '任务名称不能包含控制字符'
  if (/[<>:"/\\|?*]/.test(normalized) || normalized === '.' || normalized === '..') return '任务名称包含不支持的字符'
  return null
}

export const composeDescription = (values: Pick<NewReviewFormValues, 'remark' | 'professional' | 'equipment' | 'drawingType' | 'recognitionTaskType'>): string => {
  const configText = `${values.professional}-${values.equipment}-${values.drawingType}-${values.recognitionTaskType}`
  const trimmedRemark = values.remark?.trim()
  return trimmedRemark ? `${trimmedRemark}\n${configText}` : configText
}
