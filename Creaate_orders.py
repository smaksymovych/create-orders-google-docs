from __future__ import print_function

import json
import os
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import re

from config import settings as config


# ================== LOGGING ==================
logger = logging.getLogger("create_orders")


def setup_logging() -> None:
    level_name = getattr(config, "LOG_LEVEL", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)

    handlers: List[logging.Handler] = [logging.StreamHandler()]
    log_file = (getattr(config, "LOG_FILE", "") or "").strip()
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=handlers,
    )

    logger.info("Logging initialized: level=%s file=%s", level_name, log_file or "(disabled)")


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

def parse_spreadsheet_ids(raw: str) -> List[str]:
    return [x.strip() for x in (raw or "").split(",") if x.strip()]

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


# ================== SHEETS (NORMALIZE DATE) ==================
# 03.01 == 3.01
def norm_ddmm(s: str) -> str:
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2})\.(\d{1,2})", s)
    if not m:
        return ""
    return f"{m.group(1).zfill(2)}.{m.group(2).zfill(2)}"

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


# ================== SHEETS (ROUTES BY DATE) ==================
def norm_plate(s: str) -> str:
    """
    "1234Н9 ", " 1234Н9 ", "1234 Н9 " -> "1234Н9"
    """
    if not s:
        return ""
    s = re.sub(r"\s+", "", str(s))  # прибрати ВСІ пробіли
    return s.strip().upper()

def load_routes_for_date_from_many(
    sheets_service,
    spreadsheet_ids: List[str],
    plate_tab_names: List[str],
    cur_date: date,
    start_row: int,
) -> Dict[str, str]:
    """
    Шукає виїзди по списку spreadsheets по черзі.
    Як тільки для plate знайдено дату/маршрут — далі spreadsheets для цієї plate не перевіряємо.
    Повертає {plate_norm: route_text}.
    """
    routes_by_plate: Dict[str, str] = {}
    pending = list(plate_tab_names)  # які plate ще не знайдені

    for sid in spreadsheet_ids:
        if not pending:
            break

        logger.info("Checking spreadsheet: %s (pending plates: %d)", sid, len(pending))

        found_here = load_sheet_routes_for_date(
            sheets_service=sheets_service,
            spreadsheet_id=sid,
            plate_tab_names=pending,
            cur_date=cur_date,
            start_row=start_row,
        )

        # merge: тільки те, що ще не було знайдено
        for plate_norm, route in found_here.items():
            if plate_norm not in routes_by_plate:
                routes_by_plate[plate_norm] = route

        # оновити pending
        found_set = set(found_here.keys())
        pending = [p for p in pending if norm_plate(p) not in found_set]

    return routes_by_plate

