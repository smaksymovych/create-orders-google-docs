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
RANGE = "Sheet1!E6:E21"

# Поточна дата
today = datetime.today().date()
# print("Сьогодні:", today.strftime("%d.%m.%Y"))
target_date = date(2025, 9, 1)
date_before = target_date - timedelta(days=1)
date_next = target_date + timedelta(days=1)
odr_num = target_date.strftime("%d")
odr_idx = "999дск"
print("Дата наказу: ", target_date)
print("Номер наказу: ", odr_num + '/' + odr_idx)
bg = {"red": 1, "green": 0.9, "blue": 0.2}
print(get_color_name(bg)) 

# Список ваших файлів
file_list = [
    "text_block.txt",
    "extra_text.txt"
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

sheet = sheets_service.spreadsheets().get(
    spreadsheetId=SPREADSHEET_ID,
    ranges=RANGE,
    includeGridData=True
).execute()

rows = sheet["sheets"][0]["data"][0]["rowData"]

records = []

for r, row in enumerate(rows, start=1):
    if "values" in row:
        for c, cell in enumerate(row["values"], start=1):
            text = cell.get("formattedValue")

            # колір комірки (RGB у 0–1)
            bg = cell.get("effectiveFormat", {}).get("backgroundColor", {})
            red = bg.get("red", 1)
            green = bg.get("green", 1)
            blue = bg.get("blue", 1)

            doc_num, date = None, None
            if text:
                match = re.search(r"(.+?) від (\d{2}\.\d{2}\.\d{4})", text)
                if match:
                    doc_num = match.group(1).strip()
                    date = match.group(2)
            
            convert_bg = {"red": red, "green": green, "blue": blue}
            print(get_color_name(convert_bg))
            
            records.append({
                "row": r,
                "col": c,
                "doc_num": doc_num,
                "date": date,
                "raw": text,
                "color_r": red,
                "color_g": green,
                "color_b": blue,
            })

# 3. Перетворюємо у DataFrame
df = pd.DataFrame(records)

# 4. Дивимось результат
print(df.head())

# 3. Створюємо порожній документ у папці
file_metadata = {
    "name": "2025-09-01",
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


# # Читаємо текст з файлу
# with open("text_block.txt", "r", encoding="utf-8") as f:
#     file_text = f.read()

# requests = [
#     # Вставляємо текст з новим рядком (абзац)
#     {
#         'insertText': {
#             'location': {'index': 1},  # 1 = початок документа
#             "text": file_text + "\n"
#         }
#     },
#     # Продовжуємо вставку тексту
# # Читаємо текст із додаткового файла
# with open("extra_text.txt", "r", encoding="utf-8") as f:
#     extra_text = f.read()
#     {
#         "insertText": {
#             "location": {"index": end_index - 1},  # перед останнім елементом
#             "text": "\n" + extra_text + "\n"
#         }
#     }
#     # Замінюємо плейсхолдери
#     {
#         "replaceAllText": {
#             "containsText": {"text": "{{DATE_BEFORE}}", "matchCase": True},
#             "replaceText": date_before.strftime("%d.%m.%Y")
#         }
#     },
#        {
#         "replaceAllText": {
#             "containsText": {"text": "{{TARGET_DATE}}", "matchCase": True},
#             "replaceText": target_date.strftime("%d.%m.%Y")
#         }
#     },        
#        {
#         "replaceAllText": {
#             "containsText": {"text": "{{DATE_NEXT}}", "matchCase": True},
#             "replaceText": date_next.strftime("%d.%m.%Y")
#         }
#     },    
#         {
#         "replaceAllText": {
#             "containsText": {"text": "{{ODR_NUM}}", "matchCase": True},
#             "replaceText": odr_num
#         }
#     },    
#         {
#         "replaceAllText": {
#             "containsText": {"text": "{{ODR_IDX}}", "matchCase": True},
#             "replaceText": odr_idx
#         }
#     }  
# ]

# docs_service.documents().batchUpdate(
#     documentId=document_id,
#     body={"requests": requests}
# ).execute()

# # # Продовжуємо вставку тексту
# # # Читаємо текст із додаткового файла
# # with open("extra_text.txt", "r", encoding="utf-8") as f:
# #     extra_text = f.read()

# # Отримуємо довжину документа, щоб вставити наприкінці
# doc = docs_service.documents().get(documentId=document_id).execute()
# end_index = doc.get("body")["content"][-1]["endIndex"]

# requests = [
#     {
#         "insertText": {
#             "location": {"index": end_index - 1},  # перед останнім елементом
#             "text": "\n" + extra_text + "\n"
#         }
#     }
# ]

# docs_service.documents().batchUpdate(
#     documentId=document_id,
#     body={"requests": requests}
# ).execute()


# print("Текст з Google Sheets успішно додано!")