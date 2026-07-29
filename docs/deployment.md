# React MVP 部署说明

本说明仅覆盖内部试用部署。React MVP 保持既有 FastAPI `/api` 契约；后端 OCR、数据库结构和 Streamlit 文件均未替换。它不提供登录/RBAC、高可用、异步队列或生产级运维能力。

当前交付状态：Compose 配置解析已通过，但本机访问 Docker Hub 拉取 `nginx:1.27-alpine` 时返回 EOF，因此镜像构建与容器启动尚未形成通过证据。真实 FastAPI/MySQL/GPU 与客户代表性 PDF 也尚未联调；完成这两项前不得标记为“内部试用已放行”。

## 独立开发

安装前端依赖后，在 `frontend/` 目录运行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

开发服务器默认将 `/api` 代理到 `http://localhost:8000`。如后端地址不同，可在 `frontend/.env.local` 设置 `VITE_API_PROXY_TARGET`；该文件不得提交。

## 默认试用运行（React + Nginx）

1. 复制 `.env.example` 为 `.env`，并仅在部署环境中填写数据库连接信息。
2. 在项目根目录启动：

```powershell
docker compose up -d --build
```

默认 `frontend` 服务在宿主机 `8501` 提供 React 静态页面；Nginx 同源代理 `/api` 到 Compose 内的 `backend:8000`。后端仍使用 GPU 配置。上传限制为 512 MB，长任务代理读写超时均为 3600 秒。

如需以 `/drawing-review` 作为应用根路径，在 `.env` 中设置 `VITE_APP_BASE=/drawing-review` 后重新构建。

## Streamlit 回退

`streamlit_app.py` 与 `Dockerfile.frontend` 保留为回退实现。需要并行启动时使用：

```powershell
docker compose --profile legacy up -d --build
```

该命令额外启动 `frontend-legacy`，默认映射到宿主机 `8502`；React 入口仍在 `8501`。可通过 `FRONTEND_LEGACY_PORT` 调整回退端口。

## 配置检查

在没有真实 `.env` 的工作区，可临时复制 `.env.example` 为 `.env`，再以安全占位变量验证 Compose 语法；检查后删除该临时文件，不要提交：

```powershell
Copy-Item .env.example .env
$env:MYSQL_HOST='placeholder'; $env:MYSQL_PORT='3306'; $env:MYSQL_DB='placeholder'; $env:MYSQL_USER='placeholder'; $env:MYSQL_PASSWORD='placeholder'; docker compose config
Remove-Item .env
```

此检查仅验证 Compose 解析，不代表数据库、GPU、OCR 模型或真实后端可用。
