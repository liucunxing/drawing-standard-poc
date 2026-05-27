# 项目进度与资产总账

本文是 Drawing Standard POC 的唯一项目级进度与资产总账。README 只作为入口文档；后续阶段状态、分支资产、风险和推进路径以本文为准。

## 1. 项目背景与目标

本项目目标是围绕工程图纸/PDF 建立标准信息识别与内容审查 POC，覆盖以下流程：

- 文档/图纸输入
- 版面检测
- 区域切割
- 表格识别
- 字段映射
- 人工校验
- 后端联调和结果管理

当前优先验证“图纸中可能包含标准号或审查信息的区域能否被稳定定位、裁剪，并作为后续表格识别输入”。

## 2. 当前总体状态

- 前端原型已有阶段性成果：根目录 `streamlit_app.py` 是 Streamlit 轻量原型，包含总览工作台、新上传任务、结果查看等页面方向。
- 旧版图纸切割已验证过基础能力：本地存在 `new_table_parsing`、`table_parsing_klu` 等历史分支和 `drawing-standard-poc/backend/scripts/` 相关脚本；准确边界待人工确认。
- 新版图纸切割重构分支效果较好：当前分支 `feature/phase1-layout-governance-opus` 下的 `poc_layout_refactor/` 已能输出 layout overlay、final candidate JSON 和 crop 图片。
- table-recognition 尚未正式启动：下一步准备基于新版切割结果继续推进，不建议再从旧版切割分支直接延展。

## 3. Phase 规划

### Phase 0：项目初始化与样例验证

- 目标：明确 POC 目标、样例图纸、基础流程和验证边界。
- 输入：工程图纸/PDF 样例、需求说明、历史实验代码。
- 输出：需求文档、工作流文档、样例验证结论。
- 当前状态：已有 `docs/requirement.md`、`docs/workflow.md`、`docs/api_design.md` 等基础文档；样例资产和历史验证边界仍需人工复核。
- 相关目录/分支：`docs/`、`data/`、`master`。
- 暂不处理内容：生产部署、权限系统、完整数据库建模。

### Phase 1：前端原型与页面拆分

- 目标：形成可演示的图纸识别流程页面，支撑上传、任务总览和结果查看。
- 输入：演示任务数据、预期结果结构、前端交互需求。
- 输出：Streamlit 原型页面、任务总览、上传页、结果查看页。
- 当前状态：`streamlit_app.py` 已包含总览工作台、新上传任务、结果查看；代码注释显示当前不调用真实后端，使用演示数据或规范化占位结构。
- 相关目录/分支：根目录 `streamlit_app.py`、`requirements-streamlit.txt`、本地分支 `kaixin/frontend`。
- 暂不处理内容：真实任务队列、真实 OCR 后端、最终 UI 视觉定稿。

### Phase 2：图纸版面检测与图片切割

- 目标：对 PDF 图纸进行低 DPI layout 检测、高 DPI crop 裁剪，输出少量稳定的业务候选区域。
- 输入：单页 PDF、layout 配置、zone 配置。
- 输出：低/高 DPI 渲染图、layout raw JSON、layout overlay、candidate JSON、candidate overlay、candidate crop 图片、debug report。
- 当前状态：新版重构分支 `feature/phase1-layout-governance-opus` 已完成阶段性收尾，当前 sample 输出 6 个 final candidates。
- 相关目录/分支：`poc_layout_refactor/`、当前分支 `feature/phase1-layout-governance-opus`。
- 暂不处理内容：OCR、表格结构识别、标准号提取、数据库入库、FastAPI 接口。

### Phase 3：表格识别验证

- 目标：基于 Phase 2 输出的 crop 图片验证表格识别能力。
- 输入：`poc_layout_refactor/output/{pdf_name}/candidates/candidate_*.png`。
- 输出：HTML / Markdown / CSV / JSON 等表格识别结果，以及 crop 图与识别结果对比。
- 当前状态：尚未正式启动。
- 相关目录/分支：建议从 `feature/phase1-layout-governance-opus` 切出 `feature/table-recognition`；本地 `new_table_parsing`、`table_parsing_klu` 可作为历史参考，待人工确认。
- 暂不处理内容：数据库入库、完整字段业务映射、最终审查结论自动化。

### Phase 4：字段映射、结果校验与人工修正

- 目标：将表格识别结果映射为业务字段，提取标准号并支持人工校验。
- 输入：表格识别 JSON / Markdown / CSV、标准号候选文本、业务字段规则。
- 输出：字段映射结果、标准号候选、人工校验清单、异常项。
- 当前状态：待启动。
- 相关目录/分支：待人工确认。
- 暂不处理内容：生产级标准库治理、复杂权限和审计。

### Phase 5：前后端联调、结果管理与交付演示

