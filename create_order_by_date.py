from __future__ import print_function
import os, re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from datetime import date
from google_colors import get_color_name
import pandas as pd

# Скоупи для Drive і Docs
SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents','https://www.googleapis.com/auth/spreadsheets.readonly']

# Авторизація OAuth 
creds = None
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('OAuth.json', SCOPES)
        creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

# Ініціалізація API
sheets_service = build("sheets", "v4", credentials=creds)
drive_service = build('drive', 'v3', credentials=creds)
docs_service = build('docs', 'v1', credentials=creds)

# Ваші ID
FOLDER_ID = "1elSOvwojUBIfkAbrtVWhvsaPMT4jlILL" # ID вашої папки у Drive
SPREADSHEET_ID = "1nfom33V9q88o_bPbIgDeXVucU1yZ6WIW5WY8P3ui3NE" # ID таблиці у Drive
RANGE = "Sheet1!B5:AH21"

# Поточна дата
today = datetime.today().date()
# print("Сьогодні:", today.strftime("%d.%m.%Y"))
#target_date = date(2025, 9, 1)
# date_before = target_date - timedelta(days=1)
# date_next = target_date + timedelta(days=1)
# odr_num = target_date.strftime("%d")
# odr_idx = "999дск"
# Список ваших файлів
file_list = [
    "top_text.txt",
    "extra_text.txt",
    "bottom_text.txt"
]

# 1. Читаємо діапазон з Google Sheets
sheet = sheets_service.spreadsheets()
result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE).execute()
values = result.get("values", [])

# # 2. Парсимо текст (наприклад "8/375дск від 07.08.2025")
# parsed_texts = []
# for row in values:
#     if row:
#         text = row[0]
#         match = re.search(r"(.+?) від (\d{2}\.\d{2}\.\d{4})", text)
#         if match:
#             doc_num = match.group(1)
#             date = match.group(2)
#             parsed_texts.append(f"Документ: {doc_num}, Дата: {date}")
#         else:
#             parsed_texts.append(f"Невідомий формат: {text}")


# 1. Отримуємо таблицю з кольорами
sheet = sheets_service.spreadsheets().get(
    spreadsheetId=SPREADSHEET_ID,
    ranges=RANGE,
    includeGridData=True
).execute()

rows = sheet["sheets"][0]["data"][0]["rowData"]

# 2. Знаходимо колонку з потрібною датою
target_date = date(2025, 9, 12)
target_date_str = target_date.strftime("%d.%m.%Y")
headers = [cell.get("formattedValue") for cell in rows[0]["values"]]
try:
    date_col_index = headers.index(target_date_str)
except ValueError:
    raise Exception(f"Дати {target_date_str} немає серед заголовків!")

records = []

# 3. Читаємо рядки з працівниками
for row in rows[1:]:
    values = row.get("values", [])
    if not values:
        continue

    position = values[0].get("formattedValue", "")  # посада
    rank = values[1].get("formattedValue", "")  # звання
    name = values[2].get("formattedValue", "")  # ПІБ
    if not name:
        continue

    # Беремо клітинку у колонці з датою
    if date_col_index < len(values):
        cell = values[date_col_index]
        text = cell.get("formattedValue", "")

        # Колір комірки
        bg = cell.get("effectiveFormat", {}).get("backgroundColor", {})
        red = bg.get("red", 1)
        green = bg.get("green", 1)
        blue = bg.get("blue", 1)

        # Парсимо текст
        doc_num, doc_date = None, None
        match = re.search(r"(.+?) від (\d{2}\.\d{2}\.\d{4})", text)
        if match:
            doc_num = match.group(1).strip()
            doc_date = match.group(2)

        records.append({
            "position": position,
            "rank": rank,
            "name": name,
            "doc_num": doc_num,
            "doc_date": doc_date,
            "raw": text,
            "color_r": red,
            "color_g": green,
            "color_b": blue,
            "converted_bg": get_color_name({"red": red, "green": green, "blue": blue})
        })

# 4. Перетворюємо в DataFrame
curr_df = pd.DataFrame(records)
print(curr_df[["position", "rank", "name", "raw", "converted_bg"]])

# 3. Створюємо порожній документ у папці
file_metadata = {
    "name": "2025-09-12",
    "mimeType": "application/vnd.google-apps.document",
    "parents": [FOLDER_ID]
}
new_doc = drive_service.files().create(body=file_metadata).execute()
document_id = new_doc.get("id")
print(f"Документ створено: https://docs.google.com/document/d/{document_id}/edit")

# # 4. Додаємо розпарсений текст у документ
# requests = []
# for text in parsed_texts:
#     requests.append({
#         "insertText": {
#             "location": {"index": 1},
#             "text": text + "\n"
#         }
#     })


# Проходимо по кожному файлу
for file_name in file_list:
    # Читаємо вміст
    with open(file_name, "r", encoding="utf-8") as f:
        file_text = f.read()

    # Отримуємо кінець документа
    doc = docs_service.documents().get(documentId=document_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"]
    
    target_date = date(2025, 9, 12)
    date_before = target_date - timedelta(days=1)
    date_next = target_date + timedelta(days=1)
    odr_num = target_date.strftime("%d")
    odr_idx = "401дск"
    # Вставляємо вміст файлу
    docs_service.documents().batchUpdate(
        documentId=document_id,
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
                        "replaceText": target_date.strftime("%d.%m.%Y")
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

# Отримуємо документ після всіх вставок
doc = docs_service.documents().get(documentId=document_id).execute()
end_index = doc["body"]["content"][-1]["endIndex"]

# Задаємо стиль для всього тексту
requests = [
    {
        "updateTextStyle": {
            "range": {"startIndex": 1, "endIndex": end_index},
            "textStyle": {
                "weightedFontFamily": {"fontFamily": "Times New Roman", "weight": 400},
                "fontSize": {"magnitude": 13, "unit": "PT"}
            },
            "fields": "weightedFontFamily,fontSize"
        }
    }
]


docs_service.documents().batchUpdate(
    documentId=document_id,
    body={"requests": requests}
).execute()

print("Усі файли додано в документ. Стиль тексту змінено!")


