from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


POWERPAY_GREEN = colors.HexColor("#08783E")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#475569")
PALE_GREEN = colors.HexColor("#ECFDF5")


WARRANTY_TERMS = [
    "This product has warranty coverage for one year from the purchase date.",
    "The warranty covers manufacturing defects when the product is used according to the supplied user manual.",
    "Damage caused by power surges or voltage dips is not covered.",
    "Unauthorized repairs, alterations, modifications, or tampering with the product will void the warranty.",
    "Cosmetic damage and normal wear and tear are not covered.",
    "Repairs outside the warranty period may attract charges.",
    "The customer is responsible for collection and delivery transport charges.",
    "Where authorized personnel confirm a material or workmanship defect during the warranty period, defective parts will be repaired or replaced at no parts cost. This is a repair warranty, not a product replacement warranty.",
    "A warranty claim must be accompanied by this certificate and proof of purchase.",
    "This warranty is subject to the laws of Kenya.",
]

CARBON_AND_DATA_CONSENT = (
    "The customer releases to PowerPay/the Company the rights to greenhouse-gas reductions "
    "and carbon credits produced through use of this energy product, and agrees not to sell, "
    "transfer, or otherwise use those reductions or credits. The customer also consents to the "
    "collection, processing, and storage of the personal information supplied for the warranty "
    "and related service purposes in accordance with Kenya's Data Protection Act, 2019."
)


def _safe(value, fallback="Not provided"):
    if value in (None, "", [], ()):
        return fallback
    return escape(str(value))


def _display(order, field_name):
    display = getattr(order, f"get_{field_name}_display", None)
    return display() if callable(display) else getattr(order, field_name, None)


def _field_image(field, width, height):
    if not field:
        return None
    try:
        field.open("rb")
        content = BytesIO(field.read())
        field.close()
        image = Image(content, width=width, height=height)
        image._restrictSize(width, height)
        return image
    except (OSError, ValueError):
        return None


def _powerpay_logo():
    path = finders.find("images/pplogo.png") or finders.find("images/pplogo.webp")
    if not path:
        return Paragraph("<b>POWERPAY</b>", ParagraphStyle("LogoText", textColor=POWERPAY_GREEN, fontSize=18))
    image = Image(path, width=45 * mm, height=12 * mm)
    image._restrictSize(45 * mm, 12 * mm)
    return image


def _brand_header(sale, styles):
    vendor = sale.product.vendor
    vendor_logo = _field_image(vendor.logo, 45 * mm, 18 * mm)
    if vendor_logo is None:
        vendor_logo = Paragraph(f"<b>{_safe(vendor.shop_name or str(vendor))}</b>", styles["VendorLogo"])
    table = Table(
        [[vendor_logo, _powerpay_logo()]],
        colWidths=[82 * mm, 82 * mm],
        rowHeights=[20 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("LINEBELOW", (0, 0), (-1, -1), 1, POWERPAY_GREEN),
    ]))
    return table


