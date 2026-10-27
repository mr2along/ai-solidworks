"""Illustrative 3D and orthographic PDF export for supported plate plans."""

from __future__ import annotations

import math
from collections.abc import Iterable

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


INK = HexColor("#233648")
MUTED = HexColor("#647789")
TOP_FACE = HexColor("#E7EFF6")
FRONT_FACE = HexColor("#B8C9D7")
RIGHT_FACE = HexColor("#8FA6B8")
RULE = HexColor("#CBD5DE")
HIDDEN = HexColor("#75899A")


def _polygon(pdf: canvas.Canvas, points: Iterable[tuple[float, float]], fill: Color) -> None:
    points = list(points)
    path = pdf.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.close()
    pdf.setFillColor(fill)
    pdf.setStrokeColor(INK)
    pdf.drawPath(path, stroke=1, fill=1)


def _draw_page_header(pdf: canvas.Canvas, page_w: float, page_h: float, title: str, part_name: str) -> None:
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(38, page_h - 40, title)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(38, page_h - 57, f"Part: {part_name}    Units: mm    Generated from validated CAD plan")
    pdf.setStrokeColor(RULE)
    pdf.setLineWidth(0.8)
    pdf.line(38, page_h - 70, page_w - 38, page_h - 70)


def _draw_footer(pdf: canvas.Canvas, page_w: float, page_number: int) -> None:
    pdf.setStrokeColor(RULE)
    pdf.line(38, 43, page_w - 38, 43)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(
        38,
        29,
        "Illustrative drawing only. Not a certified manufacturing drawing; "
        "verify dimensions and fit before manufacture.",
    )
    pdf.drawRightString(page_w - 38, 29, f"Page {page_number} of 2")


def _dimension_horizontal(
    pdf: canvas.Canvas,
    x1: float,
    x2: float,
    object_y: float,
    dimension_y: float,
    label: str,
) -> None:
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setFillColor(INK)
    pdf.setLineWidth(0.65)
    pdf.line(x1, object_y, x1, dimension_y - 4)
    pdf.line(x2, object_y, x2, dimension_y - 4)
    pdf.line(x1, dimension_y, x2, dimension_y)
    _arrow(pdf, x1, dimension_y, 1)
    _arrow(pdf, x2, dimension_y, -1)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawCentredString((x1 + x2) / 2, dimension_y - 13, label)
    pdf.restoreState()


def _dimension_vertical(
    pdf: canvas.Canvas,
    x: float,
    y1: float,
    y2: float,
    dimension_x: float,
    label: str,
) -> None:
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setFillColor(INK)
    pdf.setLineWidth(0.65)
    pdf.line(x, y1, dimension_x + 4, y1)
    pdf.line(x, y2, dimension_x + 4, y2)
    pdf.line(dimension_x, y1, dimension_x, y2)
    _arrow_vertical(pdf, dimension_x, y1, 1)
    _arrow_vertical(pdf, dimension_x, y2, -1)
    pdf.translate(dimension_x + 11, (y1 + y2) / 2)
    pdf.rotate(90)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawCentredString(0, 0, label)
    pdf.restoreState()


def _arrow(pdf: canvas.Canvas, x: float, y: float, direction: int) -> None:
    pdf.line(x, y, x + direction * 4, y + 2)
    pdf.line(x, y, x + direction * 4, y - 2)


def _arrow_vertical(pdf: canvas.Canvas, x: float, y: float, direction: int) -> None:
    pdf.line(x, y, x - 2, y + direction * 4)
    pdf.line(x, y, x + 2, y + direction * 4)


