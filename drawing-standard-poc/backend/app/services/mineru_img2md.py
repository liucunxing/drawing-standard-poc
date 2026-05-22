# -*- coding: utf-8 -*-
"""
MinerU 图片转 Markdown 最佳方案

模型配置:
- OCR 模型: MinerU Pipeline (pipeline backend)
- 表格模型: struct_eqtable
- 语言: 中文 (ch)

预处理方案: smart_dilate_v2 (智能膨胀 - 保留表格线版本)
- DPI: 300
- 膨胀核: 2x2 (增加字符间距,解决字符粘连问题)
- 表格线处理: 先膨胀后腐蚀恢复 (在字符和表格线之间制造间隙,避免误识别)
- 缩放: 1.5x (提高图像分辨率,增强 OCR 识别精度)

输出文件:
- {task_id}.md: Markdown 格式的表格识别结果
- {task_id}.json: JSON 格式的中间结果(包含布局信息、边界框等)
"""
import os
import sys
import time
import cv2
import numpy as np
from io import BytesIO
from pathlib import Path
from PIL import Image
import shutil

os.environ['MINERU_MODEL_SOURCE'] = 'local'
os.environ['MINERU_TABLE_MODEL'] = 'struct_eqtable'


def smart_dilate_v2(image, dilate_kernel=(2, 2)):
    """
    智能膨胀 V2:先膨胀,再修复表格线
    
    作用:
    1. 对整个图像进行膨胀(2x2核),增加字符间距,解决字符粘连问题(如 1N 粘连)
    2. 检测膨胀后的表格线(水平线 >= 40px,垂直线 >= 40px)
    3. 腐蚀表格线恢复原始宽度,在字符和表格线之间制造微小间隙
    4. 避免 OCR 将紧贴表格线的字符(如 H)误识别为表格线的一部分
    
    参数:
        image: PIL Image 对象
        dilate_kernel: 膨胀核大小,默认 (2, 2)
    
    返回:
        PIL Image: 预处理后的图像
    """
    # 转换为 OpenCV 灰度图
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # 步骤1: 对整个图像进行膨胀
    # 作用:增加字符间距,解决字符粘连问题(如焊接材料表中的 1N 粘连)
    kernel = np.ones(dilate_kernel, np.uint8)
    dilated = cv2.dilate(gray, kernel, iterations=1)
    
    # 步骤2: 检测膨胀后的表格线
    # 二值化:将图像转为黑白,便于检测线条
    _, binary = cv2.threshold(dilated, 128, 255, cv2.THRESH_BINARY_INV)
    
    # 检测水平线(长度 >= 40 像素的横线)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # 检测垂直线(长度 >= 40 像素的竖线)
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # 合并所有表格线
    table_lines = cv2.add(horizontal_lines, vertical_lines)
    
    # 步骤3: 腐蚀表格线,恢复原始宽度
    # 作用:因为膨胀核是 2x2,表格线会变粗 2 像素,腐蚀掉 1 像素来恢复接近原始宽度
    # 这样可以在字符和表格线之间制造微小间隙,避免 OCR 误识别
    erode_kernel = np.ones((2, 2), np.uint8)
    restored_lines = cv2.erode(table_lines, erode_kernel, iterations=1)
    
    # 步骤4: 将修复后的表格线画回去
    # 在膨胀图像中,将表格线区域设置为黑色(0),保留表格结构
    result = dilated.copy()
    result[restored_lines > 0] = 0  # 黑色表格线
    
    # 转回 PIL Image
    return Image.fromarray(cv2.cvtColor(result, cv2.COLOR_GRAY2RGB))


