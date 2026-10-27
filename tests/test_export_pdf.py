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
