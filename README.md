# Google Docs orders generator (JSON-driven)

One template (Google Docs) + JSON catalogs + placeholders.

## Install

```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

## Configure

1) Put OAuth Desktop client JSON as `OAuth.json` in project root.
2) Set `FOLDER_ID` and `TEMPLATE_DOC_ID` in `config/settings.py`
3) Fill `config/templates.json`

## Template placeholders

Inline:
- `{{UNIT_NAME}}`, `{{CITY}}`, `{{COMMANDER}}`
- `{{TARGET_DATE}}`, `{{DATE_BEFORE}}`, `{{DATE_NEXT}}`, `{{ODR_NUM}}`, `{{ODR_IDX}}`

Blocks:
- `{{DUTY_KSP_BLOCK}}`
- `{{DUTY_DRIVE_BLOCK}}`
- `{{DUTY_SOLDIERS}}`
- `{{DUTY_CARS_BLOCK}}`
