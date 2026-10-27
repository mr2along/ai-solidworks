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
    assert plan.schema_version == "1.2"
    assert plan.features[0].length == 100
    assert len(plan.features[1].positions) == 4
    assert plan.outputs == ["fcstd", "step", "stl", "pdf"]


def test_centered_through_slot_is_combined_with_existing_hole_pattern():
    plan = plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm và "
        "rãnh xuyên dài 30 mm rộng 8 mm ở giữa tấm theo chiều dài",
        "slotted_plate",
    )

    assert [feature.type for feature in plan.features] == ["extruded_plate", "through_holes", "through_slots"]
    slot = plan.features[2]
    assert slot.slot_length == 30
    assert slot.slot_width == 8
    assert slot.orientation == "x"
    assert slot.positions[0].x == 50
    assert slot.positions[0].y == 30
    assert "slots_clear_of_holes" in plan.constraints


def test_english_slot_plan_supports_explicit_units_and_axis():
    plan = plan_from_description(
        "Make a plate length 10 cm, width 60 mm, thickness 5 mm with a through slot "
        "length 3 cm width 8 mm centered in the plate along the plate length",
        "english_slotted_plate",
    )

    assert len(plan.features) == 2
    slot = plan.features[1]
    assert slot.slot_length == 30
    assert slot.slot_width == 8
    assert slot.orientation == "x"
    assert slot.positions[0].model_dump() == {"x": 50, "y": 30}
    assert not any("Hướng rãnh không ghi rõ" in assumption for assumption in plan.assumptions)


def test_slot_accepts_explicit_center_coordinates_and_y_axis():
    plan = plan_from_description(
        "Plate length 100 mm, width 60 mm, thickness 5 mm with through slot length 20 mm "
        "width 6 mm, slot center at x=35 mm, y=25 mm, along Y"
    )

    slot = plan.features[1]
    assert slot.orientation == "y"
    assert slot.positions[0].model_dump() == {"x": 35, "y": 25}


def test_slot_requires_a_stated_center_or_coordinates():
    with pytest.raises(ValueError, match="cần có tâm X/Y"):
        plan_from_description(
            "Plate length 100 mm, width 60 mm, thickness 5 mm with a through slot length 30 mm width 8 mm"
        )


def test_slot_geometry_rejects_outside_and_colliding_features():
    base = {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5}
    slot = {
        "id": "slot", "type": "through_slots", "slot_length": 30, "slot_width": 8,
        "orientation": "x", "positions": [{"x": 50, "y": 30}],
    }
    with pytest.raises(ValidationError, match="extent lies outside"):
        CADPlan.model_validate({"part_name": "outside_slot", "features": [base, {**slot, "positions": [{"x": 10, "y": 30}]}]})

    with pytest.raises(ValidationError, match="must not overlap or touch through slots"):
        CADPlan.model_validate({
            "part_name": "slot_hole_collision",
            "features": [
                base,
                {"id": "holes", "type": "through_holes", "diameter": 6, "positions": [{"x": 50, "y": 30}]},
                slot,
            ],
        })


def test_slot_dimensions_and_unsupported_blind_slot_are_rejected():
    with pytest.raises(ValidationError, match="length must be greater than its width"):
        CADPlan.model_validate({
            "part_name": "bad_slot",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
                {"id": "slot", "type": "through_slots", "slot_length": 8, "slot_width": 8,
                 "orientation": "x", "positions": [{"x": 50, "y": 30}]},
            ],
        })
    with pytest.raises(ValueError, match="chưa được hỗ trợ"):
        plan_from_description(
            "Plate length 100 mm width 60 mm thickness 5 mm with a blind slot length 30 mm width 8 mm"
        )


def test_vietnamese_blind_rectangular_pocket_is_planned_with_holes():
    plan = plan_from_description(
        "Vẽ tấm dài 120 mm rộng 80 mm dày 10 mm, 4 lỗ Ø6 cách mép 10 mm, "
        "hốc chữ nhật dài 40 mm rộng 20 mm sâu 3 mm ở giữa tấm",
        "pocket_plate",
    )

    assert plan.schema_version == "1.2"
    assert [feature.type for feature in plan.features] == ["extruded_plate", "through_holes", "rectangular_pockets"]
    pocket = plan.features[-1]
    assert (pocket.pocket_length, pocket.pocket_width, pocket.pocket_depth) == (40, 20, 3)
    assert pocket.positions[0].model_dump() == {"x": 60, "y": 40}
    assert plan.parameters["pocket_count"] == 1
    assert "pockets_blind" in plan.constraints


