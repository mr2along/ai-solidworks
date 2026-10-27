"""Illustrative assembly drawing export for validated, placed plate plans."""

from __future__ import annotations

from typing import BinaryIO

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from .export_pdf import (
    INK,
    MUTED,
    RULE,
    _draw_elevation,
    _draw_isometric,
    _draw_top_view,
    _draw_footer,
    _draw_page_header,
    _iso_point,
    _rotate_xy,
    _view_label,
)


PART_COLORS: tuple[tuple[Color, Color, Color], ...] = (
    (HexColor("#B8C9D7"), HexColor("#8FA6B8"), HexColor("#E7EFF6")),
    (HexColor("#C8D8C5"), HexColor("#91AA8C"), HexColor("#E7F0E3")),
    (HexColor("#DDC9B6"), HexColor("#B89473"), HexColor("#F1E6D8")),
    (HexColor("#CEC7DF"), HexColor("#9C91B7"), HexColor("#E9E5F2")),
    (HexColor("#D9C5CB"), HexColor("#B08390"), HexColor("#F1E5E8")),
    (HexColor("#C7D5D7"), HexColor("#8DA7AA"), HexColor("#E5EFF0")),
)
LINE_COLORS: tuple[Color, ...] = (
    INK,
    HexColor("#315E3B"),
    HexColor("#85552B"),
    HexColor("#594B7C"),
    HexColor("#78434F"),
    HexColor("#365D63"),
)


def _rotated_plan(part_plan: dict, rotation_z: int) -> dict:
    """Rotate a supported plate plan about Z, normalizing its lower-left corner."""
    plan = {
        **part_plan,
        "features": [dict(feature) for feature in part_plan["features"]],
    }
    base = plan["features"][0]
    length, width = float(base["length"]), float(base["width"])
    odd_quarter_turn = rotation_z in {90, 270}
    if odd_quarter_turn:
        base["length"], base["width"] = width, length

    for feature in plan["features"][1:]:
        feature["positions"] = [
            {
                "x": _rotate_xy(float(position["x"]), float(position["y"]), length, width, rotation_z)[0],
                "y": _rotate_xy(float(position["x"]), float(position["y"]), length, width, rotation_z)[1],
            }
            for position in feature["positions"]
        ]
        if feature["type"] == "through_slots" and odd_quarter_turn:
            feature["orientation"] = "y" if feature["orientation"] == "x" else "x"
        if feature["type"] == "rectangular_pockets" and odd_quarter_turn:
            feature["pocket_length"], feature["pocket_width"] = (
                feature["pocket_width"], feature["pocket_length"]
            )
    return plan


def _component_instances(plan: dict) -> list[dict]:
    instances = []
    for item_index, item in enumerate(plan["items"]):
        for instance_index, placement in enumerate(item["placements"]):
            part_plan = item["part_plan"]
            rotation_z = int(placement["rotation_z"])
            rotated = _rotated_plan(part_plan, rotation_z)
            rotated_base = rotated["features"][0]
            bosses = next((feature for feature in rotated["features"][1:] if feature["type"] == "circular_bosses"), None)
            thickness = float(rotated_base["thickness"])
            instances.append({
                "item": item,
                "item_index": item_index,
                "instance_index": instance_index,
                "plan": rotated,
                "iso_plan": part_plan,
                "x": float(placement["x"]),
                "y": float(placement["y"]),
                "z": float(placement["z"]),
                "length": float(rotated_base["length"]),
                "width": float(rotated_base["width"]),
                "thickness": thickness,
                "height": thickness + (float(bosses["boss_height"]) if bosses else 0.0),
                "rotation_z": rotation_z,
                "color": LINE_COLORS[item_index % len(LINE_COLORS)],
                "face_colors": PART_COLORS[item_index % len(PART_COLORS)],
            })
    return instances


def _assembly_bounds(instances: list[dict]) -> tuple[float, float, float, float, float, float]:
    return (
        min(instance["x"] for instance in instances),
        min(instance["y"] for instance in instances),
        min(instance["z"] for instance in instances),
        max(instance["x"] + instance["length"] for instance in instances),
        max(instance["y"] + instance["width"] for instance in instances),
        max(instance["z"] + instance["height"] for instance in instances),
    )


