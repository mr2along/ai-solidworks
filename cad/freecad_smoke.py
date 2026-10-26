"""Fail fast when the FreeCAD embedded Python runtime cannot load required modules."""

import datetime
import json
import math

import FreeCAD as App
import Mesh
import Part
import Sketcher


version = ".".join(App.Version()[:3])
assert math.isfinite(1.0)
assert datetime.datetime.now().year >= 2020
assert json.loads('{"ok": true}') == {"ok": True}
assert Part.makeBox(1, 1, 1).Volume == 1
assert Mesh.Mesh is not None
assert Sketcher is not None
print(f"FREECAD_RUNTIME_OK FreeCAD {version}")
