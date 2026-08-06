import { Alert, Button, Card, Descriptions, Empty, Image, Select, Space, Spin, Table, Tabs, Tag, Typography, notification } from 'antd'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getTaskDetail } from '../api/drawingApi'
import { renderSafeMarkdown } from '../components/markdownRenderer'
import type { RecognitionTable, StandardMatch, TaskDetail } from '../types'
import { readTaskSessionMetadata } from '../taskMetadata'
import { resolveApiFileUrl } from '../../../shared/api/client'
import { formatDateTime, formatFileSize } from '../../../shared/format'
import { TaskStatusTag } from '../../../shared/taskStatus'
import styles from './TaskDetailPage.module.css'

type ResultView = 'standard-info' | 'layout' | 'content' | 'analysis'

interface AnalysisRow {
  key: string
  source: string
  extracted: string
  matched: string
  status: string
  suggestion: string
}

const display = (value: string | number | null | undefined) => value === '' || value == null ? '—' : String(value)
const standardColor = (status: string) => ({ 完全符合: 'success', 年份不一致: 'warning', 较为相似: 'processing', 不存在: 'error', 解析错误: 'error', 待识别: 'warning' }[status] || 'default')
const isRecord = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value)
const recordText = (record: Record<string, unknown> | undefined, ...keys: string[]) => {
  for (const key of keys) {
    const value = record?.[key]
    if (value != null && value !== '') return String(value)
  }
  return ''
}

