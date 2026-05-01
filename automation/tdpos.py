from __future__ import annotations

import pandas as pd
from playwright.sync_api import sync_playwright


DEBUG_URL = "http://127.0.0.1:9222"


def clean_money(value: object) -> str:
    return str(value).replace("$", "").replace(",", "").strip()


def fill_input(page, selector: str, value: object) -> None:
    loc = page.locator(selector)
    loc.click()
    loc.press("Control+A")
    loc.press("Backspace")
    loc.fill(str(value))
    loc.blur()


def fill_tdpos_rows(
    df: pd.DataFrame,
    shipping_method: str,
    inhand_date: str,
    private_notes: str,
    tags: list[str],
    row_start: int | None = None,
    row_end: int | None = None,
) -> dict[str, int]:
    start = row_start or 1
    end = row_end or len(df)
    rows = df.iloc[start - 1 : end]

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(DEBUG_URL)
        if not browser.contexts:
            raise RuntimeError("No Chrome context found on port 9222.")

        context = browser.contexts[0]
        page = context.pages[-1] if context.pages else context.new_page()

        success = 0
        failed = 0
        for _, row in rows.iterrows():
            try:
                _fill_form(
                    page=page,
                    qty=row["QTY"],
                    section=row["SEC"],
                    seat_row=row["ROW"],
                    seat_from=row["SeatFrom"],
                    sell_price=clean_money(row["2026 List"]),
                    cost=clean_money(row["2026 Cost"]),
                    shipping_method=shipping_method,
                    inhand_date=inhand_date,
                    private_notes=private_notes,
                    tags=tags,
                )
                _submit_and_confirm(page)
                success += 1
                page.wait_for_timeout(300)
            except Exception:
                failed += 1

    return {"success": success, "failed": failed}


def _fill_form(
    page,
    qty: object,
    section: object,
    seat_row: object,
    seat_from: object,
    sell_price: object,
    cost: object,
    shipping_method: str,
    inhand_date: str,
    private_notes: str,
    tags: list[str],
) -> None:
    fill_input(page, "#poticket_available_now", qty)
    fill_input(page, "#poticket_section", section)
    fill_input(page, "#poticket_row", seat_row)
    fill_input(page, "#poticket_seat", seat_from)
    page.evaluate(
        """
        ([shippingMethod]) => {
          const sel = document.querySelector('#poticket_shipping_method');
          sel.value = shippingMethod;
          sel.dispatchEvent(new Event('change'));
        }
        """,
        [shipping_method],
    )
    fill_input(page, "#poticket_price", sell_price)
    fill_input(page, "#poticket_cost_price", cost)

    checkbox = page.locator("#poticket_lock_inventory")
    if not checkbox.is_checked():
        checkbox.click()

    page.evaluate(
        """
        ([inhandDate]) => {
          const input = document.querySelector('#poticket_inhand_date');
          input.removeAttribute('readonly');
          input.value = inhandDate;
          input.dispatchEvent(new Event('change'));
          input.setAttribute('readonly', '');
        }
        """,
        [inhand_date],
    )

    page.locator("#pohandletab_private").click()
    page.wait_for_timeout(200)
    fill_input(page, "#poticket_note_private", private_notes)

    tag_input = page.locator("#ponew_tag")
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        tag_input.click()
        tag_input.fill(tag)
        page.wait_for_timeout(300)
        option = page.locator(f'#potags_select option:text-is("{tag}")')
        if option.count() > 0:
            value = option.get_attribute("value")
            page.evaluate(
                """
                ([optionValue]) => {
                  const sel = document.querySelector('#potags_select');
                  sel.value = optionValue;
                  sel.dispatchEvent(new Event('change'));
                }
                """,
                [value],
            )


def _submit_and_confirm(page) -> None:
    page.locator("#ticket_edit_approve").click()
    page.wait_for_selector(".action.yes", state="visible", timeout=5000)
    page.locator(".action.yes").click()
    page.wait_for_timeout(500)

