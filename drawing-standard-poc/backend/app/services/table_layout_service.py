from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import fitz  # PyMuPDF
from PIL import Image


class TableLayoutService:
    """
    图纸表格识别服务
    1. PDF 转图片
    2. LayoutDetection 识别表格区域
    3. 裁剪表格图片保存
    """

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parents[2] / "tmp"
        self.upload_dir = self.base_dir / "uploads"
        self.table_blocks_dir = self.base_dir / "table_blocks"
        self.markdown_dir = self.base_dir / "markdown"

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.table_blocks_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        # 初始化版面检测模型（只初始化一次）
        self.layout_engine = self._create_layout_engine()

    def extract_tables_from_uploaded_pdf(self, pdf_bytes: bytes, filename: str) -> Dict[str, Any]:
        """主入口"""
        if not pdf_bytes:
            raise ValueError("上传文件内容为空")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("仅支持PDF文件")

        task_id = uuid4().hex[:12]

        # 1. 保存PDF
        pdf_path = self._save_pdf(pdf_bytes, filename, task_id)
        print(f"[Task {task_id}] PDF已保存: {pdf_path}")

        # 2. PDF转图片
        pages = self._pdf_to_images(pdf_path)
        print(f"[Task {task_id}] PDF共 {len(pages)} 页")

        # 3. 创建任务目录
        task_table_dir = self.table_blocks_dir / task_id
        task_table_dir.mkdir(parents=True, exist_ok=True)

        # 4. 识别表格
        all_tables = []
        for page_idx, page_image in enumerate(pages, start=1):
            print(f"[Task {task_id}] 处理第 {page_idx} 页...")
            tables = self._detect_tables_on_page(
                page_image=page_image,
                page_idx=page_idx,
                task_table_dir=task_table_dir,
            )
            all_tables.extend(tables)

        return {
            "task_id": task_id,
            "pdf_path": str(pdf_path),
            "total_pages": len(pages),
            "total_tables": len(all_tables),
            "tables": all_tables,
        }

    def _create_layout_engine(self):
        """初始化版面检测模型"""
        from paddleocr import LayoutDetection

        engine = LayoutDetection(
            model_name="PP-DocLayout_plus-L",  # 你需求指定的模型
        )
        return engine

    def _save_pdf(self, pdf_bytes: bytes, filename: str, task_id: str) -> Path:
        safe_name = Path(filename).stem.strip() or "upload"
        save_path = self.upload_dir / f"{safe_name}_{task_id}.pdf"
        save_path.write_bytes(pdf_bytes)
        return save_path

    def _pdf_to_images(self, pdf_path: Path) -> List[Image.Image]:
        doc = fitz.open(pdf_path)
        images = []
        try:
            for page in doc:
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
        finally:
            doc.close()
        return images

    def _detect_tables_on_page(
            self,
            page_image: Image.Image,
            page_idx: int,
            task_table_dir: Path,
    ) -> List[Dict[str, Any]]:
        """识别页面中的表格区域"""
        temp_img_path = task_table_dir / f"_temp_page_{page_idx}.png"
        page_image.save(temp_img_path)

        output = self.layout_engine.predict(
            input=str(temp_img_path),
            batch_size=1,
            layout_nms=True,
        )

        tables = []
        table_count = 0

        for res in output:
            boxes = res.get('boxes', []) if isinstance(res, dict) else []
            if not boxes and hasattr(res, 'get'):
                boxes = res.get('boxes', [])

            # 打印所有识别到的区域（调试用）
            print(f"\n[调试] 第 {page_idx} 页所有识别区域:")
            for i, box in enumerate(boxes):
                print(f"  {i}: label={box.get('label')}, score={box.get('score'):.3f}, coord={box.get('coordinate')}")

            # 只提取表格类型（可以调低阈值）
            for box in boxes:
                label = box.get('label', '').lower()
                score = box.get('score', 0)

                # 只识别表格，且置信度 > 0.5
                if 'table' not in label or score < 0.5:
                    continue

                table_count += 1
                coordinate = box.get('coordinate', [])

                if len(coordinate) != 4:
                    continue

                x1, y1, x2, y2 = [int(v) for v in coordinate]

                # 裁剪表格区域
                table_image = page_image.crop((x1, y1, x2, y2))

                # 保存表格图片
                block_name = f"page_{page_idx:03d}_table_{table_count:03d}.png"
                block_path = task_table_dir / block_name
                table_image.save(block_path)

                tables.append({
                    "page": page_idx,
                    "table_index": table_count,
                    "bbox": [x1, y1, x2, y2],
                    "image_path": str(block_path),
                    "label": label,
                    "score": score,
                })

        if temp_img_path.exists():
            temp_img_path.unlink()

        print(f"  第 {page_idx} 页识别到 {table_count} 个表格")
        return tables


# 单例实例
table_layout_service = TableLayoutService()