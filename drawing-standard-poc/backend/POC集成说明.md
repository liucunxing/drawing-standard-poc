# 工程图纸标准比对系统 - 项目说明文档

## 📋 项目概述

### 项目背景与意图

本工程图纸标准比对系统是一个面向石化、化工等工程行业的智能化图纸识别与标准核验工具。项目旨在解决传统工程图纸审核过程中存在的人工效率低、标准号核验困难、易出错等痛点问题。

**核心目标：**
1. **自动化图纸解析**：从PDF工程图纸中自动识别并提取表格信息（图签表、管口表、技术参数表、标准引用表等）
2. **智能标准号提取**：从表格文本中自动提取标准编号（如 GB/T 150.1-2011、HG/T 20580-2024 等）
3. **标准库自动比对**：将提取的标准号与企业标准库进行智能匹配，识别标准版本有效性
4. **辅助人工审核**：生成结构化比对报告，辅助工程师快速定位标准引用问题

**技术路线：**
- 前端：Streamlit（Python Web框架，快速原型开发）
- 后端：FastAPI + Uvicorn（高性能异步API服务）
- 布局检测：PaddleOCR PP-DocLayout模型
- 表格识别：MinerU（struct_eqtable模型）
- 标准号提取：正则表达式 + 规则引擎
- 标准比对：Levenshtein编辑距离算法
- 数据库：MySQL 8.0+

---

## 🚀 项目进展

### ✅ 已完成功能

#### 1. 前端界面（Streamlit）
- [x] 总览工作台：展示任务统计、进度概览、历史任务列表
- [x] 新上传任务：PDF文件上传、任务创建、多步骤操作界面
- [x] 结果查看：任务详情、图纸识别结果、表格解析结果、标准比对结果
- [x] 四步操作流程：
  - **步骤1：上传PDF** - 支持多文件选择，上传至后端服务器
  - **步骤2：开始识别** - 调用布局检测模型，提取表格图片
  - **步骤3：转为Markdown** - 使用MinerU将表格图片转换为Markdown格式
  - **步骤4：标准检测** - 从Markdown中提取标准号并与标准库比对

#### 2. 后端服务（FastAPI）
- [x] PDF上传接口（POST /api/drawing/upload-pdf）
- [x] 表格解析接口（POST /api/drawing/process-tables）
- [x] Markdown转换接口（POST /api/drawing/convert-to-markdown）
- [x] 标准检测接口（POST /api/drawing/detect-standards）
- [x] 任务状态查询接口（GET /api/drawing/task/{task_id}/parse-status）
- [x] 文件访问服务（GET /api/files/{filepath}）
- [x] Swagger API文档（http://localhost:8000/docs）

#### 3. 核心算法模块
- [x] **布局检测**（table_layout_service.py）
  - 基于PaddleOCR PP-DocLayout_plus-L模型
  - 支持双分辨率策略：布局检测（zoom=1.5）+ OCR识别（zoom=3.2）
  - 表格智能分割：基于空白区域的表格切分算法
  - 管口表特殊处理：长宽比检测 + 固定比例切割（70%）
  
- [x] **表格识别**（mineru_img2md.py）
  - 基于MinerU Pipeline + struct_eqtable模型
  - 智能膨胀预处理（smart_dilate_v2）：解决字符粘连问题
  - 图像缩放增强：DPI 300 + 1.5x缩放
  - 法兰标准补丁：自动修复 HG/HO/HC 前缀变异
  - 大图切分识别：超过1MB或高度>3600px自动切分
  
- [x] **标准号提取与比对**（identify_standard.py）
  - 支持18种标准前缀：GB/T、NB/T、HG/T、SH/T、SY/T、JB/T 等
  - 智能提取：支持HTML表格格式和纯文本格式
  - 比对算法：Levenshtein编辑距离 + 多维度相似度计算
  - 比对结果分类：
    - ✅ 完全符合（100分）
    - ⚠️ 年份不一致
    - 🔵 较为相似（≥30%相似度）
    - ❌ 不存在

