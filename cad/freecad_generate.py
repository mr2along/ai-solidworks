"""Run inside FreeCAD's Python runtime; input/output paths are environment variables."""
import json
import os
import sys
import traceback

import FreeCAD as App
import Part
import Mesh

config_path = os.environ["CAD_JOB_CONFIG"]
output_dir = os.environ["CAD_OUTPUT_DIR"]

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

    if shape.isNull() or not shape.isValid() or shape.Volume <= 0:
        raise RuntimeError("FreeCAD produced an invalid or empty solid.")

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
