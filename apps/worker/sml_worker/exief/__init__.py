"""EXIEF: metadata-only AI-generation signals (ExifTool tags -> weighted signals -> verdict).

`signals.py` and `pipeline.py` are verbatim copies of the owner's EXIEF analyzer
(/home/shahidmuneer/exief_signals/aigc-studio/server/analyzer, copied 2026-10-01). To update,
copy both files over again unchanged; the platform only uses `analyze_records` and the signal
registry. ExifTool itself is run by `sml_worker.adapters.metadata` with the analyzer's flags.
"""

from .pipeline import analyze_records
from .signals import SIGNALS_BY_ID, verdict_for

__all__ = ["SIGNALS_BY_ID", "analyze_records", "verdict_for"]
