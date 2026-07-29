import { DeleteOutlined, EditOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Alert, Button, Empty, Form, Input, Modal, Pagination, Space, Spin, Table, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useCallback, useEffect, useState } from 'react'
import { createStandard, deleteStandard, listStandards, updateStandard } from '../api/standardApi'
import type { StandardInput, StandardRecord } from '../types'
import { getErrorMessage } from '../../../shared/api/client'
import styles from './StandardsPage.module.css'

const PAGE_SIZE = 20

function displayValue(value: string | null | undefined): string {
  return value?.trim() || '—'
}

export function StandardsPage() {
  const [form] = Form.useForm<StandardInput>()
  const [keyword, setKeyword] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [records, setRecords] = useState<StandardRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<StandardRecord | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const loadStandards = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await listStandards({ keyword: query, page, pageSize: PAGE_SIZE })
      setRecords(Array.isArray(result?.items) ? result.items : [])
      setTotal(Number.isFinite(result?.total) ? result.total : 0)
    } catch (requestError) {
      setRecords([])
      setTotal(0)
      setError(getErrorMessage(requestError, '标准库加载失败，请稍后重试'))
    } finally {
      setLoading(false)
    }
  }, [page, query])

  useEffect(() => {
    void loadStandards()
  }, [loadStandards])

  const openCreateModal = () => {
    setEditingRecord(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEditModal = (record: StandardRecord) => {
    setEditingRecord(record)
    form.setFieldsValue({
      standard_no: record.standard_no,
      standard_type: record.standard_type,
      standard_prefix: record.standard_prefix,
    })
    setModalOpen(true)
  }

  const submitForm = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      if (editingRecord) {
        await updateStandard(editingRecord.id, values)
        message.success('标准已更新')
      } else {
        await createStandard(values)
        message.success('标准已新增')
      }
      setModalOpen(false)
      await loadStandards()
    } catch (requestError) {
      if ((requestError as { errorFields?: unknown }).errorFields) return
      message.error(getErrorMessage(requestError, editingRecord ? '更新标准失败' : '新增标准失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const confirmDelete = (record: StandardRecord) => {
    Modal.confirm({
      title: '确认删除标准？',
      content: `将删除“${record.standard_no}”，此操作不可撤销。`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteStandard(record.id)
          message.success('标准已删除')
          if (records.length === 1 && page > 1) {
            setPage((current) => current - 1)
          } else {
            await loadStandards()
          }
        } catch (requestError) {
          message.error(getErrorMessage(requestError, '删除标准失败'))
          throw requestError
        }
      },
    })
  }

  const columns: ColumnsType<StandardRecord> = [
    { title: '标准编号', dataIndex: 'standard_no', key: 'standard_no', ellipsis: true },
    { title: '标准类型', dataIndex: 'standard_type', key: 'standard_type', ellipsis: true },
    { title: '标准前缀', dataIndex: 'standard_prefix', key: 'standard_prefix', ellipsis: true },
    { title: '创建时间', dataIndex: 'create_time', key: 'create_time', width: 180, render: displayValue },
    {
      title: '操作', key: 'action', width: 136, render: (_, record) => (
        <Space size={4}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>编辑</Button>
          <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => confirmDelete(record)}>删除</Button>
        </Space>
      ),
    },
  ]

  const hasNoRecords = !loading && !error && records.length === 0

  return (
    <main className="page-container">
      <div className={styles.header}>
        <div>
          <Typography.Title level={2} className="page-title">标准库</Typography.Title>
          <Typography.Text type="secondary">维护用于图纸内容比对的标准记录。</Typography.Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新增标准</Button>
      </div>

      <section className={styles.content} aria-label="标准库列表">
        <div className={styles.toolbar}>
          <Input.Search
            aria-label="按关键词搜索标准库"
            allowClear
            placeholder="搜索标准编号、类型或前缀"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={() => { setPage(1); setQuery(keyword.trim()) }}
            enterButton={<SearchOutlined />}
          />
        </div>

        {error && <Alert className={styles.alert} type="error" showIcon message="标准库加载失败" description={error} action={<Button size="small" onClick={() => void loadStandards()}>重试</Button>} />}
        {loading ? <div className={styles.state}><Spin /><div className="muted-text">正在加载标准库…</div></div> : hasNoRecords ? <div className={styles.state}><Empty description={query ? '未找到匹配的标准' : '暂无标准记录'} /></div> : !error && (
          <>
            <Table<StandardRecord> rowKey="id" columns={columns} dataSource={records} pagination={false} />
            <div className={styles.pagination}>
              <Typography.Text type="secondary">共 {total} 条</Typography.Text>
              <Pagination current={page} pageSize={PAGE_SIZE} total={total} showSizeChanger={false} showLessItems onChange={setPage} />
            </div>
          </>
        )}
      </section>

      <Modal
        destroyOnHidden
        title={editingRecord ? '编辑标准' : '新增标准'}
        open={modalOpen}
        okText={editingRecord ? '保存' : '新增'}
        cancelText="取消"
        confirmLoading={submitting}
        onCancel={() => setModalOpen(false)}
        onOk={() => void submitForm()}
      >
        <Form form={form} layout="vertical" requiredMark="optional">
          <Form.Item label="标准编号" name="standard_no" rules={[{ required: true, whitespace: true, message: '请输入标准编号' }]}>
            <Input maxLength={100} placeholder="例如：GB 50016-2014" />
          </Form.Item>
          <Form.Item label="标准类型" name="standard_type" rules={[{ required: true, whitespace: true, message: '请输入标准类型' }]}>
            <Input maxLength={100} placeholder="例如：国家标准" />
          </Form.Item>
          <Form.Item label="标准前缀" name="standard_prefix" rules={[{ required: true, whitespace: true, message: '请输入标准前缀' }]}>
            <Input maxLength={100} placeholder="例如：GB" />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  )
}
