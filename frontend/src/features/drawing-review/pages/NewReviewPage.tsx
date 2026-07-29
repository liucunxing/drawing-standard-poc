import { DeleteOutlined, InboxOutlined } from '@ant-design/icons'
import { Alert, Button, List, Progress, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect } from 'react'
import { useBeforeUnload, useBlocker, useNavigate } from 'react-router-dom'
import { formatFileSize } from '../../../shared/format'
import { useUploadStore } from '../store/uploadStore'
import styles from './NewReviewPage.module.css'

const running = (status: string) => status === 'uploading' || status === 'processing'

export function NewReviewPage() {
  const navigate = useNavigate()
  const { files, status, taskId, currentFileIndex, currentFileName, errorMessage, addFiles, removeFile, clearFiles, resetRun, run } = useUploadStore()
  const isRunning = running(status)
  const blocker = useBlocker(isRunning)
  const [messageApi, messageContext] = message.useMessage()

  useBeforeUnload((event) => {
    if (isRunning) {
      event.preventDefault()
      event.returnValue = ''
    }
  })

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm('当前任务仍在处理中，离开页面会中断后续文件处理。确定离开吗？')) blocker.proceed()
    else blocker.reset()
  }, [blocker])

  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      messageApi.error('仅支持 PDF 文件')
      return Upload.LIST_IGNORE
    }
    addFiles([file])
    return false
  }

  const start = async () => {
    const completedTaskId = await run()
    if (completedTaskId) {
      messageApi.success('全部 PDF 已处理完成')
      navigate(`/tasks/${encodeURIComponent(completedTaskId)}`)
    }
  }
  const completedFiles = status === 'completed' ? files.length : Math.max(0, currentFileIndex - 1)
  const progress = files.length ? Math.round((completedFiles / files.length) * 100) : 0

  return <main className="page-container">
    {messageContext}
    <div className="page-header"><div><h1 className="page-title">新建审查</h1><p className="page-description">选择一个或多个图纸 PDF，系统将按选择顺序逐个进行识别与标准审查。</p></div></div>
    <div className={styles.content}>
      <section className={styles.panel} aria-label="待审查文件">
        <p className={styles.hint}>仅支持 PDF 格式。本次不设置额外任务信息。</p>
        <Upload.Dragger accept="application/pdf,.pdf" multiple showUploadList={false} beforeUpload={beforeUpload} disabled={isRunning}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p><p className="ant-upload-text">点击或拖拽 PDF 到此区域</p><p className="ant-upload-hint">可一次选择多个文件，将按列表顺序处理</p>
        </Upload.Dragger>
        <List className={styles.fileList} bordered dataSource={files} locale={{ emptyText: '暂未选择 PDF 文件' }} renderItem={(file, index) => <List.Item actions={[<Button key="remove" type="link" danger size="small" disabled={isRunning} onClick={() => removeFile(index)} aria-label={`删除 ${file.name}`}><DeleteOutlined /> 删除</Button>]}><div className={styles.fileName}>{index + 1}. {file.name} <Typography.Text type="secondary">（{formatFileSize(file.size)}）</Typography.Text></div></List.Item>} />
        {status !== 'idle' && <div className={styles.progress}><div className={styles.progressText}><span>{status === 'uploading' ? '正在创建任务…' : status === 'completed' ? '处理完成' : status === 'failed' ? '处理已停止' : `正在处理第 ${currentFileIndex}/${files.length} 个文件`}</span><span>{currentFileName}</span></div><Progress percent={progress} status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'} /></div>}
        {status === 'failed' && <Alert className={styles.error} type="error" showIcon message="任务处理失败，后续文件未提交" description={errorMessage || '请查看已创建任务的已有结果，或重新创建任务。'} action={<span><Button size="small" onClick={() => taskId && navigate(`/tasks/${encodeURIComponent(taskId)}`)} disabled={!taskId}>查看已有结果</Button><Button size="small" type="link" onClick={resetRun}>重新创建任务</Button></span>} />}
        <div className={styles.actions}><Button onClick={clearFiles} disabled={isRunning || !files.length}>清空</Button><Button type="primary" onClick={start} loading={isRunning} disabled={!files.length || isRunning}>开始审查</Button></div>
      </section>
    </div>
  </main>
}
