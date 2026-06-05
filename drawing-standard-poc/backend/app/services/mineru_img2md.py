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
import json
import re
import cv2
import numpy as np
from io import BytesIO
from pathlib import Path
from PIL import Image
import shutil

from backend.app.services.qween_test import fix_nozzle_table_md

os.environ['MINERU_MODEL_SOURCE'] = 'local'
os.environ['MINERU_TABLE_MODEL'] = 'struct_eqtable'


def _normalize_standard_prefix_in_text(text):
    """Normalize common OCR prefix variants like HG/* and NB/* to the expected standard forms."""
    if not isinstance(text, str) or not text:
        return text
    normalized = re.sub(r"H[GOC]/[TI1l](?=\s*\d)", "HG/T", text)
    normalized = re.sub(r"NB/[I1l](?=\s*(?:\d|$))", "NB/T", normalized)
    normalized = re.sub(r"NB/(?=\s*(?:\d|$))", "NB/T", normalized)
    return normalized


def _apply_flange_standard_patch_md(md_content):
    """Patch markdown: always replace □->口, and normalize standard prefixes in 法兰标准 context."""
    if not isinstance(md_content, str) or not md_content:
        return md_content, False

    patched = md_content.replace("□", "口")
    if "法兰标准" in patched:
        patched = _normalize_standard_prefix_in_text(patched)

    return patched, patched != md_content


