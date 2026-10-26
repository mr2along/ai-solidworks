import re
import unicodedata

from .schemas import CADPlan


NUMBER = r"(?P<value>-?\d+(?:[.,]\d+)?)"
UNIT = r"(?P<unit>millimeters?|millimetres?|mm|centimeters?|centimetres?|cm|meters?|metres?|m|inches|inch|in)?"
QUANTITY = rf"{NUMBER}\s*{UNIT}(?![a-z])"
UNIT_TO_MM = {
    "mm": 1.0,
    "millimeter": 1.0,
    "millimeters": 1.0,
    "millimetre": 1.0,
    "millimetres": 1.0,
    "cm": 10.0,
    "centimeter": 10.0,
    "centimeters": 10.0,
    "centimetre": 10.0,
    "centimetres": 10.0,
    "m": 1000.0,
    "meter": 1000.0,
    "meters": 1000.0,
    "metre": 1000.0,
    "metres": 1000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
}


def _dimension(text: str, aliases: str, label: str):
    patterns = (
        rf"\b(?:{aliases})\b\s*(?:is|of|=|:)?\s*{QUANTITY}",
        rf"{QUANTITY}\s*(?:{aliases})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            number = float(match.group("value").replace(",", "."))
            unit = (match.group("unit") or "mm").lower()
            return number * UNIT_TO_MM[unit], match.group("unit") is not None
    raise ValueError(f"Chưa xác định được {label}. Hãy ghi rõ kích thước bằng mm, cm, m hoặc inch.")


def _diameter(text: str):
    patterns = (
        rf"(?:ø|phi|đường kính|diameter|dia\.?)[\s:=]*(?:of\s*)?{QUANTITY}",
        rf"{QUANTITY}\s*(?:diameter|dia\.?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            number = float(match.group("value").replace(",", "."))
            unit = (match.group("unit") or "mm").lower()
            return number * UNIT_TO_MM[unit], match.group("unit") is not None
    raise ValueError("Chưa xác định được đường kính lỗ. Hãy ghi Ø hoặc diameter và kích thước.")


def _edge_offset(text: str):
    patterns = (
        rf"(?:cách\s+mép|edge\s+offset|from\s+(?:each|every|the)\s+edges?|from\s+edge)\s*(?:is|of|=|:)?\s*{QUANTITY}",
        rf"{QUANTITY}\s*(?:from\s+(?:each|every|the)\s+edges?|edge\s+offset)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            number = float(match.group("value").replace(",", "."))
            unit = (match.group("unit") or "mm").lower()
            return number * UNIT_TO_MM[unit], match.group("unit") is not None
    raise ValueError("Chưa xác định được khoảng cách từ tâm lỗ đến mép. Hãy ghi rõ giá trị.")


def _hole_count(text: str):
    count = r"(?P<count>\d+|four|bốn)"
    patterns = (
        rf"\b{count}\s*(?:through\s+)?(?:lỗ|holes?)\b",
        rf"\b(?:lỗ|holes?)\s*{count}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_count = match.group("count").lower()
            return 4 if raw_count in {"four", "bốn"} else int(raw_count)
    raise ValueError("Hãy ghi rõ số lỗ. Bộ parser hiện chỉ hỗ trợ đúng 4 lỗ xuyên.")


def plan_from_description(description: str, part_name: str = "part") -> CADPlan:
    """Deterministic, allowlisted parser for the tested rectangular plate and hole case."""
    text = unicodedata.normalize("NFKC", description).lower()
    unsupported = {
        "rãnh": "rãnh/slot",
        "slot": "rãnh/slot",
        "lỗ ren": "lỗ ren/threaded hole",
        "threaded": "lỗ ren/threaded hole",
        "blind hole": "lỗ mù/blind hole",
        "counterbore": "lỗ bậc/counterbore",
        "countersink": "lỗ vát/countersink",
        "fillet": "bo tròn/fillet",
        "bo góc": "bo góc/fillet",
        "chamfer": "vát cạnh/chamfer",
    }
    for token, feature_name in unsupported.items():
        if token in text:
            raise ValueError(f"Feature '{feature_name}' chưa được hỗ trợ; không tạo mô hình một phần.")

    length, length_unit = _dimension(text, "dài|length|long", "chiều dài")
    width, width_unit = _dimension(text, "rộng|width|wide", "chiều rộng")
    thickness, thickness_unit = _dimension(text, "dày|thickness|thick", "chiều dày")
    diameter, diameter_unit = _diameter(text)
    edge, edge_unit = _edge_offset(text)
    count = _hole_count(text)
    if count != 4:
        raise ValueError("Parser hiện chỉ hỗ trợ đúng 4 lỗ xuyên; số lỗ trong yêu cầu không phù hợp.")

    positions = [
        {"x": edge, "y": edge},
        {"x": length - edge, "y": edge},
        {"x": edge, "y": width - edge},
        {"x": length - edge, "y": width - edge},
    ]
    assumptions = []
    if not all((length_unit, width_unit, thickness_unit, diameter_unit, edge_unit)):
        assumptions.append("Kích thước không ghi đơn vị được hiểu là mm.")
    if not any(token in text for token in ("tâm lỗ", "hole center", "hole centre", "center-to-edge", "centre-to-edge")):
        assumptions.append("Khoảng cách mép được hiểu là từ tâm lỗ đến cạnh tấm.")

    return CADPlan.model_validate({
        "schema_version": "1.0",
        "part_name": part_name,
        "units": "mm",
        "features": [
            {"id": "base", "type": "extruded_plate", "length": length, "width": width, "thickness": thickness},
            {"id": "holes", "type": "through_holes", "diameter": diameter, "positions": positions},
        ],
        "outputs": ["fcstd", "step", "stl", "pdf"],
        "assumptions": assumptions,
        "warnings": ["PDF đầu ra là bản vẽ minh họa, không phải bản vẽ sản xuất được chứng nhận."],
    })
