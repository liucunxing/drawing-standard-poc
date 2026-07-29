import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AppShell } from './AppShell'
import { drawingReviewRoutes } from '../features/drawing-review/routes'

function getBasename(): string {
  const raw = import.meta.env.VITE_APP_BASE?.trim() || '/'
  return raw === '/' ? '/' : `/${raw.replace(/^\/+|\/+$/g, '')}`
}

const router = createBrowserRouter(
  [
    {
      path: '/',
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="dashboard" replace /> },
        ...drawingReviewRoutes,
        { path: '*', element: <Navigate to="dashboard" replace /> },
      ],
    },
  ],
  { basename: getBasename() },
)

export function AppRouter() {
  return <RouterProvider router={router} />
}
