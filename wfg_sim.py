"""Ereignissimulation mit Gang-FIFO und Freigaberegeln (FIFO, EDD, EDD mit Konflikt-Fenster).

UNVERAENDERT uebernommen aus lager-planung/messreihe_wellen_konflikt/wellen.py. Jeder Gang ist eine
Einzelressource (kein Ueberholen, FIFO-Warteschlange am Eingang), K Kommissionierer, Freigabe sofort bei
Frei-Werden (non-delay). Mit blocking=False faellt das Modell exakt auf parallele Maschinen mit Fristen
zurueck (List-Scheduling, in tests/test_core_checks.py unabhaengig nachgerechnet). Nur Standardbibliothek."""

from __future__ import annotations

import heapq


def _choose(waiting: set[int], state: dict[int, int], B: list[dict], policy: str, w: int) -> int:
    if policy == "fifo":
        return min(waiting)
    cand = sorted(waiting, key=lambda b: (B[b]["due"], b))
    if policy == "edd":
        return cand[0]
    assert policy == "edd_w", policy
    cand = cand[:max(1, w)]
    if len(cand) == 1:
        return cand[0]
    active = [set(a for a, _ in B[ab]["visits"][i:]) for ab, i in state.items()]

    def conflict(b: int) -> int:
        return sum(len(B[b]["aisles"] & rem) for rem in active)

    return min(cand, key=lambda b: (conflict(b), B[b]["due"], b))


def simulate(inst: dict, K: int | None = None, policy: str = "edd", w: int = 1,
             blocking: bool = True, log: bool = False) -> dict:
    B = inst["batches"]
    K = K if K is not None else inst["K"]
    A = inst["cfg"].n_aisles
    waiting = set(range(len(B)))
    ev: list[tuple] = []
    seq = 0
    for p in range(K):
        heapq.heappush(ev, (0, seq, "free", p))
        seq += 1
    state: dict[int, int] = {}
    picker_batch: dict[int, int] = {}
    aisle_free = [0] * A
    start = [None] * len(B)
    comp = [None] * len(B)
    wait_total = 0
    aisle_log = [[] for _ in range(A)]
    while ev:
        t, _, kind, p = heapq.heappop(ev)
        if kind == "free":
            if not waiting:
                continue
            b = _choose(waiting, state, B, policy, w)
            waiting.remove(b)
            picker_batch[p] = b
            state[b] = 0
            start[b] = t
            heapq.heappush(ev, (t + B[b]["walks"][0], seq, "arrive", p))
            seq += 1
        else:
            b = picker_batch[p]
            i = state[b]
            aisle, dur = B[b]["visits"][i]
            entry = max(t, aisle_free[aisle]) if blocking else t
            wait_total += entry - t
            exit_ = entry + dur
            if blocking:
                aisle_free[aisle] = exit_
            if log:
                aisle_log[aisle].append((entry, exit_, b, t))
            if i + 1 < len(B[b]["visits"]):
                state[b] = i + 1
                heapq.heappush(ev, (exit_ + B[b]["walks"][i + 1], seq, "arrive", p))
            else:
                end = exit_ + B[b]["walks"][-1]
                comp[b] = end
                del state[b]
                heapq.heappush(ev, (end, seq, "free", p))
            seq += 1
    obj = 0
    late = 0
    for o, (bi, due, wt) in inst["order_info"].items():
        tard = max(0, comp[bi] - due)
        obj += wt * tard
        late += 1 if tard > 0 else 0
    return dict(obj=obj, late=late, makespan=max(comp), wait=wait_total, comp=comp, start=start,
                work=sum(b["D"] for b in B), aisle_log=aisle_log)
