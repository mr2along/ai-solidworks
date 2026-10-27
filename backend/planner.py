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


def _feature_clause(text: str, start: int, following_markers: tuple[str, ...]) -> str:
    end = min(
        (index for marker in following_markers if (index := text.find(marker, start + 1)) >= 0),
        default=len(text),
    )
    return text[start:end]


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
    slot_text = _feature_clause(text, slot_index, ("hốc", "pocket"))
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


def _pocket_position(text: str, length: float, width: float):
    coordinates = re.search(
        r"(?:tâm(?:\s+của)?\s*(?:hốc|pocket)|pocket\s+(?:center|centre)|"
        r"cent(?:er|re)\s+of\s+(?:the\s+)?pocket)\s*(?:at|tại)?\s*"
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
        "ở giữa tấm", "chính giữa tấm", "giữa tấm", "centered in the plate",
        "at the center of the plate", "at the centre of the plate",
        "center of the plate", "centre of the plate",
    ))
    if not centered:
        raise ValueError("Hốc chữ nhật cần có tâm X/Y hoặc ghi rõ đặt chính giữa tấm.")
    return {"x": length / 2, "y": width / 2}, True


def _rectangular_pocket(text: str, length: float, width: float):
    markers = (
        "hốc mù hình chữ nhật", "hốc mù chữ nhật", "hốc hình chữ nhật", "hốc chữ nhật",
        "blind rectangular pocket", "rectangular blind pocket", "rectangular pocket",
    )
    marker = next((item for item in markers if item in text), None)
    if marker is None:
        if "pocket" in text or "hốc" in text:
            raise ValueError(
                "Hiện chỉ hỗ trợ hốc chữ nhật mù; hãy ghi rõ hình chữ nhật, chiều dài, chiều rộng, độ sâu và vị trí tâm."
            )
        return None, []

    pocket_index = text.find(marker)
    pocket_text = _feature_clause(text, pocket_index, ("rãnh", "slot", "lỗ", "hole"))
    pocket_length, length_unit = _dimension(pocket_text, "dài|length|long", "chiều dài hốc")
    pocket_width, width_unit = _dimension(pocket_text, "rộng|width|wide", "chiều rộng hốc")
    pocket_depth, depth_unit = _dimension(pocket_text, "sâu|depth|deep", "chiều sâu hốc")
    position, is_centered = _pocket_position(pocket_text, length, width)
    assumptions = []
    if not all((length_unit, width_unit, depth_unit)):
        assumptions.append("Kích thước hốc không ghi đơn vị được hiểu là mm.")
    if is_centered:
        assumptions.append("Hốc chữ nhật được đặt tại tâm hình chữ nhật của tấm theo mô tả.")
    return {
        "id": "pockets",
        "type": "rectangular_pockets",
        "pocket_length": pocket_length,
        "pocket_width": pocket_width,
        "pocket_depth": pocket_depth,
        "positions": [position],
    }, assumptions


def _circular_bosses(text: str, length: float, width: float):
    markers = ("cylindrical boss", "circular boss", "gờ trụ", "bệ trụ", "gờ tròn", "boss")
    marker = next((item for item in markers if item in text), None)
    if marker is None:
        if "gờ" in text or "boss" in text:
            raise ValueError("Hiện chỉ hỗ trợ gờ trụ tròn; hãy ghi boss/bệ trụ có đường kính và chiều cao.")
        return None, []

    boss_index = text.find(marker)
    boss_text = _feature_clause(text, boss_index, ("rãnh", "slot", "hốc", "pocket", "lỗ", "hole"))
    diameter, diameter_unit = _diameter(boss_text)
    height, height_unit = _dimension(boss_text, "cao|height|high|tall", "chiều cao boss")

    unit_pattern = r"millimeters?|millimetres?|mm|centimeters?|centimetres?|cm|meters?|metres?|m|inches|inch|in"
    pair_pattern = re.compile(
        rf"\bx\s*[:=]\s*(?P<x>-?\d+(?:[.,]\d+)?)\s*(?P<x_unit>{unit_pattern})?"
        rf"\s*[,;]\s*y\s*[:=]\s*(?P<y>-?\d+(?:[.,]\d+)?)\s*(?P<y_unit>{unit_pattern})?",
        re.IGNORECASE,
    )
    positions = []
    for match in pair_pattern.finditer(boss_text):
        x_unit = (match.group("x_unit") or "mm").lower()
        y_unit = (match.group("y_unit") or "mm").lower()
        positions.append({
            "x": float(match.group("x").replace(",", ".")) * UNIT_TO_MM[x_unit],
            "y": float(match.group("y").replace(",", ".")) * UNIT_TO_MM[y_unit],
        })

    centered = any(token in boss_text for token in (
        "ở giữa tấm", "chính giữa tấm", "giữa tấm", "centered in the plate",
        "at the center of the plate", "at the centre of the plate",
        "center of the plate", "centre of the plate",
    ))
    if not positions and centered:
        positions = [{"x": length / 2, "y": width / 2}]
    elif not positions:
        raise ValueError("Boss tròn cần có tâm X/Y rõ ràng hoặc ghi rõ đặt giữa tấm.")

    count_match = re.search(
        r"\b(?P<count>\d+|one|two|three|four|five|six|một|hai|ba|bốn|năm|sáu)\s+"
        r"(?:circular\s+|cylindrical\s+)?boss(?:es)?\b",
        text,
    )
    if count_match:
        count_names = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6,
        }
        stated_count = count_match.group("count")
        expected_count = int(stated_count) if stated_count.isdigit() else count_names[stated_count]
        if expected_count != len(positions):
            raise ValueError("Số boss được nêu không khớp với số vị trí tâm X/Y.")

    assumptions = []
    if not (diameter_unit and height_unit):
        assumptions.append("Kích thước boss không ghi đơn vị được hiểu là mm.")
    if centered and len(positions) == 1:
        assumptions.append("Boss tròn được đặt tại tâm hình chữ nhật của tấm theo mô tả.")
    return {
        "id": "bosses",
        "type": "circular_bosses",
        "boss_diameter": diameter,
        "boss_height": height,
        "positions": positions,
    }, assumptions


def plan_from_description(description: str, part_name: str = "part") -> CADPlan:
    """Parse the allowlisted plate, boss, through-cut and blind-pocket subset."""
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

    bosses_feature, boss_assumptions = _circular_bosses(text, length, width)
    if bosses_feature:
        features.append(bosses_feature)
        assumptions.extend(boss_assumptions)

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

    pocket_feature, pocket_assumptions = _rectangular_pocket(text, length, width)
    if pocket_feature:
        features.append(pocket_feature)
        assumptions.extend(pocket_assumptions)

    return CADPlan.model_validate({
        "schema_version": "1.3" if bosses_feature else "1.2",
        "part_name": part_name,
        "units": "mm",
        "features": features,
        "outputs": ["fcstd", "step", "stl", "pdf"],
        "assumptions": assumptions,
        "warnings": ["PDF đầu ra là bản vẽ minh họa, không phải bản vẽ sản xuất được chứng nhận."],
    })
