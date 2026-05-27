"""Deterministic mock engine for validating the Phase 3 pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from table_recognition.engines.base import RecognitionResult


class MockTableRecognitionEngine:
    name = "mock"

    def recognize(self, image_path: Path, candidate_metadata: dict[str, Any]) -> RecognitionResult:
        region_id = str(candidate_metadata.get("region_id", "unknown_region"))
        candidate_index = candidate_metadata.get("candidate_index")
        zone = str(candidate_metadata.get("zone", "unknown_zone"))
        candidate_kind = str(candidate_metadata.get("candidate_kind", "table"))

        markdown = (
            "| field | value |\n"
            "|---|---|\n"
            f"| engine | {self.name} |\n"
            f"| region_id | {region_id} |\n"
            f"| candidate_index | {candidate_index} |\n"
            f"| zone | {zone} |\n"
            f"| candidate_kind | {candidate_kind} |\n"
            "| note | mock placeholder, not OCR output |\n"
        )
        html = (
            "<table>"
            "<thead><tr><th>field</th><th>value</th></tr></thead>"
            "<tbody>"
            f"<tr><td>engine</td><td>{self.name}</td></tr>"
            f"<tr><td>region_id</td><td>{region_id}</td></tr>"
            f"<tr><td>candidate_index</td><td>{candidate_index}</td></tr>"
            f"<tr><td>zone</td><td>{zone}</td></tr>"
            f"<tr><td>candidate_kind</td><td>{candidate_kind}</td></tr>"
            "<tr><td>note</td><td>mock placeholder, not OCR output</td></tr>"
            "</tbody></table>"
        )
        csv_text = (
            "field,value\n"
            f"engine,{self.name}\n"
            f"region_id,{region_id}\n"
            f"candidate_index,{candidate_index}\n"
            f"zone,{zone}\n"
            f"candidate_kind,{candidate_kind}\n"
            "\"note\",\"mock placeholder, not OCR output\"\n"
        )
        json_data: dict[str, Any] = {
            "engine": self.name,
            "is_mock": True,
            "message": "Mock placeholder result. This is not OCR or real table recognition.",
            "source_image_path": str(image_path),
            "candidate": {
                "region_id": region_id,
                "candidate_index": candidate_index,
                "zone": zone,
                "candidate_kind": candidate_kind,
            },
            "rows": [
                {"field": "engine", "value": self.name},
                {"field": "region_id", "value": region_id},
                {"field": "candidate_index", "value": candidate_index},
                {"field": "zone", "value": zone},
                {"field": "candidate_kind", "value": candidate_kind},
                {"field": "note", "value": "mock placeholder, not OCR output"},
            ],
        }
        raw_output = (
            f"MOCK_TABLE_RECOGNITION\n"
            f"region_id={region_id}\n"
            f"candidate_index={candidate_index}\n"
            f"zone={zone}\n"
            f"candidate_kind={candidate_kind}\n"
            "note=mock placeholder, not OCR output\n"
        )

        return RecognitionResult(
            status="succeeded",
            raw_output=raw_output,
            html=html,
            markdown=markdown,
            csv_text=csv_text,
            json_data=json_data,
            engine_message="Mock engine completed. Result is deterministic placeholder output.",
        )
