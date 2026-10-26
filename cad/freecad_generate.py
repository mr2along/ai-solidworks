"""Run inside FreeCAD's Python runtime; input/output paths are environment variables."""
import json
import math
import os
import sys
import traceback

import FreeCAD as App
import Part
import Mesh

config_path = os.environ["CAD_JOB_CONFIG"]
output_dir = os.environ["CAD_OUTPUT_DIR"]


def validate_shape(shape, length, width, thickness, holes_feature):
    if shape.isNull() or not shape.isValid() or shape.Volume <= 0:
        raise RuntimeError("FreeCAD produced an invalid or empty solid.")
    if len(shape.Solids) != 1:
        raise RuntimeError("Expected one connected solid in the generated part.")

    tolerance = 1e-6
    bounds = shape.BoundBox
    expected_bounds = (length, width, thickness)
    actual_bounds = (bounds.XLength, bounds.YLength, bounds.ZLength)
    for label, actual, expected in zip(("length", "width", "thickness"), actual_bounds, expected_bounds):
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
            raise RuntimeError(f"Generated {label} does not match the CAD plan.")

    positions = holes_feature["positions"] if holes_feature else []
    diameter = float(holes_feature["diameter"]) if holes_feature else 0.0
    expected_volume = length * width * thickness
    if holes_feature:
        expected_volume -= len(positions) * math.pi * (diameter / 2.0) ** 2 * thickness
    volume_tolerance = max(1e-5, abs(expected_volume) * 1e-8)
    if not math.isclose(shape.Volume, expected_volume, rel_tol=0.0, abs_tol=volume_tolerance):
        raise RuntimeError("Generated solid volume does not match the planned through holes.")

    if positions:
        hole_faces = []
        for face in shape.Faces:
            surface = face.Surface
            if not hasattr(surface, "Radius") or not hasattr(surface, "Center") or not hasattr(surface, "Axis"):
                continue
            axis = surface.Axis
            if (
                math.isclose(surface.Radius, diameter / 2.0, rel_tol=0.0, abs_tol=tolerance)
                and abs(axis.x) <= tolerance
                and abs(axis.y) <= tolerance
                and math.isclose(abs(axis.z), 1.0, rel_tol=0.0, abs_tol=tolerance)
            ):
                hole_faces.append(surface.Center)

        if len(hole_faces) != len(positions):
            raise RuntimeError("Generated through-hole count does not match the CAD plan.")

        unmatched = list(hole_faces)
        for position in positions:
            match = next(
                (
                    index
                    for index, center in enumerate(unmatched)
                    if math.isclose(center.x, float(position["x"]), rel_tol=0.0, abs_tol=tolerance)
                    and math.isclose(center.y, float(position["y"]), rel_tol=0.0, abs_tol=tolerance)
                ),
                None,
            )
            if match is None:
                raise RuntimeError("A generated through-hole center does not match the CAD plan.")
            unmatched.pop(match)


def main():
    with open(config_path, "r", encoding="utf-8") as handle:
        plan = json.load(handle)

    features = plan["features"]
    base = features[0]
    length = float(base["length"])
    width = float(base["width"])
    thickness = float(base["thickness"])

    holes_feature = next((item for item in features[1:] if item["type"] == "through_holes"), None)
    shape = Part.makeBox(length, width, thickness)
    if holes_feature:
        radius = float(holes_feature["diameter"]) / 2.0
        for position in holes_feature["positions"]:
            cutter = Part.makeCylinder(
                radius,
                thickness + 2.0,
                App.Vector(float(position["x"]), float(position["y"]), -1.0),
                App.Vector(0, 0, 1),
            )
            shape = shape.cut(cutter)

    validate_shape(shape, length, width, thickness, holes_feature)

    name = plan["part_name"]
    doc = App.newDocument(name)
    obj = doc.addObject("Part::Feature", "GeneratedPart")
    obj.Label = name
    obj.Shape = shape
    obj.addProperty("App::PropertyLength", "PlateLength", "Dimensions")
    obj.PlateLength = length
    obj.addProperty("App::PropertyLength", "PlateWidth", "Dimensions")
    obj.PlateWidth = width
    obj.addProperty("App::PropertyLength", "PlateThickness", "Dimensions")
    obj.PlateThickness = thickness
    if holes_feature:
        obj.addProperty("App::PropertyLength", "HoleDiameter", "Dimensions")
        obj.HoleDiameter = float(holes_feature["diameter"])
        obj.addProperty("App::PropertyInteger", "HoleCount", "Dimensions")
        obj.HoleCount = len(holes_feature["positions"])

    doc.recompute()
    fcstd_path = os.path.join(output_dir, name + ".FCStd")
    step_path = os.path.join(output_dir, name + ".step")
    stl_path = os.path.join(output_dir, name + ".stl")
    doc.saveAs(fcstd_path)
    Part.export([obj], step_path)
    Mesh.export([obj], stl_path)
    doc.recompute()
    App.closeDocument(doc.Name)

    for path in (fcstd_path, step_path, stl_path):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError("Expected output was not created: " + path)
    print("CAD_GENERATION_OK")

try:
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
