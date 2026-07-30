# Drawing Review POC

工程图纸标准信息识别与内容审查系统（POC）

---

# 1. 项目简介

本项目用于实现：

> 从工程图纸 PDF 中自动识别标准引用信息，并与企业标准库进行比对审查。

系统主要能力包括：

- 图纸 PDF 上传
- 图纸表格区域识别
- 表格内容 OCR / 结构化解析
- 标准编号自动提取
- 标准库比对
- 审查结果输出
- 异常项提示与人工复核辅助

当前版本为 POC（Proof of Concept）验证版本，目标是快速验证业务闭环和识别可行性。

---

# 2. 技术架构

## 整体流程

```text
PDF图纸
↓
PP-DocLayout_plus-L 表格区域识别
↓
表格区块裁剪
↓
MinerU StructEqTable 表格结构解析
↓
Markdown / JSON
↓
标准号规则提取
↓
标准库匹配
↓
LLM辅助校验
↓
审查结果输出
```

---

# 3. 技术栈

## Backend

- Python 3.11+
- FastAPI
- Uvicorn

## Frontend

- Vue3
- Element Plus

## OCR / Document Parsing

### Table Detection

- PaddleOCR
- PP-DocLayout_plus-L

### Table Structure Parsing

- MinerU StructEqTable

---

# 4. 项目目录结构

```text
drawing-review-poc/
├── app/
│   ├── api/
│   │   ├── upload_api.py
│   │   ├── task_api.py
│   │   └── review_api.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── constants.py
│   │
│   ├── services/
│   │   ├── pdf_service.py
│   │   ├── table_detect_service.py
│   │   ├── table_parse_service.py
│   │   ├── standard_extract_service.py
│   │   ├── standard_match_service.py
│   │   ├── llm_service.py
│   │   └── report_service.py
│   │
│   ├── models/
│   │   ├── paddle/
│   │   └── mineru/
│   │
│   ├── utils/
│   │   ├── file_utils.py
│   │   ├── regex_utils.py
│   │   └── markdown_utils.py
│   │
│   └── main.py
│
├── data/
│   ├── input/
│   ├── output/
│   ├── temp/
│   ├── markdown/
│   ├── tables/
│   └── standards/
│       └── standard_library.xlsx
│
├── frontend/
│   └── vue-project/
│
├── tests/
│
├── docs/
│   ├── requirement.md
│   ├── api_design.md
│   └── prompt_design.md
│
├── requirements.txt
├── config.yaml
└── README.md
```

---

# 5. 核心模块说明

## 5.1 PDF上传模块

功能：

- 上传单个PDF
- 上传多个PDF
- 保存任务记录

输入：

```text
PDF文件
```

输出：

```text
任务ID
文件路径
```

---

## 5.2 表格区域识别模块

模型：

```text
PP-DocLayout_plus-L
```

功能：

- 图纸版式识别
- 表格区域定位
- 表格区块切分

输入：

```text
PDF页面图片
```

输出：

```json
[
  {
    "page": 1,
    "bbox": [x1, y1, x2, y2],
    "type": "table"
  }
]
```

输出文件：

```text
data/tables/
```

---

## 5.3 表格结构解析模块

模型：

```text
MinerU StructEqTable
```

功能：

- 表格结构识别
- OCR文本提取
- Markdown生成
- JSON结构输出

输入：

```text
表格区块图片
```

输出：

```json
{
  "markdown": "...",
  "cells": [],
  "text": "..."
}
```

Markdown输出：

```md
| 标准号 | 名称 |
|---|---|
| GB/T 150 | 压力容器 |
```

---

## 5.4 标准号提取模块

功能：

- 从Markdown中提取标准编号
- 标准号归一化

示例：

```text
GB/T 150.1
NB/T 47041-2014
HG/T 20592
SH/T 3404
```

当前方案：

- 正则规则提取（主）
- LLM辅助校验（辅）

---

## 5.5 标准库匹配模块

功能：

- 标准号归一化
- 标准库比对
- 年份检查
- 模糊匹配

结果类型：

| 类型 | 说明 |
|---|---|
| 完全匹配 | 标准号与年份一致 |
| 年份不一致 | 标准存在但版本不同 |
| 疑似匹配 | OCR可能识别错误 |
| 不存在 | 标准库未找到 |

---

## 5.6 LLM辅助模块

LLM不作为主识别链路，仅用于：

- OCR异常修正
- 标准号补全
- 模糊结果辅助判断
- 审查意见生成

---

# 6. 开发阶段规划

## Phase 1：版式识别验证

目标：

```text
PDF → 表格区域识别
```

验证：

- 表格是否漏检
- 表格裁剪是否完整

---

## Phase 2：表格结构解析

目标：

```text
表格截图 → Markdown
```

验证：

- 表格结构是否错乱
- 标准号是否串行
- OCR是否可读

---

## Phase 3：标准号提取

目标：

```text
Markdown → 标准号清单
```

验证：

- 提取准确率
- 格式归一化

---

## Phase 4：标准库比对

目标：

```text
标准号 → 审查结果
```

验证：

- 完全匹配
- 年份不一致
- 不存在
- 疑似项

---

## Phase 5：Web页面

目标：

- PDF上传
- 任务查询
- 结果展示

---

# 7. 环境安装

## 创建虚拟环境

```bash
python -m venv venv
```

Windows：

```bash
venv\Scripts\activate
```

Linux：

```bash
source venv/bin/activate
```

---

## 安装依赖

```bash
pip install -r requirements.txt
```

---

# 8. 模型安装

## PaddleOCR

```bash
pip install paddleocr
pip install paddlepaddle
```

---

## MinerU

```bash
pip install -U "mineru[all]"
```

---

## StructEqTable

```bash
pip install struct-eqtable
```

---

# 9. 启动项目

## 启动后端

```bash
uvicorn app.main:app --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

---

## 启动Vue前端

```bash
cd frontend/vue-project

npm install

npm run dev
```

---

# 10. 配置说明

## config.yaml

```yaml
ocr:
  table_detector: paddle

table_parser:
  provider: mineru

llm:
  provider: qwen

system:
  upload_dir: data/input
  output_dir: data/output
```

---

# 11. POC阶段限制说明

当前版本仅用于POC验证：

- 不保证所有图纸格式兼容
- 不保证生产级准确率
- 不包含权限系统
- 不包含任务调度集群
- 不包含高可用部署
- 不包含复杂审计功能

---

# 12. 后续规划

未来可扩展：

- GPU推理服务
- OCR置信度体系
- 人工复核工作流
- 审查报告导出
- 标准库治理平台
- 多模态大模型识别
- 企业知识库联动

---

# 13. 推荐开发原则

建议：

- 小步开发
- 每次只实现一个模块
- 所有中间结果落文件
- 先规则后LLM
- 先离线验证再页面开发
- 优先验证业务闭环

---

# 14. 当前POC推荐路线

推荐：

```text
PP-DocLayout_plus-L
+
MinerU StructEqTable
+
规则提取
+
标准库比对
+
LLM辅助校验
```

原因：

- 与需求文档一致
- 支持复杂图纸表格
- 可私有化
- 后续易扩展生产化

---

# 15. 开发协作方式

推荐：

- Git共享仓库
- 小步提交
- Issue驱动开发
- 每日结果Review

建议流程：

```text
需求拆解
↓
开发实现小模块
↓
AI辅助生成代码
↓
本地验证
↓
提交代码
↓
Review结果
↓
进入下一阶段
```

---

# 16. License

POC Internal Use Only.
