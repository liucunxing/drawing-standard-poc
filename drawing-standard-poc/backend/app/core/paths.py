from pathlib import Path


def resolve_child_path(root: Path, relative_path: str) -> Path:
    """Resolve a user-provided relative path and keep it inside ``root``."""
    root_path = root.resolve()
    candidate = (root_path / str(relative_path or "")).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("非法文件路径") from exc
    return candidate
