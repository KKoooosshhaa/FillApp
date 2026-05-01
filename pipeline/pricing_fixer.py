from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .validators import format_money, parse_money, parse_number


@dataclass
class PriceChange:
    file: str
    section: str
    qty: str
    csv_row: int
    row: str
    old_price: str
    new_price: str
    reason: str


def longest_strictly_decreasing_subsequence(prices: list[float]) -> list[int]:
    n = len(prices)
    if n == 0:
        return []

    dp = [1] * n
    parent = [-1] * n

    for i in range(1, n):
        for j in range(i):
            if prices[j] > prices[i] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                parent[i] = j

    end_idx = max(range(n), key=lambda idx: dp[idx])
    indices = []
    while end_idx != -1:
        indices.append(end_idx)
        end_idx = parent[end_idx]
    return sorted(indices)


def interpolate_prices(row_nums: list[float], anchor_indices: list[int], anchor_prices: list[float]) -> list[float | None]:
    result: list[float | None] = [None] * len(row_nums)
    for idx, price in zip(anchor_indices, anchor_prices):
        result[idx] = price

    for i in range(len(row_nums)):
        if result[i] is not None:
            continue

        left = next((a for a in reversed(anchor_indices) if a < i), None)
        right = next((a for a in anchor_indices if a > i), None)

        if left is not None and right is not None:
            r0, p0 = row_nums[left], result[left]
            r1, p1 = row_nums[right], result[right]
            assert p0 is not None and p1 is not None
            t = (row_nums[i] - r0) / (r1 - r0) if r1 != r0 else 0.5
            result[i] = round(p0 + t * (p1 - p0), 2)
        elif left is not None and len(anchor_indices) >= 2:
            a, b = anchor_indices[-2], anchor_indices[-1]
            r0, p0 = row_nums[a], result[a]
            r1, p1 = row_nums[b], result[b]
            assert p0 is not None and p1 is not None
            slope = (p1 - p0) / (r1 - r0) if r1 != r0 else 0
            result[i] = round(p1 + slope * (row_nums[i] - r1), 2)
        elif right is not None and len(anchor_indices) >= 2:
            a, b = anchor_indices[0], anchor_indices[1]
            r0, p0 = row_nums[a], result[a]
            r1, p1 = row_nums[b], result[b]
            assert p0 is not None and p1 is not None
            slope = (p1 - p0) / (r1 - r0) if r1 != r0 else 0
            result[i] = round(p0 + slope * (row_nums[i] - r0), 2)
        elif left is not None:
            base = result[left]
            result[i] = round((base or 0) - 0.01, 2)
        elif right is not None:
            base = result[right]
            result[i] = round((base or 0) + 0.01, 2)

    return result


def propose_pricing_fixes(filename: str, df: pd.DataFrame) -> tuple[pd.DataFrame, list[PriceChange], list[str]]:
    fixed = df.copy()
    changes: list[PriceChange] = []
    blockers: list[str] = []

    for (section, qty), group in fixed.groupby(["Section", "QTY"], dropna=False, sort=False):
        parsed = []
        for idx, row in group.iterrows():
            row_num = parse_number(row.get("Row"))
            price = parse_money(row.get("Unit List Price"))
            if row_num is not None and price is not None:
                parsed.append((idx, row_num, price))

        if len(parsed) < 3:
            blockers.append(
                f"{filename}: Section {section}, QTY {qty} has fewer than 3 numeric row/price points, so the app cannot confidently auto-fix pricing."
            )
            continue

        parsed.sort(key=lambda item: item[1])
        prices = [item[2] for item in parsed]
        row_nums = [item[1] for item in parsed]
        anchors = longest_strictly_decreasing_subsequence(prices)
        if len(anchors) < 2:
            blockers.append(
                f"{filename}: Section {section}, QTY {qty} does not have enough decreasing anchor prices to interpolate."
            )
            continue

        fixed_prices = interpolate_prices(row_nums, anchors, [prices[i] for i in anchors])
        for pos, (orig_idx, row_num, old_price) in enumerate(parsed):
            if pos in anchors:
                continue
            new_price = fixed_prices[pos]
            if new_price is None:
                continue
            if abs(new_price - old_price) <= 0.01:
                continue
            fixed.at[orig_idx, "Unit List Price"] = format_money(new_price)
            changes.append(
                PriceChange(
                    file=filename,
                    section=str(section),
                    qty=str(qty),
                    csv_row=orig_idx + 2,
                    row=str(int(row_num) if row_num.is_integer() else row_num),
                    old_price=format_money(old_price),
                    new_price=format_money(new_price),
                    reason="Interpolated from the longest strictly decreasing price sequence.",
                )
            )

    final_changes = _enforce_strict_decrease(filename, fixed)
    changes.extend(final_changes)
    return fixed, changes, blockers


def price_changes_to_dataframe(changes: list[PriceChange]) -> pd.DataFrame:
    return pd.DataFrame([change.__dict__ for change in changes])


def _enforce_strict_decrease(filename: str, df: pd.DataFrame) -> list[PriceChange]:
    changes: list[PriceChange] = []
    for (section, qty), group in df.groupby(["Section", "QTY"], dropna=False, sort=False):
        parsed = []
        for idx, row in group.iterrows():
            row_num = parse_number(row.get("Row"))
            price = parse_money(row.get("Unit List Price"))
            if row_num is not None and price is not None:
                parsed.append((idx, row_num, price))
        parsed.sort(key=lambda item: item[1])

        prev_price: float | None = None
        prev_row: float | None = None
        for idx, row_num, price in parsed:
            if prev_price is not None and prev_row is not None and row_num != prev_row and price >= prev_price:
                new_price = round(prev_price - 0.01, 2)
                df.at[idx, "Unit List Price"] = format_money(new_price)
                changes.append(
                    PriceChange(
                        file=filename,
                        section=str(section),
                        qty=str(qty),
                        csv_row=idx + 2,
                        row=str(int(row_num) if row_num.is_integer() else row_num),
                        old_price=format_money(price),
                        new_price=format_money(new_price),
                        reason="Final pass enforced lower price for higher row.",
                    )
                )
                prev_price = new_price
            else:
                prev_price = price
            prev_row = row_num
    return changes

