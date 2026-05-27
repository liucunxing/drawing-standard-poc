"""Lazy StructEqTable / StructTable adapter."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

from table_recognition.engines.base import RecognitionResult


class StructEqTableEngine:
    name = "structeqtable"

    _RECOMMENDED_CKPT = "U4R/StructTable-InternVL2-1B"

    def __init__(
        self,
        ckpt_path: str | None = None,
        output_formats: tuple[str, ...] | None = None,
    ) -> None:
        self.ckpt_path = ckpt_path or os.environ.get("STRUCT_EQTABLE_CKPT_PATH")
        self.output_formats = output_formats or _parse_output_formats(
            os.environ.get("STRUCT_EQTABLE_OUTPUT_FORMATS")
        )
        self._module: Any | None = None
        self._model: Any | None = None
        self._import_errors: list[str] = []

    def recognize(self, image_path: Path, candidate_metadata: dict[str, Any]) -> RecognitionResult:
        module, import_errors = self._import_module()
        if module is None:
            return RecognitionResult(
                status="engine_unavailable",
                raw_output="",
                json_data={
                    "engine": self.name,
                    "available": False,
                    "import_errors": import_errors,
                },
                error_message="StructEqTable / StructTable dependency is not importable.",
                engine_message=(
                    "Install struct-eqtable before running the real adapter."
                ),
            )

        try:
            model = self._get_model(module)
        except StructEqTableUnavailable as exc:
            return RecognitionResult(
                status="engine_unavailable",
                json_data={
                    "engine": self.name,
                    "available": True,
                    "module": getattr(module, "__name__", ""),
                    "model_configured": bool(self.ckpt_path),
                    "configured_ckpt_path": self.ckpt_path or "",
                    "recommended_ckpt_path": self._RECOMMENDED_CKPT,
                },
                error_message=str(exc),
                engine_message=(
                    "StructEqTable dependency is installed, but model loading is not ready. "
                    "Set STRUCT_EQTABLE_CKPT_PATH or pass --structeqtable-ckpt to enable real inference."
                ),
            )
        except Exception as exc:  # pragma: no cover - depends on optional engine.
            return RecognitionResult(
                status="failed",
                raw_output="",
                json_data={
                    "engine": self.name,
                    "available": True,
                    "module": getattr(module, "__name__", ""),
                },
                error_message=f"{type(exc).__name__}: {exc}",
                engine_message="StructEqTable / StructTable invocation failed.",
            )

        try:
            raw_result = self._run_model(model, image_path)
        except Exception as exc:  # pragma: no cover - depends on optional engine.
            return RecognitionResult(
                status="failed",
                raw_output="",
                json_data={
                    "engine": self.name,
                    "available": True,
                    "module": getattr(module, "__name__", ""),
                    "ckpt_path": self.ckpt_path,
                },
                error_message=f"{type(exc).__name__}: {exc}",
                engine_message="StructEqTable / StructTable inference failed.",
            )

        return self._normalize_result(raw_result, image_path, candidate_metadata, module)

    def _import_module(self) -> tuple[Any | None, list[str]]:
        if self._module is not None:
            return self._module, self._import_errors
        try:
            self._module = importlib.import_module("struct_eqtable")
            return self._module, self._import_errors
        except Exception as exc:  # pragma: no cover - environment dependent.
            self._import_errors.append(f"struct_eqtable: {type(exc).__name__}: {exc}")
            return None, self._import_errors

    def _get_model(self, module: Any) -> Any:
        if self._model is not None:
            return self._model
        if not self.ckpt_path:
            raise StructEqTableUnavailable(
                "StructEqTable model checkpoint is not configured."
            )
        build_model = getattr(module, "build_model", None)
        if not callable(build_model):
            raise StructEqTableUnavailable(
                "struct_eqtable.build_model is unavailable in the installed package."
            )
        self._model = build_model(self.ckpt_path)
        try:
            self._model.eval()
        except AttributeError:
            pass
        return self._model

    def _run_model(self, model: Any, image_path: Path) -> dict[str, Any]:
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        outputs: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for output_format in self.output_formats:
            try:
                outputs[output_format] = model(image, output_format=output_format)
            except TypeError:
                outputs[output_format] = model(image)
            except Exception as exc:  # pragma: no cover - depends on optional engine.
                errors[output_format] = f"{type(exc).__name__}: {exc}"
        return {
            "outputs": outputs,
            "errors": errors,
            "output_formats": list(self.output_formats),
        }

    def _normalize_result(
        self,
        raw_result: Any,
        image_path: Path,
        candidate_metadata: dict[str, Any],
        module: Any,
    ) -> RecognitionResult:
        serialized = _json_safe(raw_result)
        output_dict = serialized if isinstance(serialized, dict) else {}
        outputs = output_dict.get("outputs", {})
        output_errors = output_dict.get("errors", {})
        outputs = outputs if isinstance(outputs, dict) else {}
        output_errors = output_errors if isinstance(output_errors, dict) else {}

        html = _format_output(outputs.get("html"))
        markdown = _format_output(outputs.get("markdown"))
        csv_text = _first_text(output_dict, ("csv", "csv_text", "table_csv"))
        raw_output = raw_result if isinstance(raw_result, str) else json.dumps(serialized, ensure_ascii=False, indent=2)
        latex = _format_output(outputs.get("latex"))
        if not markdown and latex:
            markdown = f"```latex\n{latex}\n```\n"

        json_data = {
            "engine": self.name,
            "module": getattr(module, "__name__", ""),
            "ckpt_path": self.ckpt_path,
            "source_image_path": str(image_path),
            "candidate": {
                "region_id": candidate_metadata.get("region_id"),
                "candidate_index": candidate_metadata.get("candidate_index"),
                "zone": candidate_metadata.get("zone"),
                "candidate_kind": candidate_metadata.get("candidate_kind"),
            },
            "normalized_output": serialized,
            "normalization_notes": [],
        }
        if output_errors:
            json_data["output_errors"] = output_errors
        if not csv_text:
            json_data["normalization_notes"].append("CSV output was not detected in raw engine result.")
        if not html:
            json_data["normalization_notes"].append("HTML output was not detected in raw engine result.")

        status = "succeeded" if any(outputs.values()) else "failed"
        return RecognitionResult(
            status=status,
            raw_output=raw_output,
            html=html,
            markdown=markdown,
            csv_text=csv_text,
            json_data=json_data,
            error_message="" if status == "succeeded" else "StructEqTable produced no output.",
            engine_message="StructEqTable / StructTable adapter completed.",
        )


class StructEqTableUnavailable(RuntimeError):
    pass


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return repr(value)


def _first_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _format_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "\n".join(value)
    return json.dumps(_json_safe(value), ensure_ascii=False, indent=2)


def _parse_output_formats(raw_value: str | None) -> tuple[str, ...]:
    if not raw_value:
        return ("html", "markdown", "latex")
    formats = tuple(
        value.strip().lower()
        for value in raw_value.split(",")
        if value.strip()
    )
    return formats or ("html", "markdown", "latex")