def _draw_top_view(
    pdf: canvas.Canvas,
    x0: float,
    y0: float,
    length: float,
    width: float,
    scale: float,
    holes: dict | None,
    slots: dict | None = None,
    *,
    mirror_x: bool = False,
) -> None:
    draw_w, draw_h = length * scale, width * scale
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.setLineWidth(1.2)
    pdf.rect(x0, y0, draw_w, draw_h, stroke=1, fill=1)
    if holes:
        diameter = float(holes["diameter"])
        radius = diameter * scale / 2
        pdf.setLineWidth(0.9)
        for hole in holes["positions"]:
            cx_mm = length - float(hole["x"]) if mirror_x else float(hole["x"])
            cx = x0 + cx_mm * scale
            cy = y0 + float(hole["y"]) * scale
            pdf.circle(cx, cy, radius, stroke=1, fill=0)
            pdf.line(cx - 3, cy, cx + 3, cy)
            pdf.line(cx, cy - 3, cx, cy + 3)
    if slots:
        for slot_position in slots["positions"]:
            center_x = float(slot_position["x"])
            center_y = float(slot_position["y"])
            if mirror_x:
                center_x = length - center_x
            _draw_capsule(
                pdf,
                slots,
                lambda x, y: (x0 + (center_x + x) * scale, y0 + (center_y + y) * scale),
                fill=True,
            )
    pdf.restoreState()


def _draw_capsule(pdf: canvas.Canvas, slot: dict, project, *, fill: bool) -> None:
    """Draw a rounded-end slot from its centerline length and width."""
    radius = float(slot["slot_width"]) / 2
    half_centerline = (float(slot["slot_length"]) - float(slot["slot_width"])) / 2

    def point(along: float, across: float) -> tuple[float, float]:
        if slot["orientation"] == "y":
            along, across = across, along
        return project(along, across)

    k = 0.5522847498
    path = pdf.beginPath()
    path.moveTo(*point(-half_centerline, -radius))
    path.lineTo(*point(half_centerline, -radius))
    path.curveTo(
        *point(half_centerline + k * radius, -radius),
        *point(half_centerline + radius, -k * radius),
        *point(half_centerline + radius, 0),
    )
    path.curveTo(
        *point(half_centerline + radius, k * radius),
        *point(half_centerline + k * radius, radius),
        *point(half_centerline, radius),
    )
    path.lineTo(*point(-half_centerline, radius))
    path.curveTo(
        *point(-half_centerline - k * radius, radius),
        *point(-half_centerline - radius, k * radius),
        *point(-half_centerline - radius, 0),
    )
    path.curveTo(
        *point(-half_centerline - radius, -k * radius),
        *point(-half_centerline - k * radius, -radius),
        *point(-half_centerline, -radius),
    )
    path.close()
    pdf.drawPath(path, stroke=1, fill=int(fill))


def _iso_point(
    x: float,
    y: float,
    z: float,
    scale: float,
    origin_x: float,
    origin_y: float,
) -> tuple[float, float]:
    cosine = math.cos(math.radians(30))
    return (
        origin_x + (x - y) * cosine * scale,
        origin_y + (x + y) * 0.5 * scale + z * scale,
    )


def _ellipse_path(
    pdf: canvas.Canvas,
    center: tuple[float, float],
    axis_x: tuple[float, float],
    axis_y: tuple[float, float],
    *,
    fill: bool,
) -> None:
    """Draw a projected circle using two 2D basis vectors."""
    k = 0.5522847498
    cx, cy = center
    ux, uy = axis_x
    vx, vy = axis_y
    path = pdf.beginPath()
    path.moveTo(cx + ux, cy + uy)
    path.curveTo(
        cx + ux + k * vx, cy + uy + k * vy,
        cx + vx + k * ux, cy + vy + k * uy,
        cx + vx, cy + vy,
    )
    path.curveTo(
        cx + vx - k * ux, cy + vy - k * uy,
        cx - ux + k * vx, cy - uy + k * vy,
        cx - ux, cy - uy,
    )
    path.curveTo(
        cx - ux - k * vx, cy - uy - k * vy,
        cx - vx - k * ux, cy - vy - k * uy,
        cx - vx, cy - vy,
    )
    path.curveTo(
        cx - vx + k * ux, cy - vy + k * uy,
        cx + ux - k * vx, cy + uy - k * vy,
        cx + ux, cy + uy,
    )
    path.close()
    pdf.drawPath(path, stroke=1, fill=int(fill))


