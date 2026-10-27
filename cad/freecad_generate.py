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


def _cylindrical_centers(shape, radius, tolerance):
    centers = []
    for face in shape.Faces:
        surface = face.Surface
        if not hasattr(surface, "Radius") or not hasattr(surface, "Center") or not hasattr(surface, "Axis"):
            continue
        axis = surface.Axis
        if (
            math.isclose(surface.Radius, radius, rel_tol=0.0, abs_tol=tolerance)
            and abs(axis.x) <= tolerance
            and abs(axis.y) <= tolerance
            and math.isclose(abs(axis.z), 1.0, rel_tol=0.0, abs_tol=tolerance)
        ):
            centers.append(surface.Center)
    return centers


def validate_shape(shape, length, width, thickness, holes_feature, slots_feature=None):
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
    expected_slot_centers = []
    if slots_feature:
        slot_length = float(slots_feature["slot_length"])
        slot_width = float(slots_feature["slot_width"])
        slot_radius = slot_width / 2.0
        slot_area = slot_width * (slot_length - slot_width) + math.pi * slot_radius**2
        expected_volume -= len(slots_feature["positions"]) * slot_area * thickness
        centerline_half = (slot_length - slot_width) / 2.0
        for position in slots_feature["positions"]:
            x, y = float(position["x"]), float(position["y"])
            if slots_feature["orientation"] == "x":
                expected_slot_centers.extend(((x - centerline_half, y), (x + centerline_half, y)))
            else:
                expected_slot_centers.extend(((x, y - centerline_half), (x, y + centerline_half)))
    volume_tolerance = max(1e-5, abs(expected_volume) * 1e-8)
    if not math.isclose(shape.Volume, expected_volume, rel_tol=0.0, abs_tol=volume_tolerance):
        raise RuntimeError("Generated solid volume does not match the planned through cuts.")

    expected_cylinders = {}
    if positions:
        expected_cylinders.setdefault(diameter / 2.0, []).extend(
            (float(position["x"]), float(position["y"])) for position in positions
        )
    if slots_feature:
        expected_cylinders.setdefault(float(slots_feature["slot_width"]) / 2.0, []).extend(expected_slot_centers)
    for radius, expected_centers in expected_cylinders.items():
        actual_centers = _cylindrical_centers(shape, radius, tolerance)
        if len(actual_centers) != len(expected_centers):
            raise RuntimeError("Generated through-cut cylindrical face count does not match the CAD plan.")
        unmatched = list(actual_centers)
        for x, y in expected_centers:
            match = next(
                (
                    index
                    for index, center in enumerate(unmatched)
                    if math.isclose(center.x, x, rel_tol=0.0, abs_tol=tolerance)
                    and math.isclose(center.y, y, rel_tol=0.0, abs_tol=tolerance)
                ),
                None,
            )
            if match is None:
                raise RuntimeError("A generated through-cut center does not match the CAD plan.")
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
    slots_feature = next((item for item in features[1:] if item["type"] == "through_slots"), None)
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

    if slots_feature:
        slot_length = float(slots_feature["slot_length"])
        slot_width = float(slots_feature["slot_width"])
        radius = slot_width / 2.0
        centerline_half = (slot_length - slot_width) / 2.0
        for position in slots_feature["positions"]:
            center_x, center_y = float(position["x"]), float(position["y"])
            if slots_feature["orientation"] == "x":
                box = Part.makeBox(
                    slot_length - slot_width,
                    slot_width,
                    thickness + 2.0,
                    App.Vector(center_x - centerline_half, center_y - radius, -1.0),
                )
                end_centers = ((center_x - centerline_half, center_y), (center_x + centerline_half, center_y))
            else:
                box = Part.makeBox(
                    slot_width,
                    slot_length - slot_width,
                    thickness + 2.0,
                    App.Vector(center_x - radius, center_y - centerline_half, -1.0),
                )
                end_centers = ((center_x, center_y - centerline_half), (center_x, center_y + centerline_half))
            cutter = box
            for end_x, end_y in end_centers:
                end_cylinder = Part.makeCylinder(
                    radius,
                    thickness + 2.0,
                    App.Vector(end_x, end_y, -1.0),
                    App.Vector(0, 0, 1),
                )
                cutter = cutter.fuse(end_cylinder)
            shape = shape.cut(cutter)

    validate_shape(shape, length, width, thickness, holes_feature, slots_feature)

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
    if slots_feature:
        obj.addProperty("App::PropertyLength", "SlotLength", "Dimensions")
        obj.SlotLength = float(slots_feature["slot_length"])
        obj.addProperty("App::PropertyLength", "SlotWidth", "Dimensions")
        obj.SlotWidth = float(slots_feature["slot_width"])
        obj.addProperty("App::PropertyInteger", "SlotCount", "Dimensions")
        obj.SlotCount = len(slots_feature["positions"])

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
