# Drawing Standard MVP

工程图纸标准信息识别与审查 POC。当前主链路为 React Web + FastAPI + MySQL：PaddleOCR/PaddleX 检测并裁剪表格区域，MinerU Pipeline 将表格转换为 Markdown，规则引擎提取标准号并与标准库比对。

> 2026-08-25 状态：**本机 Windows CPU 全链路已跑通；客户 GPU 生产部署仍为 NO-GO。** 生产阻断项和证据见 [`docs/code_audit_2026-08-25.md`](docs/code_audit_2026-08-25.md)。

## 1. 当前代码基线与分支边界

- 最新实际开发线：`origin/feature/react-mvp` @ `579f851`
- 本地 CPU 验证分支：`codex/local-cpu-run-20260824`
- 本地 CPU 工作树：`D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-mvp-local-cpu`
- 原 `master` 工作树存在用户未提交内容且与远端分叉，本次没有覆盖、清理或切换它。
- 本次没有推送远端，也没有部署客户环境。

提交按用途拆分：

1. `fix(deploy): align MinerU 3.1.15 pipeline dependencies`：客户 GPU 候选环境也需要的 MinerU 依赖/兼容修正，可单独 cherry-pick。
2. `chore(local): add verified Windows CPU runtime`：本地 CPU、模型下载、数据库初始化和前端机械修正，不替换客户 GPU Compose。
3. `docs(audit): record local validation and production blockers`：README 与审计报告。

交付时以 `git log --oneline -3` 显示的实际 SHA 为准，不在文档中固化可能变化的短 SHA。

## 2. 实际技术栈

| 层 | 当前实现 |
|---|---|
| 默认 Web | React 19、TypeScript、Vite 5、Ant Design 5、Nginx |
| API | Python 3.10、FastAPI、Uvicorn |
| 数据库 | MySQL 8.x、PyMySQL |
| 版面检测 | PaddlePaddle 3.2.1、PaddleOCR 3.5.0、PaddleX 3.5.2、`PP-DocLayout_plus-L` |
| 表格转 Markdown | MinerU 3.1.15 Pipeline 内置有线/无线表格模型 |
| 回退界面 | Streamlit，仅 `legacy` profile，非默认入口 |

当前 MinerU 3.1.15 主链路不使用 `struct-eqtable` 包。旧 Conda 导出清单、测试文件和历史说明中仍可能出现该名称，不能据此给当前环境降级 `transformers`。生产/本地共享的有效 pip 清单是 `requirements-linux.txt`，本地 CPU 额外使用 `requirements-local-cpu.txt`。

```text
PDF 上传
  -> Paddle PP-DocLayout_plus-L 版面检测与表格裁剪
  -> MinerU 3.1.15 Pipeline 转 Markdown
  -> 标准号规则提取与归一化
  -> MySQL standard_data 比对
  -> React 任务中心、详情和人工修订
```

外部 Qwen 后处理已禁用，不属于本地或生产主链路。

## 3. 本机已验证的 CPU 运行环境

### 3.1 当前服务

