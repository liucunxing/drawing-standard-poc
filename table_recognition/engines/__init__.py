"""Recognition engine adapters."""

from table_recognition.engines.base import RecognitionResult, TableRecognitionEngine
from table_recognition.engines.mock_engine import MockTableRecognitionEngine
from table_recognition.engines.structeqtable_engine import StructEqTableEngine

__all__ = [
    "MockTableRecognitionEngine",
    "RecognitionResult",
    "StructEqTableEngine",
    "TableRecognitionEngine",
]