#### 4. 数据库集成
- [x] MySQL数据库连接池（SQLManager）
- [x] pdf_task表：任务状态管理、进度跟踪、统计信息
- [x] 参数化查询防SQL注入
- [x] 自动事务管理
- [x] 线程安全设计

#### 5. 前后端联调
- [x] 完整四步流程联调通过
- [x] 任务状态同步机制
- [x] 文件路径转换（本地路径 ↔ URL）
- [x] 错误处理与用户提示

---

## 📝 项目待做（重点）

### 🔧 图像识别优化（高优先级）

#### 1. 布局检测精度提升
- [ ] **模型调优**：针对工程图纸特性，微调PP-DocLayout模型
- [ ] **小表格检测**：提高面积占比<0.1%的小表格召回率
- [ ] **重叠表格处理**：解决嵌套表格、重叠表格的分割问题
- [ ] **非表格区域过滤**：降低图例、标注等非表格区域的误检率

#### 2. 表格识别质量优化
- [ ] **复杂表格处理**：
  - 合并单元格识别
  - 跨页表格拼接
  - 倾斜表格矫正
- [ ] **OCR精度提升**：
  - 低分辨率表格超分增强
  - 特殊符号识别（如 ℃、MPa、φ 等）
  - 数字与字母粘连分离（如 "1N" → "1 N"）
- [ ] **MinerU模型替换**：评估更新的表格识别模型（如 RapidTable）

#### 3. 管口表识别专项优化
- [ ] **智能切割算法改进**：
  - 当前固定70%切割过于简单
  - 需要基于内容密度自动定位切割点
  - 支持多段切割（超过2段的管口表）
- [ ] **标题识别**：管口表标题与数据区域的关联
- [ ] **表格线修复**：虚线、点划线表格的完整识别

### 🤖 标准检测智能化（高优先级）

#### 1. LLM模型接入
- [ ] **上下文理解**：利用LLM理解标准号所在单元格的语义
- [ ] **模糊匹配增强**：
  - 处理OCR错误（如 "GB/T 150.1-20?4" → "GB/T 150.1-2024"）
  - 处理缩写变异（如 "GB150" → "GB/T 150"）
- [ ] **标准版本推理**：根据图纸设计年代推断最可能的标准版本
- [ ] **多标准号关联**：识别表格中的标准号引用关系

#### 2. 标准库完善
- [ ] **标准关系图谱**：建立标准之间的替代、引用关系
- [ ] **废止标准标记**：标注已废止标准及其替代标准
- [ ] **标准分类体系**：按专业（工艺、设备、管道、仪表等）分类
- [ ] **增量更新机制**：支持标准库的定期更新

#### 3. 比对报告增强
- [ ] **可视化展示**：比对结果的图形化展示
- [ ] **一键导出**：生成Excel/PDF格式的比对报告
- [ ] **差异高亮**：标注标准号差异的具体位置
- [ ] **建议生成**：自动给出标准替换建议

### 🎨 前端优化（中优先级）

#### 1. 用户体验提升
- [ ] **进度条实时显示**：WebSocket实时推送任务进度
- [ ] **表格图片预览优化**：
  - 放大/缩小功能
  - 对比查看（原图 vs 识别结果）
  - 批量下载
- [ ] **Markdown编辑器**：支持手动修正识别结果
- [ ] **响应式设计**：适配不同屏幕尺寸

#### 2. 功能增强
- [ ] **任务批量处理**：支持一次上传多个PDF并自动处理
- [ ] **历史对比**：同一图纸不同版本的比对结果对比
- [ ] **审核流程**：支持多角色审核（识别→复核→审批）
- [ ] **权限管理**：用户登录、任务权限控制

#### 3. 性能优化
- [ ] **懒加载**：大量表格图片的分页加载
- [ ] **缓存机制**：常用数据的本地缓存
- [ ] **异步处理**：长时间任务的后台队列处理

### 🗄️ 数据库完善（中优先级）

#### 1. 表结构扩展
- [ ] **table_image表**：记录表格图片元数据
- [ ] **table_markdown表**：存储Markdown内容
- [ ] **standard_extracted表**：记录提取的标准号
- [ ] **standard_comparison表**：记录比对结果详情

