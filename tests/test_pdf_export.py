"""PDF-Export: Sonderzeichen-Bereinigung (fpdf2 stuerzt bei Gedankenstrich, Euro-Zeichen, Emoji und dem Minuszeichen U+2212
ab - mit den GENAUEN Zeichen testen), Generierung fuer jedes Preset und an den Reglergrenzen."""
import pytest

import wfg_constants as C
import wfg_evaluation as E
from wfg_pdf_export import generate_wfg_pdf, pdf_text
from wfg_sim import simulate


def test_pdf_text_replaces_en_dash_and_em_dash():
    assert "–" not in pdf_text("Verspätung – Gang") and "—" not in pdf_text("Verspätung — Gang")


def test_pdf_text_replaces_euro_sign_with_eur():
    assert "EUR" in pdf_text("100 €") and "€" not in pdf_text("100 €")


def test_pdf_text_replaces_unicode_minus_sign_with_ascii():
    assert pdf_text("−5 %") == "-5 %"


def test_pdf_text_strips_or_replaces_emoji_and_greek():
    cleaned = pdf_text("🚧 📐 🎯 📊 🐌 📅 🔧 🎲 ✅ ℹ️ ⚠️ ρ τ")
    cleaned.encode("latin-1")
    assert "rho" in cleaned and "tau" in cleaned and "🚧" not in cleaned


def test_pdf_text_keeps_german_umlauts():
    text = pdf_text("Prämie für Gänge, Verspätung – Größe")
    assert "Prämie" in text and "Gänge" in text and "Größe" in text


def test_pdf_text_result_is_always_latin1_encodable():
    tricky = "Gang–Route € ≥ ≤ → ≈ ± · „x“ ‘y’ ⚠️ ✅ ℹ️ 🚧📐🎯🐌📅 − Ω λ 日本"
    pdf_text(tricky).encode("latin-1")


def test_core_font_really_renders_the_cleaned_literal_characters():
    """Die kritischen Zeichen laufen durch pdf_text und lassen fpdf2 nicht abstuerzen."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, pdf_text("– € 🚧 − ≥ ρ Prämie Gänge"))
    assert bytes(pdf.output())[:4] == b"%PDF"


def _pdf(name=None, exact=False, **over):
    p = dict(C.PRESETS[name or "Standard"], **over)
    cfg = E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])
    pop = E.evaluate_population(cfg, p["window"])
    k_rows, rho_rows = E.k_sweep(cfg), E.rho_sweep(cfg)
    inst, res = E.shown_run(cfg, p["seed"], C.RULE_EDDW, p["window"])
    x = None
    if exact:
        x = E.exact_summary(inst, p["window"], dict(status="FEASIBLE", obj=simulate(inst, policy="edd")["obj"] // 2, bound=10.0, wall=1.0),
                            dict(status="OPTIMAL", obj=100, bound=100.0, wall=1.0))
    return generate_wfg_pdf({k: p[k] for k in ("aisles", "pickers", "orders", "tau", "express_pct", "hot_corr_pct", "window")},
                            p["seed"], pop, k_rows, rho_rows, E.shown_summary(inst, res), x)


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_pdf_generation_does_not_crash_for_every_preset(name):
    data = _pdf(name)
    assert data[:4] == b"%PDF" and len(data) > 1500


def test_pdf_generation_with_exact_result_section():
    with_exact, without = _pdf(exact=True, orders=24), _pdf(orders=24)
    assert with_exact[:4] == b"%PDF" and len(with_exact) > len(without) - 200


def test_pdf_generation_at_the_slider_extremes():
    assert _pdf(aisles=4, pickers=2, orders=20, tau=0.4, express_pct=5, hot_corr_pct=0, window=1)[:4] == b"%PDF"
    assert _pdf(aisles=12, pickers=10, orders=100, tau=2.0, express_pct=50, hot_corr_pct=100, window=8)[:4] == b"%PDF"


def test_pdf_text_contains_the_key_numbers_when_uncompressed():
    from wfg_pdf_export import generate_wfg_pdf as gen
    p = C.PRESETS["Standard"]
    cfg = E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])
    pop = E.evaluate_population(cfg, p["window"])
    inst, res = E.shown_run(cfg, p["seed"], C.RULE_EDDW, p["window"])
    data = gen({k: p[k] for k in ("aisles", "pickers", "orders", "tau", "express_pct", "hot_corr_pct", "window")}, p["seed"], pop,
               E.k_sweep(cfg), E.rho_sweep(cfg), E.shown_summary(inst, res), compress=False)
    text = data.decode("latin-1")
    assert "16.3 %" in text and "+11.9 +- 3.6" in text and "139.5" in text        # Kennzahlen des Standard-Presets
    assert "Kommissionierwellen" in text
