import re

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.assembly_pdf import _assembly_bounds, _component_instances, _rotated_plan
from backend import main
from backend.main import create_assembly_drawing
from backend.schemas import AssemblyDrawingRequest


def _part_plan(name: str, length: float, width: float, thickness: float) -> dict:
    return {
        "schema_version": "1.2",
        "part_name": name,
        "units": "mm",
        "features": [{
            "id": "base",
            "type": "extruded_plate",
            "length": length,
            "width": width,
            "thickness": thickness,
        }],
        "outputs": ["fcstd", "step", "stl", "pdf"],
        "backend": "freecad",
    }


def _assembly_plan() -> dict:
    return {
        "schema_version": "1.0",
        "assembly_name": "mounting_assembly",
        "units": "mm",
        "items": [
            {
                "id": "base_plate",
                "item_number": 1,
                "part_plan": _part_plan("base_plate", 100, 60, 5),
                "placements": [{"x": 0, "y": 0, "z": 0, "rotation_z": 0}],
            },
            {
                "id": "support_plate",
                "item_number": 2,
                "part_plan": _part_plan("support_plate", 20, 20, 5),
                "placements": [{"x": 40, "y": 20, "z": 5, "rotation_z": 90}],
            },
        ],
    }


def test_rotated_plan_swaps_plate_size_and_transforms_cut_features():
    plan = _part_plan("feature_plate", 100, 60, 5)
    plan["features"].extend([
        {
            "id": "holes",
            "type": "through_holes",
            "diameter": 6,
            "positions": [{"x": 10, "y": 10}, {"x": 90, "y": 50}],
        },
        {
            "id": "slot",
            "type": "through_slots",
            "slot_length": 24,
            "slot_width": 6,
            "orientation": "x",
            "positions": [{"x": 50, "y": 30}],
        },
        {
            "id": "pocket",
            "type": "rectangular_pockets",
            "pocket_length": 20,
            "pocket_width": 10,
            "pocket_depth": 2,
            "positions": [{"x": 50, "y": 50}],
        },
    ])

    rotated = _rotated_plan(plan, 90)

    assert rotated["features"][0]["length"] == 60
    assert rotated["features"][0]["width"] == 100
    assert rotated["features"][1]["positions"] == [{"x": 50, "y": 10}, {"x": 10, "y": 90}]
    assert rotated["features"][2]["orientation"] == "y"
    assert rotated["features"][2]["positions"] == [{"x": 30, "y": 50}]
    assert rotated["features"][3]["pocket_length"] == 10
    assert rotated["features"][3]["pocket_width"] == 20


@pytest.mark.parametrize(
    ("rotation", "dimensions", "hole_center"),
    [
        (0, (100, 60), (10, 10)),
        (90, (60, 100), (50, 10)),
        (180, (100, 60), (90, 50)),
        (270, (60, 100), (10, 90)),
    ],
)
def test_all_supported_rotations_preserve_part_footprint(rotation, dimensions, hole_center):
    plan = _part_plan("rotation_test", 100, 60, 5)
    plan["features"].append({
        "id": "holes",
        "type": "through_holes",
        "diameter": 6,
        "positions": [{"x": 10, "y": 10}],
    })

    rotated = _rotated_plan(plan, rotation)

    assert (rotated["features"][0]["length"], rotated["features"][0]["width"]) == dimensions
    assert (rotated["features"][1]["positions"][0]["x"], rotated["features"][1]["positions"][0]["y"]) == hole_center


def test_assembly_schema_rejects_duplicate_bom_numbers_and_single_instance():
    plan = _assembly_plan()
    plan["items"][1]["item_number"] = plan["items"][0]["item_number"]
    with pytest.raises(ValidationError, match="BOM item numbers must be unique"):
        AssemblyDrawingRequest.model_validate({"plan": plan})

    plan = _assembly_plan()
    plan["items"] = [plan["items"][0]]
    with pytest.raises(ValidationError, match="at least two placed components"):
        AssemblyDrawingRequest.model_validate({"plan": plan})

    plan = _assembly_plan()
    plan["assembly_name"] = "../unsafe"
    with pytest.raises(ValidationError):
        AssemblyDrawingRequest.model_validate({"plan": plan})


def test_assembly_schema_rejects_unbounded_or_duplicate_poses():
    plan = _assembly_plan()
    plan["items"][1]["placements"][0]["x"] = float("inf")
    with pytest.raises(ValidationError):
        AssemblyDrawingRequest.model_validate({"plan": plan})

    plan = _assembly_plan()
    plan["items"][0]["placements"] = [
        {"x": 0, "y": 0, "z": 0, "rotation_z": 0},
        {"x": 0, "y": 0, "z": 0, "rotation_z": 0},
    ]
    with pytest.raises(ValidationError, match="placements for one BOM item must be unique"):
        AssemblyDrawingRequest.model_validate({"plan": plan})

    plan = _assembly_plan()
    plan["items"][0]["part_plan"]["warnings"] = ["x" * 301]
    with pytest.raises(ValidationError):
        AssemblyDrawingRequest.model_validate({"plan": plan})


def test_assembly_geometry_bounds_include_rotated_placed_components():
    plan = AssemblyDrawingRequest.model_validate({"plan": _assembly_plan()}).plan.model_dump(mode="json")
    instances = _component_instances(plan)

    assert _assembly_bounds(instances) == (0.0, 0.0, 0.0, 100.0, 60.0, 10.0)


def test_assembly_drawing_endpoint_returns_two_page_pdf_with_bom_and_views():
    request = AssemblyDrawingRequest.model_validate({"plan": _assembly_plan()})

    response = create_assembly_drawing(request)

    assert response.status_code == 200
    assert response.media_type == "application/pdf"
    assert response.headers["Content-Disposition"] == 'attachment; filename="assembly-drawing.pdf"'
    pdf = response.body
    assert pdf.startswith(b"%PDF-")
    assert b"%%EOF" in pdf[-1024:]
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 2
    for label in (
        b"ASSEMBLED ISOMETRIC VIEW",
        b"BILL OF MATERIALS",
        b"base_plate",
        b"support_plate",
        b"TOP VIEW",
        b"FRONT VIEW",
        b"RIGHT VIEW",
        b"No interference, mating or tolerance analysis is included.",
    ):
        assert label in pdf


def test_assembly_endpoint_does_not_return_invalid_pdf(monkeypatch):
    monkeypatch.setattr(main, "export_assembly_pdf", lambda _plan, output: output.write(b"not a pdf"))
    request = AssemblyDrawingRequest.model_validate({"plan": _assembly_plan()})

    with pytest.raises(HTTPException) as error:
        create_assembly_drawing(request)

    assert error.value.status_code == 500
    assert "not a pdf" not in error.value.detail
    assert error.value.headers["X-Correlation-ID"] in error.value.detail
