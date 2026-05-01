from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from automation.chrome import DEFAULT_CHROME_PATH, DEFAULT_DEBUG_PORT, chrome_launch_command, is_debug_port_open
from automation.stubhub import fill_stubhub_rows
from automation.tdpos import fill_tdpos_rows
from pipeline.exporters import export_for_stubhub, export_for_tdpos
from pipeline.io import read_uploaded_csv, to_csv_bytes
from pipeline.pricing_fixer import price_changes_to_dataframe, propose_pricing_fixes
from pipeline.schemas import CANONICAL_COLUMNS, PLATFORM_INPUT_COLUMNS, PLATFORMS, STUBHUB_INPUT_COLUMNS
from pipeline.validators import (
    issues_to_dataframe,
    normalize_columns,
    validate_duplicate_seats,
    validate_duplicate_stubhub_listings,
    validate_file_structure,
    validate_pricing_order,
    validate_required_values,
    validate_seat_count,
)


st.set_page_config(page_title="Fill App", layout="wide")


def main() -> None:
    st.title("Fill App")
    st.caption("Validate clean consignment CSVs, prepare platform files, then run local browser-assisted filling.")

    platform = st.radio("Platform", PLATFORMS, horizontal=True)
    uploaded_files = st.file_uploader("Upload CSV file(s)", type=["csv"], accept_multiple_files=True)

    if not uploaded_files:
        _show_expected_format(platform)
        return

    all_ready_frames: list[pd.DataFrame] = []
    all_issues = []
    all_changes = []
    blockers: list[str] = []
    required_columns = PLATFORM_INPUT_COLUMNS[platform]

    for uploaded in uploaded_files:
        raw_df = read_uploaded_csv(uploaded.getvalue())
        structure_issues = validate_file_structure(uploaded.name, raw_df)
        normalized, column_issues = normalize_columns(raw_df, required_columns)
        for issue in column_issues:
            issue.file = uploaded.name

        issues = []
        issues.extend(structure_issues)
        issues.extend(column_issues)
        if not any(issue.severity == "Error" for issue in issues):
            issues.extend(validate_required_values(uploaded.name, normalized, required_columns))
            if platform == "TDPOS":
                issues.extend(validate_seat_count(uploaded.name, normalized))
                issues.extend(validate_duplicate_seats(uploaded.name, normalized))
            else:
                issues.extend(validate_duplicate_stubhub_listings(uploaded.name, normalized))

        fixed_df = normalized
        if not any(issue.severity == "Error" for issue in issues):
            pricing_issues = validate_pricing_order(uploaded.name, normalized)
            if pricing_issues:
                fixed_df, changes, file_blockers = propose_pricing_fixes(uploaded.name, normalized)
                all_changes.extend(changes)
                blockers.extend(file_blockers)
                if file_blockers:
                    issues.extend(pricing_issues)

        all_issues.extend(issues)
        if not any(issue.severity == "Error" for issue in issues) and not blockers:
            all_ready_frames.append(fixed_df)

    if all_issues:
        st.subheader("Validation Results")
        st.dataframe(issues_to_dataframe(all_issues), use_container_width=True)
        st.download_button(
            "Download error report",
            data=to_csv_bytes(issues_to_dataframe(all_issues)),
            file_name="validation_errors.csv",
            mime="text/csv",
        )

    if blockers:
        st.error("Some pricing issues need manual CSV correction.")
        for blocker in blockers:
            st.write(blocker)
        st.info("Correct the CSV, upload it again, and recheck from this page.")
        return

    if all_changes:
        st.subheader("Proposed Pricing Changes")
        st.dataframe(price_changes_to_dataframe(all_changes), use_container_width=True)
        approved = st.checkbox("I approve these pricing changes")
        if not approved:
            st.info("Approve the proposed changes to continue, or correct the CSV manually and upload again.")
            return

    if any(issue.severity == "Error" for issue in all_issues):
        st.info("Fix the errors in the CSV, then upload again to recheck.")
        return

    empty_columns = CANONICAL_COLUMNS if platform == "TDPOS" else STUBHUB_INPUT_COLUMNS
    ready_df = pd.concat(all_ready_frames, ignore_index=True) if all_ready_frames else pd.DataFrame(columns=empty_columns)
    st.subheader("Final Dataset")
    st.dataframe(ready_df, use_container_width=True)

    export_df = export_for_tdpos(ready_df) if platform == "TDPOS" else export_for_stubhub(ready_df)
    export_name = "tdpos_ready.csv" if platform == "TDPOS" else "stubhub_ready.csv"

    st.download_button(
        f"Download {platform} CSV",
        data=to_csv_bytes(export_df),
        file_name=export_name,
        mime="text/csv",
    )

    st.divider()
    _automation_panel(platform, export_df)