def _isometric_projection(
    instances: list[dict], area: tuple[float, float, float, float]
) -> tuple[float, float, float]:
    area_x, area_y, area_w, area_h = area
    projected_points = [
        _iso_point(x, y, z, 1.0, 0.0, 0.0)
        for instance in instances
        for x in (instance["x"], instance["x"] + instance["length"])
        for y in (instance["y"], instance["y"] + instance["width"])
        for z in (instance["z"], instance["z"] + instance["height"])
    ]
    min_x = min(point[0] for point in projected_points)
    max_x = max(point[0] for point in projected_points)
    min_y = min(point[1] for point in projected_points)
    max_y = max(point[1] for point in projected_points)
    projected_w, projected_h = max_x - min_x, max_y - min_y
    scale = min(area_w / projected_w, area_h / projected_h)
    origin_x = area_x + (area_w - projected_w * scale) / 2 - min_x * scale
    origin_y = area_y + (area_h - projected_h * scale) / 2 - min_y * scale
    return scale, origin_x, origin_y


def _draw_balloon(
    pdf: canvas.Canvas,
    item_number: int,
    anchor: tuple[float, float],
    offset: tuple[float, float],
) -> None:
    x, y = anchor
    bx, by = x + offset[0], y + offset[1]
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.setLineWidth(0.7)
    pdf.line(x, y, bx, by)
    pdf.circle(bx, by, 8, stroke=1, fill=1)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawCentredString(bx, by - 2.5, str(item_number))
    pdf.restoreState()


def _draw_bom(pdf: canvas.Canvas, plan: dict, x: float, top: float, width: float) -> None:
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x, top, "BILL OF MATERIALS")
    pdf.setStrokeColor(RULE)
    pdf.line(x, top - 8, x + width, top - 8)
    columns = (x + 2, x + 34, x + 156, x + width - 4)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.setFillColor(MUTED)
    for position, label in zip(columns, ("ITEM", "PART", "QTY", "SIZE (mm)")):
        pdf.drawString(position, top - 23, label)
    row_y = top - 39
    for item in sorted(plan["items"], key=lambda value: value["item_number"]):
        base = item["part_plan"]["features"][0]
        part_name = item["part_plan"]["part_name"]
        bosses = next((feature for feature in item["part_plan"]["features"][1:] if feature["type"] == "circular_bosses"), None)
        total_height = float(base["thickness"]) + (float(bosses["boss_height"]) if bosses else 0.0)
        size = f'{float(base["length"]):g} x {float(base["width"]):g} x {total_height:g}'
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(columns[0], row_y, str(item["item_number"]))
        pdf.drawString(columns[1], row_y, part_name[:18])
        pdf.drawRightString(columns[2], row_y, str(len(item["placements"])))
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6.5)
        pdf.drawRightString(columns[3], row_y, size)
        pdf.setStrokeColor(RULE)
        pdf.line(x, row_y - 6, x + width, row_y - 6)
        row_y -= 22


def _elevation_details(part_plan: dict, axis: str) -> tuple[list[float], list[tuple[float, float]], list[tuple[float, float, float, float]]]:
    base = part_plan["features"][0]
    thickness = float(base["thickness"])
    hidden_positions: list[float] = []
    hidden_ranges: list[tuple[float, float]] = []
    hidden_rectangles: list[tuple[float, float, float, float]] = []
    holes = next((feature for feature in part_plan["features"][1:] if feature["type"] == "through_holes"), None)
    slots = next((feature for feature in part_plan["features"][1:] if feature["type"] == "through_slots"), None)
    pockets = next((feature for feature in part_plan["features"][1:] if feature["type"] == "rectangular_pockets"), None)

    if holes:
        radius = float(holes["diameter"]) / 2
        hidden_positions.extend(
            float(position[axis]) + delta
            for position in holes["positions"]
            for delta in (-radius, radius)
        )
    if slots:
        slot_width = float(slots["slot_width"])
        half_length = float(slots["slot_length"]) / 2
        for position in slots["positions"]:
            if slots["orientation"] == axis:
                center = float(position[axis])
                hidden_ranges.append((center - half_length, center + half_length))
            else:
                center = float(position[axis])
                hidden_positions.extend((center - slot_width / 2, center + slot_width / 2))
    if pockets:
        center_axis = "x" if axis == "x" else "y"
        half_span = float(pockets["pocket_length" if axis == "x" else "pocket_width"]) / 2
        floor_z = thickness - float(pockets["pocket_depth"])
        hidden_rectangles.extend(
            (
                float(position[center_axis]) - half_span,
                float(position[center_axis]) + half_span,
                floor_z,
                thickness,
            )
            for position in pockets["positions"]
        )
    return hidden_positions, hidden_ranges, hidden_rectangles


