from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .schemas import ALIASES


@dataclass
class ValidationIssue:
    rule: str
    severity: str
    file: str
    csv_row: int | str
    section: str = ""
    qty: str = ""
    row: str = ""
    seat_from: str = ""
    seat_thru: str = ""
    current_value: str = ""
    expected_value: str = ""
    message: str = ""


def parse_money(value: object) -> float | None:
    text = str(value).replace("$", "").replace(",", "").strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_number(value: object) -> float | None:
    text = str(value).replace(",", "").strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_money(value: float) -> str:
    return f"${value:,.2f}"


def normalize_columns(df: pd.DataFrame, required_columns: list[str]) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    normalized = pd.DataFrame()
    used_source_columns: set[str] = set()

    for target in required_columns:
        source = _find_source_column(df.columns, ALIASES[target])
        if source is None:
            issues.append(
                ValidationIssue(
                    rule="Format",
                    severity="Error",
                    file="",
                    csv_row="Header",
                    current_value=", ".join(df.columns),
                    expected_value=target,
                    message=f"Missing required column: {target}",
                )
            )
            continue
        normalized[target] = df[source].astype(str).str.strip()
        used_source_columns.add(source)

    extra_columns = [col for col in df.columns if col not in used_source_columns]
    for col in extra_columns:
        if str(col).strip() or df[col].astype(str).str.strip().any():
            issues.append(
                ValidationIssue(
                    rule="Format",
                    severity="Warning",
                    file="",
                    csv_row="Header",
                    current_value=str(col),
                    expected_value="Only canonical table columns",
                    message=f"Extra column will be ignored: {col}",
                )
            )

    return normalized, issues