const safeUploadFilename = (filename: string) => filename.split(/[\\/]/).pop()?.trim().replace(/[\\/:*?"<>|]+/g, '_') || 'upload.pdf'

function PdfPreview({ detail }: { detail: TaskDetail }) {
  const [fileIndex, setFileIndex] = useState(0)
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const fileName = detail.file_names[fileIndex] || detail.original_filename
  const serverUrl = useMemo(() => {
    if (!fileName || !detail.task_id) return ''
    const savedName = `${String(fileIndex + 1).padStart(3, '0')}_${safeUploadFilename(fileName)}`
    return resolveApiFileUrl(`uploads/${encodeURIComponent(detail.task_id)}/${encodeURIComponent(savedName)}`)
  }, [detail.task_id, fileIndex, fileName])

  useEffect(() => {
    setFileIndex(0)
  }, [detail.task_id])

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl = ''
    setPreviewUrl('')
    setPreviewError('')
    if (!serverUrl) {
      setPreviewError('未获得原始 PDF 文件信息')
      return () => controller.abort()
    }
    void fetch(serverUrl, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const buffer = await response.arrayBuffer()
        objectUrl = URL.createObjectURL(new Blob([buffer], { type: 'application/pdf' }))
        setPreviewUrl(objectUrl)
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setPreviewError('原始 PDF 暂时无法预览')
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [serverUrl])

  const fallbackImage = detail.annotated_images[0]
  return <div className={styles.previewBlock}>
    {detail.file_names.length > 1 && <Select className={styles.previewSelect} value={fileIndex} aria-label="选择原始图纸" onChange={setFileIndex}
      options={detail.file_names.map((name, index) => ({ value: index, label: name }))} />}
    <div className={styles.pdfFrame}>
      {previewUrl ? <iframe title={`原始图纸预览：${fileName}`} src={`${previewUrl}#page=1&view=FitH&toolbar=0`} />
        : previewError && fallbackImage ? <div className={styles.fallbackPreview}>
          <Image src={resolveApiFileUrl(fallbackImage.image_url || fallbackImage.image_path)} alt="版面识别图预览" preview={false} />
          <span>原始 PDF 暂不可用，当前显示版面识别图</span>
        </div>
          : previewError ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={previewError} />
            : <div className={styles.previewLoading}><Spin size="small" /><span>正在加载原始图纸…</span></div>}
    </div>
    <div className={styles.previewFooter}><Typography.Text ellipsis title={fileName}>{display(fileName)}</Typography.Text>{serverUrl && <Button type="link" size="small" href={serverUrl} target="_blank">打开原始 PDF</Button>}</div>
  </div>
}

function DrawingSummary({ detail }: { detail: TaskDetail }) {
  const metadata = useMemo(() => readTaskSessionMetadata(detail.task_id), [detail.task_id])
  const raw = detail.raw_json
  const primaryFile = detail.file_names[0] || detail.original_filename
  return <Card className={styles.summaryCard}>
    {detail.error_message && <Alert className={styles.taskAlert} type="error" showIcon message="任务处理异常" description={detail.error_message} />}
    <div className={styles.summaryGrid}>
      <section aria-labelledby="drawing-preview-title">
        <h2 id="drawing-preview-title" className={styles.sectionTitle}>图纸原始预览</h2>
        <PdfPreview detail={detail} />
      </section>
      <section aria-labelledby="drawing-info-title">
        <div className={styles.infoHeading}><h2 id="drawing-info-title" className={styles.sectionTitle}>图纸基础信息</h2><TaskStatusTag status={detail.status} /></div>
        <Descriptions className={styles.basicInfo} column={2} size="small" colon={false}>
          <Descriptions.Item label="任务名称">{display(metadata?.taskName || detail.task_name)}</Descriptions.Item>
          <Descriptions.Item label="图纸名称">{display(primaryFile)}</Descriptions.Item>
          <Descriptions.Item label="专业分类">{display(metadata?.professional || recordText(raw, 'professional', 'professional_type'))}</Descriptions.Item>
          <Descriptions.Item label="设备分类">{display(metadata?.equipment || recordText(raw, 'equipment', 'equipment_type'))}</Descriptions.Item>
          <Descriptions.Item label="图纸类型">{display(metadata?.drawingType || recordText(raw, 'drawing_type'))}</Descriptions.Item>
          <Descriptions.Item label="识别任务类型">{display(metadata?.recognitionTaskType || recordText(raw, 'recognition_task_type'))}</Descriptions.Item>
          <Descriptions.Item label="文件数量">{detail.pdf_count}</Descriptions.Item>
          <Descriptions.Item label="页数">{detail.page_count}</Descriptions.Item>
          <Descriptions.Item label="文件大小">{formatFileSize(detail.file_size)}</Descriptions.Item>
          <Descriptions.Item label="完成时间">{formatDateTime(detail.completed_at)}</Descriptions.Item>
          <Descriptions.Item label="备注说明" span={2}>{display(metadata?.remark || detail.description)}</Descriptions.Item>
        </Descriptions>
      </section>
    </div>
  </Card>
}

function ResultSummary({ active, detail }: { active: ResultView; detail: TaskDetail }) {
  const inconsistent = detail.year_mismatch_count + detail.not_found_count
  const manual = detail.similar_count + Math.max(0, detail.standard_count - detail.exact_match_count - inconsistent - detail.similar_count)
  if (active === 'layout') return <div className={styles.contextLine}><b>当前标签：图纸版面识别结果</b><span>展示后端已返回的版面定位标注图，共 {detail.annotated_images.length} 张。</span></div>
  if (active === 'content') return <div className={styles.contextLine}><b>当前标签：图纸内容解析结果</b><span>左侧为表格裁剪图，右侧 Markdown 可在本页临时编辑，共 {detail.tables.length} 项。</span></div>
  return <div className={styles.reviewSummary}>
    <b>{active === 'analysis' ? '标准匹配分析统计' : '审查结果统计汇总'}</b>
    <span><i className={styles.exactDot} />审查一致 <strong>{detail.exact_match_count}</strong> 条</span>
    <span><i className={styles.mismatchDot} />审查不一致 <strong>{inconsistent}</strong> 条</span>
    <span><i className={styles.manualDot} />待人工审核 <strong>{manual}</strong> 条</span>
  </div>
}

function StandardsInformation({ standards }: { standards: StandardMatch[] }) {
  return <section className={styles.resultSection} aria-labelledby="standard-list-title">
    <h2 id="standard-list-title" className={styles.resultTitle}>标准对比明细列表</h2>
    <Table<StandardMatch> rowKey={(item) => `${item.pdf_name}-${item.source_table}-${item.standard_no}-${item.matched_standard}`} pagination={false} size="middle" scroll={{ x: 900 }} dataSource={standards}
      locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标准信息审查结果" /> }} columns={[
        { title: '图纸提取标准信息', dataIndex: 'standard_no', width: 220, render: display },
        { title: '标准库标准信息', dataIndex: 'matched_standard', width: 220, render: display },
        { title: '比对差异', key: 'difference', render: (_, item) => display(item.suggestion || item.status || item.result_type) },
        { title: '判断建议', key: 'status', width: 150, render: (_, item) => { const status = item.status || item.result_type; return <Tag color={standardColor(status)}>{display(status)}</Tag> } },
      ]} />
  </section>
}