def _details_table(rows, styles):
    data = [[Paragraph(f"<b>{escape(label)}</b>", styles["Detail"]), Paragraph(_safe(value), styles["Detail"])] for label, value in rows]
    table = Table(data, colWidths=[55 * mm, 109 * mm], repeatRows=0)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), PALE_GREEN),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def build_warranty_pdf(sale):
    order = sale.order
    vendor = sale.product.vendor
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"Warranty certificate - {sale.product.name}",
        author="PowerPay Shop",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=25, leading=30, textColor=INK, spaceAfter=7 * mm))
    styles.add(ParagraphStyle("Section", parent=styles["Heading2"], fontSize=15, leading=19, textColor=POWERPAY_GREEN, spaceBefore=4 * mm, spaceAfter=3 * mm))
    styles.add(ParagraphStyle("BodyClean", parent=styles["BodyText"], fontSize=10, leading=15, textColor=INK))
    styles.add(ParagraphStyle("Term", parent=styles["BodyText"], fontSize=10, leading=14, leftIndent=7 * mm, firstLineIndent=-5 * mm, spaceAfter=3 * mm, textColor=INK))
    styles.add(ParagraphStyle("Detail", parent=styles["BodyText"], fontSize=9, leading=12, textColor=INK))
    styles.add(ParagraphStyle("VendorLogo", parent=styles["BodyText"], fontSize=15, leading=18, textColor=INK))

    purchase_date = timezone.localtime(order.submitted_at).strftime("%d %B %Y")
    dealer_address = vendor.address or vendor.shop_name or str(vendor)
    certificate_number = f"PP-W-{sale.pk:06d}"

    story = [
        _brand_header(sale, styles),
        Spacer(1, 7 * mm),
        Paragraph("WARRANTY CERTIFICATE", styles["TitleCenter"]),
        Paragraph(f"Certificate <b>{certificate_number}</b> &nbsp; | &nbsp; Status: <b>PAID AND ACTIVE</b>", styles["BodyClean"]),
        Spacer(1, 5 * mm),
    ]
    story.extend(Paragraph(f"- &nbsp;{escape(term)}", styles["Term"]) for term in WARRANTY_TERMS)

    story.extend([
        PageBreak(),
        _brand_header(sale, styles),
        Spacer(1, 5 * mm),
        Paragraph("Warranty information", styles["TitleCenter"]),
        _details_table([
            ("Certificate number", certificate_number),
            ("Product name", sale.product.name),
            ("Quantity", sale.quantity),
            ("Product model", sale.product.name),
            ("Serial / payment reference", order.mpesa_receipt or order.payment_ref),
            ("Owner's name", f"{order.first_name} {order.last_name}"),
            ("Mobile number", order.phone),
            ("Email", order.email),
            ("Street / address", order.address_detail),
            ("Village", order.village),
            ("Location", order.city),
            ("County / State", order.county),
            ("Country", order.country),
            ("Purchase date", purchase_date),
            ("Buying method", _display(order, "buying_method")),
            ("Sales person", "Online Shop"),
            ("Dealer name", vendor.shop_name or str(vendor)),
            ("Sales person / dealer address", dealer_address),
        ], styles),
        Spacer(1, 6 * mm),
        Paragraph("Owner's electronic signature", styles["Section"]),
    ])
    signature = _field_image(order.warranty_signature, 55 * mm, 18 * mm)
    story.append(signature or Paragraph("Electronic signature recorded", styles["BodyClean"]))
    story.append(Paragraph(f"Consent recorded: {_safe(order.warranty_accepted_at)}", styles["Detail"]))

    story.extend([
        PageBreak(),
        _brand_header(sale, styles),
        Spacer(1, 5 * mm),
        Paragraph("Household and energy information", styles["TitleCenter"]),
        _details_table([
            ("Gender", _display(order, "gender")),
            ("Age", order.age),
            ("National ID", order.national_id),
            ("Education", _display(order, "education")),
            ("Marital status", _display(order, "marital_status")),
            ("Employment", _display(order, "employment")),
            ("Economic activity", order.economic_activity),
            ("Monthly income", _display(order, "monthly_income")),
            ("Other loans", _display(order, "other_loans")),
            ("Home or business", _display(order, "home_or_business")),
            ("Cooking fuel", _display(order, "cooking_fuel")),
            ("Cooking stove", _display(order, "stove_type")),
            ("Will use appliance for cooking", _display(order, "is_cook_user")),
            ("Monthly cooking cost", order.monthly_cooking_cost),
            ("Grid connection", _display(order, "grid_connection")),
            ("Utility provider", _display(order, "utility_provider")),
            ("Monthly electricity cost", order.monthly_electricity_cost),
        ], styles),
        Spacer(1, 6 * mm),
        KeepTogether([
            Paragraph("Carbon title and data-processing consent", styles["Section"]),
            Paragraph(CARBON_AND_DATA_CONSENT, styles["BodyClean"]),
        ]),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(20 * mm, 12 * mm, 190 * mm, 12 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(20 * mm, 7 * mm, certificate_number)
        canvas.drawRightString(190 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
