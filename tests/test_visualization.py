"""Figuren: fixedrange-Achsen, Legenden, Balkenzahl gegen das Gangprotokoll, Konsistenz der Farben."""
import pytest

import wfg_constants as C
import wfg_evaluation as E
import wfg_visualization as V
from wfg_scenario import Cfg


def _run(cfg=None, seed=7, rule=C.RULE_EDDW, w=2):
    cfg = cfg or Cfg(n_pickers=4)
    inst, res = E.shown_run(cfg, seed, rule, w)
    return cfg, inst, res


def _locked(fig):
    return fig.layout.xaxis.fixedrange is True and fig.layout.yaxis.fixedrange is True


def test_gantt_axes_are_locked_and_legend_present():
    cfg, inst, res = _run()
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    assert _locked(fig)
    names = {t.name for t in fig.data}
    assert "Kommissionierer wartet am Eingang" in names and "Gang belegt (Farbe = Batch)" in names
    assert fig.layout.legend.orientation == "h"


def test_gantt_has_one_busy_bar_per_aisle_visit_and_one_wait_bar_per_wait():
    cfg, inst, res = _run()
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    visits = sum(len(b["visits"]) for b in inst["batches"])
    waits = sum(1 for log in res["aisle_log"] for entry, _, _, arrive in log if entry > arrive)
    wait_trace = next(t for t in fig.data if t.name == "Kommissionierer wartet am Eingang")
    busy_trace = next(t for t in fig.data if t.text is not None and len(t.x) == visits and t.showlegend is False)
    assert len(busy_trace.x) == visits and len(wait_trace.x) == waits and waits > 0


def test_gantt_wait_total_matches_simulation_wait():
    cfg, inst, res = _run()
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    wait_trace = next(t for t in fig.data if t.name == "Kommissionierer wartet am Eingang")
    assert sum(wait_trace.x) * C.MIN_DS == pytest.approx(res["wait"])


def test_gantt_busy_bars_are_colored_by_batch_and_cover_the_aisle_protocol():
    cfg, inst, res = _run()
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    busy = next(t for t in fig.data if t.showlegend is False)
    expected = [(a, e / 600, (x - e) / 600, C.BATCH_COLORS[b % len(C.BATCH_COLORS)])
                for a, log in enumerate(res["aisle_log"]) for e, x, b, _ in log]
    got = list(zip(busy.y, busy.base, busy.x, busy.marker.color))
    assert got == expected


def test_gantt_without_any_waiting_still_renders():
    cfg, inst, res = _run(Cfg(n_pickers=2, n_orders=20), seed=1, rule=C.RULE_FIFO)
    res = dict(res, aisle_log=[[(e, x, b, e) for e, x, b, _ in log] for log in res["aisle_log"]])   # Warten entfernt
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    assert _locked(fig) and len(next(t for t in fig.data if t.name == "Kommissionierer wartet am Eingang").x) == 0


def test_gantt_axis_labels_every_aisle_top_down():
    cfg, inst, res = _run(Cfg(n_aisles=5, n_pickers=3))
    fig = V.gantt_figure(cfg.n_aisles, res, inst)
    assert list(fig.layout.yaxis.ticktext) == [f"Gang {a}" for a in range(5)] and fig.layout.yaxis.autorange == "reversed"


def test_advantage_by_k_figure_has_both_series_with_error_bars():
    rows = E.k_sweep(Cfg())
    fig = V.advantage_by_k_figure(rows)
    assert _locked(fig) and [t.name for t in fig.data] == ["ohne Blockieren", "mit Blockieren"]
    assert list(fig.data[0].x) == list(range(2, 11))
    assert list(fig.data[1].y) == [r.adv_on.mean for r in rows] and list(fig.data[0].y) == [r.adv_off.mean for r in rows]
    assert all(t.error_y.visible for t in fig.data)
    assert fig.data[0].marker.color == C.NO_BLOCKING_COLOR and fig.data[1].marker.color == C.BLOCKING_COLOR
    assert "K=6" in fig.layout.xaxis.ticktext[4] and "57" in fig.layout.xaxis.ticktext[4]      # relative Aenderung unter dem Balken


def test_gain_by_rho_figure_marks_non_significant_bars_pale():
    rows = E.rho_sweep(Cfg(n_pickers=4))
    fig = V.gain_by_rho_figure(rows)
    assert _locked(fig) and [t.name for t in fig.data] == ["w = 2", "w = 4", "w = 8"]
    assert list(fig.data[0].x) == ["ρ = 0 %", "ρ = 50 %", "ρ = 100 %"]
    for trace, w in zip(fig.data, (2, 4, 8)):
        for opacity, rho in zip(trace.marker.opacity, (0, 50, 100)):
            assert opacity == (1.0 if rows[rho][w].verdict() != "none" else 0.35)
        assert trace.marker.color == C.WINDOW_COLORS[w]


def test_gain_by_rho_figure_with_artificial_cells_flips_opacity_at_two_standard_errors():
    rows = {0: {2: E.Pair(2.0, 1.0), 4: E.Pair(2.01, 1.0), 8: E.Pair(-2.01, 1.0), 6: E.Pair(-2.0, 1.0)}}
    fig = V.gain_by_rho_figure(rows)
    got = {w: t.marker.opacity[0] for w, t in zip((2, 4, 8, 6), fig.data)}
    assert got == {2: 0.35, 4: 1.0, 8: 1.0, 6: 0.35}                              # belastbar positiv UND negativ deckend


def test_relative_change_labels_never_show_minus_zero():
    assert V.rel_label(-0.1) == "±0 %" and V.rel_label(0.4) == "±0 %" and V.rel_label(0.0) == "±0 %"
    assert V.rel_label(-0.6) == "−1 %" and V.rel_label(-57.4) == "−57 %" and V.rel_label(12.0) == "+12 %"
    import wfg_ui_panel as UI
    assert UI.fmt_rel_change(-0.1) == "±0 %" and UI.fmt_rel_change(-20.1) == "-20 %" and UI.fmt_rel_change(5.6) == "+6 %"