def _draw_isometric(
    pdf: canvas.Canvas,
    length: float,
    width: float,
    thickness: float,
    holes: dict | None,
    slots: dict | None,
    area: tuple[float, float, float, float],
) -> None:
    area_x, area_y, area_w, area_h = area
    cosine = math.cos(math.radians(30))
    projected_w = cosine * (length + width)
    projected_h = 0.5 * (length + width) + thickness
    scale = min(area_w / projected_w, area_h / projected_h)
    projected_center_x = area_x + area_w / 2
    projected_center_y = area_y + area_h / 2
    min_x, max_x = -cosine * width, cosine * length
    min_y, max_y = 0.0, 0.5 * (length + width) + thickness
    origin_x = projected_center_x - (min_x + max_x) * scale / 2
    origin_y = projected_center_y - (min_y + max_y) * scale / 2

    def p(x: float, y: float, z: float) -> tuple[float, float]:
        return _iso_point(x, y, z, scale, origin_x, origin_y)

    # Show the two visible side faces and then the top face.
    _polygon(
        pdf,
        [p(0, 0, 0), p(length, 0, 0), p(length, 0, thickness), p(0, 0, thickness)],
        FRONT_FACE,
    )
    _polygon(
        pdf,
        [p(length, 0, 0), p(length, width, 0), p(length, width, thickness), p(length, 0, thickness)],
        RIGHT_FACE,
    )
    _polygon(
        pdf,
        [p(0, 0, thickness), p(length, 0, thickness), p(length, width, thickness), p(0, width, thickness)],
        TOP_FACE,
    )

    if holes:
        radius = float(holes["diameter"]) / 2
        cosine = math.cos(math.radians(30))
        for hole in holes["positions"]:
            hx, hy = float(hole["x"]), float(hole["y"])
            center_top = p(hx, hy, thickness)
            center_bottom = p(hx, hy, 0)
            axis_x = (radius * cosine * scale, radius * 0.5 * scale)
            axis_y = (-radius * cosine * scale, radius * 0.5 * scale)
            pdf.saveState()
            pdf.setStrokeColor(INK)
            pdf.setLineWidth(0.75)
            pdf.setFillColor(HexColor("#FFFFFF"))
            _ellipse_path(pdf, center_bottom, axis_x, axis_y, fill=True)
            _ellipse_path(pdf, center_top, axis_x, axis_y, fill=True)
            for sign in (-1, 1):
                x_offset, y_offset = sign * axis_x[0], sign * axis_x[1]
                pdf.line(
                    center_top[0] + x_offset,
                    center_top[1] + y_offset,
                    center_bottom[0] + x_offset,
                    center_bottom[1] + y_offset,
                )
            pdf.restoreState()

    if slots:
        for slot_position in slots["positions"]:
            center_x, center_y = float(slot_position["x"]), float(slot_position["y"])
            project_top = lambda x, y: p(center_x + x, center_y + y, thickness)
            project_bottom = lambda x, y: p(center_x + x, center_y + y, 0)
            pdf.saveState()
            pdf.setStrokeColor(INK)
            pdf.setLineWidth(0.8)
            pdf.setFillColor(HexColor("#FFFFFF"))
            _draw_capsule(pdf, slots, project_top, fill=True)
            pdf.setStrokeColor(HIDDEN)
            pdf.setDash(2, 2)
            _draw_capsule(pdf, slots, project_bottom, fill=False)
            pdf.restoreState()

    # Reassert the visible top and side edges over the hole graphics.
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.15)
    top = [p(0, 0, thickness), p(length, 0, thickness), p(length, width, thickness), p(0, width, thickness)]
    for start, end in zip(top, top[1:] + top[:1]):
        pdf.line(*start, *end)
    side_edges = (
        (p(0, 0, 0), p(length, 0, 0)),
        (p(length, 0, 0), p(length, width, 0)),
        (p(0, 0, 0), p(0, 0, thickness)),
        (p(length, 0, 0), p(length, 0, thickness)),
        (p(length, width, 0), p(length, width, thickness)),
    )
    for start, end in side_edges:
        pdf.line(*start, *end)
    pdf.restoreState()


def _unique(values: Iterable[float]) -> list[float]:
    return sorted(set(round(value, 6) for value in values))


