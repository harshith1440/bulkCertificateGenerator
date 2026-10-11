
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parents[2]
CERTIFICATE_DIR = BASE_DIR / "storage" / "certificates"


def generate_certificate(
    name: str,
    certificate_title: str,
    organization: str,
    issue_date,
    job_id: str,
    recipient_id: int,
) -> str:
    CERTIFICATE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{job_id}_{recipient_id}.pdf"
    output_path = CERTIFICATE_DIR / filename

    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(output_path), pagesize=landscape(A4))

    pdf.setTitle(f"Certificate - {name}")

    # Decorative certificate border.
    pdf.setStrokeColor(colors.HexColor("#C9A227"))
    pdf.setLineWidth(3)
    pdf.rect(30, 30, page_width - 60, page_height - 60)

    pdf.setStrokeColor(colors.HexColor("#34495E"))
    pdf.setLineWidth(1)
    pdf.rect(40, 40, page_width - 80, page_height - 80)

    # Certificate heading.
    pdf.setFillColor(colors.HexColor("#243447"))
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 110,
        "CERTIFICATE OF COMPLETION",
    )

    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 165,
        "This certificate is proudly presented to",
    )

    # Wrap long recipient names instead of drawing beyond the page.
    safe_name = name.encode("cp1252", errors="replace").decode("cp1252")
    name_lines = simpleSplit(
        safe_name,
        "Helvetica-Bold",
        28,
        page_width - 140,
    )

    pdf.setFillColor(colors.HexColor("#B8860B"))
    pdf.setFont("Helvetica-Bold", 28)

    y = page_height - 220

    for line in name_lines:
        pdf.drawCentredString(page_width / 2, y, line)
        y -= 34

    # Certificate/course information.
    y -= 10
    pdf.setFillColor(colors.HexColor("#243447"))
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(
        page_width / 2,
        y,
        "for successfully completing",
    )

    y -= 40

    safe_title = certificate_title.encode(
        "cp1252", errors="replace"
    ).decode("cp1252")

    title_lines = simpleSplit(
        safe_title,
        "Helvetica-Bold",
        19,
        page_width - 140,
    )

    pdf.setFont("Helvetica-Bold", 19)

    for line in title_lines:
        pdf.drawCentredString(page_width / 2, y, line)
        y -= 25

    # Issuing organization and date.
    y -= 14

    safe_organization = organization.encode(
        "cp1252", errors="replace"
    ).decode("cp1252")

    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(
        page_width / 2,
        y,
        f"Issued by: {safe_organization}",
    )

    y -= 30

    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(
        page_width / 2,
        y,
        f"Issue Date: {issue_date.isoformat()}",
    )

    pdf.showPage()
    pdf.save()

    # Store a project-relative path in the database.
    return str(output_path.relative_to(BASE_DIR))