def load_sheet_routes_for_date(
    sheets_service,
    spreadsheet_id: str,
    plate_tab_names: List[str],
    cur_date: date,
    start_row: int,
) -> Dict[str, str]:
    """
    Повертає маршрути з одного шляхового листа (spreadsheet) для заданої дати.

    ВАЖЛИВО:
    - Вкладка = номер авто (plate). Назви вкладок можуть містити пробіли, тому
      ми порівнюємо за нормалізованими значеннями, але в range використовуємо
      ОРИГІНАЛЬНУ назву вкладки з metadata.
    - Дату шукаємо в колонці D (текст 'DD.MM', інколи без нуля: '3.01').
    - Маршрут беремо з колонки A (A може бути об'єднана з B по ширині — це нормально).
    - Дані починаються з start_row (наприклад 25).
    - Щоб уникнути зсуву індексів у Sheets API (коли порожні ліві комірки не повертаються),
      читаємо колонки A і D ОКРЕМО через batchGet і синхронізуємо по рядку.
    """
    target = cur_date.strftime("%d.%m")
    logger.info(
        "Sheets route lookup: spreadsheet=%s date=%s (target='%s') start_row=%s plates=%d",
        spreadsheet_id,
        cur_date.isoformat(),
        target,
        start_row,
        len(plate_tab_names),
    )

    # 1) Get existing tabs (titles) once
    meta = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(title))"
    ).execute()

    titles = [sh["properties"]["title"] for sh in meta.get("sheets", [])]
    norm_to_original = {norm_plate(t): t for t in titles}

    logger.debug("Spreadsheet tabs (original): %s", titles)
    logger.debug("Spreadsheet tabs (normalized): %s", sorted(norm_to_original.keys()))

    routes_by_plate: Dict[str, str] = {}

    for plate in plate_tab_names:
        plate_norm = norm_plate(plate)
        if not plate_norm:
            logger.debug("SKIP: empty plate value: %r", plate)
            continue

        tab_title = norm_to_original.get(plate_norm)
        if not tab_title:
            logger.debug("SKIP: no tab for plate=%r (norm=%s) in spreadsheet=%s", plate, plate_norm, spreadsheet_id)
            continue

        # Read ONLY columns A and D starting from start_row to avoid index shifting
        ranges = [
            f"'{tab_title}'!A{start_row}:A",
            f"'{tab_title}'!D{start_row}:D",
        ]
        logger.debug("Read (batchGet) tab=%r ranges=%s", tab_title, ranges)

        resp = sheets_service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
        ).execute()

        vr = resp.get("valueRanges", [])
        col_a = vr[0].get("values", []) if len(vr) > 0 else []
        col_d = vr[1].get("values", []) if len(vr) > 1 else []

        logger.debug(
            "Fetched tab=%r rows: A=%d D=%d (start_row=%d)",
            tab_title,
            len(col_a),
            len(col_d),
            start_row,
        )

        max_len = max(len(col_a), len(col_d))
        matched = False

        # For debugging, log the first few rows we see
        preview_n = min(5, max_len)
        for i in range(preview_n):
            row_num = start_row + i
            a_val = str(col_a[i][0]).strip() if i < len(col_a) and col_a[i] else ""
            d_val = str(col_d[i][0]).strip() if i < len(col_d) and col_d[i] else ""
            logger.debug("Preview tab=%r row=%d A(route)=%r D(date)=%r", tab_title, row_num, a_val, d_val)

        for i in range(max_len):
            row_num = start_row + i

            route_cell = str(col_a[i][0]).strip() if i < len(col_a) and col_a[i] else ""
            date_cell = str(col_d[i][0]).strip() if i < len(col_d) and col_d[i] else ""

            if date_cell.lower() == "дата":
                continue

            if norm_ddmm(date_cell) == target:
                # Якщо маршрут порожній у рядку з датою — вважаємо, що в шляховому листі маршруту немає,
                # і повертаємо порожній рядок, щоб вище спрацював fallback на default_route_ids з JSON.
                if route_cell:
                    routes_by_plate[plate_norm] = route_cell
                    logger.info(
                        "MATCH plate=%s tab=%r row=%d date=%r route(from sheet)=%r",
                        plate_norm, tab_title, row_num, date_cell, route_cell
                    )
                else:
                    routes_by_plate[plate_norm] = ""
                    logger.warning(
                        "MATCH plate=%s tab=%r row=%d date=%r but route is EMPTY in column A -> will fallback to JSON defaults",
                        plate_norm, tab_title, row_num, date_cell
                    )
                matched = True
                break

        if not matched:
            logger.debug("NO MATCH plate=%s in tab=%r for date target=%s", plate_norm, tab_title, target)

    logger.info("Routes matched total in spreadsheet=%s: %d", spreadsheet_id, len(routes_by_plate))
    return routes_by_plate

def build_duty_soldiers_text(data: Dict[str, Any]) -> str:
    soldiers = data.get("duty_soldiers", [])
    if not soldiers:
        return ""
    lines = ["Чергові солдати:"]
    for item in soldiers:
        if isinstance(item, dict):
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


