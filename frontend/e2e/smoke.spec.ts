import { expect, test } from '@playwright/test'

const configuredBase = process.env.VITE_APP_BASE?.trim() || '/'
const pathPrefix = configuredBase === '/' ? '' : `/${configuredBase.replace(/^\/+|\/+$/g, '')}`
const appPath = (path: string) => `${pathPrefix}${path === '/' ? '/' : path}`

test.beforeEach(async ({ page }) => {
  await page.route('**/api/drawing/tasks?**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, msg: 'ok', data: [] }),
  }))
  await page.route('**/api/standard-data**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ code: 200, msg: 'ok', data: [] }),
  }))
})

for (const [path, heading] of [
  ['/', '数据统计总览'],
  ['/tasks/new', '新建审查'],
  ['/tasks', '任务中心'],
  ['/standards', '标准库'],
] as const) {
  test(`loads ${path} at the supported desktop viewports`, async ({ page }) => {
    await page.goto(appPath(path))
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  })
}

test('navigates through the fixed application menu', async ({ page }) => {
  await page.goto(appPath('/'))
  await page.getByRole('menuitem', { name: '任务中心' }).click()
  await expect(page).toHaveURL(new RegExp(`${pathPrefix.replace('/', '\\/')}\\/tasks$`))
  await expect(page.getByRole('heading', { name: '任务中心' })).toBeVisible()
})

test('dashboard quick actions refresh tasks, explain unavailable rules and open task creation', async ({ page }) => {
  await page.goto(appPath('/'))

  await page.getByRole('button', { name: '配置识别规则' }).click()
  await expect(page.getByText('暂不可配置识别规则')).toBeVisible()
  await page.getByRole('button', { name: '我知道了' }).click()

  const refreshRequest = page.waitForRequest((request) => request.url().includes('/api/drawing/tasks?'))
  await page.getByRole('button', { name: '查询历史识别任务' }).click()
  await refreshRequest

  await page.getByRole('button', { name: '创建识别任务' }).click()
  await expect(page.getByRole('heading', { name: '新建审查' })).toBeVisible()
})

test('task center submits filters explicitly and keeps pagination controls available', async ({ page }) => {
  await page.unroute('**/api/drawing/tasks?**')
  let requestCount = 0
  const tasks = [
    { task_id: 'task-a', task_name: '泵房图纸识别', original_filename: 'pump.pdf', status: 1, created_at: '2026-07-01 09:00:00' },
    { task_id: 'task-b', task_name: '阀门历史审查', original_filename: 'valve.pdf', status: 2, created_at: '2026-07-02 09:00:00' },
  ]
  await page.route('**/api/drawing/tasks?**', (route) => {
    requestCount += 1
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ code: 200, msg: 'ok', data: tasks }),
    })
  })

  await page.goto(appPath('/tasks'))
  await expect(page.getByRole('button', { name: '泵房图纸识别' })).toBeVisible()
  await page.getByLabel('文件名').fill('阀门')
  await expect(page.getByRole('button', { name: '泵房图纸识别' })).toBeVisible()

  await page.getByRole('button', { name: '筛选' }).click()
  await expect.poll(() => requestCount).toBe(2)
  await expect(page.getByRole('button', { name: '泵房图纸识别' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '阀门历史审查' })).toBeVisible()
  await expect(page.getByText('共 1 条数据')).toBeVisible()
  await expect(page.getByRole('radio', { name: '10' })).toBeChecked()
  await expect(page.getByText('20', { exact: true })).toBeVisible()
  await expect(page.getByText('50', { exact: true })).toBeVisible()
  await page.getByText('20', { exact: true }).click()
  await expect(page.getByRole('radio', { name: '20' })).toBeChecked()

  await page.getByRole('button', { name: '重置' }).click()
  await expect.poll(() => requestCount).toBe(3)
  await expect(page.getByRole('button', { name: '泵房图纸识别' })).toBeVisible()
})

test('task detail exposes the three-layer result workspace and editable Markdown', async ({ page }, testInfo) => {
  const detail = {
    task_id: 'task-demo', task_name: '换热器装配图审查', original_filename: '25.918-1 A1.pdf', file_names: ['25.918-1 A1.pdf'], pdf_count: 1,
    file_size: 624845, page_count: 1, status: 2, progress: 100, current_step: '标准检测完成', processed_count: 1, table_count: 1, standard_count: 3,
    exact_match_count: 1, year_mismatch_count: 1, similar_count: 1, not_found_count: 0, error_message: '', created_at: '2026-08-04 17:50:56',
    updated_at: '2026-08-04 18:02:38', started_at: '2026-08-04 17:50:56', completed_at: '2026-08-04 18:02:38', description: '', pdfs: [],
    annotated_images: [{ pdf_name: '25.918-1 A1.pdf', page: 1, image_url: '/api/files/mock-layout.png', image_path: '' }],
    tables: [{ pdf_name: '25.918-1 A1.pdf', page: 1, table_index: 1, display_name: '材料表', image_url: '/api/files/mock-table.png', image_path: '', raw_markdown_content: '<table><thead><tr><th>序号</th><th>标准号</th><th>名称</th></tr></thead><tbody><tr><td>1</td><td>GB 50053-2013</td><td>配电设计规范</td></tr><tr><td>2</td><td>HG/T 20570</td><td>工艺系统工程设计</td></tr></tbody></table>', markdown_content: '', highlighted_markdown_content: '' }],
    standards: [
      { pdf_name: '25.918-1 A1.pdf', standard_no: 'GB 50053-2013', matched_standard: 'GB 50053-2013', status: '完全符合', result_type: '完全符合', source_table: '材料表', confidence: 98, suggestion: '标准号、名称与发布年份一致' },
      { pdf_name: '25.918-1 A1.pdf', standard_no: 'GB 2000-2010', matched_standard: 'GB 2000-2015', status: '年份不一致', result_type: '年份不一致', source_table: '材料表', confidence: 90, suggestion: '请按现行版本复核' },
      { pdf_name: '25.918-1 A1.pdf', standard_no: 'HG/T 20570', matched_standard: 'HG/T 20570.1', status: '较为相似', result_type: '较为相似', source_table: '材料表', confidence: 78, suggestion: '建议人工确认标准分册' },
    ],
    overall_standard_compare: { results: [] }, raw_json: {},
  }
  await page.route('**/api/drawing/task/task-demo', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ code: 200, msg: 'ok', data: detail }) }))
  await page.route('**/api/files/**', (route) => route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64') }))

  await page.goto(appPath('/tasks/task-demo'))
  await expect(page.getByRole('heading', { name: '图纸原始预览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '图纸基础信息' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '标准对比明细列表' })).toBeVisible()

  await page.getByRole('tab', { name: '图纸版面识别结果' }).click()
  await expect(page.getByRole('heading', { name: '图纸版面识别明细' })).toBeVisible()
  await page.getByRole('tab', { name: '图纸内容解析结果' }).click()
  const editor = page.getByRole('textbox', { name: 'Markdown 解析结果编辑区' })
  await expect(editor.getByRole('table')).toBeVisible()
  await expect(editor).toContainText('GB 50053-2013')
  await page.screenshot({ path: `output/playwright/markdown-editor-${pathPrefix ? 'drawing-review' : 'standalone'}-${testInfo.project.name}.png`, fullPage: true })
  await editor.fill('已人工修订')
  await expect(editor).toContainText('已人工修订')
  await page.getByRole('tab', { name: '标准匹配分析结果' }).click()
  await expect(page.getByRole('heading', { name: '标准匹配分析明细' })).toBeVisible()
})