def _contains_flange_standard_json(obj):
    if isinstance(obj, dict):
        return any(_contains_flange_standard_json(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_flange_standard_json(v) for v in obj)
    if isinstance(obj, str):
        return "法兰标准" in obj
    return False


def _patch_json_strings(obj):
    if isinstance(obj, dict):
        return {k: _patch_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_patch_json_strings(v) for v in obj]
    if isinstance(obj, str):
        return _normalize_standard_prefix_in_text(obj)
    return obj


def _apply_flange_standard_patch_json(json_obj):
    """Patch json text values only when flange standard context exists."""
    if json_obj is None:
        return None, False
    if not _contains_flange_standard_json(json_obj):
        return json_obj, False
    patched = _patch_json_strings(json_obj)
    return patched, patched != json_obj


def _contains_nozzle_table_md(md_content):
    """Detect '管口表' even when OCR inserts spaces or HTML tags between characters."""
    if not isinstance(md_content, str) or not md_content:
        return False

    if re.search(r"管\s*口\s*表", md_content):
        return True

    visible_text = re.sub(r"<[^>]+>", "", md_content)
    visible_text = visible_text.replace("&nbsp;", " ")
    visible_text = re.sub(r"\s+", "", visible_text)
    return "管口表" in visible_text


def _parse_pdf_to_md_json(do_parse, pdf_bytes, temp_dir, pdf_name):
    """Run MinerU parse and return markdown content with optional middle-json content."""
    do_parse(
        output_dir=str(temp_dir),
        pdf_bytes_list=[pdf_bytes],
        pdf_file_names=[pdf_name],
        p_lang_list=["ch"],
        backend="pipeline",
        parse_method="auto",
        formula_enable=False,
        table_enable=True,
        f_draw_layout_bbox=False,
        f_draw_span_bbox=False,
        f_dump_md=True,
        f_dump_middle_json=True,
        f_dump_model_output=False,
        f_dump_orig_pdf=False,
        f_dump_content_list=False,
    )

    md_files = list(temp_dir.glob("**/*.md"))
    json_files = list(temp_dir.glob("**/*.json"))
    if not md_files:
        raise Exception("未找到 Markdown 文件")

    md_content = md_files[0].read_text(encoding="utf-8", errors="ignore")
    json_content = None
    if json_files:
        try:
            json_content = json.loads(json_files[0].read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            json_content = {"raw_text": json_files[0].read_text(encoding="utf-8", errors="ignore")}

    return md_content, json_content


def _split_vertical_2(image, overlap_px=140):
    """Split image into two vertical chunks with overlap for tall content continuity."""
    h = image.height
    split_y = h // 2
    y1_bottom = min(h, split_y + overlap_px)
    y2_top = max(0, split_y - overlap_px)
    part1 = image.crop((0, 0, image.width, y1_bottom))
    part2 = image.crop((0, y2_top, image.width, h))
    return part1, part2


def _should_split_image(
    image_path,
    resized_image,
    size_mb_threshold=1.0,
    height_threshold=3600,
    aspect_threshold=2.0,
):
    """Decide split based on size + geometry; not only file size."""
    file_size_mb = image_path.stat().st_size / (1024 * 1024)
    aspect_ratio = resized_image.height / max(1, resized_image.width)
    is_large_file = file_size_mb > size_mb_threshold
    is_tall_image = resized_image.height >= height_threshold
    is_extreme_aspect = aspect_ratio >= aspect_threshold
    should_split = is_large_file and (is_tall_image or is_extreme_aspect)

    return should_split, {
        "file_size_mb": round(file_size_mb, 3),
        "resized_width": resized_image.width,
        "resized_height": resized_image.height,
        "aspect_ratio": round(aspect_ratio, 3),
        "size_mb_threshold": size_mb_threshold,
        "height_threshold": height_threshold,
        "aspect_threshold": aspect_threshold,
    }


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


def image_to_markdown(
        image_path,
        task_id,
        output_dir,
        dpi=300,
    scale=1.5,
    auto_split=True,
    split_size_mb_threshold=1.0,
    split_height_threshold=3600,
    split_aspect_threshold=2.0,
    split_overlap_px=140,
):
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

        # 步骤3: 缩放(提高分辨率,增强 OCR 识别精度)
        resized_size = (
            int(processed_image.width * scale),
            int(processed_image.height * scale),
        )
        resized_image = processed_image.resize(resized_size, Image.LANCZOS)

        # 步骤4~6: 封装 PDF 并识别
        pdf_image_tools.DEFAULT_PDF_IMAGE_DPI = dpi

        split_applied = False
        split_reason = None
        merged_md_content = None
        merged_json_content = None

        if auto_split:
            split_applied, split_reason = _should_split_image(
                image_path=image_path,
                resized_image=resized_image,
                size_mb_threshold=split_size_mb_threshold,
                height_threshold=split_height_threshold,
                aspect_threshold=split_aspect_threshold,
            )

        if split_applied:
            # Large/tall mixed-content images are parsed in two parts, then merged.
            part1, part2 = _split_vertical_2(resized_image, overlap_px=split_overlap_px)
            part1_dir = temp_dir / "part1"
            part2_dir = temp_dir / "part2"
            part1_dir.mkdir(parents=True, exist_ok=True)
            part2_dir.mkdir(parents=True, exist_ok=True)

            part1_buf = BytesIO()
            part1.save(part1_buf, format="PNG")
            part1_pdf = pdf_image_tools.images_bytes_to_pdf_bytes(part1_buf.getvalue())

            part2_buf = BytesIO()
            part2.save(part2_buf, format="PNG")
            part2_pdf = pdf_image_tools.images_bytes_to_pdf_bytes(part2_buf.getvalue())

            md_1, json_1 = _parse_pdf_to_md_json(do_parse, part1_pdf, part1_dir, "part1.pdf")
            md_2, json_2 = _parse_pdf_to_md_json(do_parse, part2_pdf, part2_dir, "part2.pdf")

            merged_md_content = "\n\n".join([
                "<!-- part1 -->",
                md_1,
                "<!-- part2 -->",
                md_2,
            ])
            merged_json_content = {
                "split_mode": "split2",
                "split_overlap_px": split_overlap_px,
                "split_reason": split_reason,
                "part1": json_1,
                "part2": json_2,
            }
        else:
            buffer = BytesIO()
            resized_image.save(buffer, format="PNG")
            pdf_bytes = pdf_image_tools.images_bytes_to_pdf_bytes(buffer.getvalue())
            merged_md_content, merged_json_content = _parse_pdf_to_md_json(
                do_parse,
                pdf_bytes,
                temp_dir,
                "input.pdf",
            )

        # 步骤7: 先输出原始结果，再输出打补丁结果
        raw_md_target = output_dir / f"raw_{task_id}.md"
        raw_md_target.write_text(merged_md_content, encoding="utf-8")

        raw_json_target = output_dir / f"raw_{task_id}.json"
        raw_json_target.write_text(
            json.dumps(merged_json_content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        patched_md_content, md_patched = _apply_flange_standard_patch_md(merged_md_content)
        patched_json_content, json_patched = _apply_flange_standard_patch_json(merged_json_content)

        patched_md_target = output_dir / f"patched_{task_id}.md"
        patched_md_target.write_text(patched_md_content, encoding="utf-8")

        patched_json_target = output_dir / f"patched_{task_id}.json"
        patched_json_target.write_text(
            json.dumps(patched_json_content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 步骤8: 管口表 Qwen 后处理
        # 判断 patched 版本的 md 是否包含"管口表"关键字(兼容空格/HTML标签分隔)
        qwen_fixed_md_content = None
        qwen_fixed_applied = False
        qwen_fixed_md_target = None

        if _contains_nozzle_table_md(patched_md_content):
            print(f"[img2md] 检测到管口表, 调用 Qwen 后处理修复列错位...")
            qwen_fixed_md_content = fix_nozzle_table_md(patched_md_content)
            qwen_fixed_applied = qwen_fixed_md_content != patched_md_content

            if qwen_fixed_applied:
                qwen_fixed_md_target = output_dir / f"qwen_fixed_{task_id}.md"
                qwen_fixed_md_target.write_text(qwen_fixed_md_content, encoding="utf-8")
                print(f"[img2md] Qwen 修复完成, 已保存: {qwen_fixed_md_target}")
            else:
                print(f"[img2md] Qwen 返回内容与原始一致, 未生成修复文件")
        else:
            print(f"[img2md] 未检测到管口表, 跳过 Qwen 后处理")

        return {
            'md_file': str(raw_md_target),
            'json_file': str(raw_json_target),
            'patched_md_file': str(patched_md_target),
            'patched_json_file': str(patched_json_target),
            'md_patched': md_patched,
            'json_patched': json_patched,
            'qwen_fixed_md_file': str(qwen_fixed_md_target) if qwen_fixed_md_target else None,
            'qwen_fixed_applied': qwen_fixed_applied,
            'dpi': dpi,
            'scale': scale,
            'split_applied': split_applied,
            'split_reason': split_reason,
        }

    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def process_task(task_id, table_blocks_dir=None, output_base_dir=None, dpi=300, scale=1.5):
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
        dpi: PDF 封装的 DPI 值,默认 200
        scale: 图像缩放倍率,默认 1.5

    返回:
        list: 包含所有处理结果的列表
    """
    # 默认路径配置
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
                dpi=dpi,
                scale=scale,
            )

            print(f"  Markdown: {result['md_file']}")
            if result['json_file']:
                print(f"  JSON: {result['json_file']}")
            print(f"  Patched Markdown: {result.get('patched_md_file')}")
            print(f"  Patched JSON: {result.get('patched_json_file')}")
            print(f"  补丁命中: md={result.get('md_patched')} json={result.get('json_patched')}")
            print(f"  Qwen管口表修复: {'是' if result.get('qwen_fixed_applied') else '否'}")
            if result.get('qwen_fixed_md_file'):
                print(f"  Qwen修复文件: {result['qwen_fixed_md_file']}")
            print(f"  参数: dpi={result.get('dpi')} scale={result.get('scale')}")
            print(f"  切分: {'是' if result.get('split_applied') else '否'}")
            if result.get('split_reason'):
                print(f"  切分依据: {result['split_reason']}")

            results.append({
                'image': str(image_path),
                'md_file': result['md_file'],
                'json_file': result['json_file'],
                'patched_md_file': result.get('patched_md_file'),
                'patched_json_file': result.get('patched_json_file'),
                'qwen_fixed_md_file': result.get('qwen_fixed_md_file'),
                'md_patched': result.get('md_patched', False),
                'json_patched': result.get('json_patched', False),
                'qwen_fixed_applied': result.get('qwen_fixed_applied', False),
                'dpi': result.get('dpi'),
                'scale': result.get('scale'),
                'split_applied': result.get('split_applied', False),
                'split_reason': result.get('split_reason'),
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

        print(f"\n{'=' * 80}")
        print(f"处理完成!")
        print(f"成功: {success_count} 个")
        print(f"失败: {fail_count} 个")
        print(f"输出目录: D:\work\Develop\drawing-poc\drawing-standard-poc\backend\tmp\{TASK_ID}")
        print(f"{'=' * 80}")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
