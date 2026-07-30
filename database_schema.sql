# table_layout_service4.py 用于后面继续调整  table_layout_service5.py在4的基础上增加了长宽比不协调表的固定裁剪(目前前后端用的5)
# mineru_img2md_test.py  用于后面继续调整  - 图片转md
# test_standard.py用于后面继续调整 - 测试标准号提取和比对功能

# 图纸标准比对系统 - 数据库表结构设计

## 数据库信息
- **数据库类型**: MySQL 8.0+
- **字符集**: utf8mb4
- **排序规则**: utf8mb4_unicode_ci
- **设计日期**: 2026-05-27

---

## 表结构总览

| 表名 | 说明 | 核心用途 |
|------|------|----------|
| `pdf_task` | PDF 解析任务表 | 记录用户上传的 PDF 文件和解析任务状态 |
| `table_image` | 表格图片表 | 存储从 PDF 中拆分出的表格图片信息 |
| `table_markdown` | 表格 Markdown 表 | 存储表格图片解析后的 Markdown 内容 |
| `standard_extracted` | 标准号提取结果表 | 存储从 Markdown 中提取的标准编号 |
| `standard_comparison` | 标准比对结果表 | 存储标准号与标准库的比对结果 |
| `standard_data` | 标准库表（已有） | 存储标准库基础数据 |

---

## DDL 语句

### 1. PDF 解析任务表 (pdf_task)

**用途**: 记录用户上传的 PDF 文件和整个解析任务的生命周期

```sql
CREATE TABLE `pdf_task` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '任务ID，主键自增',
  `task_id` VARCHAR(64) NOT NULL COMMENT '任务唯一标识，UUID格式，用于关联所有子资源',
  `user_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '上传用户ID，未登录用户可为NULL',
  `original_filename` VARCHAR(255) NOT NULL COMMENT '原始文件名，如 "02.194-1-A1(E-420310).pdf"',
  `file_size` BIGINT NOT NULL DEFAULT 0 COMMENT '文件大小，单位：字节',
  `file_path` VARCHAR(500) NOT NULL COMMENT 'PDF 文件存储路径，相对路径或绝对路径',
  `page_count` INT NOT NULL DEFAULT 0 COMMENT 'PDF 总页数',
  
  -- 任务状态
  `status` TINYINT NOT NULL DEFAULT 0 COMMENT '任务状态: 0-待处理, 1-解析中, 2-已完成, 3-失败, 4-已取消',
  `progress` DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT '任务进度百分比，0.00-100.00',
  `current_step` VARCHAR(100) DEFAULT NULL COMMENT '当前执行步骤描述，如 "正在解析表格图片"',
  
  -- 统计信息
  `table_count` INT NOT NULL DEFAULT 0 COMMENT '识别到的表格总数',
  `standard_count` INT NOT NULL DEFAULT 0 COMMENT '提取的标准号总数',
  `exact_match_count` INT NOT NULL DEFAULT 0 COMMENT '完全符合的标准号数量',
  `year_mismatch_count` INT NOT NULL DEFAULT 0 COMMENT '年份不一致的标准号数量',
  `similar_count` INT NOT NULL DEFAULT 0 COMMENT '较为相似的标准号数量',
  `not_found_count` INT NOT NULL DEFAULT 0 COMMENT '不存在的标准号数量',
  
  -- 错误信息
  `error_message` TEXT DEFAULT NULL COMMENT '错误信息，任务失败时记录详细错误原因',
  
  -- 时间戳
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '任务创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  `started_at` DATETIME DEFAULT NULL COMMENT '任务开始处理时间',
  `completed_at` DATETIME DEFAULT NULL COMMENT '任务完成时间',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_id` (`task_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='PDF解析任务表';
