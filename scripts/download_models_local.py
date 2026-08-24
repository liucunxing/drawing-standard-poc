"""Download and inventory the exact model set used by the local CPU stack."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


MODEL_ROOT = Path(os.environ.get("MODEL_ROOT", "/app/models"))
PADDLE_MODEL_ROOT = Path(
    os.environ.get("PADDLE_PDX_CACHE_HOME", str(MODEL_ROOT / "paddlex"))
)
MODELSCOPE_CACHE = Path(
    os.environ.get("MODELSCOPE_CACHE", str(MODEL_ROOT / "modelscope"))
)
HF_HOME = Path(os.environ.get("HF_HOME", str(MODEL_ROOT / "huggingface")))
MINERU_CONFIG = Path(
    os.environ.get("MINERU_TOOLS_CONFIG_JSON", "/app/models/mineru/mineru.json")
)
LAYOUT_MODEL = os.environ.get("PADDLEOCR_LAYOUT_MODEL_NAME", "PP-DocLayout_plus-L")
DOWNLOAD_SOURCE = os.environ.get("MINERU_DOWNLOAD_SOURCE", "modelscope").strip().lower()
DOWNLOAD_MODE = os.environ.get("MODEL_DOWNLOAD_MODE", "download").strip().lower()


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def tree_summary(path: Path) -> dict[str, int | str | bool]:
    file_count = 0
    total_bytes = 0
    if path.exists():
        for item in path.rglob("*"):
            if not item.is_file():
                continue
            file_count += 1
            try:
                total_bytes += item.stat().st_size
            except OSError:
                pass
    return {
        "path": str(path),
        "exists": path.exists(),
        "file_count": file_count,
        "total_bytes": total_bytes,
    }


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if DOWNLOAD_SOURCE not in {"modelscope", "huggingface"}:
        raise SystemExit(
            "MINERU_DOWNLOAD_SOURCE must be 'modelscope' or 'huggingface'"
        )
    if DOWNLOAD_MODE not in {"download", "inventory"}:
        raise SystemExit("MODEL_DOWNLOAD_MODE must be 'download' or 'inventory'")

    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    MINERU_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    MODELSCOPE_CACHE.mkdir(parents=True, exist_ok=True)
    HF_HOME.mkdir(parents=True, exist_ok=True)

    download_env = os.environ.copy()
    download_env.setdefault("MODELSCOPE_CACHE", str(MODELSCOPE_CACHE))
    download_env.setdefault("HF_HOME", str(HF_HOME))

    if DOWNLOAD_MODE == "download":
        print(
            f"[models] downloading MinerU {package_version('mineru')} pipeline bundle "
            f"from {DOWNLOAD_SOURCE}"
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mineru.cli.models_download",
                "-s",
                DOWNLOAD_SOURCE,
                "-m",
                "pipeline",
            ],
            check=True,
            env=download_env,
        )

        print(f"[models] downloading Paddle layout model {LAYOUT_MODEL}")
        from paddleocr import LayoutDetection

        LayoutDetection(model_name=LAYOUT_MODEL, device="cpu")
    else:
        layout_dir = PADDLE_MODEL_ROOT / "official_models" / LAYOUT_MODEL
        missing = [path for path in (MINERU_CONFIG, layout_dir) if not path.exists()]
        if missing:
            raise SystemExit(
                "Cannot inventory incomplete model cache: "
                + ", ".join(str(path) for path in missing)
            )
        print("[models] inventory-only mode; verified existing model roots")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "device": os.environ.get("MINERU_DEVICE_MODE", "cpu"),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "mode": DOWNLOAD_MODE,
        },
        "packages": {
            name: package_version(name)
            for name in (
                "mineru",
                "mineru-vl-utils",
                "paddleocr",
                "paddlex",
                "paddlepaddle",
                "torch",
                "torchvision",
                "transformers",
                "tokenizers",
            )
        },
        "mineru": {
            "source": DOWNLOAD_SOURCE,
            "config_path": str(MINERU_CONFIG),
            "config_sha256": sha256(MINERU_CONFIG),
        },
        "layout_model": LAYOUT_MODEL,
        "trees": {
            "mineru": tree_summary(MODEL_ROOT / "mineru"),
            "modelscope": tree_summary(MODELSCOPE_CACHE),
            "huggingface": tree_summary(HF_HOME),
            "paddlex": tree_summary(PADDLE_MODEL_ROOT),
        },
    }

    manifest_path = MODEL_ROOT / "model-manifest.local.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[models] inventory written to {manifest_path}")


if __name__ == "__main__":
    main()
