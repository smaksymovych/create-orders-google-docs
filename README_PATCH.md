Patched version: routes for DUTY_CARS are loaded from Google Sheets.

What changed:
- Added Sheets readonly scope and SPREADSHEET_ID in config/settings.py
- Added Sheets reader (per-car tab) and updated build_duty_cars_text(...) to:
  * include car only if column D (Дата) contains DD.MM for current date
  * take route from column AB (merged-safe); fallback to default_route_ids from templates.json
  * take purpose from templates.json duty_cars (purpose_id)

How to use:
1) Set SPREADSHEET_ID in config/settings.py
2) Ensure each car tab title in Google Sheets equals car_id from templates.json (CAR_1, CAR_2, ...)
   Tabs not in this list are ignored.
3) Column D must contain text dates like 25.12
4) Column AB contains route (may be merged).