function LayoutRecognition({ detail }: { detail: TaskDetail }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  useEffect(() => setSelectedIndex(0), [detail.annotated_images])
  const selected = detail.annotated_images[selectedIndex]
  if (!selected) return <div className={styles.resultEmpty}><Empty description="暂无图纸版面识别结果" /></div>
  return <section className={styles.resultSection} aria-labelledby="layout-result-title">
    <div className={styles.resultHeading}><h2 id="layout-result-title" className={styles.resultTitle}>图纸版面识别明细</h2>
      <Select value={selectedIndex} className={styles.resultSelect} aria-label="选择版面识别图" onChange={setSelectedIndex} options={detail.annotated_images.map((item, index) => ({ value: index, label: `${display(item.pdf_name)} · 第 ${item.page || '—'} 页` }))} /></div>
    <div className={styles.annotatedCanvas}><Image src={resolveApiFileUrl(selected.image_url || selected.image_path)} alt={`版面识别图 ${selectedIndex + 1}`} /></div>
  </section>
}

interface VisualMarkdownEditorProps {
  value: string
  onChange: (value: string) => void
}

function insertPlainText(text: string) {
  const selection = window.getSelection()
  if (!selection?.rangeCount) return
  const range = selection.getRangeAt(0)
  range.deleteContents()
  const lines = text.split(/\r?\n/)
  const fragment = document.createDocumentFragment()
  lines.forEach((line, index) => {
    if (index > 0) fragment.append(document.createElement('br'))
    fragment.append(document.createTextNode(line))
  })
  const lastNode = fragment.lastChild
  range.insertNode(fragment)
  if (lastNode) range.setStartAfter(lastNode)
  range.collapse(true)
  selection.removeAllRanges()
  selection.addRange(range)
}

function VisualMarkdownEditor({ value, onChange }: VisualMarkdownEditorProps) {
  return <div
    className={styles.markdownVisualEditor}
    role="textbox"
    aria-label="Markdown 解析结果编辑区"
    aria-multiline="true"
    contentEditable
    suppressContentEditableWarning
    spellCheck={false}
    dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(value) }}
    onInput={(event) => onChange(event.currentTarget.innerHTML)}
    onBlur={(event) => onChange(renderSafeMarkdown(event.currentTarget.innerHTML))}
    onPaste={(event) => {
      event.preventDefault()
      insertPlainText(event.clipboardData.getData('text/plain'))
    }}
  />
}

interface ContentRecognitionProps {
  tables: RecognitionTable[]
  drafts: Record<string, string>
  onDraftChange: (key: string, value: string) => void
}

const firstNonBlankMarkdown = (...values: Array<string | null | undefined>) => values.find((value) => value?.trim()) || ''

