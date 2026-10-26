import re
from .schemas import CADPlan


def plan_from_description(description: str, part_name: str = "part") -> CADPlan:
    """Small deterministic demo planner; not a general natural-language CAD model."""
    text = description.lower().replace(",", ".")
    def number(pattern: str, label: str) -> float:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            raise ValueError(f"Chưa xác định được {label}. Hãy ghi rõ thông số theo mm.")
        return float(match.group(1))

    length = number(r"(?:dài|length)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)", "chiều dài")
    width = number(r"(?:rộng|width)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)", "chiều rộng")
    thickness = number(r"(?:dày|thickness)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)", "chiều dày")
    diameter = number(r"(?:ø|phi|đường kính)\s*(\d+(?:\.\d+)?)", "đường kính lỗ")
    edge = number(r"cách mép\s*(\d+(?:\.\d+)?)", "khoảng cách tâm lỗ đến mép")
    count_match = re.search(r"(\d+)\s*lỗ", text)
    if not count_match or int(count_match.group(1)) != 4:
        raise ValueError("MVP demo hiện chỉ hỗ trợ mẫu có 4 lỗ. Hãy ghi rõ '4 lỗ'.")
    positions = [
        {"x": edge, "y": edge},
        {"x": length - edge, "y": edge},
        {"x": edge, "y": width - edge},
        {"x": length - edge, "y": width - edge},
    ]
    return CADPlan.model_validate({
        "schema_version": "1.0",
        "part_name": part_name,
        "units": "mm",
        "features": [
            {"id": "base", "type": "extruded_plate", "length": length, "width": width, "thickness": thickness},
            {"id": "holes", "type": "through_holes", "diameter": diameter, "positions": positions},
        ],
        "outputs": ["sldprt", "step"],
    })
