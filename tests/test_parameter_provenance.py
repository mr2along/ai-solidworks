import pytest
from pydantic import ValidationError

from backend.provenance import ParameterSet, ParameterSpec


def test_user_provided_dimension_requires_source():
    parameter = ParameterSpec(
        name="shaft_diameter",
        value=25,
        unit="mm",
        status="USER_PROVIDED",
        source="User-supplied design input",
    )
    assert parameter.value == 25
    assert parameter.status == "USER_PROVIDED"


def test_tbd_parameter_must_not_claim_a_value():
    with pytest.raises(ValidationError, match="TBD parameters must have value=null"):
        ParameterSpec(name="shaft_length", value=400, status="TBD")


def test_known_parameter_requires_a_value():
    with pytest.raises(ValidationError, match="require a value"):
        ParameterSpec(name="bracket_thickness", value=None, status="ESTIMATED")


def test_measured_parameter_requires_traceable_source():
    with pytest.raises(ValidationError, match="require a source"):
        ParameterSpec(name="bracket_height", value=350, status="MEASURED")


def test_parameter_set_rejects_duplicate_names():
    payload = {
        "part_name": "roll_holder",
        "parameters": [
            {"name": "shaft_diameter", "value": 25, "status": "USER_PROVIDED", "source": "user"},
            {"name": "shaft_diameter", "value": 30, "status": "ESTIMATED"},
        ],
    }
    with pytest.raises(ValidationError, match="unique"):
        ParameterSet.model_validate(payload)


def test_roll_holder_parameter_set_preserves_known_and_unknown_dimensions():
    payload = {
        "part_name": "roll_holder",
        "parameters": [
            {"name": "shaft_diameter", "value": 25, "status": "USER_PROVIDED", "source": "user"},
            {"name": "roll_outer_diameter", "value": 600, "status": "USER_PROVIDED", "source": "user"},
            {"name": "roll_width", "value": 400, "status": "USER_PROVIDED", "source": "user"},
            {"name": "triangular_bracket_height", "value": 350, "status": "USER_PROVIDED", "source": "user"},
            {"name": "shaft_total_length", "value": None, "status": "TBD"},
        ],
    }
    plan = ParameterSet.model_validate(payload)
    assert len(plan.parameters) == 5
    assert plan.parameters[-1].value is None
    assert plan.parameters[-1].status == "TBD"