function resolveMarkdownFileUrl(table: RecognitionTable): string {
  if (table.markdown_url?.trim()) return resolveApiFileUrl(table.markdown_url)
  const normalizedPath = String(table.markdown_path || '').trim().replace(/\\/g, '/')
  if (!normalizedPath) return ''
  if (/^markdown\//i.test(normalizedPath)) return resolveApiFileUrl(normalizedPath)
  const markerIndex = normalizedPath.toLowerCase().lastIndexOf('/markdown/')
  return markerIndex >= 0 ? resolveApiFileUrl(normalizedPath.slice(markerIndex + 1)) : ''
}

function ContentRecognition({ tables, drafts, onDraftChange }: ContentRecognitionProps) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [editorRevision, setEditorRevision] = useState(0)
  const [loadedMarkdown, setLoadedMarkdown] = useState<Record<string, string>>({})
  const [loadingKey, setLoadingKey] = useState('')
  const [loadErrorKey, setLoadErrorKey] = useState('')
  useEffect(() => setSelectedIndex(0), [tables])
  const table = tables[selectedIndex]
  const draftKey = table ? `${table.pdf_name}-${table.page}-${table.table_index}` : ''
  const inlineMarkdown = table ? firstNonBlankMarkdown(table.raw_markdown_content, table.markdown_content, table.highlighted_markdown_content) : ''
  const markdownFileUrl = table ? resolveMarkdownFileUrl(table) : ''
  const fileMarkdown = draftKey ? loadedMarkdown[draftKey] || '' : ''
  const sourceMarkdown = firstNonBlankMarkdown(inlineMarkdown, fileMarkdown)

  useEffect(() => {
    if (!draftKey || inlineMarkdown || !markdownFileUrl || fileMarkdown) return
    const controller = new AbortController()
    setLoadingKey(draftKey)
    setLoadErrorKey('')
    void fetch(markdownFileUrl, { signal: controller.signal, headers: { Accept: 'text/markdown, text/plain, */*' } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const content = await response.text()
        if (!content.trim()) throw new Error('Markdown 文件内容为空')
        setLoadedMarkdown((current) => ({ ...current, [draftKey]: content }))
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setLoadErrorKey(draftKey)
      })
      .finally(() => setLoadingKey((current) => current === draftKey ? '' : current))
    return () => controller.abort()
  }, [draftKey, fileMarkdown, inlineMarkdown, markdownFileUrl])

  if (!table) return <div className={styles.resultEmpty}><Empty description="暂无图纸内容解析结果" /></div>
  const hasDraft = Object.prototype.hasOwnProperty.call(drafts, draftKey)
  const markdown = hasDraft ? drafts[draftKey] : sourceMarkdown
  return <section className={styles.resultSection} aria-labelledby="content-result-title">
    <div className={styles.resultHeading}><h2 id="content-result-title" className={styles.resultTitle}>图纸内容解析明细</h2>
      <Select value={selectedIndex} className={styles.resultSelect} aria-label="选择识别表格" onChange={setSelectedIndex} options={tables.map((item, index) => ({ value: index, label: `${display(item.display_name) || `表格 ${item.table_index}`} · ${display(item.pdf_name)} 第 ${item.page || '—'} 页` }))} /></div>
    <div className={styles.contentSplit}>
      <div className={styles.contentPane}><h3>表格图片</h3>{table.image_url || table.image_path ? <Image src={resolveApiFileUrl(table.image_url || table.image_path)} alt="识别表格裁剪图" /> : <Empty description="裁剪图地址缺失" />}</div>
      <div className={styles.contentPane}><div className={styles.editorHeading}><h3>Markdown 解析结果（可编辑）</h3><Button type="link" size="small" disabled={!sourceMarkdown} onClick={() => { onDraftChange(draftKey, sourceMarkdown); setEditorRevision((current) => current + 1) }}>恢复识别结果</Button></div>
        {hasDraft || markdown
          ? <><VisualMarkdownEditor key={`${draftKey}-${editorRevision}`} value={markdown} onChange={(value) => onDraftChange(draftKey, value)} />
            <Typography.Text type="secondary" className={styles.draftNote}>可直接点击表格单元格或文字修改；编辑仅保留在当前页面，不会回写服务端。</Typography.Text></>
          : <div className={styles.markdownLoadState}>{loadingKey === draftKey ? <><Spin size="small" /><span>正在加载 Markdown 内容…</span></>
            : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={loadErrorKey === draftKey ? 'Markdown 内容加载失败，请刷新后重试' : '后端未返回该表格的 Markdown 内容'} />}</div>}
      </div>
    </div>
  </section>
}

function toAnalysisRows(detail: TaskDetail): AnalysisRow[] {
  const rawResults = Array.isArray(detail.overall_standard_compare.results) ? detail.overall_standard_compare.results : []
  if (rawResults.length) return rawResults.map((item, index) => {
    const row = isRecord(item) ? item : {}
    const extracted = isRecord(row.extracted) ? row.extracted : undefined
    const matched = isRecord(row.matched_library_entry) ? row.matched_library_entry : undefined
    return {
      key: `overall-${index}`,
      source: recordText(row, 'pdf_name', 'source_table') || '全部图纸',
      extracted: recordText(extracted, 'original') || recordText(row, 'standard_no', 'original_text'),
      matched: recordText(matched, 'original') || recordText(row, 'matched_standard', 'matched_standard_no') || '未匹配',
      status: recordText(row, 'status', 'result_type', 'match_status'),
      suggestion: recordText(row, 'message', 'suggestion'),
    }
  })
  return detail.standards.map((item, index) => ({ key: `standard-${index}`, source: item.pdf_name || item.source_table, extracted: item.standard_no, matched: item.matched_standard, status: item.status || item.result_type, suggestion: item.suggestion }))
}