def _draw_elevation(
    pdf: canvas.Canvas,
    center_x: float,
    center_y: float,
    horizontal_length: float,
    thickness: float,
    scale: float,
    hidden_positions: Iterable[float],
    *,
    mirror: bool = False,
    hidden_ranges: Iterable[tuple[float, float]] = (),
) -> None:
    width_pt, height_pt = horizontal_length * scale, thickness * scale
    x0, y0 = center_x - width_pt / 2, center_y - height_pt / 2
    pdf.saveState()
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.1)
    pdf.rect(x0, y0, width_pt, height_pt, stroke=1, fill=0)
    pdf.setStrokeColor(HIDDEN)
    pdf.setLineWidth(0.7)
    pdf.setDash(3, 2)
    for value in hidden_positions:
        projected = horizontal_length - value if mirror else value
        pdf.line(x0 + projected * scale, y0, x0 + projected * scale, y0 + height_pt)
    for start, end in hidden_ranges:
        if mirror:
            start, end = horizontal_length - end, horizontal_length - start
        left, right = x0 + start * scale, x0 + end * scale
        pdf.rect(left, y0, right - left, height_pt, stroke=1, fill=0)
    pdf.setDash()
    pdf.restoreState()


def _view_label(pdf: canvas.Canvas, center_x: float, y: float, title: str, subtitle: str | None = None) -> None:
    pdf.saveState()
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(center_x, y, title)
    if subtitle:
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 7)
        pdf.drawCentredString(center_x, y - 10, subtitle)
    pdf.restoreState()


