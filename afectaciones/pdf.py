"""Generación del reporte de afectaciones en PDF (RF-17, RF-18).

Este módulo no depende de Django: recibe datos ya preparados (textos y números)
y devuelve los bytes del PDF. Así se puede probar por separado y reutilizar.
"""
import io
from pathlib import Path
from decimal import Decimal
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERDE = colors.HexColor("#2f6f3e")
VERDE_CLARO = colors.HexColor("#eaf4ec")
BORDE = colors.HexColor("#d5e0d8")
GRIS = colors.HexColor("#5b6b60")

NOTA_ESTIMACION = (
    "Las pérdidas son estimaciones registradas por el productor, "
    "no una valoración técnica oficial."
)


def formato_cop(valor):
    """1500000 -> '$1.500.000' (separador de miles colombiano)."""
    valor = Decimal(valor or 0)
    return "$" + f"{valor:,.0f}".replace(",", ".")


def formato_ha(valor):
    """31.0200000000 -> '31,02' (dos decimales, coma decimal, punto de miles)."""
    valor = Decimal(valor or 0).quantize(Decimal("0.01"))
    return f"{valor:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _t(valor):
    """Texto seguro para un Paragraph (escapa &, < y >); vacío se muestra como '-'."""
    if valor is None or str(valor).strip() == "":
        return "-"
    return escape(str(valor))


LOGO_MARCA = Path(__file__).resolve().parent.parent / "static" / "img" / "logo-marca.png"


def _marca_de_agua(canvas):
    """Logo muy claro y centrado detrás del contenido; si falta el archivo, se omite."""
    if not LOGO_MARCA.exists():
        return
    ancho = 11 * cm
    alto = ancho * 764 / 900  # proporción del logo
    canvas.saveState()
    canvas.setFillAlpha(0.07)
    canvas.drawImage(
        str(LOGO_MARCA), (A4[0] - ancho) / 2, (A4[1] - alto) / 2, width=ancho, height=alto,
        mask="auto", preserveAspectRatio=True,
    )
    canvas.restoreState()


LOGO = LOGO_MARCA.with_name("logo.png")


def _encabezado_marca(canvas):
    """Logo y nombre de AgroSismo en la parte superior de cada página."""
    izquierda = 2 * cm
    base = A4[1] - 1.55 * cm
    canvas.saveState()
    ancho = 1.5 * cm
    alto = ancho * 764 / 900
    if LOGO.exists():
        canvas.drawImage(str(LOGO), izquierda, base - 0.15 * cm, width=ancho, height=alto,
                         mask="auto", preserveAspectRatio=True)
    canvas.setFillColor(VERDE)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(izquierda + ancho + 0.25 * cm, base + 0.38 * cm, "AgroSismo")
    canvas.setFillColor(GRIS)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 2 * cm, base + 0.4 * cm, "Gestión y evaluación de afectaciones sísmicas")
    canvas.setStrokeColor(BORDE)
    canvas.setLineWidth(0.6)
    canvas.line(izquierda, base - 0.3 * cm, A4[0] - 2 * cm, base - 0.3 * cm)
    canvas.restoreState()


def _pie(canvas, doc):
    _marca_de_agua(canvas)
    _encabezado_marca(canvas)
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRIS)
    canvas.drawString(2 * cm, 1.2 * cm, "AgroSismo - " + NOTA_ESTIMACION)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def generar_pdf(productor, generado, filtros, resumen, severidades, unidades, filas, finca=""):
    """Devuelve los bytes del PDF.

    productor, generado, filtros: textos para el encabezado.
    resumen: dict con 'total', 'eventos', 'area' y 'valor' (ya numéricos).
    severidades: lista de (etiqueta, cantidad), de más a menos grave.
    unidades: lista de (nombre de la unidad agrícola, cantidad de afectaciones).
    finca: nombre de la finca del productor (opcional; se muestra en el encabezado).
    filas: lista de filas del detalle, cada una con 7 textos:
        fecha del sismo, unidad agrícola, tipo de daño, elemento, severidad, área, pérdida.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.6 * cm,
        bottomMargin=2 * cm,
        title="Reporte de afectaciones sísmicas · AgroSismo",
        author="AgroSismo",
    )

    base = getSampleStyleSheet()
    normal = base["BodyText"]
    titulo = ParagraphStyle(
        "Titulo", parent=base["Title"], textColor=VERDE, alignment=0, fontSize=20, spaceAfter=8
    )
    subtitulo = ParagraphStyle(
        "Subtitulo", parent=base["Heading2"], textColor=VERDE, spaceBefore=14, spaceAfter=6
    )
    celda = ParagraphStyle("Celda", parent=normal, fontSize=8, leading=10)
    celda_enc = ParagraphStyle(
        "CeldaEnc", parent=celda, textColor=colors.white, fontName="Helvetica-Bold"
    )
    nota = ParagraphStyle("Nota", parent=normal, fontSize=8, textColor=GRIS, spaceBefore=10)

    def tabla(datos, anchos, encabezado_verde=False):
        t = Table(datos, colWidths=anchos, repeatRows=1)
        estilo = [
            ("GRID", (0, 0), (-1, -1), 0.25, BORDE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, VERDE_CLARO]),
            ("BACKGROUND", (0, 0), (-1, 0), VERDE if encabezado_verde else VERDE_CLARO),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        t.setStyle(TableStyle(estilo))
        return t

    historia = [
        Paragraph("Reporte de afectaciones sísmicas", titulo),
        Paragraph(f"<b>Productor:</b> {_t(productor)}", normal),
        *([Paragraph(f"<b>Finca:</b> {_t(finca)}", normal)] if finca else []),
        Paragraph(f"<b>Generado:</b> {_t(generado)}", normal),
        Paragraph(f"<b>Filtros:</b> {_t(filtros)}", normal),
        Paragraph("Resumen", subtitulo),
        tabla(
            [
                ["Afectaciones", "Sismos", "Área afectada", "Pérdidas estimadas"],
                [
                    str(resumen["total"]),
                    str(resumen["eventos"]),
                    f"{formato_ha(resumen['area'])} ha",
                    formato_cop(resumen["valor"]),
                ],
            ],
            [4 * cm, 3 * cm, 4 * cm, 6 * cm],
        ),
        Paragraph("Afectaciones por severidad", subtitulo),
        tabla(
            [["Severidad", "Afectaciones"]] + [[_t(e), str(n)] for e, n in severidades],
            [8 * cm, 9 * cm],
        ),
    ]

    if unidades:
        historia += [
            Paragraph("Unidades más afectadas", subtitulo),
            tabla(
                [["Unidad agrícola", "Afectaciones"]]
                + [[Paragraph(_t(nombre), celda), str(n)] for nombre, n in unidades],
                [12 * cm, 5 * cm],
            ),
        ]

    encabezados = ["Fecha del sismo", "Unidad agrícola", "Daño", "Elemento", "Severidad", "Área (ha)", "Pérdida (COP)"]
    detalle = [[Paragraph(e, celda_enc) for e in encabezados]]
    for fila in filas:
        detalle.append([Paragraph(_t(x), celda) for x in fila])
    historia += [
        Paragraph("Detalle de afectaciones", subtitulo),
        tabla(detalle, [3.2 * cm, 2.9 * cm, 2.4 * cm, 2.3 * cm, 1.9 * cm, 1.8 * cm, 2.5 * cm], True),
        Paragraph(NOTA_ESTIMACION, nota),
    ]

    doc.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()
