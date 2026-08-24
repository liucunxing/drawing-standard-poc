# Drawing Standard MVP 代码审计与本地 CPU 验证报告

- 审计日期：2026-08-25
- 审计基线：`origin/feature/react-mvp` @ `579f851`
- 验证分支：`codex/local-cpu-run-20260824`
- 审计范围：React 前端、FastAPI API 与服务层、MySQL 访问、模型调用、Docker/Compose、Nginx、部署脚本、依赖清单及 Git 历史中的高风险凭据痕迹

## 1. 结论

| 目标 | 结论 | 说明 |
|---|---|---|
| 本机 Windows CPU 功能闭环 | **GO** | 原生 MySQL + Python 3.10 CPU 环境已完成真实 PDF 全链路验证 |
| 本地 Docker Compose 配置 | **配置有效，运行未验收** | `docker compose config --quiet` 通过；当前网络下 MySQL 镜像拉取不稳定，未把 Docker 运行结果写成已通过 |
| 客户 GPU 环境部署 | **NO-GO** | 本次没有客户 GPU、网关、生产数据库与生产模型卷，且存在下述生产阻断项 |

本次任务只完成本地可运行、依赖兼容修正、审计和文档，不对审计问题做功能性优化，也没有部署或推送到客户环境。

## 2. 审计方法与边界

已执行：

- 人工审阅 API 输入边界、文件系统路径、数据库异常、模型临时目录、前端 HTML 渲染、容器权限、反向代理和部署脚本。
- `bandit 1.9.4` 静态扫描。
- `pip-audit 2.10.1` 扫描实际本地 CPU 虚拟环境。
- `pnpm audit --prod` 和完整 `pnpm audit`。
- 后端单元测试、前端 lint/typecheck/unit/build/E2E、真实浏览器响应式检查。
- 使用合成、无客户数据的 PDF 做真实 API 识别闭环。

未执行：

- 客户 GPU/CUDA/NVIDIA Container Toolkit 验证。
- 客户统一身份网关、TLS、WAF、网络分区和数据库权限验证。
- 客户图纸、客户标准库数据或生产压力测试。
- 渗透测试、恶意 PDF 沙箱测试和多任务并发压测。
- 客户 GPU 镜像发布、线上部署或数据迁移。

因此，本报告不能替代客户环境的安全验收和 GPU 发布验收。

## 3. 生产阻断项

### AUD-01 未配置应用层认证和授权

- 严重度：**Critical / 生产阻断**
- 证据：`drawing-standard-poc/backend/app/api/routes.py:42-73` 的上传接口、`:147-191` 的标准库增删改接口及 `:194-267` 的识别接口均没有认证依赖；`drawing-standard-poc/backend/app/main.py:71-72` 直接注册全部路由。
- 影响：能访问 API 的调用方可以上传和处理文件，也可以修改或删除企业标准库。
- 整改：接入客户统一身份网关并在应用层验证受信身份；对标准库写操作增加角色授权和不可抵赖审计；后端端口不得绕过网关直接暴露。
- 临时缓解：在完成整改前，只允许单机回环或严格受控的内网测试网段访问。必须验证网关确实拦截直接访问，不能只依赖“部署在内网”的假设。

### AUD-02 `task_name` 可参与目录拼接，存在路径穿越写入

- 严重度：**Critical / 生产阻断**
- 证据：`routes.py:42-67` 接收未经约束的 `task_name`；`poc_service.py:709-722` 将其直接组成 `task_id` 和目录；仅上传文件名在 `poc_service.py:45-47` 做了 basename 处理。
- 影响：包含 `..` 或路径分隔符的任务名可以使上传目录逃逸预期的 `uploads` 根目录，在服务账号权限范围内写入 PDF。
- 整改：任务 ID 必须由服务端生成；显示名称与目录 ID 分离。若保留名称，只允许明确字符白名单和长度上限。所有落盘路径统一通过根目录 containment 检查，并增加 Windows/Linux 路径穿越测试。

### AUD-03 客户端可提交服务器本地文件路径

