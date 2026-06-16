# =====================================================================
# [上线禁用] 本文件整体禁用！生产环境不允许调用外部大模型API。
# 该文件仅供开发环境测试使用，已在 mineru_img2md.py 中注释了对本文件的 import。
# 如需恢复，请同时取消 mineru_img2md.py 中的 import 注释。
# =====================================================================

import os
from openai import OpenAI

# ========== 配置 ==========
# [安全警告] API密钥禁止提交到代码仓库，生产环境请使用环境变量
API_KEY = ""
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen-plus"  # 如果效果不满意，可以换成 "qwen-max"

# ========== 管口表修复提示词 ==========
_NOZZLE_TABLE_PROMPT_TEMPLATE = """你是一位专业的OCR后处理专家。请严格修复下面HTML/Markdown表格中的**列错位**错误。

## 错误模式（仅限以下3种漂移现象）
1. **末尾字符右漂**："法兰标准"列末尾的字符（通常是年份的最后一位数字，如'8'、'9'、'0'等）被错误截断，漂移到了同行的"法兰类型代号"列开头，使其变成了类似"9 IF"、"8IF"、"0 IF"的形式。
2. **开头字符左漂**："法兰标准"列开头的字符（通常是标准代号的首字母，如'H'）被错误截断，漂移到了同行的前一列"公称尺寸DN"末尾，使其变成了类似"50 H"、"40 G"的形式（即DN列末尾出现了不应有的字母）。
3. **首尾双漂**：同一行可能同时存在上述两种漂移。

## 修复规则（必须遵守）
- 规则1：检查"法兰类型代号"列。如果该列的值以**单个数字**开头（如"9 IF"、"8IF"），将这个开头的数字移回"法兰标准"列的末尾，然后删除"法兰类型代号"列中的该数字前缀（保留原有空格格式）。
- 规则2：检查"公称尺寸DN"列。如果该列的值以**单个字母**结尾（如"50 H"、"40 G"），将这个末尾的字母移回"法兰标准"列的开头，然后删除"公称尺寸DN"列中的该字母后缀，恢复为纯数字。
- 规则3：检查"法兰标准"列。如果值以"G/T"开头（缺失首字母'H'），在开头补回该字母，使其恢复为"HG/T..."。
- 规则4：检查"法兰标准"列。如果值以"-200"结尾（缺失年份最后一位），根据同行"法兰类型代号"列开头漂移过来的数字补全年份。
- **禁令**：严禁修改文档中任何其他内容；严禁改动HTML标签、表格结构、rowspan/colspan属性；严禁推测、润色或补全任何未提及的单元格；严禁将正确的年份（如2008、2010）强制改为2009。

## 待修复文档
{md_content}

## 输出要求
直接输出修复后的完整文档内容，不要添加任何解释、说明或代码块标记（```），保持原始格式。
"""


def fix_nozzle_table_md(md_content: str) -> str:
    """
    调用 Qwen 大模型修复管口表 Markdown 中的列错位错误

    参数:
        md_content: 包含管口表的 Markdown 内容

    返回:
        str: 修复后的 Markdown 内容; 如果调用失败则返回原始内容
    """
    if not md_content or not isinstance(md_content, str):
        return md_content

    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

        prompt = _NOZZLE_TABLE_PROMPT_TEMPLATE.format(md_content=md_content)

        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个严谨的OCR文档修复助手。你只执行用户明确指定的修复规则，绝不修改规则外的任何内容，绝不擅自推测或润色。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=4096
        )

        result = completion.choices[0].message.content
        print(f"[Qwen] 管口表修复完成, 输入长度={len(md_content)}, 输出长度={len(result)}")
        return result

    except Exception as e:
        print(f"[Qwen] 管口表修复失败, 返回原始内容: {e}")
        return md_content


# ========== 以下为独立运行入口（直接执行脚本时使用）==========
if __name__ == '__main__':
    # [上线待替换] 硬编码 Windows 测试路径，生产环境请勿执行
    # INPUT_FILE = r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\markdown\..."
    # OUTPUT_FILE = r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\table_2_fixed.md"
    INPUT_FILE = "./test_input.md"
    OUTPUT_FILE = "./test_output.md"

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        md_content = f.read()

    result = fix_nozzle_table_md(md_content)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(result)

    print("修复完成，已保存到:", OUTPUT_FILE)
    print("\n========== 修复结果预览（前2000字符）==========")
    print(result[:2000])