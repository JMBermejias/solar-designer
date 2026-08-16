# Copyright (C) 2026 Enersolred
#
# Solar Designer is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Generación de documentos PDF editables (AcroForm) con ReportLab.

Genera:
- Presupuesto (con campos rellenables)
- Memoria técnica (con normativa)
- Contrato de mantenimiento
- Libro de mantenimiento (trimestral/semestral/anual)
- Informe de visita de mantenimiento
"""
import io
import json
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import Flowable

from solar import normativa

AZUL = colors.HexColor("#1565C0")
AZUL_MEDIO = colors.HexColor("#4aa8e8")
AZUL_CLARO = colors.HexColor("#dceefc")
GRIS = colors.HexColor("#555555")
GRIS_CLARO = colors.HexColor("#eeeeee")

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def hoy():
    return datetime.now().strftime("%d/%m/%Y")


def f_euro(n, dec=2):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0
    s = f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def f_num(n, dec=2):
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0
    return f"{n:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Formulario AcroForm (PDF editable)
# ---------------------------------------------------------------------------
_SANITIZAR = {
    "\u2014": "-", "\u2013": "-", "\u2019": "'", "\u2018": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " ",
    "\u00b7": "-", "\u2022": "-", "\u2714": "OK",
}


def sanitizar(texto):
    """Reemplaza caracteres que rompen la codificación de los campos AcroForm."""
    if not texto:
        return ""
    return "".join(_SANITIZAR.get(ch, ch) for ch in str(texto))


class FormText(Flowable):
    """Flowable que dibuja un campo de texto editable (AcroForm)."""

    def __init__(self, name, value="", width=120, height=18, align="left",
                 multiline=False, style=None, readonly=False, maxlen=200):
        super().__init__()
        self.name = name
        self.value = sanitizar(value) or ""
        self.width = width
        self.height = height
        self.align = align
        self.multiline = multiline
        self.style = style
        self.readonly = readonly
        self.maxlen = maxlen
        self.availWidth = width
        self.availHeight = height

    def wrap(self, aw, ah):
        return self.width, self.height

    def split(self, aw, ah):
        return []

    def draw(self):
        c = self.canv
        x, y = 0, 0
        c.saveState()
        if self.style:
            c.setFillColor(colors.HexColor("#f2f9ff"))
            c.rect(x + 1, y + 1, self.width - 2, self.height - 2, stroke=0, fill=1)
        c.setLineWidth(0.5)
        c.setStrokeColor(colors.HexColor("#99bbdd"))
        c.rect(x + 1, y + 1, self.width - 2, self.height - 2, stroke=1, fill=0)
        flags = []
        if self.readonly:
            flags.append("readOnly")
        if self.multiline:
            flags.append("multiline")
        c.acroForm.textfield(
            name=self.name,
            value=self.value,
            x=x + 1,
            y=y + 1,
            width=self.width - 2,
            height=self.height - 2,
            fontSize=8.5,
            fontName="Helvetica",
            borderStyle="inset",
            textColor=colors.black,
            borderColor=colors.HexColor("#99bbdd"),
            fillColor=colors.HexColor("#fbfdff"),
            fieldFlags=" ".join(flags),
            maxlen=self.maxlen,
        )
        c.restoreState()


def form_story(items):
    return [FormText(n, v, w, h, multiline=ml) for n, v, w, h, ml in items]


# ---------------------------------------------------------------------------
# Plantilla de página
# ---------------------------------------------------------------------------
def header_footer(empresa):
    def _draw(canv, doc):
        canv.saveState()
        w, h = A4
        # Cabecera
        canv.setFillColor(AZUL_CLARO)
        canv.rect(0, h - 1.6 * cm, w, 1.6 * cm, stroke=0, fill=1)
        canv.setFillColor(AZUL_MEDIO)
        canv.rect(0, h - 0.28 * cm, w, 0.28 * cm, stroke=0, fill=1)
        canv.setFillColor(AZUL)
        canv.setFont("Helvetica-Bold", 10)
        canv.drawString(1.2 * cm, h - 0.95 * cm, empresa.get("nombre", "EMPRESA"))
        canv.setFont("Helvetica", 8)
        canv.setFillColor(GRIS)
        canv.drawString(1.2 * cm, h - 1.22 * cm, empresa.get("direccion", ""))
        # Pie
        canv.setFillColor(AZUL_CLARO)
        canv.rect(0, 0, w, 1.0 * cm, stroke=0, fill=1)
        canv.setFillColor(GRIS)
        canv.setFont("Helvetica", 7.5)
        canv.drawString(1.2 * cm, 0.4 * cm, f"{empresa.get('telefono','')}  ·  {empresa.get('email','')}")
        canv.drawRightString(w - 1.2 * cm, 0.4 * cm, f"Página {doc.page}")
        canv.restoreState()
    return _draw


def _styles():
    ss = getSampleStyleSheet()
    s = {
        "titulo": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold",
                                 fontSize=16, textColor=AZUL, spaceAfter=6),
        "subtitulo": ParagraphStyle("st", parent=ss["Heading2"], fontName="Helvetica-Bold",
                                    fontSize=11, textColor=AZUL_MEDIO, spaceBefore=10, spaceAfter=4),
        "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold",
                             fontSize=9.5, textColor=AZUL, spaceBefore=8, spaceAfter=3),
        "normal": ParagraphStyle("n", parent=ss["Normal"], fontName="Helvetica",
                                 fontSize=8.5, leading=11.5, textColor=colors.black,
                                 alignment=TA_JUSTIFY),
        "center": ParagraphStyle("c", parent=ss["Normal"], fontName="Helvetica-Bold",
                                 fontSize=9, leading=11, alignment=TA_CENTER),
        "small": ParagraphStyle("sm", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=7.5, leading=9.5, textColor=GRIS),
        "tabla_cab": ParagraphStyle("tc", parent=ss["Normal"], fontName="Helvetica-Bold",
                                    fontSize=8, textColor=colors.white),
        "tabla": ParagraphStyle("tb", parent=ss["Normal"], fontName="Helvetica",
                                fontSize=8, leading=10),
    }
    return s


def generar_documento(nombre_archivo, story, empresa, titulo_doc):
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                          topMargin=2.1 * cm, bottomMargin=1.4 * cm,
                          title=titulo_doc, author=empresa.get("nombre", ""))
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=header_footer(empresa))])
    doc.build(story)
    buf.seek(0)
    with open(nombre_archivo, "wb") as fh:
        fh.write(buf.getvalue())
    return nombre_archivo


def cabecera_datos(empresa, cliente=None, ref="", fecha=None, titulo="", entidad=None):
    """Cabecera con datos de empresa/cliente y formulario editable de cabecera."""
    ss = _styles()
    story = []
    story.append(Paragraph(titulo, ss["titulo"]))
    story.append(Spacer(1, 4))

    ref_fecha = [
        ["Referencia:", ref, "Fecha:", fecha or hoy()],
    ]
    t = Table(ref_fecha, colWidths=[3.2 * cm, 5.2 * cm, 2.4 * cm, 5.0 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.5),
        ("FONT", (2, 0), (2, -1), "Helvetica-Bold", 8.5),
        ("FONT", (1, 0), (1, -1), "Helvetica", 9),
        ("FONT", (3, 0), (3, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
        ("TEXTCOLOR", (2, 0), (2, -1), AZUL),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    if cliente:
        filas = [
            ["DATOS DEL CLIENTE", ""],
            ["Cliente:", cliente.get("nombre", "")],
            ["NIF/CIF:", cliente.get("nif", "")],
            ["Dirección:", cliente.get("direccion", "")],
            ["Población:", (cliente.get("cp", "") + " " + cliente.get("ciudad", "")).strip()],
            ["Teléfono:", cliente.get("telefono", "")],
            ["Email:", cliente.get("email", "")],
        ]
        t = Table(filas, colWidths=[3.2 * cm, 12.4 * cm])
        t.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), AZUL_CLARO),
            ("FONT", (0, 0), (0, 0), "Helvetica-Bold", 9),
            ("FONT", (0, 1), (0, -1), "Helvetica-Bold", 8),
            ("FONT", (1, 1), (1, -1), "Helvetica", 9),
            ("TEXTCOLOR", (0, 1), (0, -1), AZUL),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
    elif entidad:
        story.append(Paragraph(entidad, ss["normal"]))
    story.append(Spacer(1, 8))
    return story


# ---------------------------------------------------------------------------
# PRESUPUESTO
# ---------------------------------------------------------------------------
def generar_presupuesto(ruta, presupuesto, lineas, proyecto, cliente, empresa):
    ss = _styles()
    story = cabecera_datos(empresa, cliente, presupuesto.get("numero"),
                           presupuesto.get("fecha"), "PRESUPUESTO DE INSTALACIÓN FOTOVOLTAICA")
    story.append(Paragraph("Instalación proyectada: " + (proyecto.get("nombre") or ""), ss["normal"]))
    story.append(Paragraph("Ubicación: " + (proyecto.get("direccion") or ""), ss["normal"]))
    story.append(Spacer(1, 8))

    # Formulario editable de cabecera
    story.append(Paragraph("Datos editables del presupuesto", ss["h3"]))
    cab = [
        [FormText("pre_nombre", proyecto.get("nombre") or "", 7.4 * cm, 22, style=1),
         FormText("pre_dir", (proyecto.get("direccion") or "") + " " + (proyecto.get("ciudad") or ""), 7.4 * cm, 22, style=1)],
        [FormText("pre_tipo", "Autoconsumo fotovoltaico con excedentes (modalidad b.1)", 7.4 * cm, 22, style=1),
         FormText("pre_potencia", f"Potencia instalada: {f_num(proyecto.get('potencia_pico_kw',0),2)} kWp", 7.4 * cm, 22, style=1)],
    ]
    t = Table(cab, colWidths=[7.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 2),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Tabla de partidas
    story.append(Paragraph("PARTIDAS DE LA INSTALACIÓN", ss["subtitulo"]))
    cab_tabla = ["Descripción de la partida", "Cant.", "Und.", "Precio/und", "Importe"]
    anchos = [7.2 * cm, 1.5 * cm, 1.4 * cm, 2.6 * cm, 2.8 * cm]
    data = [[Paragraph(c, ss["tabla_cab"]) for c in cab_tabla]]
    i = 1
    total = 0.0
    for ln in lineas:
        cantidad = float(ln.get("cantidad") or 1)
        precio = float(ln.get("precio_unitario") or 0)
        importe = cantidad * precio
        total += importe
        fila = [
            FormText(f"pre_desc_{i}", ln.get("descripcion") or "", anchos[0], 30, multiline=True),
            FormText(f"pre_cant_{i}", f_num(cantidad, 2), anchos[1], 20, align="center"),
            FormText(f"pre_und_{i}", ln.get("und") or "ud", anchos[2], 20, align="center"),
            FormText(f"pre_prec_{i}", f_num(precio, 2), anchos[3], 20, align="right"),
            Paragraph(f_num(importe, 2), ss["tabla"]),
        ]
        data.append(fila)
        i += 1

    desc_global = float(presupuesto.get("descuento_global") or 0)
    iva = float(presupuesto.get("iva") or 21)
    base = total * (1 - desc_global / 100.0)
    importe_iva = base * iva / 100.0
    total_final = base + importe_iva

    data.append(["", "", "", Paragraph("Subtotal", ss["tabla"]), f_num(total, 2)])
    if desc_global:
        data.append(["", "", "", Paragraph(f"Descuento ({f_num(desc_global,0)} %)", ss["tabla"]), f_num(-(total - base), 2)])
    data.append(["", "", "", Paragraph(f"Base imponible", ss["tabla_cab"]), f_num(base, 2)])
    data.append(["", "", "", Paragraph(f"IVA ({f_num(iva,0)} %)", ss["tabla"]), f_num(importe_iva, 2)])
    data.append(["", "", "", Paragraph("TOTAL PRESUPUESTO", ss["tabla_cab"]), f_num(total_final, 2)])

    t = Table(data, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbddff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONT", (3, 1), (3, -1), "Helvetica", 8),
        ("FONT", (4, 1), (4, -1), "Helvetica", 8),
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for fila in range(1, len(data)):
        if data[fila][3].__class__.__name__ == "Paragraph":
            txt = data[fila][3].text
            if "TOTAL" in txt or "Base" in txt:
                estilo.append(("BACKGROUND", (0, fila), (-1, fila), AZUL_CLARO))
    t.setStyle(TableStyle(estilo))
    story.append(t)
    story.append(Spacer(1, 8))

    # Condiciones
    story.append(Paragraph("CONDICIONES Y VALIDEZ", ss["subtitulo"]))
    cond = presupuesto.get("condiciones") or (
        "1. Presupuesto válido durante los días indicados en cabecera.\n"
        "2. Los precios son por unidad, IVA incluido en el total.\n"
        "3. La instalación se ejecutará conforme al REBT (ITC-BT-40), RD 244/2019 y normativa vigente.\n"
        "4. Incluye legalización, certificado de instalación y memoria técnica.\n"
        "5. Garantía de los equipos según fabricante, y 1 año de garantía de la obra.")
    story.append(FormText("pre_condiciones", cond, 15.2 * cm, 4.2 * cm, multiline=True))
    story.append(Spacer(1, 10))

    # Firmas
    firmas = [
        [Paragraph("POR LA EMPRESA", ss["center"]), Paragraph("EL CLIENTE", ss["center"])],
        [Paragraph("<br/><br/>Firma y sello", ss["small"]), Paragraph("<br/><br/>Firma", ss["small"])],
    ]
    t = Table(firmas, colWidths=[7.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEABOVE", (0, 0), (0, 0), 0.5, GRIS),
                           ("TOPPADDING", (0, 0), (-1, -1), 40)]))
    story.append(t)
    return generar_documento(ruta, story, empresa, f"Presupuesto {presupuesto.get('numero')}")


# ---------------------------------------------------------------------------
# MEMORIA TÉCNICA
# ---------------------------------------------------------------------------
def generar_memoria(ruta, memoria, proyecto, resultados, empresa, cliente):
    ss = _styles()
    story = cabecera_datos(empresa, cliente, memoria.get("numero"),
                           memoria.get("fecha"),
                           "MEMORIA TÉCNICA DE INSTALACIÓN FOTOVOLTAICA")

    story.append(Paragraph("1. OBJETO", ss["subtitulo"]))
    story.append(Paragraph(normativa.OBJETO_MEMORIA, ss["normal"]))

    story.append(Paragraph("2. EMPLAZAMIENTO Y DATOS DE PARTIDA", ss["subtitulo"]))
    datos = [
        ["Dirección", proyecto.get("direccion") or ""],
        ["Población", (proyecto.get("cp", "") + " " + proyecto.get("ciudad", "")).strip()],
        ["Coordenadas", f"Lat {f_num(proyecto.get('lat', 0), 4)}  ·  Lon {f_num(proyecto.get('lon', 0), 4)}"],
        ["Tipo de cubierta", proyecto.get("tipo_cubierta") or ""],
        ["Superficie disponible", f_num(proyecto.get("superficie_m2", 0), 1) + " m²"],
        ["Orientación / Inclinación", f"{proyecto.get('orientacion_deg',180)}° / {proyecto.get('inclinacion_deg',30)}°"],
        ["Sombreamientos", proyecto.get("sombras") or "Sin sombras"],
        ["Consumo anual", f_num(resultados.get("consumo_anual_kwh", 0), 0) + " kWh/año"],
    ]
    t = Table(datos, colWidths=[4.5 * cm, 10.7 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.5),
        ("FONT", (1, 0), (1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t)

    story.append(Paragraph("3. RECURSOS SOLARES", ss["subtitulo"]))
    story.append(Paragraph(
        f"Se ha empleado la herramienta <b>PVGIS (Photovoltaic Geographical Information System, "
        f"Centro Común de Investigación de la Comisión Europea, https://re.jrc.ec.europa.eu/pvg_tools)</b> "
        f"para la obtención de los datos de irradiación del emplazamiento. Fuente utilizada: "
        f"<b>{resultados.get('fuente_radiacion','-')}</b>.", ss["normal"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Irradiación mensual sobre superficie horizontal e inclinada (kWh/m²):", ss["h3"]))
    meses = Paragraph("Mes", ss["tabla_cab"])
    ghor = Paragraph("GHI (kWh/m²)", ss["tabla_cab"])
    ginc = Paragraph("GTI (kWh/m²)", ss["tabla_cab"])
    hsp = Paragraph("HSP", ss["tabla_cab"])
    tdata = [[meses, ghor, ginc, hsp]]
    irr_h = resultados.get("irr_horizontal_mensual") or []
    irr_i = resultados.get("irr_inclinada_mensual") or []
    hsps = resultados.get("hsp_mensual") or []
    for m in range(12):
        tdata.append([
            Paragraph(normativa.MESES[m] if False else
                      ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"][m],
                      ss["tabla"]),
            Paragraph(f_num(irr_h[m], 2), ss["tabla"]),
            Paragraph(f_num(irr_i[m], 2), ss["tabla"]),
            Paragraph(f_num(hsps[m], 1), ss["tabla"]),
        ])
    t = Table(tdata, colWidths=[5.4 * cm, 3.4 * cm, 3.4 * cm, 3.0 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Total anual sobre inclinada: <b>{f_num(resultados.get('irr_inclinada_anual',0),1)} kWh/m²</b>. "
        f"Factor de optimización por orientación/inclinación: {f_num(resultados.get('factor_optimizacion',1),2)}.", ss["normal"]))

    story.append(Paragraph("4. DIMENSIONADO DE LA INSTALACIÓN", ss["subtitulo"]))
    dim = [
        ["Potencia pico instalada", f_num(resultados.get("potencia_pico_kw", 0), 2) + " kWp"],
        ["Número de módulos", str(resultados.get("n_paneles", 0))],
        ["Potencia nominal del módulo", f_num(resultados.get("panel_potencia_w", 0), 0) + " Wp"],
        ["Superficie de captación necesaria", f_num(resultados.get("superficie_necesaria_m2", 0), 1) + " m²"],
        ["Potencia de inversor/es recomendada", f_num(resultados.get("potencia_inversor_kw", 0), 2) + " kW"],
        ["Producción específica", f_num(resultados.get("produccion_anual_kwh_kwp", 0), 0) + " kWh/kWp·año"],
        ["Producción anual estimada", f_num(resultados.get("produccion_anual_kwh", 0), 0) + " kWh/año"],
        ["Performance Ratio estimado", f_num(resultados.get("pr_estimado", 0), 2)],
        ["Cobertura del consumo", f_num(resultados.get("cobertura_consumo_pct", 0), 1) + " %"],
        ["Ahorro económico estimado", f_num(resultados.get("ahorro_estimado_eur", 0), 0) + " €/año"],
        ["Reducción de CO2", f_num(resultados.get("co2_anual_kg", 0), 0) + " kg/año"],
    ]
    bat = resultados.get("bateria")
    if bat:
        dim.append(["Almacenamiento", "Banco de baterías de litio hierro-fosfato (LFP)"])
        dim.append(["Días de autonomía", f"{bat['autonomia_dias']:g} día(s) · DOD {bat['dod_pct']:g}%"])
        dim.append(["Capacidad total del banco", f_num(bat["capacidad_total_kwh"], 1) + " kWh"
                     + f"  ({f_num(bat['capacidad_ah'], 0)} Ah a {bat['tension_v']:g} V)"])
        dim.append(["Capacidad útil", f_num(bat["capacidad_util_kwh"], 1) + " kWh"])
        dim.append(["Módulos de batería", f"{bat['n_modulos']} x {f_num(bat['modulo_kwh'],2)} kWh"
                     f"  =  {f_num(bat['capacidad_instalada_kwh'],1)} kWh instalados"])
    t = Table(dim, colWidths=[7.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.5),
        ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 8.5),
        ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("BACKGROUND", (0, 0), (0, -1), AZUL_CLARO),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t)

    story.append(Paragraph("5. DESCRIPCIÓN DE LA INSTALACIÓN", ss["subtitulo"]))
    story.append(Paragraph(
        "La instalación consiste en un sistema de generación fotovoltaica conectado a la red "
        "interior del edificio, bajo la modalidad de autoconsumo con excedentes acogido a "
        "compensación simplificada (RD 244/2019). El generador se compone de módulos "
        "fotovoltaicos montados sobre la estructura descrita, un inversor con sus protecciones "
        "DC/AC, protecciones de interfaz conforme a la ITC-BT-40, cableado solar H1Z2Z2-K, "
        "caja de protecciones de CC, sistema de puesta a tierra y equipo de medida "
        "bidireccional. Todos los equipos cumplen con las normativas CE aplicables.", ss["normal"]))
    story.append(Paragraph(
        "La instalación cumplirá con las prescripciones del <b>REBT (RD 842/2002)</b> y su "
        "instrucción <b>ITC-BT-40</b>, el <b>RD 244/2019</b> de autoconsumo, el <b>RD 1183/2020</b> "
        "de acceso y conexión, el <b>CTE DB-HE5</b> si resulta de aplicación, la norma "
        "<b>UNE-EN 62446-1</b> de documentación y verificación y el resto de normativa "
        "recogida en el anexo de este documento.", ss["normal"]))
    if resultados.get("bateria"):
        bat = resultados["bateria"]
        story.append(Paragraph(
            "El sistema de almacenamiento estará compuesto por un banco de baterías de litio "
            "hierro-fosfato (LFP) con sistema de gestión BMS, dimensionado para una autonomía de "
            f"<b>{bat['autonomia_dias']:g} día(s)</b> con una profundidad de descarga máxima del "
            f"<b>{bat['dod_pct']:g}%</b> y una capacidad instalada de "
            f"<b>{f_num(bat['capacidad_instalada_kwh'],1)} kWh</b> "
            f"({bat['n_modulos']} módulos). El almacenamiento permite incrementar la energía "
            "autoconsumida y disponer de respaldo ante cortes de red.", ss["normal"]))

    story.append(Paragraph("6. PROTECCIONES Y PUESTA A TIERRA", ss["subtitulo"]))
    story.append(Paragraph(
        "La instalación dispondrá de protección contra sobreintensidades mediante fusibles o "
        "interruptores automáticos en los circuitos de continua, protección contra "
        "sobretensiones tipo 2 en CC y CA, protecciones de interfaz para la desconexión ante "
        "perturbaciones de la red (sobre/baja frecuencia 50/51 Hz y sobre/baja tensión) y "
        "seccionador general de la instalación. Toda la masa metálica se conectará a la red de "
        "puesta a tierra del edificio con conductor de sección adecuada según ITC-BT-18. "
        "Se instalará además protección diferencial de adecuada sensibilidad conforme a la "
        "ITC-BT-24.", ss["normal"]))

    story.append(Paragraph("7. RESUMEN ENERGÉTICO Y ECONÓMICO", ss["subtitulo"]))
    inv = resultados.get("inversion")
    resumen = [
        [Paragraph("Concepto", ss["tabla_cab"]), Paragraph("Valor", ss["tabla_cab"])],
        [Paragraph("Consumo anual", ss["tabla"]), Paragraph(f_num(resultados.get("consumo_anual_kwh", 0), 0) + " kWh", ss["tabla"])],
        [Paragraph("Producción anual", ss["tabla"]), Paragraph(f_num(resultados.get("produccion_anual_kwh", 0), 0) + " kWh", ss["tabla"])],
        [Paragraph("Cobertura del consumo", ss["tabla"]), Paragraph(f_num(resultados.get("cobertura_consumo_pct", 0), 1) + " %", ss["tabla"])],
        [Paragraph("Ahorro anual estimado", ss["tabla"]), Paragraph(f_num(resultados.get("ahorro_estimado_eur", 0), 0) + " €", ss["tabla"])],
    ]
    if inv:
        resumen += [
            [Paragraph("Inversión inicial", ss["tabla"]), Paragraph(f_num(inv["inversion_total"], 0) + " €", ss["tabla"])],
            [Paragraph("Subvención", ss["tabla"]), Paragraph("- " + f_num(inv["subvencion"], 0) + " €", ss["tabla"])],
            [Paragraph("Inversión neta", ss["tabla"]), Paragraph(f_num(inv["inversion_neta"], 0) + " €", ss["tabla"])],
            [Paragraph("Retorno simple", ss["tabla"]),
             Paragraph(f"{inv['payback_anos']:g} años" if inv.get("payback_anos") else f"> {inv['vida_util']} años", ss["tabla"])],
            [Paragraph(f"Retorno descontado ({inv['tasa_descuento_pct']:g}%)", ss["tabla"]),
             Paragraph(f"{inv['payback_descontado_anos']:g} años" if inv.get("payback_descontado_anos") else f"> {inv['vida_util']} años", ss["tabla"])],
            [Paragraph(f"VAN a {inv['vida_util']} años", ss["tabla"]), Paragraph(f_num(inv["van_eur"], 0) + " €", ss["tabla"])],
            [Paragraph("TIR", ss["tabla"]),
             Paragraph(f"{inv['tir_pct']:g} %" if inv.get("tir_pct") is not None else "-", ss["tabla"])],
            [Paragraph("ROI total", ss["tabla"]), Paragraph(f"{inv['roi_total_pct']:g} %", ss["tabla"])],
            [Paragraph("Ahorro acumulado en vida útil", ss["tabla"]), Paragraph(f_num(inv["ahorro_acumulado_eur"], 0) + " €", ss["tabla"])],
        ]
    t = Table(resumen, colWidths=[8.4 * cm, 6.8 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)

    story.append(Paragraph("8. NORMATIVA APLICABLE", ss["subtitulo"]))
    for ref, txt in normativa.NORMATIVA:
        story.append(Paragraph(f"<b>{ref}.</b> {txt}", ss["normal"]))
        story.append(Spacer(1, 2))

    story.append(Paragraph("9. PRESCRIPCIONES DE MANTENIMIENTO", ss["subtitulo"]))
    story.append(Paragraph(
        "Conforme al CTE DB-HE5 y a la UNE-EN 62446, la instalación deberá someterse a "
        "revisiones periódicas: <b>trimestrales</b> (limpieza de módulos, revisión visual de "
        "cableado y conexiones, verificación de inversor), <b>semestrales</b> (apriete de "
        "bornas, verificación de aislamiento, termografía) y <b>anuales</b> (revisión completa, "
        "incluida la comprobación de protecciones de interfaz y puesta a tierra). Todas las "
        "actuaciones quedarán reflejadas en el libro de mantenimiento de la instalación.", ss["normal"]))

    story.append(Paragraph("10. CONCLUSIÓN", ss["subtitulo"]))
    story.append(Paragraph(
        "Con el dimensionado expuesto la instalación queda técnicamente justificada y cumple "
        "con la normativa vigente. No obstante, dado que este documento se genera de forma "
        "automática a partir de los datos introducidos, su validez queda supeditada a la "
        "revisión y firma por parte de un técnico competente.", ss["normal"]))
    story.append(Spacer(1, 6))
    story.append(FormText("mem_firma_tecnico", "VºBº Técnico competente: ......................................",
                          15.2 * cm, 1.6 * cm, multiline=True))
    return generar_documento(ruta, story, empresa, f"Memoria técnica {memoria.get('numero')}")


# ---------------------------------------------------------------------------
# CONTRATO DE MANTENIMIENTO
# ---------------------------------------------------------------------------
def generar_contrato(ruta, contrato, cliente, proyecto, empresa):
    ss = _styles()
    from solar import templates as tmpl
    texto = tmpl.construir_contrato(
        cliente.get("nombre", ""), empresa, contrato.get("importe", 0),
        contrato.get("periodicidad", "anual"), contrato.get("fecha_inicio", ""),
        contrato.get("fecha_fin", ""),
        (proyecto.get("direccion", "") + " " + proyecto.get("ciudad", "")).strip(),
    )
    story = cabecera_datos(empresa, cliente, contrato.get("numero"),
                           contrato.get("fecha"),
                           "CONTRATO DE MANTENIMIENTO DE INSTALACIÓN FOTOVOLTAICA")
    story.append(Paragraph(texto["intro"], ss["normal"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(texto["importe_txt"], ss["h3"]))
    story.append(Spacer(1, 6))
    for ref, cl in texto["clausulas"]:
        story.append(Paragraph(f"<b>{ref}.</b> {cl}", ss["normal"]))
        story.append(Spacer(1, 3))
    story.append(Paragraph("En prueba de conformidad, ambas partes firman el presente contrato.",
                           ss["normal"]))
    story.append(Spacer(1, 14))
    firmas = [
        [Paragraph("POR LA EMPRESA", ss["center"]), Paragraph("EL CLIENTE", ss["center"])],
        [Paragraph("<br/><br/>Firma y sello<br/>", ss["small"]), Paragraph("<br/><br/>Firma<br/>", ss["small"])],
    ]
    t = Table(firmas, colWidths=[7.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEABOVE", (0, 0), (0, 0), 0.5, GRIS),
                           ("TOPPADDING", (0, 0), (-1, -1), 60)]))
    story.append(t)
    return generar_documento(ruta, story, empresa, f"Contrato {contrato.get('numero')}")


# ---------------------------------------------------------------------------
# LIBRO DE MANTENIMIENTO
# ---------------------------------------------------------------------------
def generar_libro_mantenimiento(ruta, proyecto, registros, empresa, contrato=None):
    ss = _styles()
    story = cabecera_datos(empresa, cliente=None, ref="LIBRO-MT",
                           fecha=hoy(), titulo="LIBRO DE MANTENIMIENTO DE LA INSTALACIÓN FOTOVOLTAICA",
                           entidad=("Instalación: " + (proyecto.get("nombre") or "") + " — " +
                                    (proyecto.get("direccion") or "")))
    story.append(Paragraph(
        "Este libro recoge todas las actuaciones de mantenimiento preventivo y correctivo "
        "realizadas sobre la instalación, en sus periodos <b>trimestral, semestral y anual</b>, "
        "conforme al RD 244/2019, al CTE DB-HE5 y a la UNE-EN 62446.", ss["normal"]))
    story.append(Spacer(1, 6))

    cab = ["Fecha", "Periodicidad", "Técnico", "Estado", "Tareas realizadas", "Observaciones"]
    anchos = [1.9 * cm, 2.0 * cm, 2.4 * cm, 1.7 * cm, 4.0 * cm, 3.2 * cm]
    data = [[Paragraph(c, ss["tabla_cab"]) for c in cab]]
    i = 1
    for r in registros:
        data.append([
            FormText(f"lib_fecha_{i}", r.get("fecha_realizado") or r.get("fecha_programada") or "", anchos[0], 40, multiline=True),
            FormText(f"lib_per_{i}", r.get("periodo") or "", anchos[1], 40, multiline=True),
            FormText(f"lib_tec_{i}", r.get("tecnico") or "", anchos[2], 40, multiline=True),
            FormText(f"lib_est_{i}", r.get("estado") or "", anchos[3], 40, multiline=True),
            FormText(f"lib_tar_{i}", "\n".join(json.loads(r.get("tareas") or "[]")), anchos[4], 40, multiline=True),
            FormText(f"lib_obs_{i}", r.get("observaciones") or "", anchos[5], 40, multiline=True),
        ])
        i += 1
    # filas vacías editables
    for j in range(3):
        data.append([
            FormText(f"lib_fecha_{i}", "", anchos[0], 40, multiline=True),
            FormText(f"lib_per_{i}", "", anchos[1], 40, multiline=True),
            FormText(f"lib_tec_{i}", "", anchos[2], 40, multiline=True),
            FormText(f"lib_est_{i}", "", anchos[3], 40, multiline=True),
            FormText(f"lib_tar_{i}", "", anchos[4], 40, multiline=True),
            FormText(f"lib_obs_{i}", "", anchos[5], 40, multiline=True),
        ])
        i += 1
    t = Table(data, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t)

    story.append(Paragraph("PROGRAMA PREVENTIVO", ss["subtitulo"]))
    for periodo, tareas in [
        ("Trimestral", ["Limpieza de módulos fotovoltaicos", "Revisión visual de módulos y estructura",
                        "Comprobación de inversor/es y alarmas", "Verificación de cableado aparente"]),
        ("Semestral", ["Apriete de bornas y conexiones", "Medida de tensiones y corrientes",
                       "Verificación de aislamiento (megóhmetro)", "Termografía de módulos",
                       "Revisión de protecciones DC/AC"]),
        ("Anual", ["Revisión completa de la instalación", "Comprobación de protecciones de interfaz",
                   "Medida de puesta a tierra", "Revisión del cuadro de protecciones",
                   "Revisión de estado de estructura y fijaciones", "Informe anual y recomendaciones"]),
    ]:
        story.append(Paragraph(f"<b>{periodo}:</b> " + "; ".join(tareas) + ".", ss["normal"]))
    return generar_documento(ruta, story, empresa, "Libro de mantenimiento")


# ---------------------------------------------------------------------------
# INFORME DE VISITA
# ---------------------------------------------------------------------------
def generar_informe_mantenimiento(ruta, registro, proyecto, empresa, contrato=None):
    ss = _styles()
    story = cabecera_datos(empresa, None, f"INF-{registro.get('id','')}",
                           registro.get("fecha_realizado") or hoy(),
                           "INFORME DE VISITA DE MANTENIMIENTO",
                           entidad=("Instalación: " + (proyecto.get("nombre") or "") + " — " +
                                    (proyecto.get("direccion") or "")))
    campos = [
        ["Periodo", registro.get("periodo", "")],
        ["Técnico", registro.get("tecnico", "")],
        ["Estado", registro.get("estado", "")],
        ["Fecha programada", registro.get("fecha_programada", "")],
        ["Fecha de realización", registro.get("fecha_realizado", "")],
    ]
    t = Table(campos, colWidths=[5.0 * cm, 10.2 * cm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8.5),
        ("FONT", (1, 0), (1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbddff")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph("TAREAS REALIZADAS", ss["subtitulo"]))
    tareas = json.loads(registro.get("tareas") or "[]")
    tt = [[Paragraph("• " + ta, ss["normal"])] for ta in tareas]
    if tt:
        t = Table(tt, colWidths=[15.2 * cm])
        t.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(t)
    story.append(Paragraph("OBSERVACIONES", ss["subtitulo"]))
    story.append(FormText(f"inf_obs_{registro.get('id','')}", registro.get("observaciones") or "",
                          15.2 * cm, 4 * cm, multiline=True))
    story.append(Spacer(1, 14))
    firmas = [
        [Paragraph("TÉCNICO MANTENIMIENTO", ss["center"]), Paragraph("CLIENTE / RESPONSABLE", ss["center"])],
        [Paragraph("<br/><br/>Firma", ss["small"]), Paragraph("<br/><br/>Firma", ss["small"])],
    ]
    t = Table(firmas, colWidths=[7.6 * cm, 7.6 * cm])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 0.5, GRIS),
                           ("TOPPADDING", (0, 0), (-1, -1), 60)]))
    story.append(t)
    return generar_documento(ruta, story, empresa, "Informe de mantenimiento")


def _acortar(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"