- 严重度：**High / 生产阻断**
- 证据：`routes.py:218-241` 接收包含 `image_path` 的 `tables`；`poc_service.py:1705-1738` 直接将其转为 `Path` 并读取。`routes.py:244-267` 接收 `markdown_files`；`poc_service.py:2015-2037` 对客户端路径执行存在性检查和文本读取。
- 影响：结合未鉴权接口，调用方可触发读取服务账号可访问的图片或文本，并把派生内容写入识别结果；也可消耗模型资源。
- 整改：API 只接收服务端生成的 task/table/markdown ID。服务端从数据库查询路径，并用统一安全解析器限制在任务目录内；拒绝绝对路径、UNC 路径、设备路径和任何目录逃逸。

### AUD-04 上传资源边界不足

- 严重度：**High / 生产阻断**
- 证据：`routes.py:56-63` 对每个上传调用 `await upload_file.read()`，整包进入内存；`poc_service.py:697-705` 只校验非空和 `.pdf` 后缀；`nginx.conf:6` 允许单请求 512 MB。
- 影响：大文件或大量文件可造成内存、磁盘和模型计算拒绝服务；改后缀的非 PDF 文件会进入后续解析链路。
- 整改：按流写入有配额的隔离目录，限制单文件、文件数、请求总量、页数和像素；校验 PDF magic/content，设置解析超时和并发配额；在生产入口增加恶意文件扫描或沙箱策略。

### AUD-05 同步模型推理和共享临时目录不具备并发隔离

- 严重度：**High / 生产阻断**
- 证据：`routes.py:206-215` 的 `async` 路由直接调用同步完整识别流程；`mineru_img2md.py:310-312` 对同一输出目录固定使用 `temp`，`:452-455` 在 finally 中递归删除。识别过程中包含 CPU/GPU 密集型 MinerU/Paddle 调用。
- 影响：阻塞 Web 事件循环；同一任务并发或重试时可能互相覆盖/删除中间文件，造成串数据、失败和不可预测的 GPU 占用。
- 整改：引入受控任务队列和每任务/每尝试唯一工作目录；限制 GPU worker 并发；增加幂等键、状态机、超时、取消和失败恢复。至少先把同步推理移出事件循环并禁止同 task 并发。

### AUD-06 Git 历史存在非占位数据库口令

- 严重度：**Critical（若曾用于客户环境）/ 生产阻断**
- 证据：提交 `3f4d5e6` 与 `1676ff2` 的 `.env.example` 中发现非空、非占位的 `MYSQL_PASSWORD`。报告不记录也不展示其值。
- 影响：即使当前工作树已删除文件，能读取 Git 历史的人员仍可获得旧值。
- 整改：先确认该值是否曾被任何环境使用；只要存在可能性就立即轮换数据库凭据并审计访问日志。随后在协调所有克隆和远端备份后清理历史，并启用提交前 secret scanning。

### AUD-07 生产依赖存在已知漏洞

- 严重度：**High / 生产阻断**
- 证据：见第 5 节依赖扫描。前端生产依赖包含 1 High + 1 Moderate；Python 实际环境中 7 个包命中 53 个唯一 package/advisory 组合。
- 影响：上传、HTTP、PDF、图片和模型加载均位于攻击面内，不能仅以“POC 可运行”代替漏洞处置。
- 整改：建立兼容矩阵并分批升级，升级后重跑真实 PDF、GPU、前端 E2E 和恶意输入回归。Transformers 5.x 与 MinerU 的兼容性必须单独验证，不能直接盲升。

### AUD-08 部署脚本可能误报成功

- 严重度：**High / 生产阻断**
- 证据：`deploy.sh:7` 只有 `set -e`，但 `:53` 的 build 输出通过 `tee`，未启用 `pipefail`；`:61-80` 的健康检查循环超时后没有显式失败；`:82-102` 无条件输出“部署完成”。
- 影响：镜像构建或服务健康检查失败时，交付人员仍可能收到成功提示。
- 整改：使用 `set -euo pipefail`，为每个健康检查保留成功标志并在超时时非零退出；记录镜像 digest、Git SHA、模型 manifest 和数据库迁移结果。

### AUD-09 数据库错误被转换成空结果或 0

