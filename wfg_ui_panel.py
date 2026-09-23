"""Wiederverwendbares Panel: Kennzahlen (2 x 2), Meldung, Gantt, Regel-Tabs, Vergleichstabelle, Exakt-Tab
(Plan Abschnitt 6/8)."""
import pandas as pd
import streamlit as st

import wfg_constants as C
import wfg_evaluation as E
import wfg_visualization as V


def fmt_min(v, digits=1, signed=False):
    text = f"{v:+.{digits}f}" if signed else f"{v:.{digits}f}"
    return text.replace(".", ",")


def fmt_pct(v, digits=1, signed=False):
    text = f"{v:+.{digits}f}" if signed else f"{v:.{digits}f}"
    return f"{text} %".replace(".", ",")


def fmt_rel_change(v):
    """Relative Aenderung in Prozent ohne '-0 %': unter 0,5 % Betrag '±0 %'."""
    text = f"{v:+.0f}"
    return "±0 %" if text in ("+0", "-0") else f"{text} %"


def fmt_pair(p: E.Pair, digits=1):
    """Mittel ± Standardfehler mit Vorzeichen, deutsches Dezimalkomma."""
    return f"{p.mean:+.{digits}f} ± {p.se:.{digits}f}".replace(".", ",")


VERDICT_TEXT = {"pos": "belastbar positiv", "neg": "belastbar negativ", "none": "kein belastbarer Unterschied"}


def render_message(state, pop, gain):
    """Bedingte Meldung der Hauptansicht in vier Zustaenden (Plan Abschnitt 6)."""
    w = pop.w
    wait = pop.wait_share_pct(C.RULE_EDD)
    if state == E.STATE_IRRELEVANT:
        text = (f"ℹ️ Blockieren spielt hier kaum eine Rolle: nur {fmt_pct(wait)} der Kommissionierer-Zeit gehen fürs "
                f"Warten am Gang drauf - die Fristenregel genügt.")
        if gain.verdict() == "neg":
            text += (f" Das Konflikt-Fenster (w = {w}) macht es trotzdem messbar schlechter "
                     f"({fmt_pair(gain)} Min., belastbar).")
        st.info(text)
    elif state == E.STATE_PAYS:
        st.success(f"✅ Hier lohnt Konfliktvermeidung: das Fenster w = {w} holt {fmt_pair(gain)} gewichtete Minuten "
                   f"gegenüber EDD zurück (Mittel ± Standardfehler über {pop.n} Instanzen, mehr als 2 Standardfehler). "
                   f"Nur einen Teil des Blockierens - nicht die Blockade selbst.")
    elif state == E.STATE_HURTS:
        st.warning(f"⚠️ Hier kostet Konfliktvermeidung mehr, als sie bringt: das Fenster w = {w} verschlechtert EDD um "
                   f"{fmt_min(-gain.mean)} ± {fmt_min(gain.se)} gewichtete Minuten (mehr als 2 Standardfehler) - die Regel "
                   f"opfert Dringlichkeit, ohne genug Konflikte zu sparen.")
    else:
        text = (f"ℹ️ Kein belastbarer Unterschied: der Gewinn des Fensters w = {w} ({fmt_pair(gain)} Min.) liegt "
                f"innerhalb von 2 Standardfehlern.")
        if w == 1:
            text = ("ℹ️ w = 1 ist exakt EDD, das Konflikt-Fenster ist also ausgeschaltet - der Gewinn ist per Definition "
                    "0. Zum Untersuchen w auf 2 oder mehr stellen.")
        st.info(text)


def render_metrics(columns, pop):
    """Vier Kennzahlen im 2 x 2-Raster (Plan Abschnitt 6): Verspaetung der gewaehlten Regel, Verspaetung ohne Blockieren
    (Preis des Blockierens), Wartezeitanteil, Gewinn des Fensters gegenueber EDD (gepaart, Mittel ± SE)."""
    m = columns
    with_w = pop.mean_min(C.RULE_EDDW)
    free = pop.mean_min("edd_free")
    gain = pop.gain()
    m[0].metric(f"Verspätung (EDD mit Fenster w = {pop.w})", f"{fmt_min(with_w)} Min.",
                help="Mittlere gewichtete Gesamtverspätung der Regel EDD mit Konflikt-Fenster (Express-Bestellungen "
                     f"zählen dreifach) über {pop.n} Instanzen, mit Blockieren. Bei w = 1 ist das exakt EDD.")
    m[1].metric("Verspätung ohne Blockieren (Regel EDD)", f"{fmt_min(free)} Min.",
                delta=f"{fmt_min(with_w - free, signed=True)} Min.", delta_color="inverse",
                help="Preis des Blockierens: dieselbe Fristenregel EDD, wenn sich Kommissionierer nicht behindern "
                     "(= parallele Maschinen mit Fristen, das Modell der warehouse-transfer-demo). Delta = Verspätung "
                     "der gewählten Regel mit Blockieren minus dieser Wert.")
    m[2].metric("Wartezeitanteil (Regel EDD)", fmt_pct(pop.wait_share_pct(C.RULE_EDD)),
                help="Anteil der Kommissionierer-Zeit, die fürs Warten am Gangeingang draufgeht (Mittel über die "
                     "Instanzen).")
    m[3].metric("Gewinn des Fensters ggü. EDD", f"{fmt_pair(gain)} Min.",
                help="EDD minus EDD mit Fenster, gepaart je Instanz, Mittel ± Standardfehler über "
                     f"{pop.n} Instanzen. Positiv = das Fenster hilft, negativ = es schadet; nur ab 2 Standardfehlern "
                     "belastbar.")


