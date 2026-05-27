from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .utils import ensure_dir


@dataclass(frozen=True)
class RenderedImage:
    page: int
    dpi: int
    path: str
    width_px: int
    height_px: int
    reused_existing: bool = False


def render_page(
    pdf_path: str | Path,
    output_path: str | Path,
    page_number: int = 1,
    dpi: int = 150,
    reuse_existing: bool = True,
    force_render: bool = False,
) -> RenderedImage:
    if page_number < 1:
        raise ValueError("page_number is 1-based and must be >= 1")

    target = Path(output_path)
    ensure_dir(target.parent)
    if reuse_existing and not force_render and target.exists() and target.stat().st_size > 0:
        image_size = _read_image_size(target)
        if image_size is not None:
            width_px, height_px = image_size
            print(f"Reuse existing render: {target}")
            return RenderedImage(
                page=page_number,
                dpi=dpi,
                path=str(target),
                width_px=width_px,
                height_px=height_px,
                reused_existing=True,
            )

    try:
        import fitz
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "PyMuPDF is required to render PDFs. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    with fitz.open(str(pdf_path)) as document:
        page_index = page_number - 1
        if page_index >= document.page_count:
            raise ValueError(
                f"PDF has {document.page_count} page(s), cannot render page {page_number}"
            )

        page = document.load_page(page_index)
        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        print(f"Render PDF page {page_number} at {dpi} DPI: {target}")
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        print(f"Save rendered image: {target}")
        pixmap.save(str(target))

    return RenderedImage(
        page=page_number,
        dpi=dpi,
        path=str(target),
        width_px=pixmap.width,
        height_px=pixmap.height,
        reused_existing=False,
    )


def _read_image_size(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as image:
            size = image.size
            image.verify()
            return size
    except Exception:
        return None


def get_page_points(pdf_path: str | Path, page_number: int = 1) -> tuple[float, float]:
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - depends on local install
        raise RuntimeError(
            "PyMuPDF is required to read PDF page geometry. Install dependencies with "
            "`pip install -r requirements.txt` inside poc_layout_refactor."
        ) from exc

    with fitz.open(str(pdf_path)) as document:
        page_index = page_number - 1
        if page_index >= document.page_count:
            raise ValueError(
                f"PDF has {document.page_count} page(s), cannot read page {page_number}"
            )
        rect = document.load_page(page_index).rect
        return float(rect.width), float(rect.height)


def render_pdf_page(
    pdf_path: str | Path,
    output_dir: str | Path,
    page_number: int,
    low_dpi: int,
    high_dpi: int,
    reuse_existing: bool = True,
    force_render: bool = False,
) -> dict:
    output = ensure_dir(output_dir)
    low_image = render_page(
        pdf_path,
        output / f"page_{page_number}_lowdpi.png",
        page_number=page_number,
        dpi=low_dpi,
        reuse_existing=reuse_existing,
        force_render=force_render,
    )
    high_image = render_page(
        pdf_path,
        output / f"page_{page_number}_highdpi.png",
        page_number=page_number,
        dpi=high_dpi,
        reuse_existing=reuse_existing,
        force_render=force_render,
    )
    width_pt, height_pt = get_page_points(pdf_path, page_number=page_number)
    orientation = "landscape" if low_image.width_px >= low_image.height_px else "portrait"

    return {
        "page": page_number,
        "orientation": orientation,
        "page_width_pt": width_pt,
        "page_height_pt": height_pt,
        "low_dpi": low_dpi,
        "high_dpi": high_dpi,
        "low_image": asdict(low_image),
        "high_image": asdict(high_image),
        "low_width_px": low_image.width_px,
        "low_height_px": low_image.height_px,
        "high_width_px": high_image.width_px,
        "high_height_px": high_image.height_px,
    }
