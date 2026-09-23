"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute sind erlaubt, aber Gedankenstrich (U+2013), Minuszeichen (U+2212),
Euro-Zeichen, Emoji usw. lassen fpdf2 abstuerzen. Deshalb laeuft jeder Text durch pdf_text()."""
import time

import wfg_constants as C

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR", "±": "+-",
    "·": "-", "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "",
    "🚧": "", "📐": "", "🎯": "", "📊": "", "🐌": "", "📅": "", "🔧": "", "🎲": "", "ρ": "rho", "τ": "tau",
}


E_VERDICT = {"pos": "hilft", "neg": "schadet", "none": "n. s."}
E_CHANGE = {"pos": "Vorteil wächst", "neg": "Vorteil schrumpft", "none": "kein belastb. Unterschied"}


def pdf_text(text):
    """Text fuer die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def _min(v):
    return f"{v:.1f}"


def _pair(p):
    return f"{p.mean:+.1f} +- {p.se:.1f}"


def _pct(v, signed=False):
    return f"{v:+.1f} %" if signed else f"{v:.1f} %"


def generate_wfg_pdf(settings, seed, pop, k_rows, rho_rows, summary, exact=None, compress=True):
    """Ergebnis der aktuellen Einstellung als PDF: Einstellungen, Kennzahlen, Vergleichstabelle, Vorteil je
    Kommissionierer-Zahl, Fenster-Gewinn je rho, Hinweise zum Modell.

    settings: dict der Reglerwerte (aisles, pickers, orders, tau, express_pct, hot_corr_pct, window);
    summary: E.shown_summary der gezeigten Instanz; exact: optional E.exact_summary."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(85, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 8)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    line("Kommissionierwellen: Fristen und Gangblockaden", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    heading("Einstellungen")
    pairs([
        ("Gänge", str(settings["aisles"])), ("Kommissionierer", str(settings["pickers"])),
        ("Bestellungen", str(settings["orders"])), ("Fristendruck (kleiner = enger)", f"{settings['tau']:.1f}"),
        ("Express-Anteil", f"{settings['express_pct']} %"),
        ("Konzentration auf vordere Gänge (rho)", f"{settings['hot_corr_pct']} %"),
        ("Konflikt-Fenster w", str(settings["window"])), ("Seed (gezeigte Instanz)", str(seed)),
    ])
    pdf.ln(3)

    heading(f"Kennzahlen ({pop.n} Instanzen, Seeds 0 bis 79, Mittel +- Standardfehler)")
    gain = pop.gain()
    pairs([
        (f"Verspätung EDD mit Fenster w={pop.w}", f"{_min(pop.mean_min(C.RULE_EDDW))} gewichtete Min."),
        ("Verspätung EDD ohne Blockieren", f"{_min(pop.mean_min('edd_free'))} gewichtete Min."),
        ("Wartezeitanteil (Regel EDD)", _pct(pop.wait_share_pct(C.RULE_EDD))),
        ("Gewinn des Fensters ggü. EDD", f"{_pair(gain)} Min. ({E_VERDICT[gain.verdict()]})"),
        ("Vorteil EDD ggü. FIFO mit Blockieren", f"{_pair(pop.advantage_on())} Min."),
        ("Vorteil EDD ggü. FIFO ohne Blockieren", f"{_pair(pop.advantage_off())} Min."),
    ])
    pdf.ln(3)

    keep_together(50)
    heading("Regeln im Vergleich")
    rows = []
    for rule in C.RULE_KEYS:
        diff = "-" if rule == C.RULE_EDD else _pair(pop.diff_to_edd(rule))
        rows.append([C.RULE_SHORT[rule] + (f" (w={pop.w})" if rule == C.RULE_EDDW else ""), _min(pop.mean_min(rule)),
                     diff, _pct(pop.wait_share_pct(rule)), _pct(pop.late_share_pct(rule))])
    rows.append(["EDD ohne Blockieren", _min(pop.mean_min("edd_free")), _pair(pop.pair("edd_free", C.RULE_EDD)),
                 _pct(0.0), _pct(pop.late_share_pct("edd_free"))])
    table(["Regel", "Verspätung (Min.)", "Differenz zu EDD (+- SE)", "Wartezeitanteil", "Verspätete Best."],
          [40, 32, 45, 32, 34], rows)
    pdf.ln(3)

    keep_together(80)
    heading("Vorteil der Fristenregel (EDD gg. FIFO) je Kommissionierer-Zahl")
    table(["Kommissionierer", "ohne Blockieren", "mit Blockieren", "Änderung", "Urteil (gepaart)"], [32, 34, 34, 28, 60],
          [[r.k, _min(r.adv_off.mean), _min(r.adv_on.mean), _pct(r.rel_change_pct, True), E_CHANGE[r.verdict]]
           for r in k_rows])
    pdf.ln(3)

    keep_together(45)
    heading("Gewinn des Konflikt-Fensters je Konzentration rho (Min., +- SE)")
    windows = list(next(iter(rho_rows.values())))
    table(["rho"] + [f"w = {w}" for w in windows], [30] + [50] * len(windows),
          [[f"{rho} %"] + [f"{_pair(p)} ({E_VERDICT[p.verdict()]})" for p in by_w.values()]
           for rho, by_w in rho_rows.items()])
    pdf.ln(3)

    keep_together(40)
    heading(f"Gezeigte Instanz (Seed {seed}, Einzelfall)")
    pairs([
        ("Batches", str(summary["n_batches"])), ("Verspätung (EDD mit Fenster)", f"{_min(summary['obj_min'])} Min."),
        ("Wartezeitanteil", _pct(summary["wait_share_pct"])), ("Verspätete Bestellungen", str(summary["late"])),
    ])
    pdf.ln(3)

    if exact is not None:
        keep_together(45)
        heading("Exakte Referenz (CP-SAT, nur diese Kleininstanz)")
        pairs([
            ("Optimum" if exact["proven"] else "Beste Lösung (mit Blockieren)", f"{_min(exact['opt_min'])} Min."),
            ("Beste Schranke", f"{_min(exact['bound_min'])} Min."),
            ("Optimum ohne Blockieren" if exact["proven_free"] else "Beste Lösung ohne Blockieren",
             f"{_min(exact['opt_free_min'])} Min."),
            ("Potenzial ggü. EDD", "-" if exact["potential_pct"] is None else _pct(exact["potential_pct"])),
            ("Preis des Blockierens im Optimum", "-" if exact["price_pct"] is None else _pct(exact["price_pct"], True)),
        ])
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Stark stilisiert: S-Shape-Route mit ganzer Gangdurchquerung, jeder Gang eine Einzelressource ohne "
        "Überholen, alle Bestellungen zum Zeitpunkt 0, feste Kommissionierer-Zahl, frist-blind vorgebildete Batches.",
        "rho, heiße Gänge und Fristenverteilung sind synthetisch, nicht an einem echten Lager kalibriert. Die "
        "Kernaussage (das Vorzeichen des Fenster-Effekts hängt von Fristendruck und Dringlichkeitskonzentration "
        "ab) ist robust, die Prozentwerte sind es nicht.",
        "Alle Kennzahlen sind gepaarte Mittel über 80 deterministische Instanzen; ein Urteil gilt nur ab 2 "
        "Standardfehlern. Die exakte Referenz gilt nur für Kleininstanzen.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())