- 严重度：**High / 发布正确性阻断**
- 证据：`drawing-standard-poc/backend/config/config.py:54-94` 的查询/写入捕获数据库异常后返回 `None` 或 `0`；`:96-117` 的批量写入/创建也未向上层传播失败；`app_config.py:97-124` 在首次数据库读取失败后永久标记已加载并退回默认值。
- 影响：接口可能把数据库故障表现为“无数据”或“写入 0 行”，识别流程继续执行并形成不完整结果；配置数据库暂时不可用时，进程生命周期内不会重试。
- 整改：区分“无记录”和“数据库故障”，关键写入失败必须抛错；为可重试故障增加有限重试和健康状态；事务性保存识别结果。

### AUD-10 客户模型卷与离线就绪未被验证

- 严重度：**High / 发布环境阻断**
- 证据：`docker-compose.yml:36-41` 仍挂载旧的 MinerU/HuggingFace 缓存目录；当前验证的 MinerU 3.1.15 使用显式 `mineru.json` 和 ModelScope snapshot。生产镜像构建没有模型 manifest 或启动前完整性检查。
- 影响：客户网络受限时，GPU 容器可能在首次请求才尝试下载或发现路径不匹配，导致发布后不可用。
- 整改：在客户候选镜像/模型卷中固化版本化 manifest、哈希和配置；部署前离线加载 MinerU 与 Paddle 模型并执行合成 PDF smoke test。

## 4. 其他高/中风险项

| ID | 严重度 | 证据 | 风险与建议 |
|---|---|---|---|
| AUD-11 | Medium | 多个 API 在 `routes.py` 中直接 `Result.fail(msg=str(exc))` | 可能泄漏文件路径、数据库或模型内部错误。对外返回稳定错误码，详细堆栈仅写受控日志。 |
| AUD-12 | Medium | `FastAPI(...)` 默认开放 `/docs`、`/redoc`、`/openapi.json`；`nginx.conf` 未设置安全响应头 | 生产关闭或鉴权保护 API 文档；补充 HSTS（仅 HTTPS）、CSP、nosniff、frame-ancestors/referrer-policy，并设置 TrustedHost。 |
| AUD-13 | Medium | `Dockerfile.backend`、`Dockerfile.web`、`Dockerfile.frontend` 未设置非 root `USER`，基础镜像主要使用可漂移 tag | 使用非 root UID、只读根文件系统/最小 capabilities，并用审批后的 digest 固定镜像。 |
| AUD-14 | Low | 仓库曾跟踪 `__pycache__/*.pyc` 和浏览器输出 | 从 Git 移除生成物并由 `.gitignore` 管理，避免平台噪声和审计误差。 |
| AUD-15 | Low | 生产构建主 chunk 约 683 KB | 后续按路由/组件拆包；不阻断本次本地功能闭环。 |

## 5. 依赖与静态扫描结果

### 5.1 前端生产依赖

`pnpm audit --prod`：1 High、1 Moderate、0 Critical。

| 包 | 当前版本 | 严重度 | 已知修复范围 |
|---|---:|---|---|
| `react-router` | 7.18.1 | High | `>=7.18.2` |
| `dompurify` | 3.4.12 | Moderate | `>=3.4.13` |

完整开发依赖扫描：7 High、4 Moderate，涉及 `brace-expansion`、`dompurify`、`esbuild`、`js-yaml`、`nanoid`、`react-router`、`vite`。其中构建链漏洞不等同于生产运行时暴露，但仍需升级和 CI 固化。

### 5.2 Python 实际 CPU 环境

`pip-audit 2.10.1` 扫描 213 个安装依赖：63 条原始命中，去重后为 53 个 package/advisory 组合，影响 7 个包。原始 JSON 保存在被 Git 忽略的 `.local-runtime/python-audit.json`。

| 包 | 当前版本 | 唯一命中数 | 扫描器给出的修复方向 |
|---|---:|---:|---|
| `aiohttp` | 3.13.5 | 14 | 升级到 3.14.x，最高建议 3.14.3 |
| `pillow` | 12.2.0 | 13 | 12.3.0 |
| `pydantic-settings` | 2.14.1 | 1 | 2.14.2 |
| `pypdf` | 6.12.0 | 13 | 分批修复版本最高到 6.15.0 |
| `python-multipart` | 0.0.29 | 3 | 0.0.31 |
| `starlette` | 0.52.1 | 5 | 部分修复要求 1.x；需和 FastAPI 联合升级 |
| `transformers` | 4.57.6 | 4 | 多项要求 5.x；需先验证 MinerU 兼容性 |

### 5.3 Bandit

