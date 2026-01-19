# Create Orders Google Docs (JSON-driven)

This project generates Google Docs documents from **one Google Docs template** and fills it with:
- **Inline placeholders** (single-line values): dates, unit name, commander, etc.
- **Block placeholders** (multi-line blocks): duty officer, duty driver, duty soldiers, duty cars

All configurable text lives in **one JSON file**: `config/templates.json`.

## Project structure

```
GoogleTabs/
├── Creaate_orders.py
├── OAuth.json                  # do not commit
├── token.json                  # do not commit (generated)
├── README.md
└── config/
    ├── __init__.py
    ├── settings.py
    └── templates.json
```

## Template requirements (Google Docs)

Your template document must contain placeholders like:

Inline (examples):
- `{{UNIT_NAME}}`
- `{{CITY}}`
- `{{COMMANDER}}`
- `{{TARGET_DATE}}`
- `{{DATE_BEFORE}}`
- `{{DATE_NEXT}}`
- `{{ODR_NUM}}`
- `{{ODR_IDX}}`

Blocks (examples):
- `{{DUTY_KSP_BLOCK}}`
- `{{DUTY_DRIVE_BLOCK}}`
- `{{DUTY_SOLDIERS}}`
- `{{DUTY_CARS_BLOCK}}`

> Tip: type placeholders as plain text (not partially bold/italic) to avoid formatting surprises.

## Setup

1) Install dependencies:

```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

2) Put your Google OAuth Desktop client JSON as `OAuth.json` in the project root.

3) Open `config/settings.py` and set:
- `FOLDER_ID`
- `TEMPLATE_DOC_ID`

4) Edit `config/templates.json` with your content.

## Run

From the project root:

```bash
python Creaate_orders.py
```

On first run, your browser will open for Google login. `token.json` will be created automatically.

## Duty selection logic

- Duty officer text is selected by day of month:
  - 1,4,7,... → `first_pair_duty_officer`
  - 2,5,8,... → `second_pair_duty_officer`
  - 3,6,9,... → `third_pair_duty_officer`

- Duty driver text:
  - odd days → `first_duty_driver`
  - even days → `second_duty_driver`

## Notes

- Inline replacements are normalized (newlines replaced with spaces).
- Block replacements keep newlines.
