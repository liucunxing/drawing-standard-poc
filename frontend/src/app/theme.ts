import type { ThemeConfig } from 'antd'

export const appTheme: ThemeConfig = {
  token: {
    colorPrimary: '#1f5f99',
    colorInfo: '#1f5f99',
    colorSuccess: '#287a48',
    colorWarning: '#a66a11',
    colorError: '#b53a3a',
    colorText: '#1f2937',
    colorTextSecondary: '#667085',
    colorBgLayout: '#f4f6f8',
    colorBorder: '#d9dee5',
    borderRadius: 4,
    borderRadiusLG: 4,
    controlHeight: 36,
    fontSize: 14,
    fontFamily: '"Microsoft YaHei", "PingFang SC", Arial, sans-serif',
    boxShadow: '0 1px 2px rgba(16, 24, 40, 0.06)',
    boxShadowSecondary: '0 1px 3px rgba(16, 24, 40, 0.08)',
  },
  components: {
    Button: { primaryShadow: 'none' },
    Card: { boxShadowTertiary: 'none' },
    Layout: { bodyBg: '#f4f6f8', headerBg: '#ffffff', siderBg: '#ffffff' },
    Menu: { itemBorderRadius: 4, itemHeight: 42 },
    Table: { headerBg: '#f6f8fa', headerColor: '#344054' },
  },
}