def export_dimension_pdf(plan: dict, destination: str) -> None:
    """Export a two-page illustrative drawing with an isometric and six face views."""
    base = plan["features"][0]
    length = float(base["length"])
    width = float(base["width"])
    thickness = float(base["thickness"])
    holes = next((item for item in plan["features"][1:] if item["type"] == "through_holes"), None)
    slots = next((item for item in plan["features"][1:] if item["type"] == "through_slots"), None)

    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(destination, pagesize=(page_w, page_h), pageCompression=0)
    pdf.setTitle(f'{plan["part_name"]} - 3D and orthographic views')
    pdf.setAuthor("AI CAD Agent")

    _draw_page_header(pdf, page_w, page_h, "3D MODEL AND DIMENSIONED TOP VIEW", plan["part_name"])
    _view_label(pdf, 235, page_h - 94, "ISOMETRIC VIEW")
    _draw_isometric(pdf, length, width, thickness, holes, slots, (55, 125, 365, 325))

    _view_label(
        pdf,
        630,
        page_h - 94,
        "TOP VIEW",
        "Hole positions from bottom-left datum",
    )
    top_scale = min(292 / length, 170 / width)
    top_x = 478
    top_y = 308
    _draw_top_view(pdf, top_x, top_y, length, width, top_scale, holes, slots)
    _dimension_horizontal(pdf, top_x, top_x + length * top_scale, top_y, top_y - 22, f"L = {length:g} mm")
    _dimension_vertical(
        pdf,
        top_x + length * top_scale,
        top_y,
        top_y + width * top_scale,
        top_x + length * top_scale + 25,
        f"W = {width:g} mm",
    )

    specs_x, specs_y = 478, 252
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(specs_x, specs_y, "MODEL DATA")
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    lines = [f"Length: {length:g} mm", f"Width: {width:g} mm", f"Thickness: {thickness:g} mm"]
    if holes:
        lines.append(f"Through holes: {len(holes['positions'])} x dia. {float(holes['diameter']):g} mm")
        for index, hole in enumerate(holes["positions"][:6], start=1):
            lines.append(f"  H{index}: X {float(hole['x']):g}, Y {float(hole['y']):g} mm")
        if len(holes["positions"]) > 6:
            lines.append(f"  Remaining {len(holes['positions']) - 6} centers are shown in the top view.")
    else:
        lines.append("No holes")
    if slots:
        lines.append(
            f"Through slots: {len(slots['positions'])} x {float(slots['slot_length']):g} x "
            f"{float(slots['slot_width']):g} mm; axis {slots['orientation'].upper()}"
        )
        for index, position in enumerate(slots["positions"][:6], start=1):
            lines.append(f"  S{index} center: X {float(position['x']):g}, Y {float(position['y']):g} mm")
    else:
        lines.append("No through slots")
    for index, line in enumerate(lines, start=1):
        pdf.drawString(specs_x, specs_y - index * 12, line)
    pdf.setFont("Helvetica-Oblique", 7.5)
    pdf.drawString(specs_x, 75, "All dimensions are in mm. Do not scale from this sheet.")
    _draw_footer(pdf, page_w, 1)
    pdf.showPage()

    _draw_page_header(pdf, page_w, page_h, "ORTHOGRAPHIC PROJECTIONS - SIX PRINCIPAL VIEWS", plan["part_name"])
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        38,
        page_h - 86,
        "One consistent view scale. Dashed edges indicate through-cut boundaries hidden in edge views.",
    )

    holes_list = holes["positions"] if holes else []
    radius = float(holes["diameter"]) / 2 if holes else 0
    x_positions = _unique(float(hole["x"]) for hole in holes_list)
    y_positions = _unique(float(hole["y"]) for hole in holes_list)
    x_edges = [value for position in x_positions for value in (position - radius, position + radius)]
    y_edges = [value for position in y_positions for value in (position - radius, position + radius)]
    x_slot_ranges = []
    y_slot_ranges = []
    if slots:
        half_slot = float(slots["slot_length"]) / 2
        if slots["orientation"] == "x":
            x_slot_ranges = [
                (float(position["x"]) - half_slot, float(position["x"]) + half_slot)
                for position in slots["positions"]
            ]
        else:
            y_slot_ranges = [
                (float(position["y"]) - half_slot, float(position["y"]) + half_slot)
                for position in slots["positions"]
            ]

    scale = min(2.1, (page_w - 76 - 3 * 22) / (2 * (length + width)))
    gap = 22
    # Third-angle style row: left, front, right, and rear; top and bottom align with front.
    widths = [width, length, width, length]
    total_width = sum(widths) * scale + 3 * gap
    left_edge = (page_w - total_width) / 2
    centers: list[float] = []
    cursor = left_edge
    for view_width in widths:
        centers.append(cursor + view_width * scale / 2)
        cursor += view_width * scale + gap
    left_center, front_center, right_center, rear_center = centers
    front_y = 282
    top_y_center = front_y + (thickness / 2 + 20 + width / 2) * scale
    bottom_y_center = front_y - (thickness / 2 + 20 + width / 2) * scale

    _view_label(pdf, left_center, 300, "LEFT VIEW", "looking toward +X")
    _draw_elevation(pdf, left_center, front_y, width, thickness, scale, y_edges, mirror=True,
                    hidden_ranges=y_slot_ranges)
    _view_label(pdf, front_center, top_y_center + width * scale / 2 + 17, "TOP VIEW")
    _draw_top_view(pdf, front_center - length * scale / 2, top_y_center - width * scale / 2,
                   length, width, scale, holes, slots)
    _view_label(pdf, right_center, 300, "RIGHT VIEW", "looking toward -X")
    _draw_elevation(pdf, right_center, front_y, width, thickness, scale, y_edges,
                    hidden_ranges=y_slot_ranges)
    _view_label(pdf, rear_center, 300, "REAR VIEW", "looking toward -Y")
    _draw_elevation(pdf, rear_center, front_y, length, thickness, scale, x_edges, mirror=True,
                    hidden_ranges=x_slot_ranges)

    _view_label(pdf, front_center, 300, "FRONT VIEW", "looking toward +Y")
    _draw_elevation(pdf, front_center, front_y, length, thickness, scale, x_edges,
                    hidden_ranges=x_slot_ranges)
    _view_label(pdf, front_center, bottom_y_center - width * scale / 2 - 20, "BOTTOM VIEW", "looking toward +Z")
    _draw_top_view(pdf, front_center - length * scale / 2, bottom_y_center - width * scale / 2,
                   length, width, scale, holes, slots, mirror_x=True)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(page_w - 38, 55, f"Projection views at consistent scale; plate thickness = {thickness:g} mm")
    _draw_footer(pdf, page_w, 2)
    pdf.save()
