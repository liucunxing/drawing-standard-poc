from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List


BACKEND_DIR = Path(__file__).resolve().parents[1]
INNER_PROJECT_DIR = BACKEND_DIR.parent
REPO_ROOT = INNER_PROJECT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.table_layout_service import TableLayoutService
from validate_table_crop_manifest import validate_manifest


def iter_pdf_paths(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.glob("*.pdf") if path.is_file())
    raise FileNotFoundError(f"PDF 文件或目录不存在: {input_path}")


def draw_page_overlays(result: dict, output_dir: Path) -> List[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("缺少 Pillow，无法绘制叠框图。请先安装 requirements.txt") from exc

    overlay_dir = output_dir / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    overlay_paths: List[str] = []
    tables_by_page = {}
    for table in result.get("tables", []):
        tables_by_page.setdefault(table["page"], []).append(table)

    for page_info in result.get("page_images", []):
        page = page_info["page"]
        image_path = Path(page_info["image_path"])
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()

        for table in tables_by_page.get(page, []):
            model_bbox = table.get("model_bbox")
            final_bbox = table.get("bbox")
            table_name = f"p{page:03d}_t{table['table_index']:03d}"

            if model_bbox:
                draw.rectangle(model_bbox, outline=(255, 170, 0), width=4)
                draw.text((model_bbox[0], max(0, model_bbox[1] - 14)), "model", fill=(255, 170, 0), font=font)

            if final_bbox:
                draw.rectangle(final_bbox, outline=(220, 20, 60), width=5)
                label = f"{table_name} {table.get('refine_method', '')}"
                draw.text((final_bbox[0], final_bbox[1] + 4), label, fill=(220, 20, 60), font=font)

        overlay_path = overlay_dir / f"{Path(result['filename']).stem}_page_{page:03d}_overlay.png"
        image.save(overlay_path)
        overlay_paths.append(str(overlay_path))

    return overlay_paths


def copy_manifest(result: dict, overlay_paths: Iterable[str], output_dir: Path) -> Path:
    manifest = {
        **result,
        "overlay_images": list(overlay_paths),
        "legend": {
            "orange_box": "Paddle/LayoutDetection 原始模型框",
            "red_box": "最终裁剪框，优先使用表格线精裁结果",
        },
    }
    manifest_path = output_dir / f"{result['task_id']}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="本地运行 Paddle 表格检测，并输出裁剪结果和叠框图。")
    parser.add_argument(
        "--pdf",
        default=str(REPO_ROOT / "data" / "samples" / "pdf"),
        help="PDF 文件路径，或包含 PDF 的目录。默认读取 data/samples/pdf",
    )
    parser.add_argument(
        "--output-dir",
        default=str(BACKEND_DIR / "tmp" / "table_crop_debug"),
        help="调试输出目录。默认 backend/tmp/table_crop_debug",
    )
    parser.add_argument("--score-threshold", type=float, default=0.45, help="表格候选框最小置信度")
    parser.add_argument("--render-scale", type=float, default=2.0, help="PDF 页面渲染缩放倍数")
    parser.add_argument("--crop-padding", type=int, default=16, help="模型框外扩像素")
    parser.add_argument("--refine-padding", type=int, default=8, help="表格线精裁后保留边距")
    parser.add_argument(
        "--enable-line-fallback",
        action="store_true",
        help="启用整页线条兜底候选。默认关闭，避免把图框碎片裁成几十张。",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="只生成图片，不执行 manifest 回归校验。",
    )
    args = parser.parse_args()

    input_path = Path(args.pdf)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    service = TableLayoutService(base_dir=output_dir / "artifacts")
    pdf_paths = iter_pdf_paths(input_path)
    if not pdf_paths:
        raise RuntimeError(f"没有找到 PDF: {input_path}")

    print(f"发现 {len(pdf_paths)} 个 PDF，开始运行 Paddle 表格识别...")
    print(f"输出目录: {output_dir}")

    manifest_paths: List[Path] = []
    for pdf_path in pdf_paths:
        print(f"\n处理: {pdf_path}")
        result = service.extract_tables_from_pdf_path(
            pdf_path=pdf_path,
            filename=pdf_path.name,
            score_threshold=args.score_threshold,
            render_scale=args.render_scale,
            crop_padding=args.crop_padding,
            refine_padding=args.refine_padding,
            enable_line_fallback=args.enable_line_fallback,
        )
        overlay_paths = draw_page_overlays(result, output_dir)
        manifest_path = copy_manifest(result, overlay_paths, output_dir)
        manifest_paths.append(manifest_path)

        print(f"任务 ID: {result['task_id']}")
        print(f"页数: {result['total_pages']}，表格数: {result['total_tables']}")
        print(f"叠框图:")
        for overlay_path in overlay_paths:
            print(f"  {overlay_path}")
        print("裁剪图片:")
        for table in result.get("tables", []):
            print(f"  [{table['refine_method']}] {table['image_path']}")
        print(f"明细 JSON: {manifest_path}")

    print("\n完成。红框是最终裁剪框，橙框是 Paddle 模型原始框。")
    if args.skip_validation:
        return 0

    errors: List[str] = []
    for manifest_path in manifest_paths:
        errors.extend(validate_manifest(manifest_path))

    if errors:
        print("\n回归校验失败：")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\n回归校验通过：未发现少检、过检、重复或包含框。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