#### 2. 数据管理
- [ ] **数据清理**：定期清理过期任务数据
- [ ] **备份策略**：数据库自动备份
- [ ] **性能优化**：索引优化、查询优化

### 🔒 生产环境准备（低优先级）

- [ ] **Docker容器化**：Docker Compose一键部署
- [ ] **日志系统**：结构化日志记录
- [ ] **监控告警**：任务失败告警、性能监控
- [ ] **安全加固**：文件上传限制、XSS防护、CSRF防护

---

## 🛠️ 项目环境准备

### 基础环境要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10.x | 推荐使用 Anaconda/Miniconda 管理环境 |
| MySQL | 8.0+ | 本地开发可用 Docker 容器 |
| 操作系统 | Windows 10+/Ubuntu 20.04+ | 推荐使用 Linux 服务器部署 |
| 内存 | ≥16GB | PaddleOCR 模型加载需要较大内存 |
| 硬盘 | ≥50GB | 模型文件+临时文件+输出文件 |
| GPU（可选） | NVIDIA CUDA 11.8+ | 有GPU可大幅提升识别速度 |

### 1. Python环境配置

```bash
# 1. 创建Python 3.10虚拟环境（推荐使用conda）
conda create -n drawing-poc python=3.10
conda activate drawing-poc

# 2. 进入项目目录
cd D:\work\Develop\drawing-poc\drawing-standard-poc

# 3. 安装依赖（使用清华镜像源加速）这里不建议用命令全装, 测试时按需要下载
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**重要依赖说明：**
- `paddlepaddle==3.0.0`：飞桨深度学习框架
- `paddleocr==3.5.0`：OCR识别引擎
- `paddlex==3.5.2`：PaddleX工具链
- `magic-pdf==1.3.12`：MinerU核心库
- `fastapi==0.136.1`：后端Web框架
- `streamlit`：前端框架（需单独安装，见下方）

### 2. 数据库配置

#### 2.1 创建数据库

```sql
-- 1. 创建数据库
CREATE DATABASE `drawing-poc` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 2. 使用数据库
USE `drawing-poc`;
```

#### 2.2 创建数据表

**⚠️ 重要提示**：请按照 `database_schema.sql` 文件中的DDL语句，依次执行创建以下6个数据表：

| 表名 | 说明 | 核心用途 |
|------|------|----------|
| `pdf_task` | PDF解析任务表 | 记录用户上传的PDF文件和解析任务状态 |
| `table_image` | 表格图片表 | 存储从PDF中拆分出的表格图片信息 |
| `table_markdown` | 表格Markdown表 | 存储表格图片解析后的Markdown内容 |
| `standard_extracted` | 标准号提取结果表 | 存储从Markdown中提取的标准编号 |
| `standard_comparison` | 标准比对结果表 | 存储标准号与标准库的比对结果 |
| `standard_data` | 标准库表（已有） | 存储标准库基础数据 |

**执行方式：**

```bash
# 方式1：命令行执行
mysql -u root -p drawing-poc < D:\work\Develop\drawing-poc\database_schema.sql

# 方式2：MySQL Workbench
# 打开 MySQL Workbench → 连接数据库 → 打开 database_schema.sql → 点击执行按钮（⚡）
```

**⚠️ 特别注意**：
- `standard_data` 表需要**手动导入**用户提供的标准库数据（Excel/CSV格式）
- 标准库数据导入示例：

```sql
-- 从CSV文件导入标准库数据
LOAD DATA INFILE 'D:/path/to/standard_library.csv'
INTO TABLE standard_data
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(standard_no, standard_type, standard_prefix);
```

#### 2.3 配置数据库连接

**配置文件位置**：`drawing-standard-poc/backend/config/setting.py`

**默认配置**：
```python
DEFAULTS = {
    "MYSQL_HOST": "localhost",
    "MYSQL_PORT": "3306",
    "MYSQL_DB": "drawing-poc",
    "MYSQL_USER": "root",
    "MYSQL_PASSWORD": "root",
}
```

**修改个人本地数据库账户名或密码**：

方式1：直接修改 `setting.py` 文件（不推荐）

方式2：使用环境变量（推荐）

在项目根目录创建 `.env` 文件：
```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=drawing-poc
MYSQL_USER=你的用户名
MYSQL_PASSWORD=你的密码
```

**测试数据库连接**：
```bash
cd D:\work\Develop\drawing-poc\drawing-standard-poc\backend
python test_db_connection.py
```

### 3. 模型与环境测试

**⚠️ 重要**：在启动项目之前，必须先测试两个核心脚本能否在本地跑通！

#### 3.1 测试表格布局检测（table_layout_service5.py）

**步骤：**

1. **修改模型路径**（第64行）：
```python
# 将此行
default_models_root = Path(r"D:\work\Develop\conda_envs\.paddlex\official_models")