def validate_file_structure(filename: str, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    unnamed = [col for col in df.columns if str(col).startswith("Unnamed")]
    empty_headers = [idx + 1 for idx, col in enumerate(df.columns) if str(col).strip() == ""]
    if unnamed or empty_headers:
        issues.append(
            ValidationIssue(
                rule="Format",
                severity="Error",
                file=filename,
                csv_row="Header",
                current_value=", ".join(map(str, df.columns)),
                expected_value="Named columns only",
                message="The header row has blank columns. Remove extra commas or empty columns.",
            )
        )

    header_like_rows = []
    for idx, row in df.iterrows():
        values = {str(v).strip().lower() for v in row.values}
        if "section" in values and ("row" in values or "qty" in values):
            header_like_rows.append(idx + 2)
    for row_num in header_like_rows:
        issues.append(
            ValidationIssue(
                rule="Format",
                severity="Error",
                file=filename,
                csv_row=row_num,
                message="A second header-like row was found inside the data. Remove extra content before rechecking.",
            )
        )

    return issues


def validate_required_values(filename: str, df: pd.DataFrame, required_columns: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for idx, row in df.iterrows():
        csv_row = idx + 2
        if not any(str(v).strip() for v in row.values):
            issues.append(
                ValidationIssue(
                    rule="Format",
                    severity="Error",
                    file=filename,
                    csv_row=csv_row,
                    message="Blank row found inside the table. Remove it before rechecking.",
                )
            )
            continue

        for col in required_columns:
            if str(row.get(col, "")).strip() == "":
                issues.append(
                    ValidationIssue(
                        rule="Format",
                        severity="Error",
                        file=filename,
                        csv_row=csv_row,
                        current_value="Blank",
                        expected_value=col,
                        message=f"Missing value in required column: {col}",
                    )
                )
    return issues


def validate_seat_count(filename: str, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for idx, row in df.iterrows():
        qty = parse_number(row.get("QTY"))
        seat_from = parse_number(row.get("SeatFrom"))
        seat_thru = parse_number(row.get("SeatThru"))
        if qty is None or seat_from is None or seat_thru is None:
            issues.append(
                ValidationIssue(
                    rule="Seat Count",
                    severity="Error",
                    file=filename,
                    csv_row=idx + 2,
                    section=str(row.get("Section", "")),
                    qty=str(row.get("QTY", "")),
                    row=str(row.get("Row", "")),
                    seat_from=str(row.get("SeatFrom", "")),
                    seat_thru=str(row.get("SeatThru", "")),
                    message="QTY, SeatFrom, and SeatThru must be numeric.",
                )
            )
            continue
        expected = int(seat_thru - seat_from + 1)
        if int(qty) != expected:
            issues.append(
                ValidationIssue(
                    rule="Seat Count",
                    severity="Error",
                    file=filename,
                    csv_row=idx + 2,
                    section=str(row.get("Section", "")),
                    qty=str(row.get("QTY", "")),
                    row=str(row.get("Row", "")),
                    seat_from=str(row.get("SeatFrom", "")),
                    seat_thru=str(row.get("SeatThru", "")),
                    current_value=str(int(qty)),
                    expected_value=str(expected),
                    message=(
                        f"QTY is {int(qty)}, but seats "
                        f"{int(seat_from)}-{int(seat_thru)} contain {expected} seat(s)."
                    ),
                )
            )
    return issues


def validate_duplicate_seats(filename: str, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[tuple[str, str, int], int] = {}

    for idx, row in df.iterrows():
        section = str(row.get("Section", "")).strip()
        row_name = str(row.get("Row", "")).strip()
        seat_from = parse_number(row.get("SeatFrom"))
        seat_thru = parse_number(row.get("SeatThru"))
        if seat_from is None or seat_thru is None:
            continue

        start = int(seat_from)
        end = int(seat_thru)
        if start > end:
            issues.append(
                ValidationIssue(
                    rule="Duplicate Seats",
                    severity="Error",
                    file=filename,
                    csv_row=idx + 2,
                    section=section,
                    row=row_name,
                    seat_from=str(start),
                    seat_thru=str(end),
                    message="SeatFrom is greater than SeatThru.",
                )
            )
            continue

        for seat in range(start, end + 1):
            key = (section, row_name, seat)
            if key in seen:
                issues.append(
                    ValidationIssue(
                        rule="Duplicate Seats",
                        severity="Error",
                        file=filename,
                        csv_row=idx + 2,
                        section=section,
                        row=row_name,
                        seat_from=str(start),
                        seat_thru=str(end),
                        current_value=f"Seat {seat}",
                        expected_value=f"Unique seat; first seen on CSV row {seen[key]}",
                        message=(
                            f"Duplicate seat found: Section {section}, Row {row_name}, Seat {seat}. "
                            f"First seen on CSV row {seen[key]}."
                        ),
                    )
                )
            else:
                seen[key] = idx + 2

    return issues


def validate_duplicate_stubhub_listings(filename: str, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[tuple[str, str, str], int] = {}

    for idx, row in df.iterrows():
        section = str(row.get("Section", "")).strip()
        row_name = str(row.get("Row", "")).strip()
        qty = str(row.get("QTY", "")).strip()
        key = (section, row_name, qty)
        if key in seen:
            issues.append(
                ValidationIssue(
                    rule="Duplicate Listings",
                    severity="Error",
                    file=filename,
                    csv_row=idx + 2,
                    section=section,
                    qty=qty,
                    row=row_name,
                    expected_value=f"Unique listing; first seen on CSV row {seen[key]}",
                    message=(
                        f"Duplicate StubHub listing found for Section {section}, "
                        f"Row {row_name}, QTY {qty}. First seen on CSV row {seen[key]}."
                    ),
                )
            )
        else:
            seen[key] = idx + 2

    return issues


def validate_pricing_order(filename: str, df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    grouped = df.groupby(["Section", "QTY"], dropna=False, sort=False)

    for (section, qty), listings in grouped:
        parsed = []
        for idx, row in listings.iterrows():
            row_num = parse_number(row.get("Row"))
            price = parse_money(row.get("Unit List Price"))
            if row_num is None or price is None:
                continue
            parsed.append((idx, row_num, price))

        parsed.sort(key=lambda item: item[1])
        for i, (a_idx, a_row, a_price) in enumerate(parsed):
            for b_idx, b_row, b_price in parsed[i + 1 :]:
                if b_row > a_row and b_price >= a_price:
                    issues.append(
                        ValidationIssue(
                            rule="Pricing Order",
                            severity="Fixable",
                            file=filename,
                            csv_row=b_idx + 2,
                            section=str(section),
                            qty=str(qty),
                            row=str(int(b_row) if b_row.is_integer() else b_row),
                            current_value=format_money(b_price),
                            expected_value=f"Lower than {format_money(a_price)} at row {int(a_row)}",
                            message=(
                                f"Same section and QTY: row {int(b_row)} has list price "
                                f"{format_money(b_price)}, which is not lower than row {int(a_row)} "
                                f"at {format_money(a_price)}."
                            ),
                        )
                    )
                    break

    return issues


def issues_to_dataframe(issues: Iterable[ValidationIssue]) -> pd.DataFrame:
    return pd.DataFrame([issue.__dict__ for issue in issues])


def _find_source_column(columns: Iterable[str], aliases: set[str]) -> str | None:
    for col in columns:
        if str(col).strip() in aliases:
            return col
    return None