def build_duty_cars_text(data: Dict[str, Any], cur_date: date, sheets_service) -> str:
    """Build cars block using:
    - static data from templates.json (cars_catalog, drivers_catalog, radios_catalog, purposes_catalog, routes_catalog)
    - dynamic route presence from Google Sheets (per-car tab named by PLATE, column D 'Дата' == DD.MM)

    Car is included ONLY if its PLATE tab contains the date in column D.
    Route:
      - from column AB if present (merged-safe)
      - otherwise fallback to car.default_route_ids via routes_catalog
    Purpose:
      - taken from templates.json duty_cars mapping by car_id (purpose_id) if present
    """
    drivers = data.get("drivers_catalog", {})
    routes_catalog = data.get("routes_catalog", {})
    purposes = data.get("purposes_catalog", {})
    radios = data.get("radios_catalog", {})

    cars_list = data.get("cars_catalog", []) or []
    if not cars_list:
        logger.warning("cars_catalog is empty in templates.json; nothing to build")
        return ""

    # Build maps:
    # - plate_norm -> car dict
    # - plate_norm -> car_id
    cars_by_plate: Dict[str, Dict[str, Any]] = {}
    car_id_by_plate: Dict[str, str] = {}
    for c in cars_list:
        if not isinstance(c, dict):
            continue
        plate = norm_plate(c.get("plate", ""))
        car_id = c.get("car_id", "")
        if plate and car_id:
            cars_by_plate[plate] = c
            car_id_by_plate[plate] = car_id
        else:
            logger.debug("SKIP car in JSON (missing plate or car_id): %s", c)

    # Purpose mapping stays in JSON (existing structure)
    duty_map: Dict[str, Dict[str, Any]] = {}
    for it in data.get("duty_cars", []) or []:
        if isinstance(it, dict) and it.get("car_id"):
            duty_map[it["car_id"]] = it

    # Only look for tabs that are listed in JSON (by plate)
    plate_tab_names = list(cars_by_plate.keys())

    # routes_by_plate = load_sheet_routes_for_date(
    #     sheets_service=sheets_service,
    #     spreadsheet_id=config.SPREADSHEET_ID,
    #     plate_tab_names=plate_tab_names,
    #     cur_date=cur_date,
    # )

    spreadsheet_ids = parse_spreadsheet_ids(getattr(config, "SPREADSHEET_IDS", ""))
    if not spreadsheet_ids:
        raise ValueError("Set SPREADSHEET_IDS in config/settings.py")

    routes_by_plate = load_routes_for_date_from_many(
        sheets_service=sheets_service,
        spreadsheet_ids=spreadsheet_ids,
        plate_tab_names=plate_tab_names,
        cur_date=cur_date,
        start_row=config.SHEETS_DATA_START_ROW,
    )

    if not routes_by_plate:
        logger.warning("No cars matched in Sheets for date=%s (target=%s)", cur_date.isoformat(), cur_date.strftime("%d.%m"))
        return ""

    def driver_name(driver_id: str) -> str:
        return drivers.get(driver_id, driver_id)

    def route_text(route_id: str) -> str:
        return routes_catalog.get(route_id, route_id)

    def radio_text(radio_id: str) -> str:
        return radios.get(radio_id, radio_id)

    def purpose_text_by_car_id(car_id: str) -> str:
        item = duty_map.get(car_id, {})
        ptxt = (item.get("purpose_text") or "").strip()
        if ptxt:
            return ptxt
        pid = item.get("purpose_id")
        return purposes.get(pid, pid) if pid else ""

    lines: List[str] = ["Чергові автомобілі:"]

    # Stable order: by plate (sorted), or keep original JSON order if you prefer.
    for idx, plate_norm in enumerate(sorted(routes_by_plate.keys()), start=1):
        car = cars_by_plate.get(plate_norm, {})
        car_id = car_id_by_plate.get(plate_norm, "")

        model = (car.get("model") or "").strip()
        plate_display = (car.get("plate") or plate_norm).strip()

        main_driver = driver_name(car.get("main_driver_id", ""))
        reserve_ids = car.get("reserve_driver_ids", []) or []
        reserve_str = ", ".join(driver_name(x) for x in reserve_ids if x)

        radio = radio_text(car.get("radio_id", ""))

        # Route from sheet; fallback to defaults if empty
        route_str = (routes_by_plate.get(plate_norm) or "").strip()
        if not route_str:
            defaults = car.get("default_route_ids", []) or []
            route_str = "; ".join(route_text(rid) for rid in defaults if rid)
            logger.warning("Empty route in sheet for plate=%s (car_id=%s) -> fallback to defaults='%s'", plate_norm, car_id, route_str)
        else:
            logger.debug("Route from sheet used: plate=%s (car_id=%s) route='%s'", plate_norm, car_id, route_str)

        purpose = purpose_text_by_car_id(car_id) if car_id else ""

        # 1 iteration = 1 line
        parts: List[str] = [f"{idx}) "]

        if route_str:
            parts.append(route_str)

        if model or plate_display:
            parts.append(f"т/з {model} з реєстраційним номером {plate_display}".strip())

        # Put driver/radio into one bracketed chunk (avoids unclosed brackets)
        meta: List[str] = []
        if main_driver:
            meta.append(f"основний водій - {main_driver}")
        if reserve_str:
            meta.append(f"запасні водії: {reserve_str}")
        if radio:
            meta.append(f"радіостанція - {radio}")
        if meta:
            parts.append(f"({'; '.join(meta)})")

        if purpose:
            parts.append(f"{purpose}.")

        line = " ".join(parts).strip()
        logger.debug("CAR LINE: %s", line)
        lines.append(line)

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
    setup_logging()
    if config.FOLDER_ID.startswith("PASTE_") or config.TEMPLATE_DOC_ID.startswith("PASTE_"):
        raise ValueError("Set FOLDER_ID and TEMPLATE_DOC_ID in config/settings.py")

    creds = get_oauth_creds()
    drive_service = build("drive", "v3", credentials=creds)
    docs_service = build("docs", "v1", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds)

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
            "{{DUTY_CARS_BLOCK}}": build_duty_cars_text(templates, cur_date, sheets_service),
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
