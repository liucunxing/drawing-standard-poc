import { HistoryOutlined, PlusOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons'
import { Button, Card, Empty, Modal, Table, Typography, notification } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listTasks } from '../api/drawingApi'
import type { TaskSummary } from '../types'
import { formatDateTime } from '../../../shared/format'
import { TaskStatusTag } from '../../../shared/taskStatus'
import styles from './DashboardPage.module.css'

interface DashboardMetrics {
  recent: number
  processing: number
  completed: number
  failed: number
}

function metricsFor(tasks: TaskSummary[]): DashboardMetrics {
  return {
    recent: tasks.length,
    processing: tasks.filter((task) => task.status === 1).length,
    completed: tasks.filter((task) => task.status === 2).length,
    failed: tasks.filter((task) => task.status === 3).length,
  }
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [notificationApi, notificationContext] = notification.useNotification()
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rulesModalOpen, setRulesModalOpen] = useState(false)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setTasks(await listTasks(100))
    } catch (reason) {
      setTasks([])
      const errorMessage = reason instanceof Error ? reason.message : '近期任务加载失败，请稍后重试。'
      setError(errorMessage)
      notificationApi.error({
        key: 'dashboard-data-load-error',
        message: '数据加载失败',
        description: errorMessage,
        placement: 'topRight',
      })
    } finally {
      setLoading(false)
    }
  }, [notificationApi])

  useEffect(() => {
    void loadTasks()
  }, [loadTasks])

  const metrics = metricsFor(tasks)
  const columns: ColumnsType<TaskSummary> = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      ellipsis: true,
      render: (value: string, task) => (
        <Button type="link" className={styles.taskLink} onClick={() => navigate(`/tasks/${task.task_id}`)}>
          {value || '未命名任务'}
        </Button>
      ),
    },
    { title: '文件数', dataIndex: 'pdf_count', key: 'pdf_count', width: 90, align: 'right' },
    { title: '状态', dataIndex: 'status', key: 'status', width: 110, render: (status) => <TaskStatusTag status={status} /> },
    {
      title: '当前进度',
      key: 'progress',
      width: 180,
      render: (_, task) => task.current_step || `${task.progress}%`,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (value: string | null) => formatDateTime(value),
    },
  ]

  return (
    <main className="page-container">
      {notificationContext}
      <div className="page-header">
        <div>
          <h1 className="page-title">数据统计总览</h1>
          <p className="page-description">查看图纸审查任务统计、快捷入口及最近任务。</p>
        </div>
      </div>

      <section className={styles.metrics} aria-label="数据统计总览">
        <MetricCard label="所有任务数量" value={metrics.recent} />
        <MetricCard label="进行中任务数量" value={metrics.processing} tone="blue" />
        <MetricCard label="审核确认任务数量" value={metrics.completed} tone="green" />
        <MetricCard label="报错任务数量" value={metrics.failed} tone="red" />
      </section>

      <Card className={styles.quickActionsCard} title="快捷功能入口" variant="outlined">
        <div className={styles.quickActions}>
          <button
            type="button"
            className={`${styles.quickActionButton} ${styles.primaryAction}`}
            onClick={() => navigate('/tasks/new')}
          >
            <PlusOutlined className={styles.quickActionIcon} />
            <span>创建识别任务</span>
          </button>
          <button
            type="button"
            className={styles.quickActionButton}
            disabled={loading}
            onClick={() => void loadTasks()}
          >
            <HistoryOutlined className={styles.quickActionIcon} />
            <span>查询历史识别任务</span>
          </button>
          <button
            type="button"
            className={styles.quickActionButton}
            onClick={() => setRulesModalOpen(true)}
          >
            <SettingOutlined className={styles.quickActionIcon} />
            <span>配置识别规则</span>
          </button>
        </div>
      </Card>

      <Card className={styles.taskCard} title="最近任务" variant="outlined">
        <Table<TaskSummary>
          rowKey={(task) => task.task_id}
          columns={columns}
          dataSource={tasks.slice(0, 8)}
          pagination={false}
          loading={loading}
          size="middle"
          scroll={{ x: 760 }}
          locale={{
            emptyText: (
              <Empty
                description={error ? '近期任务数据暂不可用' : '暂无近期任务'}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              >
                {error && <Button size="small" icon={<ReloadOutlined />} onClick={() => void loadTasks()}>重新加载</Button>}
              </Empty>
            ),
          }}
        />
      </Card>

      <Modal
        title="配置识别规则"
        open={rulesModalOpen}
        onCancel={() => setRulesModalOpen(false)}
        footer={<Button type="primary" onClick={() => setRulesModalOpen(false)}>我知道了</Button>}
      >
        <p className={styles.rulesUnavailable}>暂不可配置识别规则</p>
      </Modal>
    </main>
  )
}

function MetricCard({ label, value, tone = 'neutral' }: { label: string; value: number; tone?: 'neutral' | 'blue' | 'green' | 'red' }) {
  return (
    <Card className={`${styles.metricCard} ${styles[tone]}`} variant="outlined">
      <Typography.Text className={styles.metricLabel}>{label}</Typography.Text>
      <Typography.Text className={styles.metricValue}>{value}</Typography.Text>
    </Card>
  )
}
