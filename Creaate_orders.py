from __future__ import print_function
import os, re
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List

import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from google_colors import get_color_name  # ваш модуль з мапою кольорів

# ====== НАЛАШТУВАННЯ ======
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

OAUTH_FILE = "OAuth.json"            # ваш OAuth Client ID (Desktop) JSON
TOKEN_FILE = "token.json"

FOLDER_ID = "1VYgnyx44YCNwKVt1kftk0ydrpjOiVa5W"             # куди складати документи
SPREADSHEET_ID = "10t158B1ZDa2UkuPimTcrVeuK8d7ccC71Btv7GIK3an4"
RANGE = "Sheet1!B5:N22"  # підлаштуйте під вашу таблицю

# Текстові блоки, які вставляємо у кожен документ (послідовно)
FILE_LIST = ["top_text.txt", "extra_text.txt", "bottom_text.txt"]

# Діапазон дат (ВКЛЮЧНО)
START_DATE_STR = "01.01.2026"
END_DATE_STR   = "02.01.2026"

# Опціональні плейсхолдери
ODR_IDX = "434дск"  # приклад


# ====== АВТОРИЗАЦІЯ ======
def get_oauth_creds() -> Credentials:
    creds: Optional[Credentials] = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return creds


# ====== ДОПОМОЖНІ ======
def daterange(start: date, end: date):
    """Ітератор по датах (включно)."""
    cur = start
    while cur <= end:
        yield cur
        cur = cur + timedelta(days=1)


def fetch_sheet_with_colors(sheets_service, spreadsheet_id: str, rng: str) -> Dict[str, Any]:
    """Раз зчитуємо діапазон із форматами (для кольорів)."""
    return sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=rng,
        includeGridData=True
    ).execute()


def find_date_col_index(rows: List[Dict[str, Any]], date_str: str) -> Optional[int]:
    headers = [cell.get("formattedValue") for cell in rows[0]["values"]]
    try:
        return headers.index(date_str)
    except ValueError:
        return None


def parse_cell(cell: Dict[str, Any]) -> Dict[str, Any]:
    """Дістає сирий текст, парсить номер/дату та колір."""
    text = cell.get("formattedValue", "")
    bg = cell.get("effectiveFormat", {}).get("backgroundColor", {})
    red = bg.get("red", 1)
    green = bg.get("green", 1)
    blue = bg.get("blue", 1)

    doc_num, doc_date = None, None
    m = re.search(r"(.+?) від (\d{2}\.\d{2}\.\d{4})", text)
    if m:
        doc_num = m.group(1).strip()
        doc_date = m.group(2)

    return {
        "raw": text,
        "doc_num": doc_num,
        "doc_date": doc_date,
        "color_r": red, "color_g": green, "color_b": blue,
        "color_name": get_color_name({"red": red, "green": green, "blue": blue})
    }


def build_dataframe_for_date(rows: List[Dict[str, Any]], target_str: str) -> pd.DataFrame:
    """На основі вже зчитаних rows готує DataFrame для однієї дати."""
    col_idx = find_date_col_index(rows, target_str)
    if col_idx is None:
        # Порожній DF, якщо дати в заголовку нема
        return pd.DataFrame(columns=["position", "rank", "name", "doc_num", "doc_date",
                                     "raw", "color_r", "color_g", "color_b", "color_name"])

    records = []
    for row in rows[1:]:
        values = row.get("values", [])
        if not values:
            continue

        # A: посада, B: звання, C: ПІБ (бо у вашому B5:AH21 перший рядок — заголовок; далі: 0,1,2 — службові колонки)
        position = values[0].get("formattedValue", "")
        rank = values[1].get("formattedValue", "")
        name = values[2].get("formattedValue", "")
        if not name:
            continue

        if col_idx < len(values):
            cell = values[col_idx]
            parsed = parse_cell(cell)
            records.append({
                "position": position,
                "rank": rank,
                "name": name,
                **parsed
            })

    return pd.DataFrame(records)


