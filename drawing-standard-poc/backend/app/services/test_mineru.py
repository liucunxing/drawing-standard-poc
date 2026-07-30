"""
测试 MinerU structeqtable 表格识别（使用 rapid_table）
输入：表格区块图像
输出：MARKDOWN格式的表格文本
模型：rapid_table (MinerU 使用的表格识别模型)
"""

from pathlib import Path
import cv2
import numpy as np
from rapid_table import RapidTable, RapidTableInput
from paddleocr import PaddleOCR


def image_to_markdown(image_path: str, output_dir: str = None) -> str:
    """
    使用 rapid_table 模型将表格图像转换为 Markdown
    
    Args:
        image_path: 表格图像路径
        output_dir: 输出目录，默认为图像同目录下的 markdown 文件夹
        
    Returns:
        Markdown 格式的表格文本
    """
    # 检查图像是否存在
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"图像文件不存在: {image_path}")
    
    # 设置输出目录
    if output_dir is None:
        output_dir = image_path.parent / "markdown_output"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"输入图像: {image_path}")
    print(f"输出目录: {output_dir}")
    
    # 读取图像
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"无法读取图像: {image_path}")
    
    print(f"图像尺寸: {img.shape[1]}x{img.shape[0]}")
    
    try:
        # 初始化 OCR 模型
        print("正在初始化 PaddleOCR 模型...")
        ocr_engine = PaddleOCR(lang='ch')
        print("OCR 模型初始化成功")
        
        # 进行 OCR 识别
        print("正在进行 OCR 文字识别...")
        ocr_result = ocr_engine.predict(img)
        
        # 提取 OCR 结果供 rapid_table 使用
        # PaddleOCR 3.x 返回的是列表，每个元素是字典
        ocr_data = []
        if ocr_result and len(ocr_result) > 0:
            # 获取第一页的结果
            page_result = ocr_result[0]
            
            # 从字典中提取 rec_polys, rec_texts 和 rec_scores
            if 'rec_polys' in page_result and 'rec_texts' in page_result:
                rec_polys = page_result['rec_polys']
                rec_texts = page_result['rec_texts']
                rec_scores = page_result.get('rec_scores', [1.0] * len(rec_texts))
                
                for i in range(len(rec_texts)):
                    bbox = rec_polys[i] if i < len(rec_polys) else None
                    text = rec_texts[i]
                    score = rec_scores[i] if i < len(rec_scores) else 1.0
                    if bbox is not None:
                        ocr_data.append([bbox, text, score])
        
        print(f"OCR 识别完成，识别到 {len(ocr_data)} 个文本块")
        
        # 初始化 rapid_table 模型
        print("正在初始化 rapid_table 模型...")
        
        # 配置模型参数
        config = RapidTableInput(
            model_type="slanet_plus",  # 使用 SLANetPlus 模型
            device="cpu",  # 如果有 GPU 可以改为 "cuda"
        )
        
        table_engine = RapidTable(config)
        print("rapid_table 模型初始化成功")
        
        # 对图像进行表格识别
        print("正在进行表格结构识别...")
        
        # 调用模型进行识别，传入 OCR 结果
        result = table_engine(img, ocr_result=ocr_data)
        
        print(f"识别完成!")
        print(f"识别结果类型: {type(result)}")
        
        # 提取 HTML 内容
        html_content = ""
        markdown_content = ""
        
        if hasattr(result, 'pred_html'):
            html_content = result.pred_html
            print(f"找到表格 HTML (pred_html)，长度: {len(html_content)}")
        elif hasattr(result, 'html'):
            html_content = result.html
            print(f"找到表格 HTML，长度: {len(html_content)}")
        
        if html_content:
            markdown_content = convert_html_to_markdown(html_content)
            
            # 保存 Markdown 文件
            output_md_path = output_dir / f"{image_path.stem}.md"
            output_md_path.write_text(markdown_content, encoding="utf-8")
            print(f"✅ Markdown 已保存: {output_md_path}")
            
            # 同时保存 HTML 用于对比查看
            output_html_path = output_dir / f"{image_path.stem}.html"
            output_html_path.write_text(html_content, encoding="utf-8")
            print(f"✅ HTML 已保存: {output_html_path}")
            
            # 打印预览
            print(f"\n========== Markdown 内容预览 ==========")
            preview = markdown_content[:1000] if len(markdown_content) > 1000 else markdown_content
            print(preview)
            print("========================================\n")
            
            return markdown_content
        
    except Exception as e:
        print(f"识别失败: {e}")
        import traceback
        traceback.print_exc()
        raise


def convert_html_to_markdown(html_str: str) -> str:
    """
    将 HTML 表格字符串转换为 Markdown 表格
    """
    import re
    
    rows = []
    
    # 按 <tr> 分割
    tr_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL)
    td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
    
    for tr_match in tr_pattern.finditer(html_str):
        tr_content = tr_match.group(1)
        cells = []
        for td_match in td_pattern.finditer(tr_content):
            # 清理内部标签和空白
            cell_text = re.sub(r'<[^>]+>', '', td_match.group(1))
            cell_text = cell_text.strip()
            cells.append(cell_text if cell_text else " ")
        
        if cells:
            rows.append(cells)
    
    # 生成 Markdown
    if not rows:
        return ""
    
    md_lines = []
    for i, row in enumerate(rows):
        md_lines.append("| " + " | ".join(row) + " |")
        if i == 0:  # 表头后加分隔线
            md_lines.append("| " + " | ".join(["---"] * len(row)) + " |")
    
    return "\n".join(md_lines)


def test_mineru_table():
    """测试函数 - 使用写死的图像路径"""
    # 写死的图片路径（管口表）
    image_path = Path(r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\table_blocks\9ceb33f3e2a5\page_001_table_002.png")
    
    # 输出目录
    output_dir = Path(r"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\markdown\test_mineru")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 调用图像转 Markdown 函数
        markdown_content = image_to_markdown(
            image_path=str(image_path),
            output_dir=str(output_dir)
        )
        
        if markdown_content:
            print("✅ 表格识别成功!")
        else:
            print("❌ 表格识别失败，未获取到内容")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    test_mineru_table()
# 核心代码逻辑
# 使用 PaddleOCR 3.x 进行文字识别
# 将 OCR 结果传给 rapid_table 模型识别表格结构
# 模型输出 HTML 格式表格
# 将 HTML 转换为 Markdown 格式
# 保存结果文件