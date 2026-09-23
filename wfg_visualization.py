"""Plotly-Figuren der Wellenfreigabe-Demo: Gang-Belegung (Gantt) der gezeigten Instanz, Vorteil der Fristenregel je
Kommissionierer-Zahl, Gewinn des Konflikt-Fensters je Konzentration rho.

Konventionen des Portfolios: Achsen `fixedrange` (Touch-Scrollen), Vorlage plotly_white, Farbcodierung Regeln und
Batches ueber alle Figuren konsistent, Gantt MIT Legende. Plotly wird erst in den Funktionen importiert, damit die
reine Rechnung ohne Plotly testbar bleibt."""
import wfg_constants as C

LEGEND_BOTTOM = dict(orientation="h", yref="container", yanchor="bottom", y=0.0, x=0)


def _lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _min(ds):
    return ds / C.MIN_DS


def rel_label(v):
    """Relative Aenderung als Achsenbeschriftung: Minuszeichen U+2212, unter 0,5 % Betrag '±0 %' statt '-0 %'."""
    text = f"{v:+.0f}"
    return "±0 %" if text in ("+0", "-0") else f"{text} %".replace("-", "−")


def _de(v, digits=1):
    return f"{v:.{digits}f}".replace(".", ",")


# ---------------------------------------------------------------------------------------------------
# Gang-Belegung (Plan Abschnitt 4/6): farbige Balken je Batch, grauer Streifen = Warten am Gangeingang
# ---------------------------------------------------------------------------------------------------
def gantt_figure(n_aisles, result, inst):
    """result: simulate(..., log=True); inst: die Instanz. Ein Balken je Gangbesuch (Farbe = Batch), darauf ein
    grauer Streifen je Wartezeit am Eingang (Ankunft bis Einfahrt)."""
    import plotly.graph_objects as go

    busy_x, busy_base, busy_y, busy_col, busy_text, busy_hover = [], [], [], [], [], []
    wait_x, wait_base, wait_y, wait_hover = [], [], [], []
    for aisle, log in enumerate(result["aisle_log"]):
        for entry, exit_, batch, arrive in log:
            due = inst["batches"][batch]["due"]
            comp = result["comp"][batch]
            busy_x.append(_min(exit_ - entry))
            busy_base.append(_min(entry))
            busy_y.append(aisle)
            busy_col.append(C.BATCH_COLORS[batch % len(C.BATCH_COLORS)])
            busy_text.append(f"B{batch}")
            busy_hover.append(f"Batch {batch} in Gang {aisle}<br>belegt {_de(_min(entry))} bis {_de(_min(exit_))} Min."
                              f"<br>Frist {_de(_min(due))} Min., fertig {_de(_min(comp))} Min.")
            if entry > arrive:
                wait_x.append(_min(entry - arrive))
                wait_base.append(_min(arrive))
                wait_y.append(aisle)
                wait_hover.append(f"Batch {batch} wartet vor Gang {aisle}<br>{_de(_min(arrive))} bis "
                                  f"{_de(_min(entry))} Min. ({_de(_min(entry - arrive))} Min.)")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=busy_x, base=busy_base, y=busy_y, orientation="h", width=0.8, marker=dict(color=busy_col),
        text=busy_text, textposition="inside", insidetextanchor="middle", textfont=dict(color="white", size=10),
        name="Gang belegt (Farbe = Batch)", hovertext=busy_hover, hoverinfo="text", showlegend=False))
    # Warten am Eingang als Streifen im unteren Teil der Gangzeile, OBEN drauf: die Wartezeit faellt fast immer in die
    # Belegung des Vorgaengers und wuerde sonst hinter dessen Balken verschwinden.
    fig.add_trace(go.Bar(
        x=wait_x, base=wait_base, y=wait_y, orientation="h", width=0.3, offset=0.1, marker=dict(color=C.WAIT_COLOR),
        name="Kommissionierer wartet am Eingang", hovertext=wait_hover, hoverinfo="text"))
    # Legendeneintrag fuer die Batchfarben (ein Sammelbalken statt einer Zeile je Batch)
    fig.add_trace(go.Bar(x=[None], y=[None], orientation="h", marker=dict(color=C.BATCH_COLORS[0]),
                         name="Gang belegt (Farbe = Batch)"))
    fig.update_layout(template="plotly_white", height=max(C.CHART_HEIGHT, 90 + 34 * n_aisles), barmode="overlay",
                      margin=dict(t=20, b=70), legend=LEGEND_BOTTOM, xaxis_title="Zeit in Minuten",
                      uniformtext=dict(minsize=8, mode="hide"), bargap=0.15)
    fig.update_yaxes(tickmode="array", tickvals=list(range(n_aisles)),
                     ticktext=[f"Gang {a}" for a in range(n_aisles)], autorange="reversed")
    fig.update_xaxes(rangemode="tozero")
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Kernabschnitt 1: Vorteil der Fristenregel ohne und mit Blockieren je Kommissionierer-Zahl
# ---------------------------------------------------------------------------------------------------
def advantage_by_k_figure(rows):
    import plotly.graph_objects as go

    ticks = [f"K={r.k}<br>{rel_label(r.rel_change_pct)}" for r in rows]
    xs = [r.k for r in rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=xs, y=[r.adv_off.mean for r in rows], name="ohne Blockieren", marker_color=C.NO_BLOCKING_COLOR,
        error_y=dict(type="data", array=[r.adv_off.se for r in rows], visible=True),
        hovertemplate="K=%{x}, ohne Blockieren<br>Vorteil %{y:.1f} Min.<extra></extra>"))
    fig.add_trace(go.Bar(
        x=xs, y=[r.adv_on.mean for r in rows], name="mit Blockieren", marker_color=C.BLOCKING_COLOR,
        error_y=dict(type="data", array=[r.adv_on.se for r in rows], visible=True),
        hovertemplate="K=%{x}, mit Blockieren<br>Vorteil %{y:.1f} Min.<extra></extra>"))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, barmode="group", margin=dict(t=20, b=70),
                      legend=LEGEND_BOTTOM, yaxis_title="Vorteil EDD gg. FIFO (gewichtete Min.)",
                      xaxis_title="Kommissionierer (darunter: relative Änderung durch das Blockieren)")
    fig.update_xaxes(tickmode="array", tickvals=xs, ticktext=ticks)
    return _lock_axes(fig)


