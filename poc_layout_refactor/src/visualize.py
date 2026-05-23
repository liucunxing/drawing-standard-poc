from __future__ import annotations

from numbers import Real
from pathlib import Path
from typing import Any, Sequence

from .utils import bbox_ratio_to_pixels, ensure_dir

LABEL_COLORS: dict[str, tuple[int, int, int]] = {
    "table": (232, 102, 61),
    "text": (47, 122, 198),
    "aside_text": (145, 86, 191),
    "figure_title": (42, 157, 143),
    "image": (133, 133, 133),
    "fixed_roi": (225, 162, 38),
    "roi_fallback": (225, 162, 38),
    "merged": (219, 70, 108),
    "layout_box": (47, 122, 198),
}


SOURCE_COLORS: dict[str, tuple[int, int, int]] = {
    "roi_fallback": (225, 162, 38),
    "merged": (219, 70, 108),
    "layout_box": (47, 122, 198),
    "full_page": (47, 122, 198),
    "roi": (96, 132, 196),
}


def draw_ratio_boxes(
    image_path: str | Path,
    items: list[dict[str, Any]],
    output_path: str | Path,
    bbox_field: str = "bbox_ratio",
    title_field: str | None = None,
) -> None:
    from PIL import Image, ImageDraw

    with Image.open(image_path).convert("RGB") as image:
        draw = ImageDraw.Draw(image)
        font = _load_font(image.size)
        line_width = max(2, round(min(image.size) / 500))
        for item in items:
            bbox = item.get(bbox_field)
            if not bbox:
                continue
            xy = bbox_ratio_to_pixels(bbox, image.width, image.height)
            _draw_one_box(draw, xy, item, font, line_width, title_field)
        target = Path(output_path)
        ensure_dir(target.parent)
        image.save(target)


def draw_pixel_boxes(
    image_path: str | Path,
    items: list[dict[str, Any]],
    output_path: str | Path,
    bbox_field: str = "bbox_px",
    title_field: str | None = None,
) -> None:
    from PIL import Image, ImageDraw

    with Image.open(image_path).convert("RGB") as image:
        draw = ImageDraw.Draw(image)
        font = _load_font(image.size)
        line_width = max(2, round(min(image.size) / 500))
        for item in items:
            bbox = item.get(bbox_field)
            if not bbox:
                continue
            x1, y1, x2, y2 = [int(round(float(v))) for v in bbox]
            _draw_one_box(draw, (x1, y1, x2, y2), item, font, line_width, title_field)
        target = Path(output_path)
        ensure_dir(target.parent)
        image.save(target)


def _draw_one_box(
    draw: Any,
    xy: Sequence[int],
    item: dict[str, Any],
    font: Any,
    line_width: int,
    title_field: str | None,
) -> None:
    label = _item_label(item, title_field)
    color = _item_color(item)
    draw.rectangle(xy, outline=color, width=line_width)
    if not label:
        return

    left, top, _, _ = xy
    text_bbox = draw.textbbox((left, top), label, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    label_top = max(0, top - text_height - 4)
    draw.rectangle(
        (left, label_top, left + text_width + 6, label_top + text_height + 4),
        fill=color,
    )
    draw.text((left + 3, label_top + 2), label, fill=(255, 255, 255), font=font)


def _item_label(item: dict[str, Any], title_field: str | None) -> str:
    if title_field and item.get(title_field):
        base = str(item[title_field])
    elif item.get("region_id"):
        labels = ",".join(item.get("labels", []))
        source = item.get("source")
        suffix = f"[{source}]" if source else ""
        base = f"{item['region_id']}:{labels}{suffix}"
    elif item.get("raw_id"):
        base = f"{item['raw_id']}:{item.get('label', '')}"
    elif item.get("labels"):
        base = ",".join(item["labels"])
    else:
        base = str(item.get("label", ""))

    score = item.get("score")
    if isinstance(score, Real):
        return f"{base} {score:.2f}"
    return base


def _item_color(item: dict[str, Any]) -> tuple[int, int, int]:
    source = item.get("source")
    if source in SOURCE_COLORS:
        return SOURCE_COLORS[source]
    labels = item.get("labels") or [item.get("label")]
    for label in labels:
        if label in LABEL_COLORS:
            return LABEL_COLORS[label]
    return LABEL_COLORS["merged"]


def _load_font(image_size: tuple[int, int]) -> Any:
    from PIL import ImageFont

    size = max(12, min(28, round(min(image_size) / 70)))
    for font_name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
