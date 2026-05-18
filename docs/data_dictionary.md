# 数据字典草案

## 1. review_task 审查任务

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 任务 ID |
| task_name | string | 任务名称 |
| status | string | pending/processing/success/failed/review_required |
| file_count | int | 上传文件数量 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| error_message | string | 失败原因 |

## 2. drawing_file 图纸文件

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 文件 ID |
| task_id | string/int | 所属任务 |
| file_name | string | 原始文件名 |
| file_path | string | 文件保存路径 |
| page_count | int | 页数 |
| status | string | 处理状态 |

## 3. table_block 表格区块

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 表格区块 ID |
| task_id | string/int | 所属任务 |
| file_id | string/int | 所属文件 |
| page_no | int | 页码 |
| bbox | json | [x1, y1, x2, y2] |
| image_path | string | 裁剪后的表格图片路径 |
| confidence | float | 表格检测置信度 |

## 4. parsed_table 表格解析结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 解析结果 ID |
| table_block_id | string/int | 对应表格区块 |
| markdown | text | Markdown 表格文本 |
| json_content | json | 单元格结构化结果 |
| raw_text | text | OCR 原始文本 |
| confidence | float | 表格解析置信度 |

## 5. extracted_standard 标准提取结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 标准提取记录 ID |
| parsed_table_id | string/int | 来源表格 |
| original_text | string | 图纸中识别出的原文 |
| normalized_code | string | 归一化标准号 |
| standard_year | string | 标准年份 |
| confidence | float | 提取置信度 |

## 6. standard_library 标准库

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 标准库记录 ID |
| standard_code | string | 标准号，不含年份 |
| standard_year | string | 标准年份 |
| standard_name | string | 标准名称 |
| status | string | 现行/废止/替代 |
| replaced_by | string | 替代标准 |
| source | string | 数据来源 |
| remark | string | 备注 |

## 7. standard_match_result 比对结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 比对结果 ID |
| extracted_standard_id | string/int | 标准提取记录 |
| matched_standard_id | string/int | 匹配到的标准库记录 |
| result_type | string | 完全符合/年份不一致/相似匹配/不存在/待人工复核 |
| similarity | float | 相似度 |
| review_comment | text | 审查意见 |

