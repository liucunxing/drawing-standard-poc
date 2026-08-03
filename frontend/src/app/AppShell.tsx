import {
  AppstoreOutlined,
  BookOutlined,
  FileAddOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'
import { Layout, Menu } from 'antd'
import { useLocation, useNavigate, Outlet } from 'react-router-dom'
import styles from './AppShell.module.css'

const navigationItems = [
  { key: '/dashboard', icon: <AppstoreOutlined />, label: '数据统计总览' },
  { key: '/tasks/new', icon: <FileAddOutlined />, label: '新建审查' },
  { key: '/tasks', icon: <UnorderedListOutlined />, label: '任务中心' },
  { key: '/standards', icon: <BookOutlined />, label: '标准库' },
]

function currentNavigationKey(pathname: string): string {
  if (pathname === '/tasks/new') return '/tasks/new'
  if (pathname === '/tasks' || pathname.startsWith('/tasks/')) return '/tasks'
  if (pathname === '/standards' || pathname.startsWith('/standards/')) return '/standards'
  return '/dashboard'
}

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <Layout className={styles.shell}>
      <Layout.Sider width={220} className={styles.sider} theme="light">
        <div className={styles.brand} aria-label="图纸标准审查">
          <span className={styles.brandMark}>审</span>
          <span>图纸标准审查</span>
        </div>
        <Menu
          className={styles.menu}
          mode="inline"
          selectedKeys={[currentNavigationKey(location.pathname)]}
          items={navigationItems}
          onClick={({ key }) => navigate(key)}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header className={styles.header}>
          <span className={styles.headerTitle}>工程图纸识别与标准审查</span>
        </Layout.Header>
        <Layout.Content className={styles.content}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
