from pathlib import Path

# ================== PATHS ==================
BASE_DIR = Path(__file__).resolve().parents[1]          # .../GoogleTabs
CONFIG_DIR = BASE_DIR / "config"
TEMPLATES_JSON_PATH = str(CONFIG_DIR / "templates.json")

# ================== GOOGLE API ==================
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
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

# ================== DATE RANGE (inclusive) ==================
START_DATE_STR = "01.01.2026"
END_DATE_STR = "03.01.2026"

# ================== OTHER ==================
ODR_IDX = "434дск"

# Optional styling (applied to the whole document)
DEFAULT_FONT = "Times New Roman"
DEFAULT_FONT_SIZE_PT = 13
