import { lazy, Suspense } from 'react'
import type { RouteObject } from 'react-router-dom'

const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const NewReviewPage = lazy(() => import('./pages/NewReviewPage').then((m) => ({ default: m.NewReviewPage })))
const StandardsPage = lazy(() => import('./pages/StandardsPage').then((m) => ({ default: m.StandardsPage })))
const TaskCenterPage = lazy(() => import('./pages/TaskCenterPage').then((m) => ({ default: m.TaskCenterPage })))
const TaskDetailPage = lazy(() => import('./pages/TaskDetailPage').then((m) => ({ default: m.TaskDetailPage })))

export const drawingReviewRoutes: RouteObject[] = [
  { 
    path: 'dashboard', 
    element: (
      <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>
        <DashboardPage />
      </Suspense>
    ) 
  },
  { 
    path: 'tasks/new', 
    element: (
      <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>
        <NewReviewPage />
      </Suspense>
    ) 
  },
  { 
    path: 'tasks', 
    element: (
      <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>
        <TaskCenterPage />
      </Suspense>
    ) 
  },
  { 
    path: 'tasks/:taskId', 
    element: (
      <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>
        <TaskDetailPage />
      </Suspense>
    ) 
  },
  { 
    path: 'standards', 
    element: (
      <Suspense fallback={<div className="route-loading">正在加载页面…</div>}>
        <StandardsPage />
      </Suspense>
    ) 
  },
]