def render_gantt(key, n_aisles, result, inst, caption=None):
    st.plotly_chart(V.gantt_figure(n_aisles, result, inst), width="stretch", key=key)
    if caption:
        st.caption(caption)


def shown_caption(seed, summary):
    return (f"Gezeigte Instanz (Seed {seed}, ein einzelner Fall - die Kennzahlen oben stehen auf den Seeds 0 bis 79): "
            f"{summary['n_batches']} Batches, Verspätung {fmt_min(summary['obj_min'])} Min., "
            f"{fmt_pct(summary['wait_share_pct'])} Wartezeitanteil, {summary['late']} verspätete Bestellungen. "
            "Farbige Balken = Gang belegt (Farbe und Kürzel = Batch), grauer Streifen = Kommissionierer wartet am "
            "Gangeingang.")


def rule_rows(pop):
    """Zeilen der Vergleichstabelle: Regel | gewichtete Verspaetung | Differenz zu EDD (± SE) | Wartezeitanteil |
    verspaetete Bestellungen. Differenz = Regel minus EDD (positiv = mehr Verspaetung)."""
    rows = []
    for rule in C.RULE_KEYS:
        key = rule
        diff = "-" if rule == C.RULE_EDD else fmt_pair(pop.diff_to_edd(rule))
        label = C.RULE_LABELS[rule] + (f" (w = {pop.w})" if rule == C.RULE_EDDW else "")
        rows.append({
            "Regel": label, "Gewichtete Verspätung (Min.)": fmt_min(pop.mean_min(key)),
            "Differenz zu EDD (Min., ± SE)": diff, "Wartezeitanteil": fmt_pct(pop.wait_share_pct(key)),
            "Verspätete Bestellungen": fmt_pct(pop.late_share_pct(key)),
        })
    rows.append({
        "Regel": "📅 EDD ohne Blockieren (Referenz)", "Gewichtete Verspätung (Min.)": fmt_min(pop.mean_min("edd_free")),
        "Differenz zu EDD (Min., ± SE)": fmt_pair(pop.pair("edd_free", C.RULE_EDD)), "Wartezeitanteil": fmt_pct(0.0),
        "Verspätete Bestellungen": fmt_pct(pop.late_share_pct("edd_free")),
    })
    return rows


def render_rule_panel(prefix, rule, pop, cfg, seed, shown_inst, shown_result):
    """Beschreibung, Kennzahlen (2 x 2) und Gantt einer Regel (je Tab im Regeln-Expander)."""
    st.markdown(C.RULE_DESCRIPTIONS[rule])
    if rule == C.RULE_EDDW:
        st.caption(f"Eingestelltes Fenster: w = {pop.w}" + (" (= EDD)." if pop.w == 1 else "."))
    c = [st.columns(2), st.columns(2)]
    c[0][0].metric("Gewichtete Verspätung", f"{fmt_min(pop.mean_min(rule))} Min.",
                   help=f"Mittel über {pop.n} Instanzen (Seeds 0 bis 79), mit Blockieren.")
    diff = pop.diff_to_edd(rule)
    c[0][1].metric("Differenz zu EDD", "-" if rule == C.RULE_EDD else f"{fmt_pair(diff)} Min.",
                   help="Regel minus EDD, gepaart je Instanz, Mittel ± Standardfehler. Positiv = mehr Verspätung als EDD.")
    c[1][0].metric("Wartezeitanteil", fmt_pct(pop.wait_share_pct(rule)))
    c[1][1].metric("Verspätete Bestellungen", fmt_pct(pop.late_share_pct(rule)))
    render_gantt(f"{prefix}_gantt", cfg.n_aisles, shown_result, shown_inst,
                 shown_caption(seed, E.shown_summary(shown_inst, shown_result)))


def render_comparison_tab(pop, k_rows, rho_rows, exact=None):
    st.dataframe(pd.DataFrame(rule_rows(pop)), width="stretch", hide_index=True)
    st.caption("Differenz = Regel minus EDD (positiv = mehr Verspätung), gepaart über die Instanzen; ± = Standardfehler. "
               "Wartezeitanteil und verspätete Bestellungen sind Mittel über die Instanzen.")
    if exact is not None:
        st.markdown(f"**Exakt (nur gezeigte Kleininstanz):** {exact_headline(exact)}")
    render_core_charts("comparison_tab", k_rows, rho_rows)


