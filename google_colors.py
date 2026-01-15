# google_colors.py
"""
Мапа стандартних кольорів Google Sheets (≈60 відтінків) + функції для роботи.
"""

COLOR_MAP = {
    # Greys
    "#000000": "black",
    "#434343": "dark grey 4",
    "#666666": "dark grey 3",
    "#999999": "dark grey 2",
    "#B7B7B7": "dark grey 1",
    "#CCCCCC": "grey",
    "#D9D9D9": "light grey 1",
    "#EFEFEF": "light grey 2",
    "#F3F3F3": "light grey 3",
    "#FFFFFF": "white",

    # Basic colors
    "#980000": "red berry",
    "#FF0000": "red",
    "#FF9900": "orange",
    "#FFFF00": "yellow",
    "#00FF00": "green",
    "#00FFFF": "cyan",
    "#4A86E8": "cornflower blue",
    "#0000FF": "blue",
    "#9900FF": "purple",
    "#FF00FF": "magenta",

    # Light tones 3
    "#E6B8AF": "light red berry 3",
    "#F4CCCC": "light red 3",
    "#FCE5CD": "light orange 3",
    "#FFF2CC": "light yellow 3",
    "#D9EAD3": "light green 3",
    "#D0E0E3": "light cyan 3",
    "#C9DAF8": "light cornflower blue 3",
    "#CFE2F3": "light blue 3",
    "#D9D2E9": "light purple 3",
    "#EAD1DC": "light magenta 3",

    # Light tones 2
    "#DD7E6B": "light red berry 2",
    "#EA9999": "light red 2",
    "#F9CB9C": "light orange 2",
    "#FFE599": "light yellow 2",
    "#B6D7A8": "light green 2",
    "#A2C4C9": "light cyan 2",
    "#A4C2F4": "light cornflower blue 2",
    "#9FC5E8": "light blue 2",
    "#B4A7D6": "light purple 2",
    "#D5A6BD": "light magenta 2",

    # Light tones 1
    "#CC4125": "light red berry 1",
    "#E06666": "light red 1",
    "#F6B26B": "light orange 1",
    "#FFD966": "light yellow 1",
    "#93C47D": "light green 1",
    "#76A5AF": "light cyan 1",
    "#6D9EEB": "light cornflower blue 1",
    "#6FA8DC": "light blue 1",
    "#8E7CC3": "light purple 1",
    "#C27BA0": "light magenta 1",

    # Dark tones 1
    "#A61C00": "dark red berry 1",
    "#CC0000": "dark red 1",
    "#E69138": "dark orange 1",
    "#F1C232": "dark yellow 1",
    "#6AA84F": "dark green 1",
    "#45818E": "dark cyan 1",
    "#3C78D8": "dark cornflower blue 1",
    "#3D85C6": "dark blue 1",
    "#674EA7": "dark purple 1",
    "#A64D79": "dark magenta 1",

    # Dark tones 2
    "#85200C": "dark red berry 2",
    "#990000": "dark red 2",
    "#B45F06": "dark orange 2",
    "#BF9000": "dark yellow 2",
    "#38761D": "dark green 2",
    "#134F5C": "dark cyan 2",
    "#1155CC": "dark cornflower blue 2",
    "#0B5394": "dark blue 2",
    "#351C75": "dark purple 2",
    "#741B47": "dark magenta 2",

    # Dark tones 3
    "#5B0F00": "dark red berry 3",
    "#660000": "dark red 3",
    "#783F04": "dark orange 3",
    "#7F6000": "dark yellow 3",
    "#274E13": "dark green 3",
    "#0C343D": "dark cyan 3",
    "#1C4587": "dark cornflower blue 3",
    "#073763": "dark blue 3",
    "#20124D": "dark purple 3",
    "#4C1130": "dark magenta 3",
}


def rgb_to_hex(rgb: dict) -> str:
    """Конвертувати RGB (0–1) у HEX (#RRGGBB)."""
    r = int(rgb.get("red", 1) * 255)
    g = int(rgb.get("green", 1) * 255)
    b = int(rgb.get("blue", 1) * 255)
    return f"#{r:02X}{g:02X}{b:02X}"


def get_color_name(rgb: dict) -> str:
    """
    Повернути назву кольору за RGB з Google Sheets API.
    Якщо HEX немає у мапі — повертає HEX-код.
    """
    hex_code = rgb_to_hex(rgb)
    return COLOR_MAP.get(hex_code, hex_code)