def create_doc(drive_service, docs_service, folder_id: str, title: str) -> str:
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id]
    }
    new_doc = drive_service.files().create(body=file_metadata).execute()
    doc_id = new_doc.get("id")
    print(f"Створено документ: {title} → https://docs.google.com/document/d/{doc_id}/edit")
    return doc_id


def insert_files_with_replacements(docs_service, doc_id: str, target: date, file_list: List[str], odr_idx: str):
    """Вставляє послідовно вміст файлів + робить текстові заміни (дати/номер і т.д.)."""
    for file_name in file_list:
        with open(file_name, "r", encoding="utf-8") as f:
            file_text = f.read()

        # кінець документа
        doc = docs_service.documents().get(documentId=doc_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"]

        date_before = target - timedelta(days=1)
        date_next = target + timedelta(days=1)
        odr_num = target.strftime("%d")

        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": end_index - 1},
                            "text": f"\n{file_text}\n"
                        }
                    },
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{DATE_BEFORE}}", "matchCase": True},
                            "replaceText": date_before.strftime("%d.%m.%Y")
                        }
                    },
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{TARGET_DATE}}", "matchCase": True},
                            "replaceText": target.strftime("%d.%m.%Y")
                        }
                    },
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{DATE_NEXT}}", "matchCase": True},
                            "replaceText": date_next.strftime("%d.%m.%Y")
                        }
                    },
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{ODR_NUM}}", "matchCase": True},
                            "replaceText": odr_num
                        }
                    },
                    {
                        "replaceAllText": {
                            "containsText": {"text": "{{ODR_IDX}}", "matchCase": True},
                            "replaceText": odr_idx
                        }
                    }
                ]
            }
        ).execute()


def apply_document_default_style(docs_service, doc_id: str, font="Times New Roman", size_pt=13):
    """В кінці — один прохід по всьому документу, задаємо шрифт/розмір."""
    doc = docs_service.documents().get(documentId=doc_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "updateTextStyle": {
                        "range": {"startIndex": 1, "endIndex": end_index},
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": font, "weight": 400},
                            "fontSize": {"magnitude": size_pt, "unit": "PT"}
                        },
                        "fields": "weightedFontFamily,fontSize"
                    }
                }
            ]
        }
    ).execute()


# ====== ГОЛОВНЕ ======
def main():
    # 1) Авторизація
    creds = get_oauth_creds()
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    # 2) Зчитуємо таблицю (один раз на весь батч)
    sheet = fetch_sheet_with_colors(sheets_service, SPREADSHEET_ID, RANGE)
    rows = sheet["sheets"][0]["data"][0]["rowData"]

    # 3) Парсимо строки дат
    start_date = datetime.strptime(START_DATE_STR, "%d.%m.%Y").date()
    end_date = datetime.strptime(END_DATE_STR, "%d.%m.%Y").date()

    for cur_date in daterange(start_date, end_date):
        target_str = cur_date.strftime("%d.%m.%Y")

        # 3.1) формуємо DF для поточної дати (можете використати df далі для логіки/перевірок)
        df = build_dataframe_for_date(rows, target_str)
        print(f"\n=== {target_str} ===")
        if df.empty:
            print("  У заголовку такої дати немає — пропускаю.")
            continue
        else:
            print(df[["position", "rank", "name", "raw", "color_name"]])#.head())

        # 3.2) створюємо документ і наповнюємо
        title = cur_date.strftime("%Y-%m-%d")
        doc_id = create_doc(drive_service, docs_service, FOLDER_ID, title)

        insert_files_with_replacements(
            docs_service=docs_service,
            doc_id=doc_id,
            target=cur_date,
            file_list=FILE_LIST,
            odr_idx=ODR_IDX
        )

        # 3.3) стиль наприкінці
        apply_document_default_style(docs_service, doc_id)

    print("\nГотово: усі доступні дати в діапазоні оброблені.")


if __name__ == "__main__":
    main()
