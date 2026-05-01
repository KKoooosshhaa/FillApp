from __future__ import annotations

import pandas as pd

from .schemas import STUBHUB_EXPORT_COLUMNS, TDPOS_EXPORT_COLUMNS
from .validators import format_money, parse_money


def export_for_tdpos(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["QTY"] = df["QTY"]
    out["SEC"] = df["Section"]
    out["ROW"] = df["Row"]
    out["SeatFrom"] = df["SeatFrom"]
    out["SeatThru"] = df["SeatThru"]
    out["2026 Cost"] = df["Unit Cost"].map(_money_or_original)
    out["2026 List"] = df["Unit List Price"].map(_money_or_original)
    return out[TDPOS_EXPORT_COLUMNS]


def export_for_stubhub(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["Quantity"] = df["QTY"]
    out["Section"] = df["Section"]
    out["Row"] = df["Row"]
    out["Unit List Price"] = df["Unit List Price"].map(_money_or_original)
    return out[STUBHUB_EXPORT_COLUMNS]


def _money_or_original(value: object) -> str:
    parsed = parse_money(value)
    return format_money(parsed) if parsed is not None else str(value).strip()