# 修改为你的本地模型路径，例如：
default_models_root = Path(r"C:\Users\YourName\.paddlex\official_models")
```

2. **修改测试PDF路径**（第951行）：
```python
# 将此行
local_pdf = Path(r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\25.918-1 A1.pdf")

# 修改为你本地的测试PDF路径，例如：
local_pdf = Path(r"D:\your_path\test_drawing.pdf")
```

3. **运行测试**：
```bash
cd D:\work\Develop\drawing-poc\drawing-standard-poc\backend\app\services
python table_layout_service5.py
```

**预期输出**：
```
[testP] init pipeline: LayoutDetection (stable mode)
[testP] [1/4] converting PDF pages to images...
[testP] rendered 1 page(s) in 2.34s
[testP] [2/4] page 1: image saved -> ...
[testP] [3/4] page 1: layout parsed in 1.56s
[testP] [4/4] page 1: annotated image -> ...
[testP] combo=4.17_2900 done
```

**如果报错**：
- 检查模型路径是否正确
- 检查PDF文件是否存在
- 安装缺失的依赖：`pip install pymupdf paddlepaddle paddleocr`

#### 3.2 测试表格识别（mineru_img2md_test.py）

**步骤：**

1. **确认MinerU模型已下载**：
```bash
# MinerU会自动下载模型到 ~/.mineru 目录
# 首次运行可能需要较长时间下载模型
```

2. **修改测试参数**（第491行）：
```python
# 将此行
TASK_ID = "task001"

# 确保对应的图片目录存在：
# D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\table_blocks\task001\
```

3. **运行测试**：
```bash
cd D:\work\Develop\drawing-poc\drawing-standard-poc\backend\app\services
python mineru_img2md_test.py
```

**预期输出**：
```
================================================================================
MinerU 图片转 Markdown (批量处理)
================================================================================

任务 ID: task001
找到 3 个图片文件

处理: page_001_table_001.png
  Markdown: D:\...\tmp\task001\raw_task001_page_001_table_001.md
  JSON: D:\...\tmp\task001\raw_task001_page_001_table_001.json
  Patched Markdown: D:\...\tmp\task001\patched_task001_page_001_table_001.md
  ...
```

**如果报错**：
- 检查 `magic-pdf` 是否正确安装：`pip show magic-pdf`
- 检查MinerU模型是否下载完成
- 参考 `requirements.txt` 安装所有依赖

**✅ 确认标准**：两个脚本都能成功运行并输出结果后，才能继续下一步！

### 4. 启动后端服务

```bash
# 进入后端目录
cd D:\work\Develop\drawing-poc\drawing-standard-poc\backend

# 运行后端启动脚本
python run.py
```

**启动成功标志**：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**访问Swagger API文档**：
- 打开浏览器访问：http://localhost:8000/docs#/default/
- 可以在此页面测试所有API接口

### 5. 启动前端服务

**打开新的终端窗口**（保持后端运行）：

```bash
# 进入项目根目录
cd D:\work\Develop\drawing-poc

# 安装streamlit（如果未安装）
pip install streamlit -i https://pypi.tuna.tsinghua.edu.cn/simple

# 启动前端应用
streamlit run streamlit_app.py --server.port 8583
```

**启动成功标志**：
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8583
  Network URL: http://192.168.x.x:8583
```

**访问前端界面**：
- 打开浏览器访问：http://localhost:8583

### 6. 功能测试流程

1. **点击左侧导航栏** → 选择"新上传任务"
2. **步骤1：上传PDF**
   - 输入任务名称（可选）
   - 点击"选择文件"上传PDF图纸
   - 点击"开始上传"按钮
3. **步骤2：开始识别**
   - 等待上传成功后，点击"开始识别"
   - 查看表格图片预览
4. **步骤3：转为Markdown**
   - 点击"转为Markdown"按钮
   - 查看Markdown转换结果
5. **步骤4：标准检测**
   - 点击"标准检测"按钮
   - 查看标准号比对结果

---

## 📚 项目结构说明

```
drawing-poc/
├── streamlit_app.py                    # 前端Streamlit应用
├── database_schema.sql                 # 数据库表结构DDL
├── drawing-standard-poc/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   └── routes.py          # API路由定义
│   │   │   ├── services/
│   │   │   │   ├── poc_service.py     # 核心业务逻辑
│   │   │   │   ├── table_layout_service5.py  # 布局检测服务
│   │   │   │   ├── mineru_img2md_test.py     # 表格识别服务
│   │   │   │   └── identify_standard.py      # 标准号提取与比对
│   │   │   └── main.py                # FastAPI应用入口
│   │   ├── config/
│   │   │   ├── setting.py             # 数据库配置
│   │   │   └── config.py              # SQLManager数据库访问类
│   │   ├── tmp/                       # 临时文件目录
│   │   │   ├── uploads/               # 上传的PDF文件
│   │   │   ├── page_images/           # 页面渲染图片
│   │   │   ├── table_blocks/          # 表格裁剪图片
│   │   │   └── markdown/              # Markdown输出文件
│   │   └── run.py                     # 后端启动脚本
│   └── requirements.txt               # Python依赖列表
└── data/
    ├── standards/
    │   └── standard_library.xlsx      # 标准库数据（需导入数据库）
    └── samples/
        └── pdf/                       # 测试PDF样例
```

---

## 🔍 常见问题排查

### 1. 模型加载失败
```
Error: Model directory not found
```
**解决**：检查 `table_layout_service5.py` 第64行的模型路径是否正确

### 2. 数据库连接失败
```
pymysql.err.OperationalError: (2003, "Can't connect to MySQL server")
```
**解决**：
- 检查MySQL服务是否启动
- 检查 `.env` 文件中的数据库配置
- 测试连接：`mysql -u root -p`

### 3. MinerU识别报错
```
ModuleNotFoundError: No module named 'magic_pdf'
```
**解决**：`pip install magic-pdf==1.3.12`

### 4. 端口占用
```
ERROR: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)
```
**解决**：
- 后端：修改 `run.py` 中的端口号
- 前端：`streamlit run streamlit_app.py --server.port 8584`

### 5. PaddleOCR PIR转换错误
```
NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute
```
**解决**：已在代码中设置环境变量禁用PIR，如仍报错，尝试：
```bash
pip install paddlepaddle==3.0.0
```

---

## 📞 技术支持

- **项目文档**：参见 `drawing-standard-poc/backend/POC集成说明.md`
- **API文档**：启动后端后访问 http://localhost:8000/docs
- **数据库设计**：参见 `database_schema.sql`
- **依赖清单**：参见 `drawing-standard-poc/requirements.txt`

---

## 📅 版本历史

| 版本 | 日期 | 说明 | 作者 |
|------|------|------|------|
| 1.0 | 2026-05-29 | 初始版本，完成前后端联调 | 开发团队 |

---

## 🎯 后续规划

本项目正在持续开发完善中，后续将重点推进：

1. **图像识别精度提升** - 针对工程图纸特性优化模型
2. **LLM智能标准检测** - 接入大语言模型增强语义理解
3. **前端交互优化** - 提升用户体验和操作效率
4. **生产环境部署** - Docker容器化、监控告警、权限管理

---

**更新日期**：2026-05-29  
**文档版本**：v1.0
