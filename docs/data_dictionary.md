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
| drawing_no | string | 图号 |
| drawing_name | string | 图纸名称 |
| project_name | string | 项目名称 |
| project_no | string | 项目号 |
| owner_doc_no | string | 业主文件号 |
| equipment_name | string | 设备名称 |
| equipment_tag | string | 设备位号 |
| design_stage | string | 设计阶段 |
| discipline | string | 专业 |
| scale | string | 比例 |
| revision_no | string | 版本/修订号 |
| issue_date | string/date | 出图日期 |

## 3. drawing_metadata 图纸元数据

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 元数据记录 ID |
| task_id | string/int | 所属任务 |
| file_id | string/int | 所属文件 |
| page_no | int | 页码 |
| field_name | string | 字段名 |
| field_value | string | 字段值 |
| source_text | text | OCR 原文 |
| bbox | json | 来源区域 bbox |
| confidence | float | 抽取置信度 |
| review_status | string | 待复核/已确认/已修正 |

## 4. table_block 表格区块

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 表格区块 ID |
| task_id | string/int | 所属任务 |
| file_id | string/int | 所属文件 |
| page_no | int | 页码 |
| bbox | json | [x1, y1, x2, y2] |
| image_path | string | 裁剪后的表格图片路径 |
| confidence | float | 表格检测置信度 |
| block_type | string | 标准/技术参数表、管口表、材料明细表、标题栏、签审栏、技术要求、其它 |
| participate_review | bool | 是否进入标准审查链路 |
| page_width | int | 渲染后页面宽度 |
| page_height | int | 渲染后页面高度 |
| render_scale | float | PDF 渲染缩放比例 |
| render_dpi | int | PDF 渲染 DPI |

## 5. parsed_table 表格解析结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 解析结果 ID |
| table_block_id | string/int | 对应表格区块 |
| markdown | text | Markdown 表格文本 |
| json_content | json | 单元格结构化结果 |
| raw_text | text | OCR 原始文本 |
| confidence | float | 表格解析置信度 |

## 6. extracted_standard 标准提取结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 标准提取记录 ID |
| parsed_table_id | string/int | 来源表格 |
| original_text | string | 图纸中识别出的原文 |
| normalized_code | string | 归一化标准号 |
| standard_year | string | 标准年份 |
| confidence | float | 提取置信度 |
| source_type | string | 表格/技术要求文本/标题栏/其它 |
| source_block_id | string/int | 来源区块 ID |

## 7. standard_library 标准库

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

## 8. standard_match_result 比对结果

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string/int | 比对结果 ID |
| extracted_standard_id | string/int | 标准提取记录 |
| matched_standard_id | string/int | 匹配到的标准库记录 |
| result_type | string | 完全符合/年份不一致/相似匹配/不存在/待人工复核 |
| similarity | float | 相似度 |
| review_comment | text | 审查意见 |