| 服务 | 地址 | 当前验证方式 |
|---|---|---|
| React | <http://127.0.0.1:8501> | Vite 本地开发服务 |
| FastAPI | <http://127.0.0.1:8000> | 原生 Python 3.10 CPU 环境 |
| API 文档 | <http://127.0.0.1:8000/docs> | 仅本地调试使用 |
| MySQL | `127.0.0.1:3307` | 官方 MySQL 8.4.11 Windows noinstall |

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod http://127.0.0.1:8000/api/drawing/tasks
Invoke-RestMethod http://127.0.0.1:8000/api/standard-data
Test-NetConnection 127.0.0.1 -Port 3307
```

### 3.2 当前机器上的运行资产

| 资产 | 路径/版本 |
|---|---|
| Python venv | `.venv-local-cpu`，Python 3.10.21 |
| PyTorch | 2.6.0+cpu，CUDA 不可用 |
| MinerU 模型 | `models/modelscope`，40 文件，2,595,586,833 bytes |
| MinerU 配置 | `models/mineru/mineru.json` |
| Paddle 模型 | `%LOCALAPPDATA%\drawing-standard-mvp-runtime\models\paddlex\official_models\PP-DocLayout_plus-L`，3 文件，130,391,437 bytes |
| MySQL 程序 | `%LOCALAPPDATA%\drawing-standard-mvp-runtime\mysql-8.4.11-winx64` |
| MySQL 数据 | `%LOCALAPPDATA%\drawing-standard-mvp-runtime\mysql-data` |
| 运行时临时目录 | `%LOCALAPPDATA%\drawing-standard-mvp-runtime\tmp` |
| 模型清单 | `models/model-manifest.local.json`（本地生成、Git 忽略） |

Paddle Windows 原生库在包含中文的项目路径下出现过模型加载问题，因此 Paddle 模型和 MySQL 数据放在 `%LOCALAPPDATA%` 的纯 ASCII 路径；MinerU ModelScope snapshot 已在项目路径中验证可用。不要把这些本地绝对路径直接复制到客户 Linux 配置。

## 4. 重启后在本机启动

以下命令针对本次已准备好的本机运行资产。三个服务建议分别开 PowerShell 终端。

### 4.1 MySQL（端口未监听时执行）

```powershell
$runtime = Join-Path $env:LOCALAPPDATA 'drawing-standard-mvp-runtime'
$mysqlRoot = Join-Path $runtime 'mysql-8.4.11-winx64'
$mysqlArgs = @(
  '--no-defaults',
  "--basedir=$mysqlRoot",
  "--datadir=$(Join-Path $runtime 'mysql-data')",
  '--port=3307',
  '--bind-address=127.0.0.1',
  '--mysqlx=0',
  '--character-set-server=utf8mb4',
  '--collation-server=utf8mb4_0900_ai_ci',
  "--pid-file=$(Join-Path $runtime 'mysql-local.pid')",
  "--log-error=$(Join-Path $runtime 'mysql-local.err')"
)
Start-Process -FilePath (Join-Path $mysqlRoot 'bin\mysqld.exe') `
  -ArgumentList $mysqlArgs -WindowStyle Hidden
```

确认 `Test-NetConnection 127.0.0.1 -Port 3307` 成功后再启动后端。

### 4.2 FastAPI CPU 后端

```powershell
$repo = 'D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-mvp-local-cpu'
$runtime = Join-Path $env:LOCALAPPDATA 'drawing-standard-mvp-runtime'

$env:MYSQL_HOST = '127.0.0.1'
$env:MYSQL_PORT = '3307'
$env:MYSQL_DB = 'drawing_poc'
$env:MYSQL_USER = 'drawing_poc'
$env:MYSQL_PASSWORD = 'drawing_local_dev'
$env:BACKEND_TMP_DIR = Join-Path $runtime 'tmp'
$env:LOG_DIR = Join-Path $repo 'logs\local-backend-native'

$env:MINERU_DEVICE_MODE = 'cpu'
$env:MINERU_MODEL_SOURCE = 'local'
$env:MINERU_TOOLS_CONFIG_JSON = Join-Path $repo 'models\mineru\mineru.json'
$env:MODELSCOPE_CACHE = Join-Path $repo 'models\modelscope'
$env:HF_HOME = Join-Path $repo 'models\huggingface'
$env:PADDLE_PDX_CACHE_HOME = Join-Path $runtime 'models\paddlex'
$env:PADDLEOCR_LOCAL_MODELS_ROOT = Join-Path $runtime 'models\paddlex\official_models'
$env:PADDLEOCR_LAYOUT_MODEL_NAME = 'PP-DocLayout_plus-L'
$env:PADDLE_PDX_MODEL_SOURCE = 'BOS'
$env:CUDA_VISIBLE_DEVICES = ''
$env:FLAGS_use_onednn = '0'
$env:FLAGS_use_mkldnn = '0'
$env:FLAGS_enable_pir_api = '0'
$env:FLAGS_enable_pir_in_executor = '0'

Set-Location (Join-Path $repo 'drawing-standard-poc')
& (Join-Path $repo '.venv-local-cpu\Scripts\python.exe') `
  -m uvicorn backend.app.main:app `
  --host 127.0.0.1 --port 8000 --log-level info --access-log
```

`drawing_local_dev` 只用于本机隔离数据库，来自 `.env.local.example`，不是客户凭据。若本机已修改该密码，应同步修改上述环境变量。

### 4.3 React 前端

```powershell
Set-Location 'D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-mvp-local-cpu\frontend'
pnpm.cmd dev --host 127.0.0.1 --port 8501 --strictPort
```

