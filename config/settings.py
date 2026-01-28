from pathlib import Path

# ================== PATHS ==================
BASE_DIR = Path(__file__).resolve().parents[1]          # .../GoogleTabs
CONFIG_DIR = BASE_DIR / "config"
TEMPLATES_JSON_PATH = str(CONFIG_DIR / "templates.json")

# ================== GOOGLE API ==================
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# OAuth client (Desktop) JSON from Google Cloud Console:
OAUTH_FILE = str(BASE_DIR / "OAuth.json")

# Will be created automatically after first login:
TOKEN_FILE = str(BASE_DIR / "token.json")

# ================== GOOGLE IDS ==================
# Folder where generated documents will be created:
FOLDER_ID = "1VYgnyx44YCNwKVt1kftk0ydrpjOiVa5W"

# One Google Docs template for all documents:
# https://docs.google.com/document/d/<TEMPLATE_DOC_ID>/edit
TEMPLATE_DOC_ID = "18kjR_6IWczUerivTqTk8kyMjbg_bE48nyQ_cniIT_IQ"

# Google Sheets file with car tabs and departure dates:
# https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
SPREADSHEET_IDS = "150IBYL5_B-9T_7WrZWSF2t7nFbE_epDpY_Fwio1WFXU, 1ftxRDv40W4EaHTVE6oqCqOe8g-Q4NUUcPzuvGOtttN8, 1a1rtMO4aFN33QnWBPpEBqrjjHM6OlaoXGEjXr31WIEw"

# In each car tab, data rows start from this row (inclusive).
# Row 25 means the range should begin with D25.
SHEETS_DATA_START_ROW = 26

# ================== DATE RANGE (inclusive) ==================
START_DATE_STR = "19.01.2026"
END_DATE_STR = "19.01.2026"

# ================== OTHER ==================
ODR_IDX = "434дск"

# Optional styling (applied to the whole document)
DEFAULT_FONT = "Times New Roman"
DEFAULT_FONT_SIZE_PT = 13

# ================== LOGGING ==================
# Set to "DEBUG" to see how rows are scanned and why cars are included/skipped.
LOG_LEVEL = "DEBUG"   # DEBUG / INFO / WARNING / ERROR
LOG_FILE = "app.log"  # set to "" to disable file logging
