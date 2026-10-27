"""Typed parameter provenance for production CAD plans.

This module is intentionally independent of the existing CADPlan schema so it can
be introduced without breaking schema versions 1.0–1.2. Later feature schemas can
embed ParameterSpec directly.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ParameterStatus = Literal[
    "USER_PROVIDED",
    "MEASURED",
    "DERIVED",
    "ESTIMATED",
    "TBD",
]


class ParameterSpec(BaseModel):
    """A dimension or design parameter with explicit provenance."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    value: float | str | bool | None = None
    unit: str = Field(default="mm", min_length=1, max_length=24)
    status: ParameterStatus
    source: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_value_status(self):
        if self.status == "TBD" and self.value is not None:
            raise ValueError("TBD parameters must have value=null")
        if self.status != "TBD" and self.value is None:
            raise ValueError(f"{self.status} parameters require a value")
        if isinstance(self.value, float):
            if self.value != self.value or self.value in (float("inf"), float("-inf")):
                raise ValueError("Parameter values must be finite")
        if self.status in {"USER_PROVIDED", "MEASURED"} and not self.source:
            raise ValueError(f"{self.status} parameters require a source")
        return self


class ParameterSet(BaseModel):
    """Versioned collection of parameters for a part or assembly."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    part_name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    units: Literal["mm"] = "mm"
    parameters: list[ParameterSpec] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_parameter_names(self):
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Parameter names must be unique")
        return self
