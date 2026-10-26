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


def test_plan_discloses_edge_offset_interpretation_and_validation_metadata():
    plan = plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm"
    )

    assert plan.validation == "passed"
    assert plan.backend == "freecad"
    assert plan.parameters["hole_count"] == 4
    assert "Khoảng cách mép được hiểu là từ tâm lỗ đến cạnh tấm." in plan.assumptions
    assert plan.warnings


def test_non_finite_geometry_is_rejected():
    with pytest.raises(ValidationError):
        CADPlan.model_validate({
            "part_name": "invalid_nan",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": float("nan"), "width": 60, "thickness": 5},
            ],
        })


def test_non_finite_metadata_and_unimplemented_output_selection_are_rejected():
    payload = {
        "part_name": "invalid_metadata",
        "features": [
            {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
        ],
        "parameters": {"unsafe": float("inf")},
    }
    with pytest.raises(ValidationError, match="finite"):
        CADPlan.model_validate(payload)

    with pytest.raises(ValidationError, match="always exports"):
        CADPlan.model_validate({**payload, "parameters": {}, "outputs": ["stl"]})


def test_english_description_and_unit_conversion():
    plan = plan_from_description(
        "Make a plate 10 cm long, 60 mm wide, 0.5 cm thick, with four through holes Ø6 mm, 10 mm from each edge",
        "english_plate",
    )

    assert plan.features[0].length == 100
    assert plan.features[0].width == 60
    assert plan.features[0].thickness == 5
    assert plan.features[1].diameter == 6
    assert len(plan.features[1].positions) == 4
    assert "tâm lỗ" in plan.assumptions[0]


def test_inches_and_decimal_comma_are_converted_to_millimeters():
    plan = plan_from_description(
        "Plate length 4 in, width 2.4 in, thickness 0.2 in, four holes Ø0.24 in from each edge 0.4 in"
    )

    assert plan.features[0].length == pytest.approx(101.6)
    assert plan.features[0].width == pytest.approx(60.96)
    assert plan.features[0].thickness == pytest.approx(5.08)
    assert plan.features[1].diameter == pytest.approx(6.096)
    assert plan.features[1].positions[0].x == pytest.approx(10.16)


def test_unsupported_feature_and_incomplete_bracket_are_actionable():
    with pytest.raises(ValueError, match="chưa được hỗ trợ"):
        plan_from_description(
            "Plate length 100 mm, width 60 mm, thickness 5 mm, four threaded holes Ø6 mm, 10 mm from each edge"
        )
    with pytest.raises(ValueError, match="chiều dài"):
        plan_from_description("Create a metal bracket")


def test_base_feature_rejects_ignored_hole_parameters():
    with pytest.raises(ValidationError, match="cannot contain hole parameters"):
        CADPlan.model_validate({
            "part_name": "ignored_holes",
            "features": [
                {
                    "id": "base",
                    "type": "extruded_plate",
                    "length": 100,
                    "width": 60,
                    "thickness": 5,
                    "diameter": 6,
                    "positions": [{"x": 10, "y": 10}],
                },
            ],
        })


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