# ---------------------------------------------------------------------------------------------------
# Kernabschnitt 2: Gewinn des Konflikt-Fensters je Konzentration rho
# ---------------------------------------------------------------------------------------------------
def gain_by_rho_figure(rho_rows):
    """rho_rows: {rho_pct: {w: Pair}}. Balken ausserhalb von 2 Standardfehlern deckend, sonst blass."""
    import plotly.graph_objects as go

    rhos = list(rho_rows)
    windows = list(next(iter(rho_rows.values())))
    fig = go.Figure()
    for w in windows:
        pairs = [rho_rows[r][w] for r in rhos]
        fig.add_trace(go.Bar(
            x=[f"ρ = {r} %" for r in rhos], y=[p.mean for p in pairs], name=f"w = {w}",
            marker=dict(color=C.WINDOW_COLORS.get(w, "#7d5ba6"), opacity=[1.0 if p.verdict() != "none" else 0.35 for p in pairs]),
            error_y=dict(type="data", array=[p.se for p in pairs], visible=True),
            hovertemplate=f"w = {w}, %{{x}}<br>Gewinn %{{y:+.1f}} Min.<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="#5b6b80", width=1))
    fig.update_layout(template="plotly_white", height=C.CHART_HEIGHT, barmode="group", margin=dict(t=20, b=70),
                      legend=LEGEND_BOTTOM, yaxis_title="Gewinn des Fensters ggü. EDD (gewichtete Min.)",
                      xaxis_title="Konzentration der Express-Positionen auf vordere Gänge")
    return _lock_axes(fig)
