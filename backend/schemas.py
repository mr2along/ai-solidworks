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
    type: Literal["extruded_plate", "through_holes"]
    length: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    width: float | None = Field(default=None, gt=0, le=2000, allow_inf_nan=False)
    thickness: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    diameter: float | None = Field(default=None, gt=0, le=500, allow_inf_nan=False)
    positions: list[Hole] = Field(default_factory=list, max_length=100)


class CADPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")
    schema_version: Literal["1.0"] = "1.0"
    part_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    units: Literal["mm"] = "mm"
    features: list[Feature] = Field(min_length=1, max_length=2)
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
        if len(self.features) > 2 or any(feature.type != "through_holes" for feature in self.features[1:]):
            raise ValueError("Only one extruded_plate and one optional through_holes feature are supported")
        if len({feature.id for feature in self.features}) != len(self.features):
            raise ValueError("Feature IDs must be unique")
        base = self.features[0]
        if base.length is None or base.width is None or base.thickness is None:
            raise ValueError("extruded_plate requires length, width, thickness")
        if base.diameter is not None or base.positions:
            raise ValueError("extruded_plate cannot contain hole parameters; add a through_holes feature")
        for feature in self.features[1:]:
            if feature.type == "through_holes":
                if feature.diameter is None or not feature.positions:
                    raise ValueError("through_holes requires diameter and positions")
                if any(value is not None for value in (feature.length, feature.width, feature.thickness)):
                    raise ValueError("through_holes cannot contain plate dimensions")
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

        # These fields are always recomputed from the validated features. A client
        # cannot make stale preview metadata authoritative by editing it.
        self.parameters = {
            "length_mm": base.length,
            "width_mm": base.width,
            "thickness_mm": base.thickness,
        }
        self.constraints = ["one_valid_solid", "plate_dimensions_within_limits"]
        if len(self.features) == 2:
            holes = self.features[1]
            self.parameters["hole_diameter_mm"] = holes.diameter
            self.parameters["hole_count"] = float(len(holes.positions))
            self.constraints.extend(["holes_inside_plate", "holes_non_overlapping", "holes_through_all"])
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
