import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.table_layout_service import TableLayoutService


class PaddleLikeResult:
    def __init__(self, payload):
        self.json = payload


class FakeLayoutEngine:
    def predict(self, **kwargs):
        return [
            {
                "res": {
                    "boxes": [
                        {
                            "label": "table",
                            "score": 0.92,
                            "coordinate": [30, 20, 180, 130],
                        },
                        {
                            "label": "text",
                            "score": 0.99,
                            "coordinate": [1, 1, 20, 20],
                        },
                        {
                            "label": "table",
                            "score": 0.2,
                            "coordinate": [190, 20, 230, 80],
                        },
                    ]
                }
            }
        ]


class TableLayoutServiceTest(unittest.TestCase):
    def test_normalize_layout_boxes_supports_nested_paddle_result(self):
        service = TableLayoutService(layout_engine=object())
        output = [
            {
                "res": {
                    "boxes": [
                        {
                            "label": "table",
                            "score": "0.88",
                            "coordinate": [1, 2, 30, 40],
                        }
                    ]
                }
            },
            PaddleLikeResult(
                {
                    "result": {
                        "boxes": [
                            {
                                "label": "table",
                                "confidence": 0.77,
                                "bbox": [[3, 4], [9, 4], [9, 12], [3, 12]],
                            }
                        ]
                    }
                }
            ),
        ]

        boxes = service._normalize_layout_boxes(output)

        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0]["score"], 0.88)
        self.assertEqual(boxes[1]["coordinate"], [[3, 4], [9, 4], [9, 12], [3, 12]])

    def test_clip_bbox_accepts_polygon_and_clamps_to_image_bounds(self):
        service = TableLayoutService(layout_engine=object())

        bbox = service._clip_bbox(
            [[-3, 4], [42.2, 4], [42, 17.6], [-3, 17]],
            image_size=(40, 20),
            padding=3,
        )

        self.assertEqual(bbox, (0, 1, 40, 20))

    def test_detect_tables_refines_loose_model_box_to_table_lines(self):
        try:
            import cv2  # noqa: F401
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow or OpenCV is not installed")

        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            service = TableLayoutService(base_dir=base_dir, layout_engine=FakeLayoutEngine())
            page_image = Image.new("RGB", (240, 170), "white")
            draw = ImageDraw.Draw(page_image)

            # Real table boundary is intentionally tighter than model bbox.
            for x in (50, 90, 130, 170):
                draw.line((x, 40, x, 115), fill="black", width=2)
            for y in (40, 65, 90, 115):
                draw.line((50, y, 170, y), fill="black", width=2)

            page_image_path = base_dir / "page_images" / "task" / "page_001.png"
            table_dir = base_dir / "table_blocks" / "task"
            page_image_path.parent.mkdir(parents=True)
            table_dir.mkdir(parents=True)
            page_image.save(page_image_path)

            tables = service._detect_tables_on_page(
                page_image=page_image,
                page_image_path=page_image_path,
                page_idx=1,
                task_table_dir=table_dir,
                score_threshold=0.45,
                crop_padding=18,
                refine_padding=4,
            )

            self.assertEqual(len(tables), 1)
            self.assertEqual(tables[0]["refine_method"], "line_refine")
            self.assertEqual(tables[0]["model_bbox"], [30, 20, 180, 130])
            self.assertLessEqual(tables[0]["bbox"][0], 50)
            self.assertGreaterEqual(tables[0]["bbox"][2], 170)
            self.assertLess(tables[0]["width"], 150)
            self.assertTrue((table_dir / "page_001_table_001.png").exists())

    def test_safe_stem_removes_path_and_invalid_filename_chars(self):
        service = TableLayoutService(layout_engine=object())

        self.assertEqual(service._safe_stem(r"..\bad:name?.pdf"), "bad_name")
        self.assertEqual(service._safe_stem("   .pdf"), "upload")


if __name__ == "__main__":
    unittest.main()