```

**字段说明**:
- `task_id`: 核心关联字段，所有子表都通过此字段关联到具体任务
- `status`: 任务状态机，便于前端展示进度和状态
- `progress`: 支持小数进度，更精确地展示处理进度
- 统计字段: 便于快速查询比对结果摘要，无需实时计算

---

### 2. 表格图片表 (table_image)

**用途**: 存储从 PDF 中拆分出的所有表格图片信息

```sql
CREATE TABLE `table_image` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '表格图片ID，主键自增',
  `task_id` VARCHAR(64) NOT NULL COMMENT '关联的任务ID，对应 pdf_task.task_id',
  `table_index` INT NOT NULL COMMENT '表格在 PDF 中的序号，从1开始',
  `page_number` INT NOT NULL COMMENT '表格所在的 PDF 页码，从1开始',
  
  -- 图片信息
  `image_filename` VARCHAR(255) NOT NULL COMMENT '图片文件名，如 "table_001.png"',
  `image_path` VARCHAR(500) NOT NULL COMMENT '图片文件存储路径',
  `image_width` INT NOT NULL DEFAULT 0 COMMENT '图片宽度，单位：像素',
  `image_height` INT NOT NULL DEFAULT 0 COMMENT '图片高度，单位：像素',
  `file_size` BIGINT NOT NULL DEFAULT 0 COMMENT '图片文件大小，单位：字节',
  `dpi` INT NOT NULL DEFAULT 300 COMMENT '图片渲染DPI，影响OCR识别质量',
  
  -- 表格位置信息（可选，用于精确定位）
  `bbox_x` INT DEFAULT NULL COMMENT '表格在PDF页面中的X坐标（左上角）',
  `bbox_y` INT DEFAULT NULL COMMENT '表格在PDF页面中的Y坐标（左上角）',
  `bbox_width` INT DEFAULT NULL COMMENT '表格宽度',
  `bbox_height` INT DEFAULT NULL COMMENT '表格高度',
  
  -- 处理状态
  `ocr_status` TINYINT NOT NULL DEFAULT 0 COMMENT 'OCR处理状态: 0-待处理, 1-处理中, 2-已完成, 3-失败',
  `ocr_error` TEXT DEFAULT NULL COMMENT 'OCR处理错误信息',
  
  -- 时间戳
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_task_table_index` (`task_id`, `table_index`),
  KEY `idx_ocr_status` (`ocr_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='表格图片表';
