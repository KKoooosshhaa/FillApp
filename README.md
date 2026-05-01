# Fill App

A local Streamlit app for preparing clean ticket consignment CSVs and running browser-assisted fill automation.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Expected Input CSVs

The CSV header must be the first row. Do not include notes, blank rows before the header, totals, footer text, or extra content outside the actual table.

### TDPOS

```csv
QTY,Section,Row,SeatFrom,SeatThru,Unit Cost,Unit List Price
```

### StubHub

```csv
Quantity,Section,Row,Unit List Price
```

Accepted aliases are supported for common names like `QTY`, `SEC`, `ROW`, `2026 Cost`, and `2026 List`, but the cleaner the input file is, the better. Seat-count and duplicate-seat validation only apply to TDPOS files because StubHub input does not include seat ranges.

For StubHub automation, `Face Value` is entered in the app before filling starts. It is not required in the uploaded CSV. The default is `200.00`, matching the original `stubhub_fill.py` script.

## Workflow

1. Choose `TDPOS` or `StubHub`.
2. Upload one or more CSV files.
3. Review validation results.
4. Approve proposed pricing fixes when available.
5. Download the final platform CSV.
6. Launch Chrome from the app, navigate to the correct page, confirm readiness, and start automation.

## Chrome Automation

After validation, the app shows a PowerShell command for opening Chrome in debug mode. Run that command manually in PowerShell:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:LOCALAPPDATA\FillApp\chrome_debug_profile" --no-first-run --new-window about:blank
```

Then log in, navigate to the correct page, leave that Chrome window open, and return to the app. The app connects Playwright to `127.0.0.1:9222` and starts filling only after you confirm the page is ready.
