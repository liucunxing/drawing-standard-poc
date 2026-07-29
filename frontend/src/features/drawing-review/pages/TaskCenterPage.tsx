import { Alert, Button, DatePicker, Empty, Input, Pagination, Select, Spin, Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listTasks } from '../api/drawingApi'
import type { TaskSummary } from '../types'
import { TaskStatusTag } from '../../../shared/taskStatus'
import { formatDateTime, formatPercent } from '../../../shared/format'
import styles from './TaskCenterPage.module.css'

const PAGE_SIZE = 10
type StatusFilter = 'all' | '0' | '1' | '2' | '3' | 'unknown'

export function TaskCenterPage() {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [page, setPage] = useState(1)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setTasks(await listTasks(100)) }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : '任务列表加载失败') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void loadTasks() }, [loadTasks])
  const filtered = useMemo(() => tasks.filter((task) => {
    const text = `${task.task_name} ${task.original_filename} ${task.file_names.join(' ')}`.toLowerCase()
    const matchKeyword = !keyword.trim() || text.includes(keyword.trim().toLowerCase())
    const known = [0, 1, 2, 3].includes(task.status as number)
    const matchStatus = status === 'all' || (status === 'unknown' ? !known : task.status === Number(status))
    const taskDate = task.created_at ? dayjs(task.created_at) : null
    const matchDate = !dateRange || (!dateRange[0] && !dateRange[1]) || (!!taskDate && (!dateRange[0] || !taskDate.isBefore(dateRange[0].startOf('day'))) && (!dateRange[1] || !taskDate.isAfter(dateRange[1].endOf('day'))))
    return matchKeyword && matchStatus && matchDate
  }), [dateRange, keyword, status, tasks])
  useEffect(() => setPage(1), [keyword, status, dateRange])
  const columns: ColumnsType<TaskSummary> = [
    { title: '任务名称', dataIndex: 'task_name', render: (value, task) => <div><Button className={styles.taskName} type="link" onClick={() => navigate(`/tasks/${encodeURIComponent(task.task_id)}`)}>{value || '—'}</Button><div className={styles.subtle}>{task.file_names.join('、') || task.original_filename || '—'}</div></div> },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => <TaskStatusTag status={value} /> },
    { title: '进度', dataIndex: 'progress', width: 100, render: (value) => `${formatPercent(value)}%` },
    { title: '文件/页数', width: 110, render: (_, task) => `${task.pdf_count || 0} / ${task.page_count || 0}` },
    { title: '审查统计', width: 180, render: (_, task) => `符合 ${task.exact_match_count || 0}｜年份 ${task.year_mismatch_count || 0}｜相似 ${task.similar_count || 0}｜缺失 ${task.not_found_count || 0}` },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: formatDateTime },
    { title: '操作', width: 90, fixed: 'right', render: (_, task) => <Button type="link" onClick={() => navigate(`/tasks/${encodeURIComponent(task.task_id)}`)}>查看详情</Button> },
  ]
  const current = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  return <main className="page-container"><div className="page-header"><div><h1 className="page-title">任务中心</h1><p className="page-description">展示最近 100 条任务，可按名称、状态和创建日期筛选。</p></div></div><section className={styles.tableCard}>
    <div className={styles.filters}><Input allowClear placeholder="搜索任务或文件名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} style={{ width: 240 }} /><Select value={status} onChange={setStatus} style={{ width: 130 }} options={[{ value: 'all', label: '全部状态' }, { value: '0', label: '待处理' }, { value: '1', label: '处理中' }, { value: '2', label: '已完成' }, { value: '3', label: '异常' }, { value: 'unknown', label: '未知状态' }]} /><DatePicker.RangePicker value={dateRange} onChange={setDateRange} /></div>
    {error ? <Alert type="error" showIcon message="任务列表加载失败" description={error} action={<Button size="small" onClick={() => void loadTasks()}>重试</Button>} /> : loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /><div className="muted-text">正在加载任务…</div></div> : filtered.length ? <><Table rowKey={(task) => task.task_id} columns={columns} dataSource={current} pagination={false} size="middle" /><Pagination current={page} pageSize={PAGE_SIZE} total={filtered.length} showSizeChanger={false} onChange={setPage} style={{ margin: '16px 0', textAlign: 'right' }} /></> : <Empty description={tasks.length ? '没有符合筛选条件的任务' : '暂无任务'} image={Empty.PRESENTED_IMAGE_SIMPLE} />}
  </section></main>
}
