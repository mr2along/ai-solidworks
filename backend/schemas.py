from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Hole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float
    y: float


class Feature(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["extruded_plate", "through_holes"]
    length: float | None = Field(default=None, gt=0, le=2000)
    width: float | None = Field(default=None, gt=0, le=2000)
    thickness: float | None = Field(default=None, gt=0, le=500)
    diameter: float | None = Field(default=None, gt=0, le=500)
    positions: list[Hole] = Field(default_factory=list, max_length=100)


class CADPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    part_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    units: Literal["mm"] = "mm"
    features: list[Feature] = Field(min_length=1, max_length=20)
    outputs: list[Literal["step", "stl", "fcstd", "pdf"]] = Field(
        default_factory=lambda: ["fcstd", "step", "stl", "pdf"]
    )

    @model_validator(mode="after")
    def validate_feature_sequence(self):
        if self.features[0].type != "extruded_plate":
            raise ValueError("The first feature must be extruded_plate")
        base = self.features[0]
        if base.length is None or base.width is None or base.thickness is None:
            raise ValueError("extruded_plate requires length, width, thickness")
        for feature in self.features[1:]:
            if feature.type == "through_holes":
                if feature.diameter is None or not feature.positions:
                    raise ValueError("through_holes requires diameter and positions")
                if feature.diameter >= min(base.length, base.width):
                    raise ValueError("Hole diameter must be smaller than plate dimensions")
                radius = feature.diameter / 2
                for hole in feature.positions:
                    if not (radius <= hole.x <= base.length - radius):
                        raise ValueError("Hole X coordinate lies outside the plate")
                    if not (radius <= hole.y <= base.width - radius):
                        raise ValueError("Hole Y coordinate lies outside the plate")
        return self


class PlanRequest(BaseModel):
    description: str = Field(min_length=5, max_length=4000)
    part_name: str = Field(default="part", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class JobResponse(BaseModel):
    job_id: str
    status: str
    plan: CADPlan
    message: str