Bandit 共报告 16 项：6 Medium、10 Low。原始 JSON 位于 `.local-runtime/bandit.json`。

- 5 个 B608 为 Low-confidence 动态 SQL 告警；人工确认动态片段来自固定字段或参数化筛选，值仍通过 PyMySQL 参数绑定，不作为已确认 SQL 注入。
- B104 是容器服务绑定 `0.0.0.0`，在容器内属于预期，但生产必须由网络和网关限制外部暴露。
- B105 命中的是空数据库密码默认值，不是硬编码凭据；真正风险是 Git 历史中的值，已单列 AUD-06。
- B110/B112 反映吞掉异常或静默跳过，和 AUD-09 的可观测性/正确性风险一致。

## 6. 已确认的正向控制

- `backend/app/core/paths.py:4-12` 对 `/api/files` 的相对路径做了根目录 containment 检查。
- 数据库调用大部分使用 PyMySQL 参数绑定；Bandit 的动态 SQL 告警经人工核查未确认注入。
- Markdown 渲染在 `frontend/src/features/drawing-review/components/markdownRenderer.ts:1-16` 使用 DOMPurify 清洗。
- CORS 默认为关闭，仅在显式设置 `CORS_ORIGINS` 时开启（`backend/app/main.py:56-69`）。
- 外部 Qwen 后处理在生产主链路中已禁用。
- 本地 Compose 的 MySQL、后端和前端只绑定 `127.0.0.1`；本地 CPU 后端镜像使用固定 Python 基础镜像 digest 和非 root 用户。
- `.env.local`、模型、虚拟环境、日志和本地运行输出均被 Git 忽略。

这些控制不能抵消第 3 节的生产阻断项。

## 7. 本地 CPU 验证证据

### 7.1 运行时与模型

- 本机无可用 NVIDIA GPU，`nvidia-smi` 不存在；使用 CPU 验证。
- Python 3.10.21（uv 管理虚拟环境）。
- PyTorch 2.6.0+cpu，`torch.cuda.is_available() == False`。
- PaddlePaddle 3.2.1、PaddleOCR 3.5.0、PaddleX 3.5.2。
- MinerU 3.1.15、Transformers 4.57.6、Tokenizers 0.22.2。
- MinerU ModelScope snapshot：40 个文件，2,595,586,833 bytes。
- Paddle `PP-DocLayout_plus-L`：3 个文件，130,391,437 bytes。
- `pip check`：通过。

### 7.2 自动化与浏览器

| 检查 | 结果 |
|---|---|
| 后端 unittest | 3/3 通过 |
| 前端 unit | 10 个文件、28/28 通过 |
| ESLint | 通过，0 warning |
| TypeScript typecheck | 通过 |
| Vite production build | 通过；仅有 683 KB chunk warning |
| `/drawing-review` 基路径构建/HTTP | 200，静态资源前缀正确 |
| Playwright E2E | 独立根路径 16/16，`/drawing-review` 基路径 16/16（Chrome，1366 与 1920） |
| 真实浏览器 console | favicon 修正后 0 error、0 warning |
| 横向溢出 | 1366 与 1920 均无 |

### 7.3 真实 API 闭环

使用 `data/tmp/pdfs/local_cpu_smoke_test.pdf`（合成数据，不含客户资料）完成：

```text
PDF 上传 -> Paddle 版面检测 -> 表格裁剪 -> MinerU Markdown
-> 标准号提取 -> MySQL 比对 -> React 详情展示
```

结果：1 页、1 个表格、1 份 Markdown，提取 3 个标准号：`HG/T 20592-2009`、`GB/T 150.1-2024`、`NB/T47013.2-2015`。本地 `standard_data` 表为空，因此比对结果为“不存在/标准库为空，无法比对”，属于数据前置条件，不是识别链路失败。

## 8. 下一阶段建议顺序

1. 先处理 AUD-01 至 AUD-06，并轮换任何可能泄露的数据库凭据。
2. 修正生产依赖和部署脚本，建立锁定版本、镜像 digest、模型 manifest。
3. 在客户候选 GPU 机器做离线模型加载、合成 PDF smoke、并发/重试和故障恢复测试。
4. 再进行功能优化和识别效果优化，避免把安全/发布问题与算法调优混在同一次部署中。