def test_english_pocket_uses_explicit_units_and_center_coordinates():
    plan = plan_from_description(
        "Make a plate length 120 mm width 80 mm thickness 10 mm with a blind rectangular pocket "
        "length 40 mm width 20 mm depth 3 mm, pocket center at x=60 mm, y=40 mm"
    )

    pocket = plan.features[-1]
    assert pocket.type == "rectangular_pockets"
    assert (pocket.pocket_length, pocket.pocket_width, pocket.pocket_depth) == (40, 20, 3)
    assert pocket.positions[0].model_dump() == {"x": 60, "y": 40}


def test_blind_pocket_requires_explicit_shape_dimensions_and_location():
    with pytest.raises(ValueError, match="chiều sâu hốc"):
        plan_from_description(
            "Plate length 120 mm width 80 mm thickness 10 mm with rectangular pocket length 40 mm width 20 mm"
        )
    with pytest.raises(ValueError, match="cần có tâm X/Y"):
        plan_from_description(
            "Plate length 120 mm width 80 mm thickness 10 mm with rectangular blind pocket "
            "length 40 mm width 20 mm depth 3 mm"
        )
    with pytest.raises(ValueError, match="cần có tâm X/Y"):
        plan_from_description(
            "Plate length 120 mm width 80 mm thickness 10 mm with rectangular blind pocket "
            "length 40 mm width 20 mm depth 3 mm, and a through slot length 20 mm width 6 mm centered in the plate"
        )
    with pytest.raises(ValueError, match="chỉ hỗ trợ hốc chữ nhật mù"):
        plan_from_description(
            "Plate length 120 mm width 80 mm thickness 10 mm with circular pocket depth 3 mm"
        )


def test_blind_pocket_validation_rejects_through_depth_collision_and_overlap():
    base = {"id": "base", "type": "extruded_plate", "length": 120, "width": 80, "thickness": 10}
    pocket = {
        "id": "pockets", "type": "rectangular_pockets", "pocket_length": 40,
        "pocket_width": 20, "pocket_depth": 3, "positions": [{"x": 60, "y": 40}],
    }
    with pytest.raises(ValidationError, match="depth must be less than the plate thickness"):
        CADPlan.model_validate({"part_name": "through_pocket", "features": [base, {**pocket, "pocket_depth": 10}]})

    with pytest.raises(ValidationError, match="must not overlap or touch through holes"):
        CADPlan.model_validate({
            "part_name": "pocket_hole_collision",
            "features": [base,
                {"id": "holes", "type": "through_holes", "diameter": 6, "positions": [{"x": 40, "y": 40}]},
                pocket],
        })

    with pytest.raises(ValidationError, match="Rectangular pockets must not overlap or touch"):
        CADPlan.model_validate({
            "part_name": "overlapping_pockets",
            "features": [base, {**pocket, "positions": [{"x": 50, "y": 40}, {"x": 75, "y": 40}]}],
        })


def test_pocket_requires_schema_v12_and_is_clear_of_through_slots():
    base = {"id": "base", "type": "extruded_plate", "length": 120, "width": 80, "thickness": 10}
    pocket = {
        "id": "pockets", "type": "rectangular_pockets", "pocket_length": 30,
        "pocket_width": 12, "pocket_depth": 3, "positions": [{"x": 60, "y": 40}],
    }
    with pytest.raises(ValidationError, match="requires CAD Plan schema version 1.2"):
        CADPlan.model_validate({
            "schema_version": "1.1", "part_name": "legacy_pocket", "features": [base, pocket],
        })

    with pytest.raises(ValidationError, match="must not overlap or touch through slots"):
        CADPlan.model_validate({
            "part_name": "pocket_slot_collision",
            "features": [base,
                {"id": "slot", "type": "through_slots", "slot_length": 40, "slot_width": 8,
                 "orientation": "x", "positions": [{"x": 60, "y": 40}]},
                pocket],
        })


def test_schema_v10_remains_compatible_for_existing_plate_plans():
    plan = CADPlan.model_validate({
        "schema_version": "1.0",
        "part_name": "legacy_plate",
        "features": [
            {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
        ],
    })
    assert plan.schema_version == "1.0"

    with pytest.raises(ValidationError, match="requires CAD Plan schema version 1.1"):
        CADPlan.model_validate({
            "schema_version": "1.0",
            "part_name": "legacy_slot",
            "features": [
                {"id": "base", "type": "extruded_plate", "length": 100, "width": 60, "thickness": 5},
                {"id": "slot", "type": "through_slots", "slot_length": 30, "slot_width": 8,
                 "orientation": "x", "positions": [{"x": 50, "y": 30}]},
            ],
        })


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
