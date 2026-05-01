from __future__ import annotations

from io import BytesIO

import pandas as pd


def read_uploaded_csv(data: bytes) -> pd.DataFrame:
    return pd.read_csv(BytesIO(data), dtype=str, keep_default_na=False, encoding="utf-8-sig")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")