def _boss_elevation_rectangles(part_plan: dict, axis: str) -> list[tuple[float, float, float, float]]:
    bosses = next((feature for feature in part_plan["features"][1:] if feature["type"] == "circular_bosses"), None)
    if not bosses:
        return []
    base = part_plan["features"][0]
    radius = float(bosses["boss_diameter"]) / 2
    top_z = float(base["thickness"]) + float(bosses["boss_height"])
    return [
        (float(position[axis]) - radius, float(position[axis]) + radius, float(base["thickness"]), top_z)
        for position in bosses["positions"]
    ]


def export_assembly_pdf(plan: dict, destination: str | BinaryIO) -> None:
    """Render an assembly PDF from explicit plate plans and user-supplied poses."""
    instances = _component_instances(plan)
    xmin, ymin, zmin, xmax, ymax, zmax = _assembly_bounds(instances)
    extent_x, extent_y, extent_z = xmax - xmin, ymax - ymin, zmax - zmin
    total_instances = len(instances)

    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(destination, pagesize=(page_w, page_h), pageCompression=0)
    pdf.setTitle(f'{plan["assembly_name"]} - assembly drawing')
    pdf.setAuthor("AI CAD Agent")

    _draw_page_header(
        pdf, page_w, page_h, "ASSEMBLY DRAWING", plan["assembly_name"], entity_label="Assembly"
    )
    _view_label(pdf, 290, page_h - 95, "ASSEMBLED ISOMETRIC VIEW")
    area = (40, 100, 485, 365)
    projection = _isometric_projection(instances, area)
    draw_order = sorted(instances, key=lambda instance: (instance["x"] + instance["y"] + instance["z"]))
    for instance in draw_order:
        iso_plan = instance["iso_plan"]
        base = iso_plan["features"][0]
        holes = next((feature for feature in iso_plan["features"][1:] if feature["type"] == "through_holes"), None)
        slots = next((feature for feature in iso_plan["features"][1:] if feature["type"] == "through_slots"), None)
        pockets = next((feature for feature in iso_plan["features"][1:] if feature["type"] == "rectangular_pockets"), None)
        bosses = next((feature for feature in iso_plan["features"][1:] if feature["type"] == "circular_bosses"), None)
        _draw_isometric(
            pdf,
            float(base["length"]),
            float(base["width"]),
            float(base["thickness"]),
            holes,
            slots,
            pockets,
            area,
            bosses=bosses,
            projection=projection,
            placement=(instance["x"], instance["y"], instance["z"], instance["rotation_z"]),
            face_colors=instance["face_colors"],
        )

    for index, instance in enumerate(instances):
        center = _iso_point(
            instance["x"] + instance["length"] / 2,
            instance["y"] + instance["width"] / 2,
            instance["z"] + instance["height"] / 2,
            projection[0],
            projection[1],
            projection[2],
        )
        offsets = ((27, 22), (-27, 22), (27, -22), (-27, -22))
        _draw_balloon(pdf, instance["item"]["item_number"], center, offsets[index % len(offsets)])

    _draw_bom(pdf, plan, 555, page_h - 103, 245)
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(555, 160, "ASSEMBLY ENVELOPE")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    for index, line in enumerate((
        f"X: {extent_x:g} mm",
        f"Y: {extent_y:g} mm",
        f"Z: {extent_z:g} mm",
        f"Placed components: {total_instances}",
    )):
        pdf.drawString(555, 145 - index * 13, line)
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(555, 82, "Poses are supplied by the user.")
    pdf.drawString(555, 71, "Mates, collisions and fit are not checked.")
    _draw_footer(pdf, page_w, 1)
    pdf.showPage()

    _draw_page_header(
        pdf, page_w, page_h, "ORTHOGRAPHIC ASSEMBLY VIEWS", plan["assembly_name"], entity_label="Assembly"
    )
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(38, page_h - 86, "Third-angle arrangement. Hidden edges are dashed; overall extents are shown in mm.")
    scale = min(2.5, 400 / extent_x, 190 / extent_y, 115 / extent_z)
    top_center_x, top_center_y = page_w / 2, 353
    front_center_x, front_center_y = page_w / 2, 158
    right_center_x, right_center_y = 685, 158
    _view_label(pdf, top_center_x, 473, "TOP VIEW")
    _view_label(pdf, front_center_x, 219, "FRONT VIEW")
    _view_label(pdf, right_center_x, 219, "RIGHT VIEW")

    top_x0 = top_center_x - ((xmin + xmax) / 2) * scale
    top_y0 = top_center_y - ((ymin + ymax) / 2) * scale
    front_x0 = front_center_x - ((xmin + xmax) / 2) * scale
    side_y0 = right_center_x - ((ymin + ymax) / 2) * scale
    z0 = front_center_y - ((zmin + zmax) / 2) * scale

    for instance in instances:
        part_plan = instance["plan"]
        base = part_plan["features"][0]
        holes = next((feature for feature in part_plan["features"][1:] if feature["type"] == "through_holes"), None)
        slots = next((feature for feature in part_plan["features"][1:] if feature["type"] == "through_slots"), None)
        pockets = next((feature for feature in part_plan["features"][1:] if feature["type"] == "rectangular_pockets"), None)
        bosses = next((feature for feature in part_plan["features"][1:] if feature["type"] == "circular_bosses"), None)
        color = instance["color"]
        _draw_top_view(
            pdf,
            top_x0 + instance["x"] * scale,
            top_y0 + instance["y"] * scale,
            float(base["length"]),
            float(base["width"]),
            scale,
            holes,
            slots,
            pockets,
            bosses,
            fill_part=False,
            stroke_color=color,
        )

        x_hidden, x_ranges, x_rectangles = _elevation_details(part_plan, "x")
        _draw_elevation(
            pdf,
            front_x0 + (instance["x"] + instance["length"] / 2) * scale,
            z0 + (instance["z"] + instance["thickness"] / 2) * scale,
            instance["length"],
            instance["thickness"],
            scale,
            x_hidden,
            hidden_ranges=x_ranges,
            hidden_rectangles=x_rectangles,
            visible_rectangles=_boss_elevation_rectangles(part_plan, "x"),
            stroke_color=color,
        )

        y_hidden, y_ranges, y_rectangles = _elevation_details(part_plan, "y")
        _draw_elevation(
            pdf,
            side_y0 + (instance["y"] + instance["width"] / 2) * scale,
            z0 + (instance["z"] + instance["thickness"] / 2) * scale,
            instance["width"],
            instance["thickness"],
            scale,
            y_hidden,
            hidden_ranges=y_ranges,
            hidden_rectangles=y_rectangles,
            visible_rectangles=_boss_elevation_rectangles(part_plan, "y"),
            stroke_color=color,
        )

    pdf.setFillColor(INK)
    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(top_center_x, 244, f"Overall X = {extent_x:g} mm    Y = {extent_y:g} mm")
    pdf.drawCentredString(front_center_x, 82, f"Overall X = {extent_x:g} mm    Z = {extent_z:g} mm")
    pdf.drawCentredString(right_center_x, 82, f"Overall Y = {extent_y:g} mm    Z = {extent_z:g} mm")
    pdf.setStrokeColor(RULE)
    pdf.line(38, 65, page_w - 38, 65)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Oblique", 7)
    pdf.drawString(38, 53, "Assembly positions are user-defined. No interference, mating or tolerance analysis is included.")
    _draw_footer(pdf, page_w, 2)
    pdf.save()
