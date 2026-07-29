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
  ['/', '工作台'],
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
