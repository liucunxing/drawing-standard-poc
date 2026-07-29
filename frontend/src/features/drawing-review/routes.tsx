import { lazy, Suspense, type ReactNode } from 'react'
import type { RouteObject } from 'react-router-dom'

const DashboardPage = lazy(() => import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })))
const NewReviewPage = lazy(() => import('./pages/NewReviewPage').then((module) => ({ default: module.NewReviewPage })))
const StandardsPage = lazy(() => import('./pages/StandardsPage').then((module) => ({ default: module.StandardsPage })))
const TaskCenterPage = lazy(() => import('./pages/TaskCenterPage').then((module) => ({ default: module.TaskCenterPage })))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage').then((module) => ({ default: module.TaskDetailPage })))

const load = (element: ReactNode) => <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>{element}</Suspense>

export const drawingReviewRoutes: RouteObject[] = [
  { path: 'dashboard', element: load(<DashboardPage />) },
  { path: 'tasks/new', element: load(<NewReviewPage />) },
  { path: 'tasks', element: load(<TaskCenterPage />) },
  { path: 'tasks/:taskId', element: load(<TaskDetailPage />) },
  { path: 'standards', element: load(<StandardsPage />) },
]
