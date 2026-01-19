from __future__ import print_function

import json
import os
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import settings as config


# ================== AUTH ==================
def get_oauth_creds() -> Credentials:
    creds: Optional[Credentials] = None
    if os.path.exists(config.TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.OAUTH_FILE, config.SCOPES)
            creds = flow.run_local_server(port=0)

        with open(config.TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


# ================== HELPERS ==================
def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def load_templates_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ================== DUTY LOGIC ==================
def build_duty_officer_text(cur_date: date, data: Dict[str, Any]) -> str:
    # 1,4,7... -> first; 2,5,8... -> second; 3,6,9... -> third
    r = (cur_date.day - 1) % 3
    duty = data.get("duty_officer", {})
    if r == 0:
        return duty.get("first_pair_duty_officer", "")
    elif r == 1:
        return duty.get("second_pair_duty_officer", "")
    else:
        return duty.get("third_pair_duty_officer", "")


def build_duty_driver_text(cur_date: date, data: Dict[str, Any]) -> str:
    # odd day -> first; even day -> second
    k = (cur_date.day - 1) % 2
    duty = data.get("duty_driver", {})
    return duty.get("first_duty_driver", "") if k == 0 else duty.get("second_duty_driver", "")


# ================== PLACEHOLDERS ==================
def build_date_replacements(target: date, odr_idx: str) -> Dict[str, str]:
    return {
        "{{TARGET_DATE}}": target.strftime("%d.%m.%Y"),
        "{{DATE_BEFORE}}": (target - timedelta(days=1)).strftime("%d.%m.%Y"),
        "{{DATE_NEXT}}": (target + timedelta(days=1)).strftime("%d.%m.%Y"),
        "{{ODR_NUM}}": target.strftime("%d"),
        "{{ODR_IDX}}": odr_idx,
    }


def normalize_inline_replacements(repl: Dict[str, str]) -> Dict[str, str]:
    # Inline placeholders should not break lines
    return {k: str(v).replace("\n", " ").strip() for k, v in repl.items()}


def apply_replacements(docs_service, doc_id: str, repl: Dict[str, str]) -> None:
    requests = []
    for k, v in repl.items():
        requests.append({
            "replaceAllText": {
                "containsText": {"text": k, "matchCase": True},
                "replaceText": "" if v is None else str(v),
            }
        })

    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests}
        ).execute()


# ================== BLOCK BUILDERS ==================
def build_duty_soldiers_text(data: Dict[str, Any]) -> str:
    soldiers = data.get("duty_soldiers", [])
    if not soldiers:
        return ""
    # Accept list[str] or list[dict]
    lines = ["Чергові солдати:"]
    for item in soldiers:
        if isinstance(item, dict):
            # you can extend schema freely: rank/name/notes etc
            name = item.get("name") or item.get("full_name") or ""
            rank = item.get("rank") or ""
            notes = item.get("notes") or ""
            s = " ".join([rank, name]).strip()
            if notes:
                s = f"{s} ({notes})" if s else notes
            if s:
                lines.append(f"- {s}")
        else:
            s = str(item).strip()
            if s:
                lines.append(f"- {s}")
    return "\n".join(lines).strip()


def build_duty_cars_text(data: Dict[str, Any]) -> str:
    cars = data.get("duty_cars", [])
    if not cars:
        return ""

    lines = ["Чергові автомобілі:"]
    for idx, car in enumerate(cars, start=1):
        if not isinstance(car, dict):
            s = str(car).strip()
            if s:
                lines.append(f"\n{idx}. {s}")
            continue

        route = (car.get("route") or "").strip()
        make = (car.get("car_make") or "").strip()
        plate = (car.get("car_plate") or "").strip()
        drivers = car.get("drivers") or []
        radio = (car.get("radio_number") or "").strip()
        purpose = (car.get("purpose") or "").strip()

        drivers_str = ", ".join([str(d).strip() for d in drivers if str(d).strip()]) if isinstance(drivers, list) else str(drivers).strip()

        lines.append(f"\n{idx}.")
        if route:
            lines.append(f"Маршрут: {route}")
        if make or plate:
            lines.append(f"Авто: {make} {plate}".strip())
        if drivers_str:
            lines.append(f"Водії: {drivers_str}")
        if radio:
            lines.append(f"Номер рації: {radio}")
        if purpose:
            lines.append(f"Ціль поїздки: {purpose}")

    return "\n".join(lines).strip()


# ================== DOC ==================
def create_doc_from_template(drive_service, template_id: str, folder_id: str, title: str) -> str:
    copied = drive_service.files().copy(
        fileId=template_id,
        body={"name": title, "parents": [folder_id]},
    ).execute()
    return copied["id"]


def apply_document_default_style(docs_service, doc_id: str, font: str, size_pt: int) -> None:
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
                            "fontSize": {"magnitude": size_pt, "unit": "PT"},
                        },
                        "fields": "weightedFontFamily,fontSize",
                    }
                }
            ]
        },
    ).execute()


# ================== MAIN ==================
def main():
    if config.FOLDER_ID.startswith("PASTE_") or config.TEMPLATE_DOC_ID.startswith("PASTE_"):
        raise ValueError("Set FOLDER_ID and TEMPLATE_DOC_ID in config/settings.py")

    creds = get_oauth_creds()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)

    templates = load_templates_json(config.TEMPLATES_JSON_PATH)

    start_date = datetime.strptime(config.START_DATE_STR, "%d.%m.%Y").date()
    end_date = datetime.strptime(config.END_DATE_STR, "%d.%m.%Y").date()

    for cur_date in daterange(start_date, end_date):
        title = cur_date.strftime("%Y-%m-%d")

        doc_id = create_doc_from_template(
            drive_service,
            config.TEMPLATE_DOC_ID,
            config.FOLDER_ID,
            title,
        )

        # ---- INLINE placeholders (no new lines) ----
        inline: Dict[str, str] = {}
        inline.update(templates.get("static_replacements", {}))
        inline.update(build_date_replacements(cur_date, config.ODR_IDX))
        inline = normalize_inline_replacements(inline)
        apply_replacements(docs_service, doc_id, inline)

        # ---- BLOCK placeholders (multiline text allowed) ----
        blocks: Dict[str, str] = {
            "{{DUTY_KSP_BLOCK}}": build_duty_officer_text(cur_date, templates),
            "{{DUTY_DRIVE_BLOCK}}": build_duty_driver_text(cur_date, templates),
            "{{DUTY_SOLDIERS}}": build_duty_soldiers_text(templates),
            "{{DUTY_CARS_BLOCK}}": build_duty_cars_text(templates),
        }
        apply_replacements(docs_service, doc_id, blocks)

        # Optional: apply style to whole doc
        apply_document_default_style(
            docs_service,
            doc_id,
            config.DEFAULT_FONT,
            config.DEFAULT_FONT_SIZE_PT,
        )

        print(f"Created: {title} -> https://docs.google.com/document/d/{doc_id}/edit")

    print("Done.")


if __name__ == "__main__":
    main()
