from __future__ import annotations

from dataclasses import dataclass


PLATFORMS = ("TDPOS", "StubHub")


CANONICAL_COLUMNS = [
    "QTY",
    "Section",
    "Row",
    "SeatFrom",
    "SeatThru",
    "Unit Cost",
    "Unit List Price",
]

STUBHUB_INPUT_COLUMNS = [
    "QTY",
    "Section",
    "Row",
    "Unit List Price",
]

TDPOS_INPUT_COLUMNS = CANONICAL_COLUMNS

PLATFORM_INPUT_COLUMNS = {
    "TDPOS": TDPOS_INPUT_COLUMNS,
    "StubHub": STUBHUB_INPUT_COLUMNS,
}


TDPOS_EXPORT_COLUMNS = [
    "QTY",
    "SEC",
    "ROW",
    "SeatFrom",
    "SeatThru",
    "2026 Cost",
    "2026 List",
]


STUBHUB_EXPORT_COLUMNS = [
    "Quantity",
    "Section",
    "Row",
    "Unit List Price",
]


ALIASES = {
    "QTY": {"QTY", "Qty", "Quantity"},
    "Section": {"Section", "SEC", "Sec"},
    "Row": {"Row", "ROW"},
    "SeatFrom": {"SeatFrom", "Seat From", "Seat Low", "Seats Low"},
    "SeatThru": {"SeatThru", "Seat Thru", "Seat High", "Seats High", "High"},
    "Unit Cost": {"Unit Cost", "Cost", "2026 Cost", "2026 Unit Cost", "2026 Cost Per"},
    "Unit List Price": {
        "Unit List Price",
        "List Price",
        "2026 List",
        "2026 List Price",
        "2026 Unit List Price",
    },
}


@dataclass(frozen=True)
class UploadedCsv:
    filename: str
    data: bytes
