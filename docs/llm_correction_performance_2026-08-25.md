# MinerU 转 Markdown 后 Qwen 修正性能评估

日期：2026-08-25

范围：管口表 OCR 列漂移后处理

结论：已完成本地代码优化与可重复验证；客户 Qwen 32B 现场 A/B 尚未执行。

## 1. 结论

用户关于“全量喂给 LLM、输出 Token 较大”的判断基本成立，但不是唯一待确认因素。

历史部署实现存在三个直接放大时延的设计：

1. 把整份 MinerU Markdown 放入提示词，增加模型 prefill 工作量。
2. 要求模型重新生成整份 Markdown，哪怕只需改两三个单元格；这会把主要耗时转为完整文档的逐 Token 解码。
3. 历史客户候选调用未显式关闭 Qwen 思考模式，且输出上限曾为 16,384 tokens；思考 Token 和过大的生成预算都可能进一步拉长请求。

4–5 分钟不能仅凭代码归因到上述三项。客户推理服务的排队、并发、GPU 型号/数量、量化方式、上下文长度、KV cache、服务端超时和网络也可能占比明显，必须用现场指标拆分。

## 2. 代码证据与待确认项

| 项目 | 历史行为 | 影响判断 |
|---|---|---|
| 输入 | 完整 Markdown 嵌入用户提示词 | 增加 prefill，文档越大越明显 |
| 输出 | 要求返回修正后的完整文档 | 高置信度主因；只改少数单元格也要生成全文 |
| 输出上限 | 历史客户候选提交设置为 16,384 tokens | 上限不等于实际消耗，但缺少停止边界和异常输出保护 |
| Qwen 思考模式 | 调用未传 `enable_thinking=false`，提示词也没有 `/no_think` | 中高概率附加耗时，需用 usage/服务日志确认 |
| 可观测性 | 只打印输入/输出字符长度，不记录耗时和 Token | 无法区分排队、prefill、thinking、decode |
| 模型身份 | 用户描述为 Qwen 32B；历史候选代码的模型路径为 27B 系列 | 现场配置存在口径差异，必须以实际服务模型和 revision 为准 |
| 凭据 | 历史候选代码曾包含硬编码内网端点/凭据 | 新实现已移除；若该凭据真实使用过，应按审计要求轮换 |

近似时延组成：

```text
总耗时 = 客户端等待/网络 + 服务排队 + 输入 prefill + 思考/答案 decode + 序列化
```

全量输入主要放大 prefill；“返回完整文档”和思考模式主要放大 decode。32B 模型的实际 tokens/s 与部署硬件高度相关，本地 CPU 或小参数模型不能替代客户现场数据。

Qwen 官方资料说明 Qwen3 默认进入思考模式，并支持 `/no_think` 或 chat template 参数关闭；Qwen-Agent 官方配置分别给出了 DashScope 的 `enable_thinking=false` 和 vLLM/SGLang 的 `chat_template_kwargs.enable_thinking=false` 用法：

