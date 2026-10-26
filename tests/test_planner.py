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


def test_reject_duplicate_through_holes():
    with pytest.raises(ValidationError, match="positions must be unique"):
        CADPlan.model_validate({
            "part_name": "duplicate_holes",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
                {
                    "id": "holes",
                    "type": "through_holes",
                    "diameter": 6,
                    "positions": [{"x": 10, "y": 10}, {"x": 10, "y": 10}],
                },
            ],
        })


def test_reject_feature_types_the_executor_would_ignore():
    with pytest.raises(ValidationError, match="Only one extruded_plate"):
        CADPlan.model_validate({
            "part_name": "ignored_feature",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
                {"id": "second_base", "type": "extruded_plate", "length": 20, "width": 20, "thickness": 5},
            ],
        })


def test_reject_tangent_hole_and_holes_that_overlap():
    base = {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5}
    with pytest.raises(ValidationError, match="outside the plate"):
        CADPlan.model_validate({
            "part_name": "tangent_hole",
            "features": [
                base,
                {"id": "holes", "type": "through_holes", "diameter": 6, "positions": [{"x": 3, "y": 10}]},
            ],
        })

    with pytest.raises(ValidationError, match="must not overlap or touch"):
        CADPlan.model_validate({
            "part_name": "overlap_holes",
            "features": [
                base,
                {
                    "id": "holes",
                    "type": "through_holes",
                    "diameter": 6,
                    "positions": [{"x": 10, "y": 10}, {"x": 15, "y": 10}],
                },
            ],
        })
