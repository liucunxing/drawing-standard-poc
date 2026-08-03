import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, DatePicker, Empty, Input, Pagination, Radio, Select, Table, notification } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs, { type Dayjs } from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listTasks } from '../api/drawingApi'
import type { TaskSummary } from '../types'
import { TaskStatusTag } from '../../../shared/taskStatus'
import { formatDateTime, formatPercent } from '../../../shared/format'
import styles from './TaskCenterPage.module.css'

const DEFAULT_PAGE_SIZE = 10
type StatusFilter = 'all' | '0' | '1' | '2' | '3' | 'unknown'

export function TaskCenterPage() {
  const navigate = useNavigate()
  const [notificationApi, notificationContext] = notification.useNotification()
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [appliedKeyword, setAppliedKeyword] = useState('')
  const [appliedStatus, setAppliedStatus] = useState<StatusFilter>('all')
  const [appliedDateRange, setAppliedDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setTasks(await listTasks(100)) }
    catch (requestError) {
      setTasks([])
      const errorMessage = requestError instanceof Error ? requestError.message : '任务列表加载失败'
      setError(errorMessage)
      notificationApi.error({ key: 'task-center-data-load-error', message: '数据加载失败', description: errorMessage, placement: 'topRight' })
    }
    finally { setLoading(false) }
  }, [notificationApi])
  useEffect(() => { void loadTasks() }, [loadTasks])
  const filtered = useMemo(() => tasks.filter((task) => {
    const text = `${task.task_name} ${task.original_filename} ${task.file_names.join(' ')}`.toLowerCase()
    const matchKeyword = !appliedKeyword.trim() || text.includes(appliedKeyword.trim().toLowerCase())
    const known = [0, 1, 2, 3].includes(task.status as number)
    const matchStatus = appliedStatus === 'all' || (appliedStatus === 'unknown' ? !known : task.status === Number(appliedStatus))
    const taskDate = task.created_at ? dayjs(task.created_at) : null
    const matchDate = !appliedDateRange || (!appliedDateRange[0] && !appliedDateRange[1]) || (!!taskDate && (!appliedDateRange[0] || !taskDate.isBefore(appliedDateRange[0].startOf('day'))) && (!appliedDateRange[1] || !taskDate.isAfter(appliedDateRange[1].endOf('day'))))
    return matchKeyword && matchStatus && matchDate
  }), [appliedDateRange, appliedKeyword, appliedStatus, tasks])

  const handleFilter = async () => {
    setAppliedKeyword(keyword)
    setAppliedStatus(status)
    setAppliedDateRange(dateRange)
    setPage(1)
    await loadTasks()
  }

  const handleReset = async () => {
    setKeyword('')
    setStatus('all')
    setDateRange(null)
    setAppliedKeyword('')
    setAppliedStatus('all')
    setAppliedDateRange(null)
    setPage(1)
    await loadTasks()
  }

  const columns: ColumnsType<TaskSummary> = [
    { title: '任务名称', dataIndex: 'task_name', render: (value, task) => <div><Button className={styles.taskName} type="link" onClick={() => navigate(`/tasks/${encodeURIComponent(task.task_id)}`)}>{value || '—'}</Button><div className={styles.subtle}>{task.file_names.join('、') || task.original_filename || '—'}</div></div> },
    { title: '状态', dataIndex: 'status', width: 100, render: (value) => <TaskStatusTag status={value} /> },
    { title: '进度', dataIndex: 'progress', width: 100, render: (value) => `${formatPercent(value)}%` },
    { title: '文件/页数', width: 110, render: (_, task) => `${task.pdf_count || 0} / ${task.page_count || 0}` },
    { title: '审查统计', width: 180, render: (_, task) => `符合 ${task.exact_match_count || 0}｜年份 ${task.year_mismatch_count || 0}｜相似 ${task.similar_count || 0}｜缺失 ${task.not_found_count || 0}` },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: formatDateTime },
    { title: '操作', width: 90, fixed: 'right', render: (_, task) => <Button type="link" onClick={() => navigate(`/tasks/${encodeURIComponent(task.task_id)}`)}>查看详情</Button> },
  ]
  const current = filtered.slice((page - 1) * pageSize, page * pageSize)

  return (
    <main className="page-container">
      {notificationContext}
      <div className="page-header">
        <div>
          <h1 className="page-title">任务中心</h1>
          <p className="page-description">设置文件名、状态和创建日期后，点击筛选查看对应任务。</p>
        </div>
      </div>

      <section className={styles.filterCard} aria-labelledby="task-filter-title">
        <h2 id="task-filter-title" className={styles.sectionTitle}>任务筛选条件</h2>
        <div className={styles.filters}>
          <div className={styles.filterField}>
            <label htmlFor="task-file-keyword">文件名</label>
            <Input id="task-file-keyword" allowClear placeholder="搜索任务或文件名称" value={keyword} onChange={(event) => setKeyword(event.target.value)} />
          </div>
          <div className={styles.filterField}>
            <label htmlFor="task-status-filter">状态</label>
            <Select
              id="task-status-filter"
              value={status}
              onChange={setStatus}
              options={[{ value: 'all', label: '全部状态' }, { value: '0', label: '待处理' }, { value: '1', label: '处理中' }, { value: '2', label: '已完成' }, { value: '3', label: '异常' }, { value: 'unknown', label: '未知状态' }]}
            />
          </div>
          <div className={styles.filterField}>
            <label>创建日期</label>
            <DatePicker.RangePicker value={dateRange} onChange={setDateRange} aria-label="创建日期范围" />
          </div>
        </div>
        <div className={styles.filterActions}>
          <Button type="primary" icon={<SearchOutlined />} loading={loading} onClick={() => void handleFilter()}>筛选</Button>
          <Button icon={<ReloadOutlined />} disabled={loading} onClick={() => void handleReset()}>重置</Button>
        </div>
      </section>

      <section className={styles.tableCard} aria-labelledby="task-list-title">
        <h2 id="task-list-title" className={styles.sectionTitle}>任务列表</h2>
        <Table
          rowKey={(task) => task.task_id}
          columns={columns}
          dataSource={current}
          pagination={false}
          loading={loading}
          bordered
          size="middle"
          scroll={{ x: 1040 }}
          locale={{ emptyText: <Empty description={error ? '任务数据暂不可用' : tasks.length ? '没有符合筛选条件的任务' : '暂无任务'} image={Empty.PRESENTED_IMAGE_SIMPLE}>{error && <Button size="small" icon={<ReloadOutlined />} onClick={() => void loadTasks()}>重新加载</Button>}</Empty> }}
        />
        <div className={styles.paginationBar}>
          <div className={styles.pageSummary}>
            <span>每页显示：</span>
            <div role="radiogroup" aria-label="每页显示条数">
              <Radio.Group
                size="small"
                value={pageSize}
                onChange={(event) => {
                  setPageSize(event.target.value as number)
                  setPage(1)
                }}
              >
                <Radio.Button value={10}>10</Radio.Button>
                <Radio.Button value={20}>20</Radio.Button>
                <Radio.Button value={50}>50</Radio.Button>
              </Radio.Group>
            </div>
            <span className={styles.totalCount}>共 {filtered.length} 条数据</span>
          </div>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={filtered.length}
            showSizeChanger={false}
            showQuickJumper={{ goButton: <Button size="small">跳转</Button> }}
            onChange={setPage}
          />
        </div>
      </section>
    </main>
  )
}