关闭前后端终端即可停止对应服务。MySQL 可用其 `bin\mysqladmin.exe` 对 `127.0.0.1:3307` 执行受控 shutdown；不要直接删除 `mysql-data`。

## 5. 从零重建 Python 与模型

### 5.1 Python 3.10 CPU 环境

系统默认 Python 3.13 不在本项目验证矩阵内。本次使用 uv 管理的 Python 3.10：

```powershell
uv venv --python 3.10 .venv-local-cpu

uv pip install --python .venv-local-cpu\Scripts\python.exe `
  torch==2.6.0+cpu torchvision==0.21.0+cpu torchaudio==2.6.0+cpu `
  --index-url https://download.pytorch.org/whl/cpu

uv pip install --python .venv-local-cpu\Scripts\python.exe `
  -r requirements-local-cpu.txt `
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple

.\.venv-local-cpu\Scripts\python.exe -m pip check
```

GPU wheel 不应安装到这个 venv；客户 CUDA wheel 仍由 `Dockerfile.backend` 管理。

### 5.2 模型下载或盘点

```powershell
$repo = (Resolve-Path '.').Path
$runtime = Join-Path $env:LOCALAPPDATA 'drawing-standard-mvp-runtime'
$env:MODEL_ROOT = Join-Path $repo 'models'
$env:MINERU_DOWNLOAD_SOURCE = 'modelscope'
$env:MINERU_DEVICE_MODE = 'cpu'
$env:MINERU_TOOLS_CONFIG_JSON = Join-Path $repo 'models\mineru\mineru.json'
$env:MODELSCOPE_CACHE = Join-Path $repo 'models\modelscope'
$env:HF_HOME = Join-Path $repo 'models\huggingface'
$env:PADDLE_PDX_CACHE_HOME = Join-Path $runtime 'models\paddlex'
$env:PADDLEOCR_LAYOUT_MODEL_NAME = 'PP-DocLayout_plus-L'

# 首次下载
$env:MODEL_DOWNLOAD_MODE = 'download'
& .\.venv-local-cpu\Scripts\python.exe scripts\download_models_local.py

# 已有模型只做完整性盘点，不重复下载
$env:MODEL_DOWNLOAD_MODE = 'inventory'
& .\.venv-local-cpu\Scripts\python.exe scripts\download_models_local.py
```

中国大陆网络默认使用 ModelScope；可将 `MINERU_DOWNLOAD_SOURCE` 改为 `huggingface`。`models/`、模型清单和虚拟环境均被 Git 忽略。

### 5.3 本次旧模型清理结果

本次先检查了用户级 HuggingFace、ModelScope、MinerU 和 Paddle 缓存。发现的旧版本/不完整缓存没有永久删除，而是可恢复地移动到：

```text
D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\model-cache-quarantine-20260824
```

其中还包含一次中断下载产生的约 26 MB ModelScope partial cache。确认新模型和业务验证稳定后，再由人工决定是否永久删除隔离目录；不得把隔离目录提交到 Git。

## 6. 本地 Docker Compose：可选但本次未完成运行验收

仓库提供独立 CPU 配置：

- `Dockerfile.backend.local`
- `compose.local.yml`
- `.env.local.example`
- `docker/local/mysql/001-schema.sql`

配置语法已验证：

```powershell
docker compose --env-file .env.local.example -f compose.local.yml config --quiet
```

当前网络环境下 Docker Hub 的 MySQL 镜像拉取多次不稳定，因此本次最终验收采用官方 MySQL Windows noinstall + 原生 CPU 后端；**不能把 Compose 语法通过写成容器运行通过。** 在镜像网络正常的机器上可继续：

```powershell
Copy-Item .env.local.example .env.local
docker compose --env-file .env.local -f compose.local.yml build backend
docker compose --env-file .env.local -f compose.local.yml --profile setup run --rm model-init
docker compose --env-file .env.local -f compose.local.yml up -d --build
docker compose --env-file .env.local -f compose.local.yml ps
```

停止时使用 `docker compose ... down`。`down -v` 会删除本地 MySQL volume，只有确认不需要本地测试数据后才能执行；它不会删除宿主机 `models/`。

## 7. 客户 GPU 环境的部署边界

