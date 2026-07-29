import { Alert, Button, Card, Descriptions, Empty, Image, List, Progress, Radio, Select, Space, Spin, Tabs, Tag } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getTaskDetail } from '../api/drawingApi'
import { SafeMarkdown } from '../components/SafeMarkdown'
import type { RecognitionTable, StandardMatch, TaskDetail } from '../types'
import { resolveApiFileUrl } from '../../../shared/api/client'
import { formatDateTime, formatFileSize, formatPercent } from '../../../shared/format'
import { TaskStatusTag } from '../../../shared/taskStatus'
import styles from './TaskDetailPage.module.css'

const display = (value: string | number | null | undefined) => value === '' || value == null ? '—' : String(value)
const standardColor = (status: string) => ({ 完全符合: 'success', 年份不一致: 'warning', 较为相似: 'processing', 不存在: 'error' }[status] || 'default')

function Overview({ detail }: { detail: TaskDetail }) {
  return <Space direction="vertical" size={16} className={styles.fullWidth}>
    {detail.error_message && <Alert type="error" showIcon message="任务处理异常" description={detail.error_message} />}
    <Card size="small" title="任务信息">
      <Descriptions column={3} size="small">
        <Descriptions.Item label="任务名称">{display(detail.task_name)}</Descriptions.Item>
        <Descriptions.Item label="任务状态"><TaskStatusTag status={detail.status} /></Descriptions.Item>
        <Descriptions.Item label="当前步骤">{display(detail.current_step)}</Descriptions.Item>
        <Descriptions.Item label="文件数量">{detail.pdf_count}</Descriptions.Item>
        <Descriptions.Item label="文件大小">{formatFileSize(detail.file_size)}</Descriptions.Item>
        <Descriptions.Item label="页数">{detail.page_count}</Descriptions.Item>
        <Descriptions.Item label="创建时间">{formatDateTime(detail.created_at)}</Descriptions.Item>
        <Descriptions.Item label="开始时间">{formatDateTime(detail.started_at)}</Descriptions.Item>
        <Descriptions.Item label="完成时间">{formatDateTime(detail.completed_at)}</Descriptions.Item>
      </Descriptions>
      <div className={styles.progressRow}><span>处理进度</span><Progress percent={formatPercent(detail.progress)} /></div>
    </Card>
    <Card size="small" title="处理统计">
      <div className={styles.counts}>
        <span>已处理 <b>{detail.processed_count}</b></span><span>识别表格 <b>{detail.table_count}</b></span>
        <span>标准比对 <b>{detail.standard_count}</b></span><span>完全符合 <b>{detail.exact_match_count}</b></span>
        <span>年份不一致 <b>{detail.year_mismatch_count}</b></span><span>较为相似 <b>{detail.similar_count}</b></span><span>不存在 <b>{detail.not_found_count}</b></span>
      </div>
    </Card>
    <Card size="small" title="文件列表">
      {detail.file_names.length ? <List size="small" dataSource={detail.file_names} renderItem={(name) => <List.Item>{name}</List.Item>} /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无文件信息" />}
    </Card>
  </Space>
}

function LayoutRecognition({ detail }: { detail: TaskDetail }) {
  return detail.annotated_images.length ? <div className={styles.imageGrid}>{detail.annotated_images.map((image, index) => (
    <Card size="small" key={`${image.image_path}-${index}`} title={`${display(image.pdf_name)} · 第 ${image.page || '—'} 页`}>
      {image.image_url || image.image_path
        ? <Image className={styles.previewImage} src={resolveApiFileUrl(image.image_url || image.image_path)} alt={`版面识别图 ${index + 1}`} />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="图片地址缺失" />}
    </Card>
  ))}</div> : <Empty description="暂无版面识别图" />
}

function ContentRecognition({ tables }: { tables: RecognitionTable[] }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [view, setView] = useState<'image' | 'raw' | 'highlighted'>('image')
  const table = tables[selectedIndex]
  useEffect(() => setSelectedIndex(0), [tables])
  if (!tables.length) return <Empty description="暂无内容识别结果" />
  return <Space direction="vertical" size={16} className={styles.fullWidth}>
    <Select value={selectedIndex} className={styles.tableSelect} aria-label="选择识别表格" onChange={setSelectedIndex}
      options={tables.map((item, index) => ({ value: index, label: `${display(item.display_name) || `表格 ${item.table_index}`} · ${display(item.pdf_name)} 第 ${item.page || '—'} 页` }))} />
    <Radio.Group value={view} onChange={(event) => setView(event.target.value)}>
      <Radio.Button value="image">裁剪图</Radio.Button><Radio.Button value="raw">原始 Markdown</Radio.Button><Radio.Button value="highlighted">高亮 Markdown</Radio.Button>
    </Radio.Group>
    <Card size="small" title={`${display(table.display_name) || `表格 ${table.table_index}`} · ${display(table.pdf_name)} 第 ${table.page || '—'} 页`}>
      {view === 'image' ? (table.image_url || table.image_path
        ? <Image className={styles.contentImage} src={resolveApiFileUrl(table.image_url || table.image_path)} alt="识别表格裁剪图" />
        : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="裁剪图地址缺失" />) :
        <SafeMarkdown content={view === 'raw' ? table.raw_markdown_content || table.markdown_content : table.highlighted_markdown_content || table.markdown_content} />}
    </Card>
  </Space>
}

function StandardsReview({ standards }: { standards: StandardMatch[] }) {
  const [filter, setFilter] = useState('all')
  const statuses = useMemo(() => Array.from(new Set(standards.map((item) => item.status || item.result_type).filter(Boolean))), [standards])
  const visible = filter === 'all' ? standards : standards.filter((item) => (item.status || item.result_type) === filter)
  if (!standards.length) return <Empty description="暂无标准审查结果" />
  return <Space direction="vertical" size={16} className={styles.fullWidth}>
    <Select value={filter} className={styles.filterSelect} aria-label="按审查结果筛选" onChange={setFilter} options={[{ value: 'all', label: '全部结果' }, ...statuses.map((status) => ({ value: status, label: status }))]} />
    {visible.length ? <List className={styles.standardsList} dataSource={visible} renderItem={(item) => <List.Item>
      <Descriptions column={3} size="small" className={styles.fullWidth}>
        <Descriptions.Item label="标准号">{display(item.standard_no)}</Descriptions.Item>
        <Descriptions.Item label="匹配标准">{display(item.matched_standard)}</Descriptions.Item>
        <Descriptions.Item label="审查结果"><Tag color={standardColor(item.status || item.result_type)}>{display(item.status || item.result_type)}</Tag></Descriptions.Item>
        <Descriptions.Item label="来源">{display(item.source_table)}</Descriptions.Item>
        <Descriptions.Item label="置信度">{item.confidence == null ? '—' : `${formatPercent(item.confidence <= 1 ? item.confidence * 100 : item.confidence)}%`}</Descriptions.Item>
        <Descriptions.Item label="建议">{display(item.suggestion)}</Descriptions.Item>
      </Descriptions>
    </List.Item>} /> : <Empty description="当前筛选下暂无结果" />}
  </Space>
}

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    if (!taskId) { setError('任务编号缺失'); setLoading(false); return }
    setLoading(true); setError('')
    try { setDetail(await getTaskDetail(taskId)) } catch (reason) { setError(reason instanceof Error ? reason.message : '任务详情加载失败') } finally { setLoading(false) }
  }, [taskId])
  useEffect(() => { void load() }, [load])
  if (loading) return <main className="page-container"><div className={styles.state}><Spin /><div className="muted-text">正在加载任务详情…</div></div></main>
  if (error) return <main className="page-container"><Alert type="error" showIcon message="任务详情加载失败" description={error} action={<Button size="small" onClick={() => void load()}>重试</Button>} /></main>
  if (!detail) return <main className="page-container"><Empty description="未找到任务详情" /></main>
  return <main className="page-container">
    <div className="page-header"><div><h1 className="page-title">任务详情</h1><p className="page-description">{detail.task_id}</p></div><TaskStatusTag status={detail.status} /></div>
    <Tabs items={[
      { key: 'overview', label: '任务概览', children: <Overview detail={detail} /> },
      { key: 'layout', label: '版面识别', children: <LayoutRecognition detail={detail} /> },
      { key: 'content', label: '内容识别', children: <ContentRecognition tables={detail.tables} /> },
      { key: 'standards', label: '标准审查', children: <StandardsReview standards={detail.standards} /> },
    ]} />
  </main>
}