- 目标：完成前端、后端、识别结果和人工校验流程的演示闭环。
- 输入：Phase 3/4 的结构化结果、前端页面、后端接口草案。
- 输出：可演示的任务流程、结果查看、人工修正和交付材料。
- 当前状态：待启动。
- 相关目录/分支：`streamlit_app.py`、`drawing-standard-poc/backend/`、待确认的后端集成分支。
- 暂不处理内容：高可用部署、企业级权限、生产任务调度。

## 4. 当前分支与资产状态

| 分支名称 | 功能定位 | 当前状态 | 主要产物 | 是否推荐作为后续主线 | 后续动作 |
|---|---|---|---|---|---|
| `master` | 基础主分支 | 本地存在，具体内容待人工确认 | README、docs、历史基础代码 | 否，需先比对当前重构分支 | 人工确认是否接收文档和切割重构成果 |
| `kaixin/frontend` | 前端原型分支 | 本地存在，疑似前端展示资产 | Streamlit 或前端原型相关成果，待人工确认 | 仅作为前端联调参考 | 后续与真实 table-recognition 结果联调 |
| `new_table_parsing` | 旧版切割/表格解析相关分支 | 本地存在，提交点较新，具体边界待人工确认 | 历史表格解析/切割资产，待人工确认 | 否，作为历史验证资产 | 只做思路对比，合并前需人工确认可复用代码 |
| `table_parsing_klu` | 旧版切割/表格解析相关分支 | 本地存在，具体边界待人工确认 | 历史表格解析/切割资产，待人工确认 | 否，作为历史验证资产 | 只做历史结果对比，不建议延展为主线 |
| `feature/phase1-layout-governance-opus` | 新版图纸切割重构分支 | 当前分支，Phase 2 效果较好 | `poc_layout_refactor/`、layout overlay、candidate crop、debug report | 是 | 文档收尾后作为 `feature/table-recognition` 基础 |
| `feature/table-recognition` | 后续表格识别分支 | 尚未创建 | 计划输出 HTML / Markdown / CSV / JSON 表格识别结果 | 是，建议从当前分支切出 | 基于新版 crop 图片验证 MinerU / StructEqTable / StructTable |

当前 git 信息：

- 当前分支：`feature/phase1-layout-governance-opus`
- 本地分支：`feature/phase1-layout-governance-opus`、`kaixin/frontend`、`master`、`new_table_parsing`、`table_parsing_klu`
- 最近提交：`4bfbf81 opus modification version`、`949bcd4 improvement`、`f7a73f8 revert frontend` 等
- 当前未提交修改：`poc_layout_refactor/config.yaml`、`poc_layout_refactor/run_pipeline.py`、`poc_layout_refactor/src/cropper.py`、`poc_layout_refactor/src/pdf_render.py`

## 5. 新版图纸切割重构分支说明

当前分支 `feature/phase1-layout-governance-opus` 用于图纸版面检测和图片切割能力的重构版本。该分支的定位是 Phase 2 主线资产：

- 使用 PyMuPDF 渲染 PDF。
- 使用 PP-DocLayout_plus-L 做区域检测。
- 将 layout box 统一为 page_ratio 坐标。
- 按业务 zone 收敛候选区域。
- 从高 DPI 渲染图裁剪 final candidate crop。
- 输出 overlay、debug report、manifest 和可人工验收的中间资产。

当前重构版切割效果优于旧版分支。后续表格识别应优先基于当前分支输出的 crop 图片继续推进。当前分支完成文档收尾后，可作为 `feature/table-recognition` 的基础。

## 6. 旧版切割分支说明

旧版切割相关分支保留为历史验证资产：

- 可用于对比早期切割思路和历史结果。
- 不建议作为后续主线继续开发。
- 如需合并旧版分支代码，应人工确认是否还有可复用代码。
- 当前无法从分支名完全确认各分支的精确责任边界，标记为待人工确认。

涉及分支：

- `new_table_parsing`：待人工确认。
- `table_parsing_klu`：待人工确认。

## 7. 前端分支说明

当前前端资产主要用于流程展示和页面原型：

- 根目录 `streamlit_app.py` 是 Streamlit 轻量原型。
- 已涉及总览工作台、新上传任务、结果查看等页面方向。
- 代码注释显示当前 Streamlit 页面不调用真实后端，主要通过 demo 数据和规范化结构模拟任务结果。
- 本地分支 `kaixin/frontend` 疑似前端分支，具体差异待人工确认。
- 当前前端可以用于流程演示，但不代表最终识别准确率。
- 后续需要与 table-recognition 的真实 crop、表格识别结果和调试 JSON 联调。

## 8. 图片切割结果使用说明

新版切割输出默认位于：

```text
poc_layout_refactor/output/{pdf_name}/
```

