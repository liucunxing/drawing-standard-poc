import '@ant-design/v5-patch-for-react-19'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import { AppRouter } from './app/AppRouter'
import { appTheme } from './app/theme'
import './app/global.css'

dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider theme={appTheme} locale={zhCN}>
      <AntApp>
        <AppRouter />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
