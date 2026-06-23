"""Shared mutable state — loaded once at startup."""
from typing import Any, Optional
import pandas as pd

model: Any   = None
encoders: dict[str, Any] = {}
zones_df: Optional[pd.DataFrame] = None

# Historical incidents (MDI 2019–2025) — loaded once, used for the summary tables
incidents_df: Optional[pd.DataFrame] = None

# Pre-encoding maps: original_value → alphabetical_index_str
idx_subcircuito: dict[str, str] = {}
idx_circuito:    dict[str, str] = {}
idx_distrito:    dict[str, str] = {}
idx_macro_lugar: dict[str, str] = {}
idx_flag_coord:  dict[str, str] = {}
idx_iccs:        dict[str, str] = {}

# Human-readable label maps
iccs_labels:     dict[str, str] = {}
district_labels: dict[str, str] = {}
circuit_labels:  dict[str, str] = {}
delito_options:  list[dict]     = []