```

**字段说明**:
- `table_index`: 表格序号，便于按顺序展示和查询
- `bbox_*`: 边界框信息，可选字段，用于前端高亮显示表格位置
- `dpi`: 记录渲染参数，便于追溯和优化 OCR 质量
- `ocr_status`: 独立的 OCR 状态，支持异步处理和错误重试

---

### 3. 表格 Markdown 表 (table_markdown)

**用途**: 存储表格图片经过 OCR 解析后的 Markdown 内容

```sql
CREATE TABLE `table_markdown` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Markdown记录ID，主键自增',
  `task_id` VARCHAR(64) NOT NULL COMMENT '关联的任务ID，对应 pdf_task.task_id',
  `table_image_id` BIGINT UNSIGNED NOT NULL COMMENT '关联的表格图片ID，对应 table_image.id',
  
  -- Markdown 内容
  `markdown_content` MEDIUMTEXT NOT NULL COMMENT '表格的 Markdown 格式内容',
  `markdown_path` VARCHAR(500) DEFAULT NULL COMMENT 'Markdown 文件存储路径（如果保存到文件）',
  `content_length` INT NOT NULL DEFAULT 0 COMMENT 'Markdown 内容长度（字符数）',
  
  -- 解析信息
  `parser_type` VARCHAR(50) NOT NULL DEFAULT 'mineru' COMMENT '解析器类型，如 "mineru", "paddleocr"',
  `parser_version` VARCHAR(50) DEFAULT NULL COMMENT '解析器版本号',
  `confidence_score` DECIMAL(5,2) DEFAULT NULL COMMENT 'OCR 置信度评分，0.00-100.00',
  
  -- 表格类型（用于差异化处理）
  `table_type` VARCHAR(50) DEFAULT NULL COMMENT '表格类型，如 "管口表", "技术参数表", "标准清单表"',
  
  -- 时间戳
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_table_image_id` (`table_image_id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_table_type` (`table_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='表格Markdown表';
```

**字段说明**:
- `markdown_content`: 使用 MEDIUMTEXT 支持较大表格（最大16MB）
- `markdown_path`: 如果同时保存到文件，记录路径便于下载
- `confidence_score`: OCR 置信度，便于评估识别质量
- `table_type`: 表格分类，支持后续差异化处理和统计分析

---

### 4. 标准号提取结果表 (standard_extracted)

**用途**: 存储从 Markdown 中提取的所有标准编号信息

```sql
CREATE TABLE `standard_extracted` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '提取记录ID，主键自增',
  `task_id` VARCHAR(64) NOT NULL COMMENT '关联的任务ID，对应 pdf_task.task_id',
  `table_markdown_id` BIGINT UNSIGNED NOT NULL COMMENT '关联的Markdown记录ID，对应 table_markdown.id',
  
  -- 标准号信息
  `original_text` VARCHAR(255) NOT NULL COMMENT '原始提取文本，如 "GB/T 150.1-2011"',
  `prefix` VARCHAR(20) NOT NULL COMMENT '标准前缀，如 "GB/T", "NB/T", "HG"',
  `standard_type` VARCHAR(20) NOT NULL COMMENT '标准类型，与 prefix 相同',
  `number` VARCHAR(50) NOT NULL COMMENT '标准号数字部分，如 "150.1"',
  `year` VARCHAR(10) NOT NULL COMMENT '年份，如 "2011"',
  `has_t` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否带/T推荐标识: 0-否, 1-是',
  
  -- 位置信息
  `row_index` INT NOT NULL DEFAULT 0 COMMENT '在表格中的行号，从0开始',
  `col_index` INT NOT NULL DEFAULT 0 COMMENT '在表格中的列号，从0开始',
  `cell_text` TEXT DEFAULT NULL COMMENT '所在单元格的完整文本内容',
  
  -- 时间戳
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  
  PRIMARY KEY (`id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_table_markdown_id` (`table_markdown_id`),
  KEY `idx_prefix` (`prefix`),
  KEY `idx_year` (`year`),
  UNIQUE KEY `uk_task_standard` (`task_id`, `original_text`, `row_index`, `col_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标准号提取结果表';
```

**字段说明**:
- `original_text`: 保留原始文本，便于追溯和展示
- `prefix`, `number`, `year`: 结构化存储，便于查询和统计
- `row_index`, `col_index`: 定位标准号在表格中的位置
- `uk_task_standard`: 唯一索引，防止同一任务中重复提取相同的标准号

---

### 5. 标准比对结果表 (standard_comparison)

**用途**: 存储提取的标准号与标准库的比对结果

```sql
CREATE TABLE `standard_comparison` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '比对记录ID，主键自增',
  `task_id` VARCHAR(64) NOT NULL COMMENT '关联的任务ID，对应 pdf_task.task_id',
  `standard_extracted_id` BIGINT UNSIGNED NOT NULL COMMENT '关联的提取记录ID，对应 standard_extracted.id',
  
  -- 比对结果
  `match_status` VARCHAR(20) NOT NULL COMMENT '比对状态: "完全符合", "年份不一致", "较为相似", "不存在", "解析错误"',
  `match_score` INT NOT NULL DEFAULT 0 COMMENT '相似度分数，0-110分',
  
  -- 匹配的标准库信息
  `matched_library_id` BIGINT UNSIGNED DEFAULT NULL COMMENT '匹配到的标准库记录ID，对应 standard_library.id',
  `matched_standard_no` VARCHAR(100) DEFAULT NULL COMMENT '匹配到的标准库标准号',
  `matched_prefix` VARCHAR(20) DEFAULT NULL COMMENT '匹配到的标准库前缀',
  `matched_number` VARCHAR(50) DEFAULT NULL COMMENT '匹配到的标准库编号',
  `matched_year` VARCHAR(10) DEFAULT NULL COMMENT '匹配到的标准库年份',
  
  -- 匹配详情
  `prefix_match` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '前缀是否匹配: 0-否, 1-是',
  `number_match` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '编号是否完全匹配: 0-否, 1-是',
  `main_number_match` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '主编号是否匹配（忽略小数点）: 0-否, 1-是',
  `year_match` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '年份是否匹配: 0-否, 1-是',
  `number_similarity` DECIMAL(5,2) NOT NULL DEFAULT 0.00 COMMENT '编号相似度，0.00-1.00',
  
  -- 说明信息
  `message` VARCHAR(500) DEFAULT NULL COMMENT '比对结果说明，用于前端展示',
  
  -- 时间戳
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_extracted_id` (`standard_extracted_id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_match_status` (`match_status`),
  KEY `idx_match_score` (`match_score`),
  KEY `idx_matched_library_id` (`matched_library_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标准比对结果表';
```

**字段说明**:
- `match_status`: 核心比对结果，直接对应前端的展示状态
- `match_score`: 相似度分数，支持按分数排序和过滤
- `matched_library_id`: 关联到标准库，便于查看标准详情
- `prefix_match`, `number_match` 等: 详细的匹配维度，支持多维度分析
- `number_similarity`: 编号相似度，用于"较为相似"的判定

---

### 6. 标准库表 (standard_library) - 已有

**说明**: 这是你已经存在的表，这里仅做参考

```sql
-- 假设你的标准库表结构如下（根据实际情况调整）
CREATE TABLE `standard_data` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '标准库ID，主键自增',
  `standard_no` VARCHAR(100) NOT NULL COMMENT '完整标准号，如 "GB/T 150.1-2011"',
  `standard_type` VARCHAR(20) NOT NULL COMMENT '标准类型，如 "GB/T"',
  `standard_prefix` VARCHAR(20) NOT NULL COMMENT '标准前缀，如 "GB/T"',

  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_standard_no` (`standard_no`),
  KEY `idx_standard_type` (`standard_type`),
  KEY `idx_standard_prefix` (`standard_prefix`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标准库表';
```

---

## 表关系图

```
pdf_task (1) ─────< (N) table_image (1) ─────< (1) table_markdown (1) ─────< (N) standard_extracted (1) ─────< (1) standard_comparison
                                                                                                                      │
                                                                                                                      │ matched_library_id
                                                                                                                      ↓
                                                                                                              standard_library
```

**关系说明**:
- 一个 PDF 任务包含多个表格图片
- 一个表格图片对应一个 Markdown 记录
- 一个 Markdown 记录包含多个提取的标准号
- 每个提取的标准号对应一个比对结果
- 比对结果关联到标准库中的具体记录

---

## 常用查询示例

### 1. 查询任务的完整比对报告

```sql
SELECT 
  pt.task_id,
  pt.original_filename,
  pt.status,
  pt.table_count,
  pt.standard_count,
  pt.exact_match_count,
  pt.year_mismatch_count,
  pt.similar_count,
  pt.not_found_count,
  pt.progress,
  pt.created_at,
  pt.completed_at
FROM pdf_task pt
WHERE pt.task_id = 'your-task-id';
```

### 2. 查询某个任务的所有表格图片

```sql
SELECT 
  ti.id,
  ti.table_index,
  ti.page_number,
  ti.image_filename,
  ti.image_path,
  ti.image_width,
  ti.image_height,
  ti.ocr_status,
  tm.markdown_content
FROM table_image ti
LEFT JOIN table_markdown tm ON ti.id = tm.table_image_id
WHERE ti.task_id = 'your-task-id'
ORDER BY ti.table_index;
```

### 3. 查询某个任务的比对结果详情

```sql
SELECT 
  se.original_text,
  se.prefix,
  se.number,
  se.year,
  sc.match_status,
  sc.match_score,
  sc.matched_standard_no,
  sc.message,
  sc.number_similarity
FROM standard_extracted se
INNER JOIN standard_comparison sc ON se.id = sc.standard_extracted_id
WHERE se.task_id = 'your-task-id'
ORDER BY sc.match_score DESC;
```

### 4. 统计比对结果分布

```sql
SELECT 
  match_status,
  COUNT(*) as count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM standard_comparison
WHERE task_id = 'your-task-id'
GROUP BY match_status;
```

### 5. 查询某个标准号在哪些任务中出现过

```sql
SELECT 
  pt.task_id,
  pt.original_filename,
  se.original_text,
  sc.match_status,
  sc.matched_standard_no,
  pt.created_at
FROM standard_extracted se
INNER JOIN standard_comparison sc ON se.id = sc.standard_extracted_id
INNER JOIN pdf_task pt ON se.task_id = pt.task_id
WHERE se.original_text = 'GB/T 150.1-2011'
ORDER BY pt.created_at DESC;
```

---

## 索引优化建议

### 核心索引（已包含在DDL中）
1. `task_id` 相关索引 - 支持按任务查询所有关联数据
2. `match_status` 索引 - 支持按比对状态过滤
3. `standard_extracted_id` 唯一索引 - 保证一对一关系

### 可选索引（根据查询频率添加）
```sql
-- 如果经常按标准前缀查询
ALTER TABLE standard_extracted ADD INDEX idx_prefix_year (prefix, year);

-- 如果经常按日期范围查询任务
ALTER TABLE pdf_task ADD INDEX idx_created_date (DATE(created_at));

-- 如果经常查询特定匹配分数的结果
ALTER TABLE standard_comparison ADD INDEX idx_score_range (match_score, match_status);
```

---

## 数据迁移建议

### 1. 从旧系统迁移
```sql
-- 如果有旧数据，可以使用 INSERT INTO ... SELECT 语句迁移
INSERT INTO pdf_task (task_id, original_filename, file_path, status, table_count, created_at)
SELECT 
  old_task_id,
  filename,
  file_path,
  2, -- 已完成
  table_count,
  created_at
FROM old_task_table;
```

### 2. 批量导入标准库
```sql
-- 从CSV文件导入标准库数据
LOAD DATA INFILE '/path/to/standard_library.csv'
INTO TABLE standard_library
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(standard_no, standard_type, standard_prefix, standard_name);
```

---

## 性能优化建议

### 1. 分区表（大数据量时）
```sql
-- 如果任务量很大，可以按月份分区
ALTER TABLE pdf_task PARTITION BY RANGE (YEAR(created_at) * 100 + MONTH(created_at)) (
  PARTITION p202601 VALUES LESS THAN (202602),
  PARTITION p202602 VALUES LESS THAN (202603),
  PARTITION p202603 VALUES LESS THAN (202604),
  -- ... 更多分区
  PARTITION pmax VALUES LESS THAN MAXVALUE
);
```

### 2. 定期清理历史数据
```sql
-- 清理30天前的已完成任务（根据业务需求调整）
DELETE FROM pdf_task 
WHERE status = 2 
  AND completed_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

---

## 执行方式

### 在 MySQL 客户端执行
```bash
mysql -u your_username -p your_database < database_schema.sql
```

### 在 MySQL Workbench 中执行
1. 打开 MySQL Workbench
2. 连接到你的数据库
3. 打开此文件
4. 点击执行按钮（⚡）

### 分表执行（推荐）
如果表较多，建议逐个执行 CREATE TABLE 语句，便于排查错误。

---

## 后续扩展建议

1. **用户权限表**: 如果需要多用户系统，可以添加用户表和权限控制
2. **操作日志表**: 记录用户的操作历史，便于审计
3. **文件存储表**: 统一管理文件存储路径和元数据
4. **缓存表**: 缓存热门查询结果，提升性能
5. **消息队列表**: 支持异步任务处理和解耦

---

## 版本历史

| 版本 | 日期 | 说明 | 作者 |
|------|------|------|------|
| 1.0 | 2026-05-27 | 初始版本，包含核心业务表 | AI Assistant |

---

## 联系方式

如有问题或需要调整表结构，请联系开发团队。
