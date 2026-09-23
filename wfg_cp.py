"""Exakte Referenz (CP-SAT) fuer Kleininstanzen: Job-Shop-artiges Modell mit Cumulative(K) ueber die Batches.

`solve_cp` UNVERAENDERT uebernommen aus lager-planung/messreihe_wellen_konflikt/wellen.py. `ortools` wird
erst in der Funktion importiert, damit die App auch dann startet, wenn der Solver fehlt (nur der Exakt-Tab
braucht ihn). Dazu die Groessenpruefung des Exakt-Tabs (Plan Abschnitt 8)."""

from __future__ import annotations

import wfg_constants as C


def exact_size_ok(inst: dict) -> bool:
    """CP-SAT beweist bei etwa 7-9 Batches, bei 17 nicht (Plan Abschnitt 13): nur Kleininstanzen."""
    return len(inst["batches"]) <= C.EXACT_MAX_BATCHES and len(inst["orders"]) <= C.EXACT_MAX_ORDERS


def solve_cp(inst: dict, K: int | None = None, blocking: bool = True, time_limit: float = 20.0,
             workers: int = 8) -> dict:
    """Exakte Referenz: Job-Shop-artiges Modell. Je Batch ein Startzeitpunkt (Kommissionierer verlaesst das
    Depot) und ein Ende (zurueck am Depot); je Gangbesuch ein Intervall fester Laenge mit Mindestabstaenden
    (Wartezeit erlaubt); NoOverlap je Gang (nur bei blocking); Cumulative(K) ueber die Batch-Intervalle."""
    from ortools.sat.python import cp_model

    B = inst["batches"]
    K = K if K is not None else inst["K"]
    H = sum(b["D"] for b in B) + 1
    m = cp_model.CpModel()
    S, E, batch_iv, aisle_iv = [], [], [], {}
    for bi, b in enumerate(B):
        s0 = m.NewIntVar(0, H, f"S{bi}")
        e0 = m.NewIntVar(0, H, f"E{bi}")
        size = m.NewIntVar(0, H, f"z{bi}")
        batch_iv.append(m.NewIntervalVar(s0, size, e0, f"biv{bi}"))
        S.append(s0)
        E.append(e0)
        prev_end = None
        for i, (a, dur) in enumerate(b["visits"]):
            st = m.NewIntVar(0, H, f"s{bi}_{i}")
            iv = m.NewFixedSizeIntervalVar(st, dur, f"v{bi}_{i}")
            aisle_iv.setdefault(a, []).append(iv)
            if i == 0:
                m.Add(st >= s0 + b["walks"][0])
            else:
                m.Add(st >= prev_end + b["walks"][i])
            prev_end = st + dur
        m.Add(e0 >= prev_end + b["walks"][-1])
    if blocking:
        for ivs in aisle_iv.values():
            m.AddNoOverlap(ivs)
    m.AddCumulative(batch_iv, [1] * len(B), K)
    terms = []
    for o, (bi, due, wt) in inst["order_info"].items():
        t = m.NewIntVar(0, H, f"T{o}")
        m.Add(t >= E[bi] - due)
        terms.append(wt * t)
    m.Minimize(sum(terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    status = solver.Solve(m)
    ok = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    return dict(status=solver.StatusName(status), obj=int(solver.ObjectiveValue()) if ok else None,
                bound=solver.BestObjectiveBound() if ok else None, wall=solver.WallTime())
