"""
Kommissionierwellen: Fristen und Gangblockaden - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Erweiterung der Batching-Demo (order_batch-demo, Lager-Linie): Kommissionierer arbeiten vorgebildete Batches mit
Versandfristen ab und laufen dabei durch schmale Gaenge, in denen sie sich nicht ueberholen koennen (jeder Gang eine
Einzelressource mit FIFO-Warteschlange am Eingang). Formal ein Job-Shop mit Fristen und Obergrenze paralleler
Auftraege; ohne Blockieren faellt das Modell auf parallele Maschinen mit Fristen zurueck (warehouse-transfer-demo).
Regeln: FIFO, EDD, EDD mit Konflikt-Fenster w; exakt (CP-SAT) nur fuer Kleininstanzen.

Lauffaehig mit: streamlit run app.py
"""
import time

import streamlit as st

import wfg_constants as C
import wfg_cp as CP
import wfg_evaluation as E
import wfg_ui_panel as UI
import wfg_visualization as VZ
from wfg_pdf_export import generate_wfg_pdf
from wfg_presets import (apply_preset, bounds, init_session_state_defaults, load_permalink_settings,
                         randomize_seed, SETTING_SPECS, sync_query_params)

st.set_page_config(page_title="Kommissionierwellen – Sebastian Hanisch", layout="wide")

SCENARIO_KEYS = list(SETTING_SPECS)


@st.cache_data(show_spinner=False, max_entries=64)
def _population(aisles, pickers, orders, tau, express_pct, hot_corr_pct, w):
    return E.evaluate_population(E.cfg_from_controls(aisles, pickers, orders, tau, express_pct, hot_corr_pct), w)


@st.cache_data(show_spinner=False, max_entries=32)
def _k_sweep(aisles, orders, tau, express_pct, hot_corr_pct):
    """Unabhaengig von Kommissionierer-Zahl und Fenster: der Sweep variiert K selbst."""
    return E.k_sweep(E.cfg_from_controls(aisles, C.PICKERS_DEFAULT, orders, tau, express_pct, hot_corr_pct))


@st.cache_data(show_spinner=False, max_entries=32)
def _rho_sweep(aisles, pickers, orders, tau, express_pct):
    """Unabhaengig von rho und Fenster: der Sweep variiert beides selbst."""
    return E.rho_sweep(E.cfg_from_controls(aisles, pickers, orders, tau, express_pct, C.HOT_CORR_PCT_DEFAULT))


