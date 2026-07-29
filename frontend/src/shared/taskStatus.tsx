/* eslint-disable react-refresh/only-export-components */
import { Tag } from 'antd'
import type { TaskStatus } from '../features/drawing-review/types'

export interface TaskStatusMeta {
  label: string
  color: string
}

export function getTaskStatusMeta(status: TaskStatus): TaskStatusMeta {
  if (status == null || status === '') return { label: '—', color: 'default' }
  if (status === 0) return { label: '待处理', color: 'default' }
  if (status === 1) return { label: '处理中', color: 'processing' }
  if (status === 2) return { label: '已完成', color: 'success' }
  if (status === 3) return { label: '异常', color: 'error' }
  return { label: `状态 ${status}`, color: 'default' }
}

export function TaskStatusTag({ status }: { status: TaskStatus }) {
  const meta = getTaskStatusMeta(status)
  return <Tag color={meta.color}>{meta.label}</Tag>
}
