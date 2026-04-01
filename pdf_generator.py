"""
Generació de PDFs per a la parada de mercat.

PDF 1 — Comandes per client:
  Una secció per client amb tot el que ha demanat.

PDF 2 — Preparació per demà:
  Tots els productes agrupats amb les quantitats totals.
"""

from fpdf import FPDF
from datetime import date
from io import BytesIO


VERD_FOSC  = (27,  94,  32)   # capçalera
VERD_CLAR  = (232, 245, 233)  # fons fila parell
TARONJA    = (230, 81,  0)    # capçalera PDF 2
TARONJA_CL = (255, 243, 224)  # fons fila parell PDF 2
GRIS_TEXT  = (80,  80,  80)
NEGRE      = (20,  20,  20)


class PDF(FPDF):
    def __init__(self, titol, color_cap):
        super().__init__()
        self.titol     = titol
        self.color_cap = color_cap
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        r, g, b = self.color_cap
        self.set_fill_color(r, g, b)
        self.rect(0, 0, 210, 22, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
        self.set_y(6)
        self.cell(0, 10, self.titol, align="C")
        data = date.today().strftime("%d/%m/%Y")
        self.set_font("Helvetica", "", 8)
        self.set_xy(150, 7)
        self.cell(40, 8, data, align="R")
        self.ln(18)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRIS_TEXT)
        self.cell(0, 10, f"Pàgina {self.page_no()}", align="C")


def generar_pdf_clients(comandes: list) -> bytes:
    """PDF amb les comandes agrupades per client."""
    data_str = date.today().strftime("%d/%m/%Y")
    pdf = PDF(f"Comandes del divendres — {data_str}", VERD_FOSC)
    pdf.add_page()

    if not comandes:
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(*GRIS_TEXT)
        pdf.cell(0, 10, "Cap comanda registrada avui.", align="C")
        return bytes(pdf.output())

    for i, comanda in enumerate(comandes):
        nom = comanda.get("client") or comanda.get("telefon", "Desconegut")

        # Capçalera del client
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(*VERD_FOSC)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 9, f"  {nom}", fill=True, ln=True)

        # Articles
        articles = comanda.get("articles", [])
        for j, art in enumerate(articles):
            bg = VERD_CLAR if j % 2 == 0 else (255, 255, 255)
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*NEGRE)
            pdf.set_font("Helvetica", "", 10)

            nom_art = art.get("nom", "")
            quant   = art.get("quantitat", "")
            unitat  = art.get("unitat", "")

            pdf.set_x(22)
            pdf.cell(110, 8, f"{nom_art}", fill=True)
            pdf.cell(40, 8, f"{quant} {unitat}", fill=True, align="R", ln=True)

        if not articles:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*GRIS_TEXT)
            pdf.set_x(22)
            pdf.cell(0, 7, "(sense articles)", ln=True)

        pdf.ln(4)

        # Salt de pàgina si queda poc espai i no és l'últim
        if i < len(comandes) - 1 and pdf.get_y() > 240:
            pdf.add_page()

    return bytes(pdf.output())


def generar_pdf_preparacio(comandes: list) -> bytes:
    """PDF amb els totals per producte — llista de preparació."""
    data_str = date.today().strftime("%d/%m/%Y")
    pdf = PDF(f"Preparació per a demà — {data_str}", TARONJA)
    pdf.add_page()

    if not comandes:
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(*GRIS_TEXT)
        pdf.cell(0, 10, "Cap comanda registrada avui.", align="C")
        return bytes(pdf.output())

    # Agrupar per producte i sumar quantitats
    totals: dict[str, dict] = {}
    for comanda in comandes:
        for art in comanda.get("articles", []):
            nom    = art.get("nom", "").strip().lower()
            quant  = float(art.get("quantitat") or 0)
            unitat = art.get("unitat", "")
            if nom not in totals:
                totals[nom] = {"nom_orig": art.get("nom", nom), "quant": 0, "unitat": unitat}
            totals[nom]["quant"] += quant

    # Ordenar alfabèticament
    items = sorted(totals.values(), key=lambda x: x["nom_orig"].lower())

    # Capçalera de la taula
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(*TARONJA)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(120, 9, "  Producte", fill=True)
    pdf.cell(50, 9, "Total a preparar", fill=True, align="C", ln=True)

    # Files
    for i, item in enumerate(items):
        bg = TARONJA_CL if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*bg)
        pdf.set_text_color(*NEGRE)
        pdf.set_font("Helvetica", "", 10)

        quant_fmt = f"{item['quant']:g} {item['unitat']}"
        pdf.cell(120, 8, f"  {item['nom_orig']}", fill=True)
        pdf.cell(50, 8, quant_fmt, fill=True, align="C", ln=True)

    # Resum final
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TARONJA)
    total_clients = len(comandes)
    pdf.cell(0, 8, f"Total: {len(items)} productes diferents · {total_clients} client{'s' if total_clients != 1 else ''}", ln=True)

    return bytes(pdf.output())
