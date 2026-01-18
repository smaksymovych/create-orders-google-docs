from __future__ import print_function

import os
import re
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List

import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ====== НАЛАШТУВАННЯ ======
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

OAUTH_FILE = "OAuth.json"  # ваш OAuth Client ID (Desktop) JSON
TOKEN_FILE = "token.json"

FOLDER_ID = "1VYgnyx44YCNwKVt1kftk0ydrpjOiVa5W"  # куди складати документи
SPREADSHEET_ID = "10t158B1ZDa2UkuPimTcrVeuK8d7ccC71Btv7GIK3an4"
RANGE = "Sheet1!B5:N22"  # підлаштуйте під вашу таблицю

TOP_FILE = "top_text.txt"
BOTTOM_FILE = "bottom_text.txt"

FILE_FROM_1 = "first_duty_ksp.txt"      # 1,4,7,10...
FILE_FROM_2 = "second_duty_ksp.txt"     # 2,5,8,11...
FILE_FROM_3 = "third_duty_ksp.txt"      # 3,6,9,12...
FILE_FROM_4 = "first_duty_drive.txt"    # 1,3,5...
FILE_FROM_5 = "second_duty_drive.txt"   # 2,4,6...
FILE_FROM_6 = "routs.txt"

# Діапазон дат (ВКЛЮЧНО)
START_DATE_STR = "01.01.2026"
END_DATE_STR = "04.01.2026"

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


def build_file_list_for_date(cur_date: date) -> List[str]:
    d = cur_date.day
    r = (d - 1) % 3  # 0 для 1,4,7...; 1 для 2,5,8...; 2 для 3,6,9...
    k = (d - 1) % 2  # 0 для 1,3,5...; 1 для 2,4,6...;

    if r == 0:
        duty_ksp = FILE_FROM_1
    elif r == 1:
        duty_ksp = FILE_FROM_2
    else:
        duty_ksp = FILE_FROM_3

    if k == 0:
        duty_drive = FILE_FROM_4
    else:
        duty_drive = FILE_FROM_5

    routs = FILE_FROM_6
    return [TOP_FILE, duty_ksp, duty_drive, routs, BOTTOM_FILE]


def fetch_sheet(sheets_service, spreadsheet_id: str, rng: str) -> Dict[str, Any]:
    """Зчитуємо діапазон з gridData (для rowData/values), без використання кольорів."""
    return sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=rng,
        includeGridData=True
    ).execute()


def find_date_col_index(rows: List[Dict[str, Any]], date_str: str) -> Optional[int]:
    headers = [cell.get("formattedValue") for cell in rows[0].get("values", [])]
    try:
        return headers.index(date_str)
    except ValueError:
        return None


def parse_doc_from_text(text: str) -> Dict[str, Optional[str]]:
    """Парсить 'номер від дата' з тексту клітинки."""
    doc_num, doc_date = None, None
    m = re.search(r"(.+?) від (\d{2}\.\d{2}\.\d{4})", text or "")
    if m:
        doc_num = m.group(1).strip()
        doc_date = m.group(2)
    return {"doc_num": doc_num, "doc_date": doc_date}


def build_dataframe_for_date(rows: List[Dict[str, Any]], target_str: str) -> pd.DataFrame:
    """Готує DataFrame для однієї дати (без кольорів)."""
    col_idx = find_date_col_index(rows, target_str)
    if col_idx is None:
        return pd.DataFrame(columns=["position", "rank", "name", "doc_num", "doc_date", "raw"])

    records = []
    for row in rows[1:]:
        values = row.get("values", [])
        if not values:
            continue

        # 0: посада, 1: звання, 2: ПІБ
        position = values[0].get("formattedValue", "")
        rank = values[1].get("formattedValue", "")
        name = values[2].get("formattedValue", "")
        if not name:
            continue

        cell = values[col_idx] if col_idx < len(values) else {}
        text = cell.get("formattedValue", "") if cell else ""
        parsed = parse_doc_from_text(text)

        records.append({
            "position": position,
            "rank": rank,
            "name": name,
            "raw": text,
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
    sheet = fetch_sheet(sheets_service, SPREADSHEET_ID, RANGE)
    rows = sheet["sheets"][0]["data"][0]["rowData"]

    # 3) Парсимо строки дат
    start_date = datetime.strptime(START_DATE_STR, "%d.%m.%Y").date()
    end_date = datetime.strptime(END_DATE_STR, "%d.%m.%Y").date()

    for cur_date in daterange(start_date, end_date):
        target_str = cur_date.strftime("%d.%m.%Y")

        # 3.1) формуємо DF для поточної дати
        df = build_dataframe_for_date(rows, target_str)
        print(f"\n=== {target_str} ===")
        if df.empty:
            print("  У заголовку такої дати немає — пропускаю.")
            continue
        else:
            print(df[["position", "rank", "name", "raw"]])

        # 3.2) створюємо документ і наповнюємо
        title = cur_date.strftime("%Y-%m-%d")
        doc_id = create_doc(drive_service, docs_service, FOLDER_ID, title)

        file_list = build_file_list_for_date(cur_date)
        print(f"Файли для {target_str}: {file_list}")  # опціонально, для контролю

        insert_files_with_replacements(
            docs_service=docs_service,
            doc_id=doc_id,
            target=cur_date,
            file_list=file_list,
            odr_idx=ODR_IDX
        )

        # 3.3) стиль наприкінці
        apply_document_default_style(docs_service, doc_id)

    print("\nГотово: усі доступні дати в діапазоні оброблені.")


if __name__ == "__main__":
    main()