def _show_expected_format(platform: str) -> None:
    st.subheader("Expected Input Format")
    st.write("The CSV header must be the first row. No notes, blank intro rows, totals, or footer content.")
    if platform == "TDPOS":
        example = pd.DataFrame(
            [
                {
                    "QTY": "2",
                    "Section": "104",
                    "Row": "12",
                    "SeatFrom": "1",
                    "SeatThru": "2",
                    "Unit Cost": "$218.00",
                    "Unit List Price": "$1,600.00",
                }
            ],
            columns=CANONICAL_COLUMNS,
        )
    else:
        example = pd.DataFrame(
            [{"Quantity": "2", "Section": "212", "Row": "23", "Unit List Price": "$519.98"}],
            columns=["Quantity", "Section", "Row", "Unit List Price"],
        )
    st.dataframe(example, use_container_width=True)


def _automation_panel(platform: str, export_df: pd.DataFrame) -> None:
    st.subheader("Browser Automation")
    st.write("Launch Chrome in debug mode, then confirm when the correct page is ready.")

    chrome_path = Path(st.text_input("Chrome path", str(DEFAULT_CHROME_PATH)))
    profile_dir = Path(st.text_input("Debug profile folder", r"C:\Users\KooshaKabiri\chrome_debug_profile"))
    port = st.number_input("Debug port", min_value=1000, max_value=65535, value=DEFAULT_DEBUG_PORT, step=1)

    st.info(
        "Open PowerShell, run this command, then use the Chrome window that opens to log in and navigate "
        "to the correct page. Leave that Chrome window open while the app fills the listings."
    )
    st.code(chrome_launch_command(chrome_path, profile_dir, int(port)), language="powershell")
    st.metric("Chrome debug connection", "Open" if is_debug_port_open(int(port)) else "Closed")

    page_ready = st.checkbox("The correct page is open and ready to fill")
    if not page_ready:
        return

    if platform == "TDPOS":
        shipping_method = st.text_input("Shipping method value", "7")
        inhand_date = st.text_input("In-hand date", "03/01/2027")
        private_notes = st.text_input("Private notes", "NOVIVID2 NOGOT2 NOTP2 NOSTUB2")
        tags = st.text_input("Tags, comma-separated", "anthony@venuekings.com, vk, autoprice")
        start = st.number_input("Start row", min_value=1, max_value=max(len(export_df), 1), value=1)
        end = st.number_input("End row", min_value=1, max_value=max(len(export_df), 1), value=max(len(export_df), 1))
        if st.button("Start TDPOS automation", type="primary"):
            try:
                result = fill_tdpos_rows(
                    export_df,
                    shipping_method=shipping_method,
                    inhand_date=inhand_date,
                    private_notes=private_notes,
                    tags=[tag.strip() for tag in tags.split(",")],
                    row_start=int(start),
                    row_end=int(end),
                )
                st.success(f"Finished. Success: {result['success']}, Failed: {result['failed']}")
            except Exception as exc:
                st.error(str(exc))
    else:
        stubhub_face_value = st.text_input("Face value", "200.00")
        if st.button("Start StubHub automation", type="primary"):
            try:
                result = fill_stubhub_rows(export_df, face_value=stubhub_face_value)
                st.success(f"Finished. Success: {result['success']}, Failed: {result['failed']}")
            except Exception as exc:
                st.error(str(exc))


if __name__ == "__main__":
    main()