st.title("🚧 Kommissionierwellen: Fristen und Gangblockaden")
st.markdown(
    """
Mehr Kommissionierer bedeuten nicht proportional mehr Durchsatz: In schmalen Gängen **blockieren** sie sich, und das trifft ausgerechnet die Batches mit knappen **Fristen**. Die Demo zeigt, wie viel das
Blockieren kostet, wie viel vom Vorteil einer Fristenregel übrig bleibt und wann sich ein **Konflikt-Fenster** lohnt, das Gangkonflikte gezielt vermeidet – mit dem exakten Optimum als Maßstab für kleine Fälle.
Eine **Erweiterung der Batching-Demo** (`order_batch-demo`): sie hebt deren stillschweigende Annahmen auf, dass Batches ohne Fristen bearbeitet werden und dass sich gleichzeitig arbeitende Kommissionierer nicht
behindern. Wie das Modell funktioniert, steht im Expander „Wie funktioniert diese Demo?" weiter unten, die formale Beschreibung im Expander „📐 Mathematische Formulierung". Ohne Blockieren ist das Modell die
`warehouse-transfer-demo` (Fristen-Disposition), das Blockieren auf gemeinsamer Bahn zeigt die `quaycrane-demo` in einer Dimension.
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_names = list(C.PRESETS)
for row in (preset_names[:3], preset_names[3:]):
    cols = st.columns(3)
    for col, name in zip(cols, row):
        with col:
            st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    aisles = st.slider("Gänge", *bounds("aisles_slider"), key="aisles_slider",
                       help="Je weniger Gänge bei gleicher Kommissionierer-Zahl, desto mehr Blockieren.")
    pickers = st.slider("Kommissionierer", *bounds("pickers_slider"), key="pickers_slider",
                        help="Gleichzeitig arbeitende Kommissionierer. Minimum 2, damit Blockieren nie trivial null ist.")
    orders = st.slider("Bestellungen", *bounds("orders_slider"), key="orders_slider",
                       help="Instanzgröße; beim Standard etwa 17 Batches. Der Exakt-Tab rechnet nur bis "
                            f"{C.EXACT_MAX_ORDERS} Bestellungen und {C.EXACT_MAX_BATCHES} Batches.")
    tau = st.slider("Fristendruck", *bounds("tau_slider"), step=C.TAU_STEP, key="tau_slider", format="%.1f",
                    help="Steuert alle Fristen relativ zur geschätzten Gesamtdauer; kleiner = enger.")
    express_pct = st.slider("Express-Anteil", *bounds("express_slider"), key="express_slider", format="%d%%",
                            help="Anteil der Express-Bestellungen (Gewicht 3, engere Frist). Minimum 5 %, damit die "
                                 "Konzentration nie wirkungslos ist.")
    hot_corr_pct = st.slider("Konzentration auf vordere Gänge", *bounds("hot_corr_slider"), step=C.HOT_CORR_STEP,
                             key="hot_corr_slider", format="%d%%",
                             help="ρ: Anteil der Express-Positionen, die in den 3 vordersten („heißen“) Gängen liegen. "
                                  "Der Schlüssel zur Wechselwirkung zwischen Dringlichkeit und Gangkonflikt.")
    window = st.slider("Konflikt-Fenster w", *bounds("window_slider"), key="window_slider",
                       help="Unter den w dringendsten Batches wird der mit den wenigsten Gangkonflikten freigegeben. "
                            "w = 1 ist exakt EDD; größeres w opfert mehr Dringlichkeit für weniger Konflikte.")
    seed = st.number_input("Seed", *bounds("seed_input"), key="seed_input", step=1,
                           help="Bestimmt die gezeigte Instanz (Gang-Belegung). Die Kennzahlen stehen auf 80 "
                                "Instanzen (Seeds 0 bis 79 des Reglerstands).")
    st.button("🎲 Neue Instanz", width="stretch", on_click=randomize_seed, help="Würfelt einen neuen Seed.")

sync_query_params({key: st.session_state[key] for key in SCENARIO_KEYS})

aisles, pickers, orders, express_pct, hot_corr_pct, window, seed = (
    int(aisles), int(pickers), int(orders), int(express_pct), int(hot_corr_pct), int(window), int(seed))
tau = round(float(tau), 1)

cfg = E.cfg_from_controls(aisles, pickers, orders, tau, express_pct, hot_corr_pct)
pop = _population(aisles, pickers, orders, tau, express_pct, hot_corr_pct, window)
k_rows = _k_sweep(aisles, orders, tau, express_pct, hot_corr_pct)
rho_rows = _rho_sweep(aisles, pickers, orders, tau, express_pct)
gain = pop.gain()

shown_inst, shown_result = E.shown_run(cfg, seed, C.RULE_EDDW, window)
shown_summary = E.shown_summary(shown_inst, shown_result)

# Exakte Referenz (nur gezeigte Kleininstanz): Ergebnis gilt nur fuer genau diese Instanz
inst_key = (aisles, pickers, orders, tau, express_pct, hot_corr_pct, seed)
exact_raw = st.session_state.get("exact_raw")
exact_now = None
if exact_raw is not None and exact_raw["key"] == inst_key:
    exact_now = E.exact_summary(shown_inst, window, exact_raw["opt"], exact_raw["opt_free"])

# ---------------------------------------------------------------------------------------------------
# Hauptansicht
# ---------------------------------------------------------------------------------------------------
st.markdown("## 🚧 Was kostet das Blockieren – und lohnt sich Konfliktvermeidung?")
st.caption(f"{aisles} Gänge, {pickers} Kommissionierer, {orders} Bestellungen (etwa {pop.n_batches:.0f} Batches), "
           f"Fristendruck {UI.fmt_min(tau)}, Express {express_pct} %, ρ = {hot_corr_pct} %, Fenster w = {window}. "
           f"Kennzahlen: Mittel über {pop.n} Instanzen (Seeds 0 bis 79), Werte in gewichteten Verspätungsminuten.")

metric_rows = [st.columns(2), st.columns(2)]
UI.render_metrics(metric_rows[0] + metric_rows[1], pop)
UI.render_message(E.message_state(pop.wait_share_pct(C.RULE_EDD), gain), pop, gain)

st.markdown("#### 🚧 Gang-Belegung über die Zeit")
UI.render_gantt("main_gantt", aisles, shown_result, shown_inst, UI.shown_caption(seed, shown_summary))

pdf_slot = st.container()

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
st.markdown("### 📐 Wie viel Vorteil bleibt der Fristenregel, wenn sich Kommissionierer blockieren?")
st.markdown(
    """
Kernfrage dieser Demo: Eine Fristenregel (EDD) schlägt FIFO deutlich, solange sich Kommissionierer nicht behindern. Mit Blockieren schrumpft dieser Vorteil – je mehr Kommissionierer auf denselben
Gängen arbeiten, desto stärker. Und das Konflikt-Fenster? Es hilft nur bei engen Fristen **und** auf wenige heiße Gänge konzentrierter Dringlichkeit, sonst schadet es. Beides live für Ihre übrigen Einstellungen.
"""
)
st.markdown("**Vorteil der Fristenregel je Kommissionierer-Zahl** (EDD gegenüber FIFO, ohne und mit Blockieren)")
st.plotly_chart(VZ.advantage_by_k_figure(k_rows), width="stretch", key="core_k_chart")
here = next((r for r in k_rows if r.k == pickers), None)
if here is not None:
    change = (f"({UI.fmt_rel_change(here.rel_change_pct)}; gepaarte Änderung {UI.fmt_pair(here.change)} Min., "
              f"{UI.VERDICT_TEXT[here.verdict]})")
    span = f"von {UI.fmt_min(here.adv_off.mean)} auf {UI.fmt_min(here.adv_on.mean)} Min."
    if here.verdict == "none":
        st.info(f"Bei Ihren {pickers} Kommissionierern verändert das Blockieren den Vorteil der Fristenregel nicht "
                f"belastbar: {span} {change}.")
    else:
        verb = "wächst" if here.verdict == "pos" else "schrumpft"
        st.info(f"Bei Ihren {pickers} Kommissionierern {verb} der Vorteil der Fristenregel durch das Blockieren {span} "
                f"{change}.")
st.dataframe(UI.k_table(k_rows), width="stretch", hide_index=True)

st.markdown("**Konflikt-Fenster über die Konzentration ρ** (Gewinn gegenüber EDD, für w = 2, 4 und 8)")
st.plotly_chart(VZ.gain_by_rho_figure(rho_rows), width="stretch", key="core_rho_chart")
counts = E.verdict_counts(rho_rows)
st.info(f"Von {sum(counts.values())} Zellen (3 Konzentrationen × 3 Fenster) hilft das Fenster in {counts['pos']} "
        f"belastbar, schadet in {counts['neg']} belastbar und zeigt in {counts['none']} keinen belastbaren Unterschied "
        f"(deckende Balken = mehr als 2 Standardfehler). Das Vorzeichen hängt vom Regime ab, nicht von der Regel allein.")
st.dataframe(UI.rho_table(rho_rows), width="stretch", hide_index=True)
st.caption(f"Basis: {pop.n} Instanzen je Zelle, gepaarte Differenzen, Mittel ± Standardfehler; keine Prozentwerte ohne "
           f"Streuung. Rechenzeit gemessen: 80 Simulationen zusammen etwa 6 ms, 80 Instanzen erzeugen etwa 60 ms, die "
           f"größte Einzelinstanz (100 Bestellungen, 12 Gänge, 10 Kommissionierer) 2 ms – ohne Knopf, live bei jedem "
           f"Reglerzug (Ergebnisse je Einstellung zwischengespeichert).")

with pdf_slot:
    st.download_button(
        "📄 Ergebnis als PDF herunterladen",
        data=generate_wfg_pdf(dict(aisles=aisles, pickers=pickers, orders=orders, tau=tau, express_pct=express_pct,
                                   hot_corr_pct=hot_corr_pct, window=window), seed, pop, k_rows, rho_rows,
                              shown_summary, exact_now),
        file_name="kommissionierwellen_ergebnis.pdf", mime="application/pdf", key="primary_pdf_download",
        help="Einstellungen, Kennzahlen, Regelvergleich, Vorteil je Kommissionierer-Zahl, Fenster-Gewinn je ρ.")

st.markdown("---")

# ---------------------------------------------------------------------------------------------------
# Regeln im Vergleich
# ---------------------------------------------------------------------------------------------------
with st.expander("🔧 Wie wir das erreichen – Regeln im Vergleich"):
    tabs = st.tabs([C.RULE_LABELS[C.RULE_FIFO], C.RULE_LABELS[C.RULE_EDD], C.RULE_LABELS[C.RULE_EDDW],
                    C.EXACT_TAB_LABEL, C.COMPARISON_TAB_LABEL])
    for tab, rule, prefix in zip(tabs[:3], C.RULE_KEYS, ("tab_fifo", "tab_edd", "tab_eddw")):
        with tab:
            inst_r, res_r = (shown_inst, shown_result) if rule == C.RULE_EDDW else E.shown_run(cfg, seed, rule, window)
            UI.render_rule_panel(prefix, rule, pop, cfg, seed, inst_r, res_r)

    with tabs[3]:
        st.markdown(
            "Googles Open-Source-Solver OR-Tools (CP-SAT) sucht direkt nach dem bestmöglichen Gesamtplan des "
            "Job-Shop-Modells (Gangbesuche als Intervalle, ein Gang bedient einen Batch zur Zeit, höchstens so viele "
            "Batches gleichzeitig wie Kommissionierer) – für die **gezeigte Einzelinstanz**, mit und ohne Blockieren. "
            "Das ist der Maßstab für das Rest-Potenzial und den Preis des Blockierens, den selbst die beste Planung "
            "zahlt. Nur für Kleininstanzen (bis etwa 10 Batches, 30 Bestellungen); Button-gesteuert mit Zeitlimit und "
            "Abkühlpause. In der Vorab-Messung (10 Kleininstanzen je ρ, 12-s-Limit) lag das Optimum 19,6 % (ρ = 0) "
            "bzw. 13,0 % (ρ = 1) unter EDD und zahlte 29,2 % bzw. 35,1 % Aufpreis fürs Blockieren."
        )
        if not CP.exact_size_ok(shown_inst):
            st.info(f"Die gezeigte Instanz ({orders} Bestellungen, {len(shown_inst['batches'])} Batches) ist für den "
                    f"exakten Solver zu groß: erlaubt sind bis zu {C.EXACT_MAX_ORDERS} Bestellungen und "
                    f"{C.EXACT_MAX_BATCHES} Batches (CP-SAT beweist bei etwa 7 bis 9 Batches, bei 17 nicht). "
                    "Zum Ausprobieren die Zahl der Bestellungen verkleinern, z. B. auf 24.")
        else:
            last_run = st.session_state.get("exact_last_run_at")
            remaining = 0.0
            if last_run is not None:
                remaining = max(0.0, C.EXACT_COOLDOWN_SECONDS - (time.time() - last_run))

            @st.fragment(run_every=1.0 if remaining > 0 else None)
            def _render_exact_tab(remaining=remaining):
                if remaining > 0:
                    left = C.EXACT_COOLDOWN_SECONDS - (time.time() - st.session_state["exact_last_run_at"])
                    if left <= 0:
                        st.rerun()                     # Abkuehlpause vorbei: Knopf wieder freigeben
                    remaining = max(0.0, left)
                clicked = st.button(f"Mit OR-Tools lösen (bis zu {C.EXACT_TIME_LIMIT:.0f} s je Lösung)",
                                    key="exact_solve_button", disabled=remaining > 0)
                if remaining > 0:
                    st.caption(f"Kurze Abkühlpause aktiv – noch {remaining:.0f} s.")
                if clicked:
                    try:
                        with st.spinner("OR-Tools löst (mit und ohne Blockieren) ..."):
                            opt = CP.solve_cp(shown_inst, blocking=True, time_limit=C.EXACT_TIME_LIMIT,
                                              workers=C.EXACT_WORKERS)
                            opt_free = CP.solve_cp(shown_inst, blocking=False, time_limit=C.EXACT_TIME_LIMIT,
                                                   workers=C.EXACT_WORKERS)
                    except ImportError:
                        st.error("OR-Tools ist in dieser Umgebung nicht installiert – der exakte Vergleich ist "
                                 "nicht verfügbar. Die übrigen Tabs funktionieren unverändert.")
                        return
                    st.session_state["exact_raw"] = dict(key=inst_key, opt=opt, opt_free=opt_free)
                    st.session_state["exact_last_run_at"] = time.time()
                    # Vollstaendiger Rerun: Vergleich-Tab und PDF lesen das Ergebnis ebenfalls
                    st.rerun()

            _render_exact_tab()

            raw = st.session_state.get("exact_raw")
            if raw is None:
                st.info("Noch nicht gelöst.")
            elif raw["key"] != inst_key:
                st.info("Die Einstellungen haben sich geändert – bitte erneut lösen.")
            else:
                UI.render_exact_result(exact_now)

    with tabs[4]:
        UI.render_comparison_tab(pop, k_rows, rho_rows, exact_now)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        """
**Lager, Batches, Route.** Ein Parallelgang-Lager (Depot vorn links, Ganglänge 30 m, Gangabstand 3 m, 1,3 m/s, 8 s je Pickposition). Die Bestellungen (je 2 bis 6 Positionen, alle zum Zeitpunkt 0 verfügbar) sind
vorab zu **Batches** mit höchstens 15 Positionen gebündelt – nach Gangähnlichkeit, aber **ohne Rücksicht auf Fristen**. Ein Kommissionierer arbeitet einen Batch in **S-Shape** ab: aufsteigende Gänge, alternierende
Richtung, jeder Gang mit Positionen wird ganz durchquert, bei ungerader Gangzahl der letzte als Sackgasse, am Ende zurück zum Depot.

**Gang als Einzelressource.** In einem schmalen Gang kann niemand überholen: jeder Gang bedient einen Kommissionierer zur Zeit, wer ankommt, wartet in einer FIFO-Warteschlange am Eingang (der graue Streifen in der
Gang-Belegung). Die Querwege vorn und hinten sind frei. Wird ein Kommissionierer frei, bekommt er sofort den nächsten Batch.

**Fristen.** Jede Bestellung hat eine Frist relativ zur geschätzten Gesamtdauer (Fristendruck: kleiner = enger); Express-Bestellungen (Gewicht 3) haben engere Fristen. Die Frist eines Batches ist die früheste Frist
seiner Bestellungen; Ziel ist die **gewichtete Gesamtverspätung** in Minuten.

**Drei Regeln plus ein exakter Maßstab.** **FIFO** gibt die Batches in Bildungsreihenfolge frei, **EDD** immer den mit der frühesten Frist – blind dafür, wo andere Kommissionierer gerade sind. **EDD mit Konflikt-Fenster w**
betrachtet die w dringendsten Batches und nimmt den mit den wenigsten Gangkonflikten zu gerade aktiven Batches (w = 1 ist EDD). **Exakt (CP-SAT)** liefert für Kleininstanzen das Optimum.

**Warum Blockieren mit dem Verhältnis Kommissionierer zu Gängen wächst und Fristenregeln entwertet.** Je mehr Kommissionierer sich dieselben Gänge teilen, desto öfter warten sie am Eingang – und die Wartezeit
verlängert die Batches, gerade die dringenden. Damit schrumpft der Vorteil, den EDD gegenüber FIFO hat (Grafik im Kernabschnitt): Ohne das Blockier-Modell würde man den Wert der Fristenregel bei vielen
Kommissionierern deutlich überschätzen.

**Warum Konfliktvermeidung nur bei enger Frist und konzentrierter Dringlichkeit hilft.** Die **heißen Gänge** (die 3 vordersten) koppeln Dringlichkeit und Gangkonflikt: Sind die Express-Positionen dort
konzentriert (ρ hoch), schickt eine reine Fristenregel mehrere Kommissionierer gleichzeitig in dieselben Gänge – das Fenster kann das entschärfen. Sind die Fristen locker oder die Dringlichkeit unabhängig von den Gängen,
opfert das Fenster Dringlichkeit für Konfliktvermeidung, die dann nichts bringt. Deshalb formuliert die Hauptansicht eine **bedingte Aussage** statt eines Siegers – und das Fenster holt auch im günstigen Fall nur
einen Teil des Blockierens zurück.

**Wie die Zahlen entstehen.** Alle Instanzen sind deterministisch (Seed). Die Kennzahlen stehen auf 80 Instanzen (Seeds 0 bis 79), Vergleiche sind gepaart je Instanz, angegeben als Mittel ± Standardfehler; ein
Vorzeichen gilt nur ab 2 Standardfehlern. Der Seed bestimmt nur die gezeigte Instanz (Gang-Belegung), einen Einzelfall.

**Grenzen dieses Modells** (bewusst so gewählt, damit die Aussage ehrlich bleibt):

- **Stark stilisiert** – S-Shape mit ganzer Gangdurchquerung, Einzelressource Gang, alle Bestellungen zum Zeitpunkt 0 (keine Ankünfte über die Zeit), feste Kommissionierer-Zahl, frist-blind vorgebildete Batches.
- **Nicht kalibriert** – ρ, heiße Gänge und Fristenverteilung sind synthetisch, nicht an einem echten Lager. Die Kernaussage (das Vorzeichen des Fenster-Effekts hängt von Fristendruck und Dringlichkeitskonzentration ab)
  ist robust über die getesteten Zellen, die Prozentwerte sind es nicht.
- **Exakte Referenz nur für Kleininstanzen** – für die Standardgröße (etwa 17 Batches) ist das Optimum unbekannt, das Potenzial dort nur abschätzbar.
- **Einfache Fenster-Regel** – eine echte blockier-bewusste Routenplanung (Besuchsreihenfolge an freie Gänge anpassen) ist nicht enthalten und könnte mehr vom Potenzial heben.
        """
    )

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Batches und Besuche.** Batch $b$ hat Besuche $i = 0, \dots, m_b-1$ mit Gang $a_i$ und Dauer $d_i$ (Gehen durch den Gang plus Pickzeiten) sowie Wege $w_i$ (Querweg zum nächsten Gang). Startzeit $S_b$ (der
Kommissionierer verlässt das Depot), Besuchsstarts $s_i$, Ende $E_b$ (zurück am Depot):
$$s_0 \ge S_b + w_0, \qquad s_i \ge s_{i-1} + d_{i-1} + w_i, \qquad E_b \ge s_{m_b-1} + d_{m_b-1} + w_{ret}.$$

**Blockieren.** Je Gang $a$ gilt NoOverlap über alle Besuchsintervalle $[s_i, s_i + d_i)$ in diesem Gang; höchstens $K$ Batches gleichzeitig (Cumulative über die Batch-Intervalle $[S_b, E_b]$).

**Ziel.** $\min \sum_o \omega_o \cdot \max(0,\ E_{b(o)} - f_o)$ mit Frist $f_o$ und Gewicht $\omega_o$ (Express 3, sonst 1); die Frist eines Batches ist $\min_{o \in b} f_o$.

**Zwei Sonderfälle.** Ohne NoOverlap sind es parallele Maschinen mit Fristen (List-Scheduling; in den Tests unabhängig nachgerechnet, Modell der `warehouse-transfer-demo`). Mit NoOverlap ist es ein Job-Shop mit Fristen
und Obergrenze paralleler Aufträge; die Blockier-Bedingung auf einer gemeinsamen Bahn ist das Modell der `quaycrane-demo` in einer Dimension. Bei $K = 1$ tritt nie Blockieren auf.

**Regeln.** FIFO: $\arg\min_b \text{Bildungsindex}(b)$. EDD: $\arg\min_b (f_b, b)$. EDD mit Fenster $w$: sei $W$ die Menge der $w$ Batches mit den frühesten Fristen unter den wartenden; der Konflikt-Wert eines
Kandidaten $c$ ist $\text{conf}(c) = \sum_{a \in \text{aktiv}} |A(c) \cap R(a)|$ mit den Gängen $A(c)$ des Kandidaten und den noch zu besuchenden Gängen $R(a)$ des aktiven Batches $a$; gewählt wird
$\arg\min_{c \in W} (\text{conf}(c), f_c, c)$. Für $w = 1$ ist das EDD.

**Statistik.** Für zwei Regeln $r, r'$ und Instanzen $j = 1..80$ ist $\Delta_j = z_j(r) - z_j(r')$ die gepaarte Differenz der gewichteten Verspätung; berichtet werden $\bar\Delta$ und $\text{SE} = s_\Delta / \sqrt{80}$
(in Minuten). Ein Vorzeichen gilt als belastbar, wenn $|\bar\Delta| > 2\,\text{SE}$.

Implementiert in `wfg_scenario.py` (Instanz, Batching, Route), `wfg_sim.py` (Ereignissimulation, Regeln), `wfg_cp.py` (CP-SAT, Größenprüfung) und `wfg_evaluation.py` (Population, gepaarte Urteile, Sweeps).
        """
    )

st.markdown("---")

st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning. Interesse an einer maßgeschneiderten Lösung für "
    "Ihr Unternehmen? [Kontakt aufnehmen](https://sebastianhanisch.net/kontakt.html)"
)
