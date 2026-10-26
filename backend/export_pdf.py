from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


def export_dimension_pdf(plan: dict, destination: str) -> None:
    """Create a printable dimension sheet for the supported plate-and-holes MVP."""
    feature = plan["features"][0]
    length = float(feature["length"])
    width = float(feature["width"])
    thickness = float(feature["thickness"])
    holes = next((item for item in plan["features"][1:] if item["type"] == "through_holes"), None)

    page_w, page_h = landscape(A4)
    pdf = canvas.Canvas(destination, pagesize=(page_w, page_h))
    pdf.setTitle(f'{plan["part_name"]} - dimension drawing')
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(38, page_h - 42, "CAD DIMENSION SHEET")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(38, page_h - 59, f'Part: {plan["part_name"]}    Units: mm    Generated from validated CAD plan')
    pdf.line(38, page_h - 70, page_w - 38, page_h - 70)

    area_x, area_y = 52, 95
    max_w, max_h = page_w * 0.48, page_h - 210
    scale = min(max_w / length, max_h / width)
    draw_w, draw_h = length * scale, width * scale
    x0, y0 = area_x + 28, area_y + 35
    pdf.setLineWidth(1.4)
    pdf.rect(x0, y0, draw_w, draw_h)
    pdf.setLineWidth(0.8)

    if holes:
        diameter = float(holes["diameter"])
        for item in holes["positions"]:
            cx, cy = x0 + float(item["x"]) * scale, y0 + float(item["y"]) * scale
            pdf.circle(cx, cy, diameter * scale / 2, stroke=1, fill=0)
            pdf.line(cx - 4, cy, cx + 4, cy)
            pdf.line(cx, cy - 4, cx, cy + 4)

    dim_y = y0 - 20
    pdf.line(x0, dim_y, x0 + draw_w, dim_y)
    pdf.line(x0, dim_y - 5, x0, dim_y + 5)
    pdf.line(x0 + draw_w, dim_y - 5, x0 + draw_w, dim_y + 5)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(x0 + draw_w / 2, dim_y - 14, f"L = {length:g} mm")

    dim_x = x0 + draw_w + 22
    pdf.line(dim_x, y0, dim_x, y0 + draw_h)
    pdf.line(dim_x - 5, y0, dim_x + 5, y0)
    pdf.line(dim_x - 5, y0 + draw_h, dim_x + 5, y0 + draw_h)
    pdf.saveState()
    pdf.translate(dim_x + 12, y0 + draw_h / 2)
    pdf.rotate(90)
    pdf.drawCentredString(0, 0, f"W = {width:g} mm")
    pdf.restoreState()

    info_x = min(x0 + draw_w + 62, page_w - 210)
    info_y = page_h - 115
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(info_x, info_y, "SPECIFICATIONS")
    pdf.setFont("Helvetica", 10)
    lines = [
        f"Length: {length:g} mm",
        f"Width: {width:g} mm",
        f"Thickness: {thickness:g} mm",
    ]
    if holes:
        lines += [
            f"Through holes: {len(holes['positions'])}",
            f"Hole diameter: {float(holes['diameter']):g} mm",
            "Hole centers (X, Y):",
        ]
        lines += [f"  ({float(p['x']):g}, {float(p['y']):g})" for p in holes["positions"]]
    lines += ["", "Illustrative dimension sheet.", "Verify dimensions and fit before manufacture."]
    y = info_y - 20
    for line in lines:
        pdf.drawString(info_x, y, line)
        y -= 16
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(38, 28, "Generated automatically. This is not a certified manufacturing drawing.")
    pdf.save()
