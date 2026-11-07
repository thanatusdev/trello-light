import { Navigate, type RouteObject } from 'react-router'

import { AppShell } from '@/components/AppShell'
import { NotFoundPage } from '@/components/NotFoundPage'
import { WorkspaceLayout } from '@/components/WorkspaceLayout'
import { LoginPage } from '@/features/auth/LoginPage'
import { ProtectedRoute } from '@/features/auth/ProtectedRoute'
import { PublicOnlyRoute } from '@/features/auth/PublicOnlyRoute'
import { RegisterPage } from '@/features/auth/RegisterPage'
import { BoardPage } from '@/features/board/BoardPage'
import { TaskListPage } from '@/features/tasks/TaskListPage'

export const routes: RouteObject[] = [
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          {
            element: <WorkspaceLayout />,
            children: [
              { index: true, element: <Navigate to="/board" replace /> },
              { path: '/board', element: <BoardPage /> },
              { path: '/tasks', element: <TaskListPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
]
