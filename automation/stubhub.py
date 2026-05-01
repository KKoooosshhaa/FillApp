from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright


DEBUG_URL = "http://127.0.0.1:9222"


def fill_stubhub_rows(df: pd.DataFrame, face_value: str) -> dict[str, int]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(DEBUG_URL)
        if not browser.contexts:
            raise RuntimeError("No Chrome context found on port 9222.")

        context = browser.contexts[0]
        page = context.pages[-1] if context.pages else context.new_page()
        success = 0
        failed = 0

        for _, row in df.iterrows():
            try:
                _add_section_and_fill(
                    page,
                    section=str(row["Section"]).strip(),
                    seat_row=str(row["Row"]).strip(),
                    quantity=str(row["Quantity"]).strip(),
                    proceeds=str(row["Unit List Price"]).replace("$", "").replace(",", "").strip(),
                    face_value=face_value,
                )
                success += 1
            except Exception:
                failed += 1
            page.wait_for_timeout(200)

    return {"success": success, "failed": failed}


def _add_section_and_fill(page, section: str, seat_row: str, quantity: str, proceeds: str, face_value: str) -> None:
    page.get_by_role("button", name="+ Add Section").click()
    _select_last_combobox_option(page, section)
    _select_last_combobox_option(page, seat_row)

    inputs = page.locator('input[type="number"]')
    count = inputs.count()
    if count < 5:
        raise RuntimeError("Not enough numeric inputs found.")

    _fill_input(inputs.nth(count - 5), quantity)
    _fill_input(inputs.nth(count - 4), quantity)
    _fill_input(inputs.nth(count - 3), proceeds)
    _fill_input(inputs.nth(count - 1), face_value)


def _select_last_combobox_option(page, target_text: str) -> None:
    combos = page.locator('button[role="combobox"]')
    combos.nth(combos.count() - 1).click()
    page.wait_for_selector('[role="option"], [role="listbox"]', state="visible", timeout=3000)

    input_box = page.locator('[role="combobox"] input, input[type="text"]').last
    input_box.fill("")
    page.wait_for_timeout(100)
    input_box.fill(target_text)

    options = page.locator('[role="option"]')
    for i in range(options.count()):
        if options.nth(i).inner_text().strip() == target_text:
            options.nth(i).click()
            page.keyboard.press("Escape")
            return

    raise RuntimeError(f'Exact option "{target_text}" not found.')


def _fill_input(locator, value: str) -> None:
    locator.click()
    locator.press("Control+A")
    locator.press("Backspace")
    locator.fill(value)
    locator.blur()

