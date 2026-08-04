import { CheckOutlined, DeleteOutlined, InboxOutlined, RollbackOutlined, SyncOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input, List, Progress, Select, Typography, Upload, message } from 'antd'
import type { UploadProps } from 'antd'
import { useEffect } from 'react'
import { useBeforeUnload, useBlocker, useNavigate } from 'react-router-dom'
import { formatFileSize } from '../../../shared/format'
import { useUploadStore } from '../store/uploadStore'
import { composeDescription, type NewReviewFormValues, validateTaskName } from './newReviewForm'
import { saveTaskSessionMetadata } from '../taskMetadata'
import styles from './NewReviewPage.module.css'

const running = (status: string) => status === 'uploading' || status === 'processing'

const selectOptions = (label: string) => [{ value: label, label }]

export function NewReviewPage() {
  const navigate = useNavigate()
  const { files, status, taskId, currentFileIndex, currentFileName, errorMessage, addFiles, removeFile, clearFiles, resetRun, run } = useUploadStore()
  const isRunning = running(status)
  const blocker = useBlocker(isRunning)
  const [messageApi, messageContext] = message.useMessage()
  const [form] = Form.useForm<NewReviewFormValues>()

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
    let values: NewReviewFormValues
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    if (!files.length) {
      messageApi.error('请至少选择一个 PDF 文件')
      return
    }
    const completedTaskId = await run(values.taskName.trim(), composeDescription(values))
    if (completedTaskId) {
      saveTaskSessionMetadata(completedTaskId, {
        taskName: values.taskName.trim(),
        remark: values.remark?.trim() || '',
        professional: values.professional,
        equipment: values.equipment,
        drawingType: values.drawingType,
        recognitionTaskType: values.recognitionTaskType,
      })
      messageApi.success('全部 PDF 已处理完成')
      clearFiles()
      resetRun()
      navigate(`/tasks/${encodeURIComponent(completedTaskId)}`)
    }
  }

  const resetForm = () => {
    form.resetFields()
    clearFiles()
    resetRun()
  }
  const completedFiles = status === 'completed' ? files.length : Math.max(0, currentFileIndex - 1)
  const progress = files.length ? Math.round((completedFiles / files.length) * 100) : 0

  return <main className="page-container">
    {messageContext}
    <div className="page-header"><div><h1 className="page-title">新建审查</h1><p className="page-description">选择一个或多个图纸 PDF，系统将按选择顺序逐个进行识别与标准审查。</p></div></div>
    <div className={styles.content}>
      <Form form={form} component={false} layout="vertical" requiredMark="optional" disabled={isRunning}>
        <section className={styles.panel} aria-labelledby="task-info-title">
          <h2 id="task-info-title" className={styles.panelTitle}>任务信息</h2>
          <Form.Item label="任务名称" name="taskName" rules={[{ validator: (_, value) => {
            const error = validateTaskName(value)
            return error ? Promise.reject(new Error(error)) : Promise.resolve()
          } }]} required>
            <Input maxLength={48} placeholder="填写任务名称" />
          </Form.Item>
          <Form.Item label="备注说明" name="remark" rules={[{ validator: (_, value) => {
            if (typeof value === 'string' && value.trim().length > 200) return Promise.reject(new Error('备注说明最多 200 个字符'))
            return Promise.resolve()
          } }]}>
            <Input.TextArea maxLength={220} rows={3} placeholder="请输入备注说明" />
          </Form.Item>
        </section>

        <section className={styles.panel} aria-labelledby="recognition-config-title">
          <h2 id="recognition-config-title" className={styles.panelTitle}>图纸识别配置信息</h2>
          <div className={styles.configGrid}>
            <Form.Item label="专业分类" name="professional" rules={[{ required: true, message: '请选择专业分类' }]}><Select placeholder="请选择专业分类" options={selectOptions('未知专业')} /></Form.Item>
            <Form.Item label="设备分类" name="equipment" rules={[{ required: true, message: '请选择设备分类' }]}><Select placeholder="请选择设备分类" options={selectOptions('未知设备')} /></Form.Item>
            <Form.Item label="图纸类型" name="drawingType" rules={[{ required: true, message: '请选择图纸类型' }]}><Select placeholder="请选择图纸类型" options={selectOptions('未知类型')} /></Form.Item>
            <Form.Item label="识别任务类型" name="recognitionTaskType" rules={[{ required: true, message: '请选择识别任务类型' }]}><Select placeholder="请选择识别任务类型" options={selectOptions('未知识别任务类型')} /></Form.Item>
          </div>
        </section>
      </Form>

      <section className={styles.panel} aria-labelledby="upload-title">
        <h2 id="upload-title" className={styles.panelTitle}>上传图纸文件</h2>
        <p className={styles.hint}>仅支持 PDF 格式。可一次选择多个文件，系统将按列表顺序处理。</p>
        <Upload.Dragger className={styles.uploadDragger} accept="application/pdf,.pdf" multiple showUploadList={false} beforeUpload={beforeUpload} disabled={isRunning}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p><p className="ant-upload-text">点击或拖拽 PDF 到此区域</p><p className="ant-upload-hint">可一次选择多个文件，将按列表顺序处理</p>
        </Upload.Dragger>
        <List className={styles.fileList} bordered dataSource={files} locale={{ emptyText: '暂未选择 PDF 文件' }} renderItem={(file, index) => <List.Item actions={[<Button key="remove" type="link" danger size="small" disabled={isRunning} onClick={() => removeFile(index)} aria-label={`删除 ${file.name}`}><DeleteOutlined /> 删除</Button>]}><div className={styles.fileName}>{index + 1}. {file.name} <Typography.Text type="secondary">（{formatFileSize(file.size)}）</Typography.Text></div></List.Item>} />
        {status !== 'idle' && <div className={styles.progress}><div className={styles.progressText}><span>{status === 'uploading' ? '正在创建任务…' : status === 'completed' ? '处理完成' : status === 'failed' ? '处理已停止' : `正在处理第 ${currentFileIndex}/${files.length} 个文件`}</span><span>{currentFileName}</span></div><Progress percent={progress} status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'} /></div>}
        {status === 'failed' && <Alert className={styles.error} type="error" showIcon message="任务处理失败，后续文件未提交" description={errorMessage || '请查看已创建任务的已有结果，或重新创建任务。'} action={<span><Button size="small" onClick={() => taskId && navigate(`/tasks/${encodeURIComponent(taskId)}`)} disabled={!taskId}>查看已有结果</Button><Button size="small" type="link" onClick={resetRun}>重新创建任务</Button></span>} />}
      </section>
      <div className={styles.actions}>
        <Button type="primary" icon={<CheckOutlined />} onClick={start} loading={isRunning} disabled={isRunning}>提交识别任务</Button>
        <Button className={styles.resetButton} icon={<SyncOutlined />} onClick={resetForm} disabled={isRunning}>重置表单</Button>
        <Button icon={<RollbackOutlined />} onClick={() => navigate('/dashboard')}>退出页面</Button>
      </div>
    </div>
  </main>
}
