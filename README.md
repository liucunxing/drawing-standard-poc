# Drawing Standard POC

工程图纸标准信息识别与内容审查 POC。

本项目围绕工程图纸/PDF 的版面检测、图片切割、表格识别和后续结构化抽取展开。当前仓库包含前端原型、历史后端/解析资产，以及新版图纸切割重构 pipeline。README 只作为项目入口，详细阶段状态、分支说明和资产总账以 [docs/progress.md](docs/progress.md) 为准。

## 项目目标

建立一个面向工程图纸/PDF 的 POC 流程，逐步完成图纸输入、版面检测、候选区域切割、表格识别、标准号与字段结构化抽取、人工校验，以及后续前后端联调和结果管理。

## 当前能力概览

- 前端原型/页面展示能力：根目录 `streamlit_app.py` 提供 Streamlit 轻量原型，包含总览工作台、新上传任务、结果查看等展示流程。
- 图纸版面检测能力：`poc_layout_refactor/` 中使用 PyMuPDF 渲染 PDF，并调用 PP-DocLayout_plus-L 做 layout 区域检测。
- 图片切割能力：新版图纸切割重构分支已能输出按业务 zone 收敛后的候选 crop 图片。
- layout 可视化能力：pipeline 会输出 layout raw boxes overlay、candidate overlay、debug report 等人工验收资产。
- table-recognition 待启动：后续计划基于新版 crop 图片验证 MinerU / StructEqTable / StructTable 等表格识别方案。

## 关键目录

```text
.
├── README.md
├── AGENTS.md
├── streamlit_app.py
├── requirements-streamlit.txt
├── docs/
│   ├── progress.md
│   ├── requirement.md
│   ├── workflow.md
│   ├── api_design.md
│   ├── data_dictionary.md
│   ├── prompt_design.md
│   └── review_rules.md
├── poc_layout_refactor/
│   ├── run_pipeline.py
│   ├── config.yaml
│   ├── config/zones.yaml
│   ├── src/
│   ├── samples/
│   └── output/
└── drawing-standard-poc/
    └── backend/
```

说明：

- `streamlit_app.py`：当前前端原型入口，主要用于流程展示和结果查看演示。
- `poc_layout_refactor/`：新版离线图纸版面检测与图片切割 pipeline，是后续 table-recognition 的推荐基础。
- `poc_layout_refactor/output/{pdf_name}/`：layout JSON、overlay 图、candidate crop 图片和 debug report 的默认输出位置。
- `drawing-standard-poc/backend/`：历史后端/解析相关资产，当前状态和是否继续作为主线需人工确认。
- `docs/progress.md`：唯一项目级进度与资产总账。

## 如何运行

### Streamlit 前端原型

```powershell
cd "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc"
python -m pip install -r requirements-streamlit.txt
streamlit run streamlit_app.py
```

当前前端主要用于流程演示；是否已经对接真实识别结果，请以 [docs/progress.md](docs/progress.md) 中的当前状态为准。

### 新版图纸切割 pipeline

```powershell
cd "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor"
.\.venv\Scripts\python.exe .\run_pipeline.py --pdf ".\samples\sample.pdf" --output ".\output"
```

典型输出：

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
```

## 文档入口

- [docs/progress.md](docs/progress.md)：项目进度、分支资产、阶段规划、风险和下一步推进路径。
- [AGENTS.md](AGENTS.md)：后续 Codex / AI coding agent 开发约束。
- [docs/requirement.md](docs/requirement.md)：需求说明。
- [docs/workflow.md](docs/workflow.md)：处理流程说明。
- [docs/api_design.md](docs/api_design.md)：接口设计草案。
- [docs/data_dictionary.md](docs/data_dictionary.md)：数据字典草案。

## 当前推进原则

- README 只保留项目入口级说明。
- 详细阶段状态、资产位置、分支关系和风险统一维护在 `docs/progress.md`。
- 当前新版图纸切割重构分支效果优于旧切割分支，后续建议从该分支切出 `feature/table-recognition`。
- 当前阶段不要直接入库，不要直接做完整字段业务映射，先完成 crop 图片到表格识别结果的离线验证。