def image_to_markdown(image_path, task_id, output_dir, dpi=300):
    """
    将图片转换为 Markdown 和 JSON 文件
    
    处理流程:
    1. 加载图片
    2. 智能膨胀预处理(smart_dilate_v2)
    3. 缩放 1.5x
    4. 封装为 PDF(DPI 300)
    5. MinerU 识别
    6. 提取并保存 Markdown 和 JSON 文件
    
    参数:
        image_path: 输入图片路径
        task_id: 任务 ID,用于命名输出文件
        output_dir: 输出目录
        dpi: PDF 封装的 DPI 值,默认 300
    
    返回:
        dict: 包含 md_file 和 json_file 的路径
    """
    import mineru.utils.pdf_image_tools as pdf_image_tools
    from mineru.cli.common import do_parse
    
    # 创建输出目录
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 临时目录(用于 MinerU 的中间输出)
    temp_dir = output_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 步骤1: 加载图片
        image_bytes = image_path.read_bytes()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        
        # 步骤2: 智能膨胀预处理
        processed_image = smart_dilate_v2(image, dilate_kernel=(2, 2))
        
        # 步骤3: 缩放 1.5x(提高分辨率,增强 OCR 识别精度)
        resized_size = (
            int(processed_image.width * 1.5),
            int(processed_image.height * 1.5),
        )
        resized_image = processed_image.resize(resized_size, Image.LANCZOS)
        
        # 步骤4: 保存为字节流
        buffer = BytesIO()
        resized_image.save(buffer, format="PNG")
        resized_bytes = buffer.getvalue()
        
        # 步骤5: 封装为 PDF
        pdf_image_tools.DEFAULT_PDF_IMAGE_DPI = dpi
        pdf_bytes = pdf_image_tools.images_bytes_to_pdf_bytes(resized_bytes)
        
        # 步骤6: MinerU 识别
        do_parse(
            output_dir=str(temp_dir),
            pdf_bytes_list=[pdf_bytes],
            pdf_file_names=["input.pdf"],
            p_lang_list=["ch"],
            backend="pipeline",
            parse_method="auto",
            formula_enable=False,
            table_enable=True,
            f_draw_layout_bbox=False,
            f_draw_span_bbox=False,
            f_dump_md=True,           # 输出 Markdown
            f_dump_middle_json=True,  # 输出 JSON(中间结果)
            f_dump_model_output=False,
            f_dump_orig_pdf=False,
            f_dump_content_list=False,
        )
        
        # 步骤7: 提取 Markdown 和 JSON 文件
        md_files = list(temp_dir.glob("**/*.md"))
        json_files = list(temp_dir.glob("**/*.json"))
        
        if not md_files:
            raise Exception("未找到 Markdown 文件")
        
        # 复制 Markdown 文件到输出目录
        md_source = md_files[0]
        md_target = output_dir / f"{task_id}.md"
        shutil.copy2(md_source, md_target)
        
        # 复制 JSON 文件到输出目录(如果有)
        json_target = None
        if json_files:
            json_source = json_files[0]
            json_target = output_dir / f"{task_id}.json"
            shutil.copy2(json_source, json_target)
        
        return {
            'md_file': str(md_target),
            'json_file': str(json_target) if json_target else None,
        }
        
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def process_task(task_id, table_blocks_dir=None, output_base_dir=None, dpi=300):
    """
    处理整个任务:遍历目录下所有图片并转换为 Markdown 和 JSON
    
    处理流程:
    1. 遍历 table_blocks/{task_id} 下的所有图片文件
    2. 对每个图片调用 image_to_markdown 进行处理
    3. 输出到 output_base_dir/{task_id} 目录
    
    参数:
        task_id: 任务 ID
        table_blocks_dir: 图片源目录,默认为 table_blocks/{task_id}
        output_base_dir: 输出基础目录,默认为 tmp/{task_id}
        dpi: PDF 封装的 DPI 值,默认 300
    
    返回:
        list: 包含所有处理结果的列表
    """
    # 默认路径配置
    task_id = 'task001'
    if table_blocks_dir is None:
        table_blocks_dir = Path(
            rf"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\table_blocks\{task_id}"
        )
    
    if output_base_dir is None:
        output_base_dir = Path(
            rf"D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\{task_id}"
        )
    
    # 确保源目录存在
    if not table_blocks_dir.exists():
        raise FileNotFoundError(f"图片目录不存在: {table_blocks_dir}")
    
    # 创建输出目录
    output_base_dir.mkdir(parents=True, exist_ok=True)
    
    # 遍历所有图片文件(支持 .png, .jpg, .jpeg)
    image_extensions = {'.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG'}
    image_files = [
        f for f in table_blocks_dir.iterdir() 
        if f.is_file() and f.suffix in image_extensions
    ]
    
    # 按文件名排序
    image_files.sort(key=lambda x: x.name)
    
    if not image_files:
        print(f"警告: 在 {table_blocks_dir} 中未找到图片文件")
        return []
    
    print(f"找到 {len(image_files)} 个图片文件")
    
    # 处理每个图片
    results = []
    for image_path in image_files:
        # 使用文件名(不含扩展名)作为 task_id 的一部分
        file_stem = image_path.stem  # 例如: page_001_table_002_s0p66
        file_task_id = f"{task_id}_{file_stem}"
        
        # 输出到 task_id 目录下
        file_output_dir = output_base_dir
        
        print(f"\n处理: {image_path.name}")
        
        try:
            result = image_to_markdown(
                image_path=image_path,
                task_id=file_task_id,
                output_dir=file_output_dir,
                dpi=dpi
            )
            
            print(f"  Markdown: {result['md_file']}")
            if result['json_file']:
                print(f"  JSON: {result['json_file']}")
            
            results.append({
                'image': str(image_path),
                'md_file': result['md_file'],
                'json_file': result['json_file'],
                'success': True
            })
            
        except Exception as e:
            print(f"  错误: {e}")
            results.append({
                'image': str(image_path),
                'error': str(e),
                'success': False
            })
    
    return results


def main():
    """
    主函数:处理任务目录下的所有图片并输出 Markdown 和 JSON 文件
    
    使用示例:
        python mineru_img2md.py
    
    或者在代码中调用:
        from mineru_img2md import process_task
        results = process_task('task001')
    """
    # 任务 ID(实际使用时会从变量传入)
    TASK_ID = "task001"
    
    print("=" * 80)
    print("MinerU 图片转 Markdown (批量处理)")
    print("=" * 80)
    print(f"\n任务 ID: {TASK_ID}")
    
    try:
        # 处理整个任务
        results = process_task(TASK_ID)
        
        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        
        print(f"\n{'='*80}")
        print(f"处理完成!")
        print(f"成功: {success_count} 个")
        print(f"失败: {fail_count} 个")
        print(f"输出目录: D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\{TASK_ID}")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
