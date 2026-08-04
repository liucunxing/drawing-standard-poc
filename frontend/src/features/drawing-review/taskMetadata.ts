export interface TaskSessionMetadata {
  taskName: string
  remark: string
  professional: string
  equipment: string
  drawingType: string
  recognitionTaskType: string
}

const storageKey = (taskId: string) => `drawing-review:task-metadata:${taskId}`

export function saveTaskSessionMetadata(taskId: string, metadata: TaskSessionMetadata): void {
  if (typeof window === 'undefined' || !taskId) return
  try {
    window.sessionStorage.setItem(storageKey(taskId), JSON.stringify(metadata))
  } catch {
    // Session storage is a best-effort frontend compatibility layer only.
  }
}

export function readTaskSessionMetadata(taskId: string): TaskSessionMetadata | null {
  if (typeof window === 'undefined' || !taskId) return null
  try {
    const value = window.sessionStorage.getItem(storageKey(taskId))
    if (!value) return null
    const parsed = JSON.parse(value) as Partial<TaskSessionMetadata>
    return {
      taskName: String(parsed.taskName || ''),
      remark: String(parsed.remark || ''),
      professional: String(parsed.professional || ''),
      equipment: String(parsed.equipment || ''),
      drawingType: String(parsed.drawingType || ''),
      recognitionTaskType: String(parsed.recognitionTaskType || ''),
    }
  } catch {
    return null
  }
}
