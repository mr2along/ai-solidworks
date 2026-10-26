import pytest
from pydantic import ValidationError
from backend.planner import plan_from_description
from backend.schemas import CADPlan


def test_four_hole_plate_plan():
    plan = plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
        "mounting_plate",
    )
    assert plan.part_name == "mounting_plate"
    assert plan.features[0].length == 100
    assert len(plan.features[1].positions) == 4
    assert plan.outputs == ["fcstd", "step", "stl", "pdf"]


def test_reject_hole_outside_plate():
    with pytest.raises(ValidationError):
        CADPlan.model_validate({
            "part_name": "bad_plate",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
                {"id": "holes", "type": "through_holes", "diameter": 6, "positions": [{"x": 1, "y": 10}]}
            ]
        })


def test_missing_dimensions_is_actionable():
    with pytest.raises(ValueError, match="chiều dài"):
        plan_from_description("Vẽ một tấm thép có lỗ")
