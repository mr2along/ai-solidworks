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


def _slot_position(text: str, length: float, width: float):
    coordinates = re.search(
        r"(?:tâm(?:\s+của)?\s+rãnh|slot\s+center|center\s+of\s+slot)\s*(?:at|tại)?\s*"
        r"x\s*[:=].*?[,;]\s*y\s*[:=]",
        text,
        re.IGNORECASE,
    )
    if coordinates:
        x_match = re.search(rf"\bx\s*[:=]\s*{QUANTITY}", coordinates.group(0), re.IGNORECASE)
        y_match = re.search(rf"\by\s*[:=]\s*{QUANTITY}", text[coordinates.start():], re.IGNORECASE)
        if x_match and y_match:
            x = float(x_match.group("value").replace(",", ".")) * UNIT_TO_MM[(x_match.group("unit") or "mm").lower()]
            y = float(y_match.group("value").replace(",", ".")) * UNIT_TO_MM[(y_match.group("unit") or "mm").lower()]
            return {"x": x, "y": y}, False

    centered = any(token in text for token in (
        "ở giữa tấm", "chính giữa tấm", "giữa tấm", "centered in the plate", "at the center of the plate",
        "at the centre of the plate", "center of the plate", "centre of the plate",
    ))
    if not centered:
        raise ValueError("Rãnh xuyên cần có tâm X/Y hoặc ghi rõ đặt chính giữa tấm.")
    return {"x": length / 2, "y": width / 2}, True


def _slot_orientation(text: str, length: float, width: float):
    if re.search(
        r"(?:theo|along)\s+(?:trục\s+)?y\b|(?:theo|along)\s+chiều\s+rộng|"
        r"(?:along|the)\s+(?:plate\s+)?width",
        text,
    ):
        return "y", False
    if re.search(
        r"(?:theo|along)\s+(?:trục\s+)?x\b|(?:theo|along)\s+chiều\s+dài|"
        r"(?:along|the)\s+(?:plate\s+)?length",
        text,
    ):
        return "x", False
    # A centered slot with no axis direction follows the plate's longer in-plane axis.
    return ("x" if length >= width else "y"), True


def _through_slot(text: str, length: float, width: float):
    slot_index = text.find("rãnh")
    if slot_index < 0:
        slot_index = text.find("slot")
    if slot_index < 0:
        return None, []
    slot_text = text[slot_index:]
    if not ("rãnh xuyên" in slot_text or re.search(r"\bthrough\s+slot\b", text)):
        raise ValueError("Hiện chỉ hỗ trợ rãnh xuyên; hãy ghi rõ 'rãnh xuyên' hoặc 'through slot'.")
    slot_length, length_unit = _dimension(slot_text, "dài|length|long", "chiều dài rãnh")
    slot_width, width_unit = _dimension(slot_text, "rộng|width|wide", "chiều rộng rãnh")
    position, is_centered = _slot_position(slot_text, length, width)
    orientation, inferred_axis = _slot_orientation(slot_text, length, width)
    assumptions = []
    if not (length_unit and width_unit):
        assumptions.append("Kích thước rãnh không ghi đơn vị được hiểu là mm.")
    if is_centered:
        assumptions.append("Rãnh được đặt tại tâm hình chữ nhật của tấm theo mô tả.")
    if inferred_axis:
        assumptions.append("Hướng rãnh không ghi rõ; rãnh được xoay theo cạnh dài của tấm.")
    return {
        "id": "slot",
        "type": "through_slots",
        "slot_length": slot_length,
        "slot_width": slot_width,
        "orientation": orientation,
        "positions": [position],
    }, assumptions


def plan_from_description(description: str, part_name: str = "part") -> CADPlan:
    """Deterministic, allowlisted parser for plates, four holes and rounded through slots."""
    text = unicodedata.normalize("NFKC", description).lower()
    unsupported = {
        "lỗ ren": "lỗ ren/threaded hole",
        "threaded": "lỗ ren/threaded hole",
        "blind hole": "lỗ mù/blind hole",
        "lỗ mù": "lỗ mù/blind hole",
        "blind slot": "rãnh mù/blind slot",
        "rãnh mù": "rãnh mù/blind slot",
        "counterbore": "lỗ bậc/counterbore",
        "countersink": "lỗ vát/countersink",
        "pocket": "hốc/pocket",
        "hốc": "hốc/pocket",
        "boss": "gờ/boss",
        "trục": "trục/shaft",
        "shaft": "trục/shaft",
        "revolve": "tiện xoay/revolve",
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
    features = [
        {"id": "base", "type": "extruded_plate", "length": length, "width": width, "thickness": thickness}
    ]
    assumptions = []
    if not all((length_unit, width_unit, thickness_unit)):
        assumptions.append("Kích thước không ghi đơn vị được hiểu là mm.")

    has_holes = bool(re.search(r"\b(?:lỗ|holes?)\b", text))
    if has_holes:
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
        features.append({"id": "holes", "type": "through_holes", "diameter": diameter, "positions": positions})
        if not all((diameter_unit, edge_unit)):
            assumptions.append("Kích thước không ghi đơn vị được hiểu là mm.")
        if not any(token in text for token in ("tâm lỗ", "hole center", "hole centre", "center-to-edge", "centre-to-edge")):
            assumptions.append("Khoảng cách mép được hiểu là từ tâm lỗ đến cạnh tấm.")

    slot_feature, slot_assumptions = _through_slot(text, length, width)
    if slot_feature:
        features.append(slot_feature)
        assumptions.extend(slot_assumptions)

    return CADPlan.model_validate({
        "schema_version": "1.1",
        "part_name": part_name,
        "units": "mm",
        "features": features,
        "outputs": ["fcstd", "step", "stl", "pdf"],
        "assumptions": assumptions,
        "warnings": ["PDF đầu ra là bản vẽ minh họa, không phải bản vẽ sản xuất được chứng nhận."],
    })