以当前 sample 为例：

```text
poc_layout_refactor/output/sample/
├── page_1_lowdpi.png
├── page_1_highdpi.png
├── layout_boxes_raw.json
├── layout_boxes_raw_overlay.png
├── candidate_regions_raw.json
├── candidate_regions_merged.json
├── candidate_regions_overlay.png
├── dropped_candidates.json
├── stage1_manifest.json
├── debug_report.md
├── roi_images/
└── candidates/
    ├── candidate_001_layout_roi_right_top_table.png
    ├── candidate_002_layout_roi_right_column_text.png
    ├── candidate_003_layout_roi_right_middle_table.png
    ├── candidate_004_layout_full_x_table.png
    ├── candidate_005_merged_layout_x_table.png
    └── candidate_006_layout_roi_right_bottom_table.png
```

使用约定：

- crop 图片目录：`poc_layout_refactor/output/{pdf_name}/candidates/`
- layout json：`layout_boxes_raw.json`、`candidate_regions_raw.json`、`candidate_regions_merged.json`
- layout 可视化结果：`layout_boxes_raw_overlay.png`、`candidate_regions_overlay.png`
- 原始渲染图片：`page_1_lowdpi.png`、`page_1_highdpi.png`
- 后续 table-recognition 应读取 `candidate_regions_merged.json` 中对应的 final candidates，并使用 `candidates/candidate_*.png` 作为输入。
- 当前 crop 结果主要用于人工验收和表格识别输入。
- 当前阶段不要直接入库。
- 当前阶段不要直接做字段业务映射。

## 9. 前端当前状态

根据当前代码检查：

- 当前前端是 Streamlit 轻量原型。
- 页面包括：总览工作台、新上传任务、结果查看。
- 结果查看中包括图纸识别结果、表格解析结果、标准提取比对结果、技术调试信息等 tab。
- 上传页支持选择 PDF 并创建演示任务。
- 代码内存在 `normalize_backend_result(payload)`，说明为后续真实后端响应预留了规范化入口。
- 代码注释显示当前 POC 不调用真实后端，演示识别结果由本地 demo 数据模拟。
- 哪些前端分支内容已合并到当前分支：待人工确认。
- 后续联动方式：table-recognition 输出 crop 图片和识别结构后，前端展示原始 crop 图与识别结果对比，并将调试 JSON 展示给人工验收。

## 10. 下一步 table-recognition 计划

建议下一阶段从当前新版切割重构分支切出：

```text
feature/table-recognition
```

计划范围：

- 读取 `poc_layout_refactor/output/{pdf_name}/candidates/candidate_*.png`。
- 验证 MinerU / StructEqTable / StructTable 的表格识别效果。
- 输出 HTML / Markdown / CSV / JSON。
- 在前端展示原始 crop 图与识别结果对比。
- 重点验证工程图纸表格的识别准确率、合并单元格、密集表格线、特殊符号和工程字体问题。

暂不处理：

- 暂不做数据库入库。
- 暂不做完整字段业务映射。
- 暂不做标准库比对闭环。
- 暂不做任务队列和生产接口封装。

## 11. 当前风险与待确认事项

- PP-DocLayout_plus-L / layout 模型只负责区域检测，不具备语义判断能力，裁剪是否准确需要通过可视化、兜底和人工验收确认。
- MinerU / 表格 OCR 对工程图纸字体、密集表格线、特殊符号、合并单元格可能识别不稳定。
- 官方桌面版样例识别也可能存在错误，后续需要通过代码调参、样例扩展和人工校验评估通用性。
- 前端当前可能只是原型，不能代表最终识别准确率。
- 多分支并行开发，需要明确后续主线，避免旧切割、新切割、前端、表格识别混乱。
- `drawing-standard-poc/backend/` 中历史后端资产的可用状态待人工确认。
- `kaixin/frontend` 与当前 `streamlit_app.py` 的差异待人工确认。
- `new_table_parsing`、`table_parsing_klu` 的具体功能边界和可复用代码待人工确认。
- 根目录没有 `scripts/` 和 `outputs/`；嵌套目录 `drawing-standard-poc/backend/scripts/` 存在历史脚本，是否仍作为有效资产待人工确认。

## 12. 文档维护规则

- `docs/progress.md` 是唯一项目级进度文档。
- 后续新增模块文档时，应放在 `docs/modules/` 下，并由 `docs/progress.md` 引用。
- 不要创建多个 progress 文件。
- 不要创建重复 README 或 asset 总账文档。
- 每次新功能分支完成后，需要更新 `docs/progress.md`。
- 合并同事分支前，需要人工确认分支状态和功能边界。
- 文档整理任务中不要修改功能代码、前端页面、模型调用、识别流程或业务逻辑。
