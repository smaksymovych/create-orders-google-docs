PATCH NOTES

1) Sheets reading A & D via batchGet (no index shifting)
- Reads only A (route) and D (date) starting from SHEETS_DATA_START_ROW
- If date matches and route empty -> returns empty route to trigger JSON default_route_ids fallback
- Uses normalized tab matching, but uses ORIGINAL tab title in ranges

2) Detailed logging
- Logs spreadsheet id, tab titles, normalized titles
- Per tab: logs ranges, rows fetched, preview of first 5 rows
- Logs MATCH / NO MATCH / SKIP with row numbers

3) settings.py updates
- Adds spreadsheets.readonly scope
- Adds SPREADSHEET_IDS (comma-separated), SHEETS_DATA_START_ROW, LOG_LEVEL, LOG_FILE

IMPORTANT:
- After adding new scope, delete token.json and re-login once.