def render_core_charts(prefix, k_rows, rho_rows):
    st.plotly_chart(V.advantage_by_k_figure(k_rows), width="stretch", key=f"{prefix}_k_chart")
    st.plotly_chart(V.gain_by_rho_figure(rho_rows), width="stretch", key=f"{prefix}_rho_chart")


def k_table(k_rows):
    return pd.DataFrame([{
        "Kommissionierer": r.k, "Vorteil ohne Blockieren (Min.)": fmt_min(r.adv_off.mean),
        "Vorteil mit Blockieren (Min.)": fmt_min(r.adv_on.mean), "Änderung": fmt_rel_change(r.rel_change_pct),
        "Urteil (gepaart)": {"pos": "Vorteil wächst (belastbar)", "neg": "Vorteil schrumpft (belastbar)",
                             "none": "kein belastbarer Unterschied"}[r.verdict],
    } for r in k_rows])


def rho_table(rho_rows):
    rows = []
    for rho, by_w in rho_rows.items():
        row = {"Konzentration ρ": f"{rho} %"}
        for w, p in by_w.items():
            mark = {"pos": " (hilft)", "neg": " (schadet)", "none": " (n. s.)"}[p.verdict()]
            row[f"w = {w}"] = fmt_pair(p) + mark
        rows.append(row)
    return pd.DataFrame(rows)


def exact_headline(x):
    opt = "Optimum" if x["proven"] else "beste gefundene Lösung"
    price = "-" if x["price_pct"] is None else fmt_pct(x["price_pct"], signed=True)
    pot = "-" if x["potential_pct"] is None else fmt_pct(x["potential_pct"])
    return f"{opt} {fmt_min(x['opt_min'])} Min., {pot} unter EDD; Preis des Blockierens im Optimum {price}."


def render_exact_result(x):
    """Ergebnis des Exakt-Tabs (Werte aus E.exact_summary)."""
    c = [st.columns(2), st.columns(2)]
    if x["proven"]:
        c[0][0].metric("Optimum (mit Blockieren)", f"{fmt_min(x['opt_min'])} Min.",
                       help="Nachweislich optimal im Job-Shop-Modell (CP-SAT).")
    else:
        c[0][0].metric("Beste Lösung (mit Blockieren)", f"{fmt_min(x['opt_min'])} Min.",
                       help=f"Nicht als optimal bewiesen; beste Schranke {fmt_min(x['bound_min'])} Min. - das wahre "
                            "Optimum liegt dazwischen.")
    c[0][1].metric("Optimum ohne Blockieren" if x["proven_free"] else "Beste Lösung ohne Blockieren",
                   f"{fmt_min(x['opt_free_min'])} Min.",
                   help="Dasselbe Modell ohne Gang-Ausschluss (Relaxation): untere Grenze für das Optimum mit Blockieren.")
    both = x["proven"] and x["proven_free"]
    pot_label = "Potenzial ggü. EDD" if x["proven"] else "Potenzial ggü. EDD (mindestens)"
    c[1][0].metric(pot_label, "-" if x["potential_pct"] is None else fmt_pct(x["potential_pct"]),
                   help=f"EDD erreicht {fmt_min(x['edd_min'])} Min. auf dieser Instanz; so viel Verspätung liegt "
                        "zwischen EDD und der exakten Lösung. Eine Einzelinstanz - qualitativ lesen."
                        + ("" if x["proven"] else " Die Lösung ist nicht als optimal bewiesen; das wahre Potenzial ist "
                                                  "mindestens so groß."))
    if both:
        price_label = "Preis des Blockierens im Optimum"
    elif x["proven_free"]:
        price_label = "Preis des Blockierens (höchstens)"
    else:
        price_label = "Preis des Blockierens (Näherung)"
    c[1][1].metric(price_label, "-" if x["price_pct"] is None else fmt_pct(x["price_pct"], signed=True),
                   help="Optimum mit gegenüber Optimum ohne Blockieren: so viel Verspätung ist selbst bei bester "
                        "Planung nicht vermeidbar."
                        + ("" if both else " Nicht bewiesen: die gefundene Lösung kann über dem Optimum liegen, der "
                                           "wahre Preis ist dann kleiner (aber nie negativ)."))
    if not (x["proven"] and x["proven_free"]):
        st.caption(f"Status: {x['status']} (mit Blockieren, beste Schranke {fmt_min(x['bound_min'])} Min.), "
                   f"{x['status_free']} (ohne Blockieren, Schranke {fmt_min(x['bound_free_min'])} Min.). Nicht bewiesene "
                   "Werte sind Näherungen.")
    st.caption(f"EDD mit Fenster (w-Regler) erreicht auf dieser Instanz {fmt_min(x['eddw_min'])} Min.")
