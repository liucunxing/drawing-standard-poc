from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.table_layout_service import table_layout_service


# [上线待替换] 本地测试用的 PDF 路径，生产环境请通过命令行参数或环境变量指定
PDF_PATH = Path("./test_input.pdf")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    pdf_bytes = PDF_PATH.read_bytes()
    result = table_layout_service.extract_tables_from_uploaded_pdf(
        pdf_bytes=pdf_bytes,
        filename=PDF_PATH.name,
    )

    print("=" * 80)
    print("Table extraction finished")
    print(f"task_id: {result['task_id']}")
    print(f"pdf_path: {result['pdf_path']}")
    print(f"total_pages: {result['total_pages']}")
    print(f"total_tables: {result['total_tables']}")

    tables = result.get("tables", [])
    for item in tables:
        print(
            f"- page={item['page']}, idx={item['table_index']}, "
            f"score={item['score']:.3f}, bbox={item['bbox']}, image={item['image_path']}"
        )


if __name__ == "__main__":
    main()
