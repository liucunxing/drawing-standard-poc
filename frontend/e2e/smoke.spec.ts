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