| 项目 | 本地 CPU 验证 | 客户 GPU 候选 |
|---|---|---|
| Compose | `compose.local.yml` 或本机原生进程 | `docker-compose.yml` |
| 后端镜像 | `Dockerfile.backend.local` | `Dockerfile.backend` |
| PyTorch | 2.6.0+cpu | 2.6.0 + CUDA 12.4 |
| Paddle | 3.2.1 CPU | 3.2.1 GPU |
| 模型设备 | `MINERU_DEVICE_MODE=cpu` | 必须在客户 GPU 实测 |
| 数据库 | 本地 MySQL 8.4.11、3307、回环绑定 | 客户 MySQL，凭据仅由受控 secret 注入 |
| 模型 | 本地 snapshot + manifest | 客户持久化模型卷 + manifest + 哈希 |

客户环境部署原则：

- 不要用 `compose.local.yml` 或 `.env.local.example` 覆盖客户部署文件。
- 需要部署 MinerU 兼容修正时，只 cherry-pick 对应的 `fix(deploy)` 提交；本地 CPU 与审计提交可按需选择。
- 本地 CPU 通过只证明功能链路，不证明 CUDA、显存、吞吐或客户图纸效果。
- 客户部署前必须处理审计报告中的 Critical/High 阻断项，至少确认身份网关、路径/上传限制、凭据轮换、生产模型卷、镜像 digest 和失败回滚。
- 客户候选 GPU 容器必须在无外网条件下预加载模型，并用合成 PDF 做一次真实 smoke test 后再接入客户数据。

## 8. 已完成的验证

| 检查 | 结果 |
|---|---|
| `pip check` | 通过 |
| 后端 unittest | 3/3 通过 |
| 前端 unit | 10 个文件、28/28 通过 |
| ESLint | 通过，0 warning |
| TypeScript typecheck | 通过 |
| Vite build | 通过；主 chunk 约 683 KB，仅为后续性能项 |
| `/drawing-review` 基路径 build/HTTP | 200，资源前缀正确 |
| Playwright E2E | 独立根路径 16/16，`/drawing-review` 基路径 16/16；Chrome 1366/1920 |
| 真实浏览器 console | 0 error、0 warning |
| Docker Compose config | 通过；容器运行未验收 |

后端：

```powershell
$env:PYTHONPATH = (Resolve-Path 'drawing-standard-poc\backend').Path
.\.venv-local-cpu\Scripts\python.exe -m unittest discover `
  -s drawing-standard-poc\backend\tests -p 'test_*.py'
```

前端：

```powershell
Set-Location frontend
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e

$env:VITE_APP_BASE = '/drawing-review'
pnpm build
```

真实 CPU API smoke 使用合成文件 `data/tmp/pdfs/local_cpu_smoke_test.pdf`，结果为 1 页、1 表格、1 Markdown，并识别出 3 个标准号。当前本地 `standard_data` 表为空，所以比对显示“不存在/标准库为空，无法比对”，这是本地数据前置条件，不是模型链路失败；导入经过确认的标准库数据后才能验证匹配分类。

## 9. 目录说明

```text
.
├─ frontend/                         React 前端
├─ drawing-standard-poc/backend/     FastAPI、识别和比对服务
├─ data/                             脱敏样例与本地临时输出
├─ docker/local/mysql/               可执行的本地 MySQL 表结构脚本
├─ scripts/                          本地模型下载与清单脚本
├─ docs/                             需求、接口、流程与审计报告
├─ Dockerfile.backend                客户 GPU 后端候选
├─ Dockerfile.backend.local          本地 CPU 后端
├─ docker-compose.yml                客户 GPU 编排候选
└─ compose.local.yml                 本地 CPU 编排
```

## 10. 当前限制

- 无应用层登录、RBAC 和完整操作审计；客户生产前必须整改或由已验证的统一网关强制保护。
- 上传、服务器路径输入、同步模型推理、任务并发和临时目录存在生产阻断风险。
- 当前依赖扫描存在已知漏洞，详见审计报告；本阶段没有擅自升级可能破坏 MinerU 的核心依赖。
- 模型效果依赖客户图纸版式，POC 结果必须保留人工复核。
- `deploy.sh`、客户 GPU 模型卷和故障回滚仍需在目标服务器单独验证。
- 当前前端生产包有约 683 KB 主 chunk，放到下一阶段优化。

License: POC Internal Use Only.
