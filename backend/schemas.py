import math
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=2000, allow_inf_nan=False)
    y: float = Field(ge=0, le=2000, allow_inf_nan=False)


class Feature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    type: Literal["extruded_plate", "through_holes", "through_slots"]
    length: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    width: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    thickness: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    diameter: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    positions: list[Hole] = Field(default_factory=list, max_length=20)
    slot_length: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    slot_width: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    orientation: Literal["x", "y"] | None = None


class CADPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    schema_version: Literal["1.0", "1.1"] = "1.1"
    part_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    units: Literal["mm"] = "mm"
    features: list[Feature] = Field(min_length=1, max_length=3)
    outputs: list[Literal["step", "stl", "fcstd", "pdf"]] = Field(
        default_factory=lambda: ["fcstd", "step", "stl", "pdf"]
    )
    parameters: dict[str, float] = Field(default_factory=dict, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    validation: Literal["passed"] = "passed"
    backend: Literal["freecad"] = "freecad"

    @field_validator("parameters")
    @classmethod
    def reject_non_finite_metadata(cls, value):
        if any(not math.isfinite(number) for number in value.values()):
            raise ValueError("Plan parameters must be finite numbers")
        return value

    @model_validator(mode="after")
    def validate_feature_sequence(self):
        if set(self.outputs) != {"fcstd", "step", "stl", "pdf"} or len(self.outputs) != 4:
            raise ValueError("The current FreeCAD backend always exports FCStd, STEP, STL and PDF")
        if self.features[0].type != "extruded_plate":
            raise ValueError("The first feature must be extruded_plate")
        if len({feature.id for feature in self.features}) != len(self.features):
            raise ValueError("Feature IDs must be unique")
        cut_types = [feature.type for feature in self.features[1:]]
        if "extruded_plate" in cut_types:
            raise ValueError("Only one extruded_plate feature is supported")
        if len(cut_types) != len(set(cut_types)) or any(
            feature_type not in {"through_holes", "through_slots"} for feature_type in cut_types
        ):
            raise ValueError("Only one through_holes and one through_slots feature are supported")
        if cut_types == ["through_slots", "through_holes"]:
            raise ValueError("through_holes must precede through_slots in the feature sequence")
        base = self.features[0]
        if base.length is None or base.width is None or base.thickness is None:
            raise ValueError("extruded_plate requires length, width, thickness")
        if any(value is not None for value in (base.diameter, base.slot_length, base.slot_width, base.orientation)) or base.positions:
            raise ValueError("extruded_plate cannot contain hole parameters or cut parameters; add a cut feature")
        holes_feature = None
        slots_feature = None
        for feature in self.features[1:]:
            if feature.type == "through_holes":
                holes_feature = feature
                if feature.diameter is None or not feature.positions:
                    raise ValueError("through_holes requires diameter and positions")
                if any(value is not None for value in (feature.length, feature.width, feature.thickness,
                                                       feature.slot_length, feature.slot_width, feature.orientation)):
                    raise ValueError("through_holes cannot contain plate or slot dimensions")
                if feature.diameter >= min(base.length, base.width):
                    raise ValueError("Hole diameter must be smaller than plate dimensions")
                radius = feature.diameter / 2
                hole_coordinates = [(hole.x, hole.y) for hole in feature.positions]
                if len(set(hole_coordinates)) != len(hole_coordinates):
                    raise ValueError("Through-hole positions must be unique")
                for index, hole in enumerate(feature.positions):
                    if not (radius < hole.x < base.length - radius):
                        raise ValueError("Hole X coordinate lies outside the plate")
                    if not (radius < hole.y < base.width - radius):
                        raise ValueError("Hole Y coordinate lies outside the plate")
                    for other in feature.positions[index + 1:]:
                        if math.dist((hole.x, hole.y), (other.x, other.y)) <= feature.diameter:
                            raise ValueError("Through holes must not overlap or touch")
            elif feature.type == "through_slots":
                if self.schema_version != "1.1":
                    raise ValueError("through_slots requires CAD Plan schema version 1.1")
                slots_feature = feature
                if feature.slot_length is None or feature.slot_width is None or not feature.positions:
                    raise ValueError("through_slots requires slot_length, slot_width and center positions")
                if feature.orientation not in {"x", "y"}:
                    raise ValueError("through_slots requires orientation 'x' or 'y'")
                if any(value is not None for value in (feature.length, feature.width, feature.thickness, feature.diameter)):
                    raise ValueError("through_slots cannot contain plate dimensions or hole diameter")
                if feature.slot_length <= feature.slot_width:
                    raise ValueError("A rounded-end slot length must be greater than its width")
                if len(set((point.x, point.y) for point in feature.positions)) != len(feature.positions):
                    raise ValueError("Through-slot centers must be unique")
                half_length = feature.slot_length / 2
                radius = feature.slot_width / 2
                for position in feature.positions:
                    half_x = half_length if feature.orientation == "x" else radius
                    half_y = radius if feature.orientation == "x" else half_length
                    if not (half_x < position.x < base.length - half_x):
                        raise ValueError("Through-slot X extent lies outside the plate")
                    if not (half_y < position.y < base.width - half_y):
                        raise ValueError("Through-slot Y extent lies outside the plate")
                centerline_half = (feature.slot_length - feature.slot_width) / 2
                for index, first in enumerate(feature.positions):
                    for second in feature.positions[index + 1:]:
                        if feature.orientation == "x":
                            axis_gap = max(0.0, abs(first.x - second.x) - 2 * centerline_half)
                            cross_gap = abs(first.y - second.y)
                        else:
                            axis_gap = max(0.0, abs(first.y - second.y) - 2 * centerline_half)
                            cross_gap = abs(first.x - second.x)
                        if math.hypot(axis_gap, cross_gap) <= feature.slot_width:
                            raise ValueError("Through slots must not overlap or touch")

        if holes_feature and slots_feature:
            slot_radius = slots_feature.slot_width / 2
            slot_half = (slots_feature.slot_length - slots_feature.slot_width) / 2
            hole_radius = holes_feature.diameter / 2
            for hole in holes_feature.positions:
                for slot in slots_feature.positions:
                    if slots_feature.orientation == "x":
                        axis_delta = max(0.0, abs(hole.x - slot.x) - slot_half)
                        cross_delta = abs(hole.y - slot.y)
                    else:
                        axis_delta = max(0.0, abs(hole.y - slot.y) - slot_half)
                        cross_delta = abs(hole.x - slot.x)
                    if math.hypot(axis_delta, cross_delta) <= slot_radius + hole_radius:
                        raise ValueError("Through holes must not overlap or touch through slots")

        # These fields are always recomputed from the validated features. A client
        # cannot make stale preview metadata authoritative by editing it.
        self.parameters = {
            "length_mm": base.length,
            "width_mm": base.width,
            "thickness_mm": base.thickness,
        }
        self.constraints = ["one_valid_solid", "plate_dimensions_within_limits"]
        if holes_feature:
            self.parameters["hole_diameter_mm"] = holes_feature.diameter
            self.parameters["hole_count"] = float(len(holes_feature.positions))
            self.constraints.extend(["holes_inside_plate", "holes_non_overlapping", "holes_through_all"])
        if slots_feature:
            self.parameters["slot_length_mm"] = slots_feature.slot_length
            self.parameters["slot_width_mm"] = slots_feature.slot_width
            self.parameters["slot_count"] = float(len(slots_feature.positions))
            self.constraints.extend(["slots_inside_plate", "slots_non_overlapping", "slots_clear_of_holes", "slots_through_all"])
        self.validation = "passed"
        return self


class PlanRequest(BaseModel):
    description: str = Field(min_length=5, max_length=4000)
    part_name: str = Field(default="part", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: CADPlan


class JobResponse(BaseModel):
    job_id: str
    status: str
    plan: CADPlan
    message: str
