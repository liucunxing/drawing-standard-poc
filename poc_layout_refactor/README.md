# 图纸 Layout Detection 离线调试版

这是一个全新的、独立于现有系统实现的第一阶段 POC pipeline。它只做：

PDF page 1 渲染 → 固定规则 ROI → PP-DocLayout_plus-L 区域检测 → 候选区域构建与合并 → 高 DPI 裁剪 → 调试结果输出。

当前阶段不包含 OCR、表格解析、标准号提取、标准库比对、前端、数据库、任务队列或 FastAPI 接口。

## 目录结构

```text
poc_layout_refactor/
├── README.md
├── requirements.txt
├── config.yaml
├── run_pipeline.py
├── src/
│   ├── __init__.py
│   ├── pdf_render.py
│   ├── layout_detect.py
│   ├── roi_builder.py
│   ├── candidate_builder.py
│   ├── cropper.py
│   ├── visualize.py
│   └── utils.py
└── output/
    └── .gitkeep
```

## 安装依赖

建议在独立虚拟环境中安装：

```powershell
cd poc_layout_refactor
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PaddleOCR 首次运行 `PP-DocLayout_plus-L` 时会下载模型权重。如果无法访问 HuggingFace，可按 PaddleOCR 官方文档设置：

```powershell
$env:PADDLE_PDX_MODEL_SOURCE="BOS"
```

Windows 下建议直接使用 `.\.venv\Scripts\python.exe -m pip`，避免激活脚本、PowerShell 执行策略或多个 Python 版本导致 `pip` 指向错误环境。

如果 PowerShell 提示符变成 `>>`，表示当前命令还没有闭合，通常是引号、括号或多行输入未结束。先按 `Ctrl+C` 回到 `PS ...>` 提示符，再重新执行命令。

如果 `.venv\Scripts\python.exe` 报 `Unable to create process`，建议把虚拟环境建到纯英文路径，例如：

```powershell
python -m venv C:\venvs\drawing-layout
C:\venvs\drawing-layout\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
C:\venvs\drawing-layout\Scripts\python.exe -m pip install -r "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor\requirements.txt"
C:\venvs\drawing-layout\Scripts\python.exe "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor\run_pipeline.py" --pdf "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor\samples\sample.pdf" --output "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor\output"
```

如果 `python -m venv .venv` 在 `ensurepip` 阶段被中断，`.venv` 很可能不完整。可以删除后重建：

```powershell
Remove-Item -LiteralPath .\.venv -Recurse -Force
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 运行

仓库内已经放了一份调试样本：

```text
poc_layout_refactor/samples/sample.pdf
```

运行后可以直接检查 overlay 标记图和候选区域截图：

```powershell
cd "D:\MyLife\09_工作资料\0910_南京石化\99_Workspace\drawing-standard-poc\poc_layout_refactor"
.\.venv\Scripts\python.exe .\run_pipeline.py --pdf ".\samples\sample.pdf" --output ".\output"
```

也可以使用任意外部 PDF：

```powershell
cd poc_layout_refactor
python run_pipeline.py --pdf "D:\path\to\sample.pdf" --output "output"
```

也可以显式指定配置：

```bash
python run_pipeline.py --pdf "D:\path\to\sample.pdf" --output "output" --config "config.yaml"
```

## 输出

每个 PDF 会输出到：

```text
output/{pdf_name}/
```

主要文件包括：

- `page_1_lowdpi.png`: 低 DPI 整页预览图，用于 layout detection 和人工检查。
- `page_1_highdpi.png`: 高 DPI 整页图，仅用于高清候选区域裁剪。
- `roi_definitions.json`: 固定规则 ROI 的 page_ratio 坐标定义。
- `roi_{roi_name}.png`: 每个固定 ROI 的低 DPI 截图。
- `full_page_layout_raw.json`: 整页 layout detection 原始归一化结果。
- `full_page_layout_overlay.png`: 整页 layout 检测框标注图。
- `roi_{roi_name}_layout_raw.json`: ROI 内 layout detection 结果，已转换回 page_ratio。
- `roi_{roi_name}_layout_overlay.png`: ROI 局部检测框标注图。
- `precise_table_regions.json`: 默认只保留 `table` 且 `score >= 0.5` 的精准表格框，不做相邻合并。
- `precise_table_regions_overlay.png`: 精准表格框标注图。
- `candidate_regions_raw.json`: 合并前候选区域。
- `candidate_regions_merged.json`: 按业务 zone 合并后的最终候选区域，统一使用 page_ratio 坐标。
- `candidate_regions_overlay.png`: 最终候选区域标注图。
- `candidates/candidate_{region_id}.png`: 只根据 `candidate_regions_merged.json` 从高 DPI 图裁剪出的最终候选区域。
- `summary.json`: 本次运行摘要。
- `debug_report.md`: 便于人工检查的调试报告。

## 坐标约定

所有候选区域对外统一使用 `page_ratio` 坐标：

```json
[x1_ratio, y1_ratio, x2_ratio, y2_ratio]
```

其中左上角为 `[0, 0]`，右下角为 `[1, 1]`。

## 当前限制

- 仅处理 PDF 第 1 页。
- 默认只做离线文件输出，不提供服务接口。
- PP-DocLayout_plus-L 只用于区域定位，不做 OCR。
- 候选合并策略偏召回优先，仍需要结合真实图纸样本调参。
- 固定 ROI 是启发式比例区域，暂未按图框线、标题栏结构或图纸比例自适应。

## 下一步建议

1. 用多种横版、竖版真实图纸跑批量样本，微调 ROI 比例、阈值和合并参数。
2. 对 candidate crops 接入 OCR，但仍保持离线调试输出。
3. 在候选区域上增加标准号正则提取和人工可验收报告。
4. 引入标题栏、明细表、技术要求等区域类型的后处理分类。
5. 最后再考虑接入 API、任务队列、数据库和前端。