function StandardAnalysis({ detail }: { detail: TaskDetail }) {
  const rows = useMemo(() => toAnalysisRows(detail), [detail])
  return <section className={styles.resultSection} aria-labelledby="analysis-result-title">
    <h2 id="analysis-result-title" className={styles.resultTitle}>标准匹配分析明细</h2>
    <Table<AnalysisRow> rowKey="key" pagination={false} size="middle" scroll={{ x: 980 }} dataSource={rows} locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标准匹配分析结果" /> }} columns={[
      { title: '图纸来源', dataIndex: 'source', width: 180, render: display },
      { title: '图纸识别结果', dataIndex: 'extracted', width: 210, render: display },
      { title: 'GB 标准识别结果', dataIndex: 'matched', width: 220, render: display },
      { title: '比对结果', dataIndex: 'status', width: 140, render: (status: string) => <Tag color={standardColor(status)}>{display(status)}</Tag> },
      { title: '判定建议', dataIndex: 'suggestion', render: display },
    ]} />
  </section>
}

interface ResultPanelProps {
  active: ResultView
  detail: TaskDetail
  contentDrafts: Record<string, string>
  onContentDraftChange: (key: string, value: string) => void
}

function ResultPanel({ active, detail, contentDrafts, onContentDraftChange }: ResultPanelProps) {
  if (active === 'layout') return <LayoutRecognition detail={detail} />
  if (active === 'content') return <ContentRecognition tables={detail.tables} drafts={contentDrafts} onDraftChange={onContentDraftChange} />
  if (active === 'analysis') return <StandardAnalysis detail={detail} />
  return <StandardsInformation standards={detail.standards} />
}

const tabItems = [
  { key: 'standard-info', label: '图纸标准信息审查', children: null },
  { key: 'layout', label: '图纸版面识别结果', children: null },
  { key: 'content', label: '图纸内容解析结果', children: null },
  { key: 'analysis', label: '标准匹配分析结果', children: null },
]

export function TaskDetailPage() {
  const { taskId = '' } = useParams()
  const [notificationApi, notificationContext] = notification.useNotification()
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [active, setActive] = useState<ResultView>('standard-info')
  const contentDrafts = useRef<Record<string, string>>({})
  useEffect(() => { contentDrafts.current = {} }, [taskId])
  const updateContentDraft = useCallback((key: string, value: string) => {
    contentDrafts.current[key] = value
  }, [])
  const load = useCallback(async () => {
    if (!taskId) { setError('任务编号缺失'); setLoading(false); return }
    setLoading(true); setError('')
    try { setDetail(await getTaskDetail(taskId)) } catch (reason) {
      setDetail(null)
      const errorMessage = reason instanceof Error ? reason.message : '任务详情加载失败'
      setError(errorMessage)
      notificationApi.error({ key: 'task-detail-data-load-error', message: '数据加载失败', description: errorMessage, placement: 'topRight' })
    } finally { setLoading(false) }
  }, [notificationApi, taskId])
  useEffect(() => { void load() }, [load])

  return <main className="page-container">
    {notificationContext}
    <div className="page-header"><div><h1 className="page-title">任务详情</h1><p className="page-description">{detail?.task_id || taskId || '—'}</p></div>{detail && <TaskStatusTag status={detail.status} />}</div>
    {detail ? <Space direction="vertical" size={16} className={styles.fullWidth}>
      <DrawingSummary detail={detail} />
      <Card className={styles.tabCard}>
        <Tabs className={styles.resultTabs} activeKey={active} onChange={(key) => setActive(key as ResultView)} items={tabItems} />
        <ResultSummary active={active} detail={detail} />
      </Card>
      <Card className={styles.resultCard}><ResultPanel active={active} detail={detail} contentDrafts={contentDrafts.current} onContentDraftChange={updateContentDraft} /></Card>
    </Space> : <Space direction="vertical" size={16} className={styles.fullWidth}>
      <Card className={styles.tabCard}><Tabs className={styles.resultTabs} activeKey={active} onChange={(key) => setActive(key as ResultView)} items={tabItems} /></Card>
      <Card className={styles.resultCard}>{loading ? <div className={styles.state}><Spin /><span>正在加载任务详情…</span></div> : <Empty description={error ? '任务数据暂不可用' : '未找到任务详情'} image={Empty.PRESENTED_IMAGE_SIMPLE}>{error && <Button size="small" onClick={() => void load()}>重新加载</Button>}</Empty>}</Card>
    </Space>}
  </main>
}
