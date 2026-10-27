import re

from backend.export_pdf import export_dimension_pdf


def _plate_plan():
    return {
        "part_name": "drawing_test_plate",
        "features": [
            {
                "id": "base",
                "type": "extruded_plate",
                "length": 100,
                "width": 60,
                "thickness": 5,
            },
            {
                "id": "holes",
                "type": "through_holes",
                "diameter": 6,
                "positions": [
                    {"x": 10, "y": 10},
                    {"x": 90, "y": 10},
                    {"x": 10, "y": 50},
                    {"x": 90, "y": 50},
                ],
            },
        ],
    }


def test_pdf_has_isometric_and_all_six_orthographic_views(tmp_path):
    destination = tmp_path / "plate-drawing.pdf"

    export_dimension_pdf(_plate_plan(), str(destination))

    pdf = destination.read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-1024:]
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 2
    for label in (
        b"ISOMETRIC VIEW",
        b"TOP VIEW",
        b"BOTTOM VIEW",
        b"FRONT VIEW",
        b"REAR VIEW",
        b"LEFT VIEW",
        b"RIGHT VIEW",
        b"4 x dia. 6 mm",
    ):
        assert label in pdf


def test_pdf_shows_slot_opening_and_dimensions(tmp_path):
    plan = _plate_plan()
    plan["features"].append({
        "id": "slot",
        "type": "through_slots",
        "slot_length": 30,
        "slot_width": 8,
        "orientation": "x",
        "positions": [{"x": 50, "y": 30}],
    })
    destination = tmp_path / "slotted-plate-drawing.pdf"

    export_dimension_pdf(plan, str(destination))

    pdf = destination.read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert b"Through slots: 1 x 30 x 8 mm; axis X" in pdf
    assert b"S1 center: X 50, Y 30 mm" in pdf
    assert b"through-cut boundaries hidden in edge views" in pdf