- [Qwen3 Transformers 推理说明](https://github.com/QwenLM/Qwen3/blob/main/docs/source/inference/transformers.md)
- [Qwen-Agent 模型配置说明](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen-agent-docs/website/content/en/guide/get_started/configuration.md)

## 3. 已实施优化

新实现位于 `drawing-standard-poc/backend/app/services/nozzle_markdown_corrector.py`，MinerU 主链路在 `mineru_img2md.py` 中调用。

### 3.1 本地规则优先

以下原提示词规则已转为确定性代码：

- `法兰类型代号` 开头的单个数字，在 `法兰标准` 只有三位年份时移回年份末位。
- `公称尺寸DN` 末尾的单个字母，在组合后形成已知标准前缀时移回 `法兰标准` 开头。
- `法兰标准` 以 `G/T` 开头时补为 `HG/T`。

规则只处理包含三个目标表头的 HTML 表格，只替换纯文本单元格内容，不重新序列化 HTML，因此不会改动表格标签、属性、rowspan/colspan 或文档其他区域。

### 3.2 歧义行 LLM 补丁

规则无法安全处理但仍保留可恢复字符的行，可按环境配置调用客户内网 OpenAI-compatible Qwen：

- 请求只包含歧义行的三个目标单元格，不包含完整文档。
- 一批默认最多 20 行。
- 模型只返回紧凑 JSON patches，不返回完整 Markdown。
- 输出默认上限 512 tokens，超时 60 秒，重试 0 次。
- Qwen-vLLM/SGLang 使用 `chat_template_kwargs.enable_thinking=false`；DashScope 使用 `enable_thinking=false`；Qwen 提示词同时带 `/no_think`。

LLM 补丁必须同时通过本地校验：

- 只能修改 `公称尺寸DN`、`法兰标准`、`法兰类型代号`。
- 三个字段去空白后的字符必须守恒，禁止臆造或删除内容。
- 修正后必须严格减少异常特征。
- 禁止 HTML/换行和五位年份。
- 任一校验失败、API 失败或超时均 fail closed：保留规则结果或原文，并标记 `needs_review_rows`。

### 3.3 可观测性与安全

每次处理记录结构化指标：

- `method`、`duration_ms`
- `input_chars`、`output_chars`
- `target_tables`、`inspected_rows`、`rule_fixes`、`patched_cells`
- `needs_review_rows`、`llm_candidate_rows`、`llm_requests`
- `llm_prompt_chars`、`llm_response_chars`
- 服务返回时的 `llm_prompt_tokens`、`llm_completion_tokens`、`llm_total_tokens`
- 失败时只记录异常类型，不记录正文、端点、密钥或完整异常消息

端点、密钥和模型名仅从环境变量读取。旧字段 `qwen_fixed_*` 暂时保留以兼容现有 API 消费方，但其内容现在可能来自本地规则而非 Qwen。

## 4. 本地验证结果

本机现状：Ollama 已安装但 `ollama list` 为空；没有本地 Qwen 模型，也没有 GPT/Qwen API 环境凭据。本轮没有下载 32B 或小参数 Qwen，因为 CPU 运行时延不具客户代表性，小模型也不能证明 32B 修正质量。

执行：

```powershell
$env:PYTHONPATH = (Resolve-Path 'drawing-standard-poc').Path
.\.venv-local-cpu\Scripts\python.exe -B -m unittest discover `
  -s drawing-standard-poc\backend\tests -p 'test_*.py' -v

.\.venv-local-cpu\Scripts\python.exe -B `
  scripts\benchmark_llm_correction.py --rows 200
```

结果：

| 项目 | 结果 |
|---|---:|
| 后端 unittest | 14/14 通过 |
| 管口表专项测试 | 11/11 通过 |
| 客户基线 `f5dda07` 专项测试 | 11/11 通过 |
| 客户候选 Compose config | 使用临时占位 `.env` 通过，测试后已删除；存在原有 `version` obsolete warning |
| 合成表行数 | 200 |
| 合成 Markdown | 13,600 chars |
| 旧契约输入 | 13,738 chars |
| 旧契约预期输出 | 13,600 chars |
| 新契约 LLM 输入 | 466 chars，1 个歧义行 |
| 新契约 LLM 输出 | 83 chars，JSON patch |
| 输入字符负载下降 | 96.61% |
| 输出字符负载下降 | 99.39% |
| 本地规则修正 | 20 个规则事件 |
| 最终修改单元格 | 42 个 |
| 本地总处理 | 约 4–7 ms，含 fake LLM 往返，不含真实模型推理 |

专项测试覆盖：MinerU 表头触发、无需修改、年份末位右漂、标准首字母左漂、双漂移、标签/属性/正文精确保留、合并或嵌套 HTML 保守跳过、仅歧义行入模、思考模式关闭参数、Token usage 采集、幻觉补丁拒绝、缺配置 fail closed；其中一项通过本机临时 OpenAI-compatible HTTP 端点验证真实 SDK 请求序列化。

## 5. 客户现场 A/B 验收

必须使用同一批脱敏或受控客户样本、同一 Qwen 服务、同一并发和同一时间窗口比较优化前 checkpoint 与 `perf(llm)` 提交。

建议至少覆盖：

- 20 份无漂移表：确认全部不调用 LLM且输出字节一致。
- 20 份常见单漂移/双漂移表：确认规则完成且不调用 LLM。
- 10 份真实歧义/失败样本：确认 JSON patch、拒绝路径和人工复核标记。
- 多页大 Markdown 与并发 1/4/8：分离文档大小和排队影响。

每次请求采集：

1. 实际模型名、revision、量化、GPU、tensor parallel、最大上下文和推理服务版本。
2. 总耗时、排队时间、prefill 时间、decode 时间、prompt/completion/reasoning tokens、tokens/s。
3. 文档字符数、目标表数量、候选行数、是否调用 LLM、补丁是否通过本地校验。
4. 修正前后目标单元格差异和人工判定；禁止把客户原文写入普通应用日志。

验收门槛：

- 非目标内容和 HTML 结构零变化。
- 常见已知漂移 100% 走本地规则，不触发 LLM。
- LLM 请求不包含完整文档，输出预算不超过 512 tokens。
- 超时/异常不阻断 MinerU 主输出，原文可人工复核。
- 在客户样本上无修正准确率回退后，再以现场 p50/p95 确认 4–5 分钟问题是否消除。

## 6. 部署与回退

当前 React 开发线与 `origin/master` 客户候选线没有共同祖先，直接 cherry-pick 会在历史 Qwen 集成文件产生冲突。已基于最新 `origin/master@1676ff2` 创建独立分支 `codex/customer-llm-perf-20260825`，人工完成冲突移植并提交为 `f5dda07`；该提交只包含性能代码、受控配置、测试和基准脚本。不要把本地 CPU 提交、`.env.local`、模型目录或生成输出带入客户环境。

`f5dda07` 已在本机使用客户基线代码完成 11/11 管口表专项测试与 200 行负载基准，但未推送、未连接客户模型、未部署。现场仍需按第 5 节执行 A/B 和回退验证后才能作为 Customer-Go。

最低配置：

```dotenv
NOZZLE_CORRECTION_ENABLED=true
LLM_CORRECTION_ENABLED=true
LLM_BASE_URL=http://YOUR_INTERNAL_QWEN_ENDPOINT/v1
LLM_API_KEY=REPLACE_WITH_SECRET
LLM_MODEL=/models/YOUR_QWEN_MODEL
LLM_PROVIDER=qwen-vllm
LLM_DISABLE_THINKING=true
LLM_MAX_OUTPUT_TOKENS=512
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=0
LLM_MAX_ROWS_PER_REQUEST=20
```

分级回退：

1. 仅关闭 LLM：`LLM_CORRECTION_ENABLED=false`，保留毫秒级本地规则。
2. 关闭全部管口表后处理：`NOZZLE_CORRECTION_ENABLED=false`。
3. Git 回退：回到优化前 checkpoint，或 revert 单独的 `perf(llm)` 提交。

客户环境切换前必须备份原配置并记录部署 SHA；新旧版本均保留 MinerU 原始/基础 patched Markdown，不能只保留自动修正结果。
