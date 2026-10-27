"""Validate the file formats in a ZIP returned by the real FreeCAD API smoke test."""

import argparse
from io import BytesIO
import struct
import zipfile


EXPECTED = {"ci_plate.FCStd", "ci_plate.step", "ci_plate.stl", "ci_plate.pdf"}


def validate_archive(path: str) -> None:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Generated artifact ZIP contains a corrupt member")
        if set(archive.namelist()) != EXPECTED:
            raise ValueError(f"Unexpected artifact list: {sorted(archive.namelist())}")
        files = {name: archive.read(name) for name in EXPECTED}

    if any(not content for content in files.values()):
        raise ValueError("Generated artifact is empty")

    with zipfile.ZipFile(BytesIO(files["ci_plate.FCStd"])) as document:
        if document.testzip() is not None or "Document.xml" not in document.namelist():
            raise ValueError("FCStd document is not a readable FreeCAD archive")

    step = files["ci_plate.step"].lstrip()
    if not step.startswith(b"ISO-10303-21;") or b"END-ISO-10303-21;" not in step:
        raise ValueError("STEP export does not have a valid exchange-file envelope")

    stl = files["ci_plate.stl"]
    binary_facets = struct.unpack("<I", stl[80:84])[0] if len(stl) >= 84 else 0
    if binary_facets and len(stl) == 84 + binary_facets * 50:
        pass
    else:
        try:
            ascii_stl = stl.decode("ascii").lstrip()
        except UnicodeDecodeError as exc:
            raise ValueError("STL export is neither valid binary nor ASCII STL") from exc
        if not ascii_stl.startswith("solid") or "facet normal" not in ascii_stl or "endsolid" not in ascii_stl:
            raise ValueError("ASCII STL export is incomplete")

    pdf = files["ci_plate.pdf"]
    if not pdf.startswith(b"%PDF-") or b"%%EOF" not in pdf[-1024:]:
        raise ValueError("PDF export is incomplete")
    if b"Through slots: 1 x 30 x 8 mm; axis X" not in pdf:
        raise ValueError("PDF drawing does not document the planned rounded through-slot")
    if b"Blind rectangular pockets: 1 x 20 x 12 mm; depth 2 mm" not in pdf:
        raise ValueError("PDF drawing does not document the planned blind rectangular pocket")
    if b"Raised circular bosses: 1 x dia. 20 mm; height 8 mm" not in pdf:
        raise ValueError("PDF drawing does not document the planned raised circular boss")
    if b"B1 center: X 60, Y 20 mm" not in pdf:
        raise ValueError("PDF drawing does not document the planned boss center")

    print("Verified FCStd, STEP, STL and PDF artifact contents, including boss, through-slot and blind-pocket geometry")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    validate_archive(parser.parse_args().archive)
