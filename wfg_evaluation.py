"""Auswertung der Wellenfreigabe-Demo: Population (80 Instanzen), gepaarte Vergleiche, Urteil in drei Zustaenden,
Kommissionierer-Sweep, rho-Sweep, gezeigte Instanz, Exakt-Zusammenfassung.

Definitionen exakt wie in messreihe_wellen_konflikt/dump_sweep.py (deren Zahlen die Presets reproduzieren muessen):
80 Instanzen = Seeds 0..79, alle Werte in MINUTEN (Dezisekunden / 600), gepaarte Differenz je Instanz, Standardfehler
= Standardabweichung der Differenzen / Wurzel(n). Vorzeichen-Konvention: `gain` = Referenz MINUS Regel (positiv =
die Regel ist besser); `diff_to_edd` = Regel MINUS EDD (positiv = mehr Verspaetung). Reine Standardbibliothek."""
from __future__ import annotations

import functools
import statistics as st
from dataclasses import dataclass, replace

import wfg_constants as C
from wfg_scenario import Cfg, make_instance
from wfg_sim import simulate

_POLICY_KWARGS = {
    C.RULE_FIFO: dict(policy="fifo"),
    C.RULE_EDD: dict(policy="edd"),
}


def rule_kwargs(rule: str, w: int) -> dict:
    """simulate()-Argumente einer Regel. Jede Regel hat einen EIGENEN Richtliniennamen (nie zwei Regeln ueber
    denselben Namen mit einem Parameter unterscheiden - so blieb in der Vorab-Messung der Fenster-Zweig unbemerkt)."""
    if rule == C.RULE_EDDW:
        return dict(policy="edd_w", w=int(w))
    return dict(_POLICY_KWARGS[rule])


def cfg_from_controls(aisles, pickers, orders, tau, express_pct, hot_corr_pct) -> Cfg:
    """Reglerwerte (ganzzahlige Prozentpunkte) -> Cfg des verifizierten Kerns."""
    return Cfg(n_aisles=int(aisles), n_pickers=int(pickers), n_orders=int(orders), tau=round(float(tau), 6),
               express_share=int(express_pct) / 100.0, hot_corr=int(hot_corr_pct) / 100.0)


# ---------------------------------------------------------------------------------------------------
# Gepaarte Statistik
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Pair:
    """Mittel und Standardfehler einer gepaarten Differenz, in Minuten."""
    mean: float
    se: float

    def verdict(self, se_factor: float = C.SE_FACTOR) -> str:
        """'pos' / 'neg' / 'none': Vorzeichen nur, wenn der Betrag ueber se_factor Standardfehlern liegt."""
        if self.mean > se_factor * self.se:
            return "pos"
        if self.mean < -se_factor * self.se:
            return "neg"
        return "none"


def pair_from_diffs(diffs) -> Pair:
    """diffs in Dezisekunden -> Pair in Minuten (Formel wie dump_sweep.py)."""
    diffs = list(diffs)
    if len(diffs) < 2:
        return Pair(st.fmean(diffs) / C.MIN_DS if diffs else 0.0, 0.0)
    return Pair(st.fmean(diffs) / C.MIN_DS, (st.stdev(diffs) / len(diffs) ** 0.5) / C.MIN_DS)


def paired(a, b) -> Pair:
    """Mittel und Standardfehler von a - b."""
    return pair_from_diffs([x - y for x, y in zip(a, b)])


# ---------------------------------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=48)
def population_instances(cfg: Cfg, n: int = C.N_POPULATION) -> tuple:
    """Die n Instanzen (Seeds 0..n-1) einer Einstellung; Instanzerzeugung ist der teuerste Schritt (61 ms je 80),
    daher zwischengespeichert - der Fenster-Regler aendert die Instanzen nicht."""
    return tuple(make_instance(cfg, s) for s in range(n))


@dataclass(frozen=True)
class Population:
    """Ergebnisse der Regeln ueber die Instanzen einer Einstellung. Schluessel: fifo, edd, edd_w (alle mit Blockieren)
    sowie fifo_free, edd_free (ohne Blockieren = parallele Maschinen mit Fristen)."""
    cfg: Cfg
    w: int
    obj: dict          # Schluessel -> Liste der gewichteten Verspaetungen (ds) je Instanz
    late: dict         # Schluessel -> Liste der Anzahl verspaeteter Bestellungen je Instanz
    wait_share: dict   # Schluessel -> Mittel des Wartezeitanteils in Prozent (nur mit Blockieren aussagekraeftig)
    n_batches: float

    @property
    def n(self) -> int:
        return len(self.obj[C.RULE_EDD])

    def mean_min(self, key: str) -> float:
        return st.fmean(self.obj[key]) / C.MIN_DS

    def late_share_pct(self, key: str) -> float:
        return st.fmean(self.late[key]) / self.cfg.n_orders * 100.0

    def pair(self, a: str, b: str) -> Pair:
        return paired(self.obj[a], self.obj[b])

    def gain(self) -> Pair:
        """Gewinn des Fensters gegenueber EDD: EDD minus EDD-w (positiv = das Fenster hilft)."""
        return self.pair(C.RULE_EDD, C.RULE_EDDW)

    def diff_to_edd(self, rule: str) -> Pair:
        """Regel minus EDD (positiv = mehr Verspaetung als EDD)."""
        return self.pair(rule, C.RULE_EDD)

    def advantage_on(self) -> Pair:
        """Vorteil der Fristenregel mit Blockieren: FIFO minus EDD."""
        return self.pair(C.RULE_FIFO, C.RULE_EDD)

    def advantage_off(self) -> Pair:
        """Vorteil der Fristenregel ohne Blockieren: FIFO minus EDD."""
        return self.pair("fifo_free", "edd_free")

    def advantage_change(self) -> Pair:
        """Gepaarte Aenderung des Vorteils durch das Blockieren (mit minus ohne), je Instanz."""
        on = [f - e for f, e in zip(self.obj[C.RULE_FIFO], self.obj[C.RULE_EDD])]
        off = [f - e for f, e in zip(self.obj["fifo_free"], self.obj["edd_free"])]
        return pair_from_diffs([a - b for a, b in zip(on, off)])

    def wait_share_pct(self, key: str = C.RULE_EDD) -> float:
        return self.wait_share[key]


def evaluate_population(cfg: Cfg, w: int) -> Population:
    """Alle Regeln auf den Seeds 0..79 (deterministisch)."""
    ins = population_instances(cfg)
    runs = {
        C.RULE_FIFO: dict(policy="fifo"), C.RULE_EDD: dict(policy="edd"),
        C.RULE_EDDW: rule_kwargs(C.RULE_EDDW, w),
        "fifo_free": dict(policy="fifo", blocking=False), "edd_free": dict(policy="edd", blocking=False),
    }
    obj, late, wait = {}, {}, {}
    for key, kw in runs.items():
        rs = [simulate(i, **kw) for i in ins]
        obj[key] = [r["obj"] for r in rs]
        late[key] = [r["late"] for r in rs]
        wait[key] = st.fmean(r["wait"] / (r["work"] + r["wait"]) for r in rs) * 100.0
    return Population(cfg=cfg, w=int(w), obj=obj, late=late, wait_share=wait,
                      n_batches=st.fmean(len(i["batches"]) for i in ins))


# ---------------------------------------------------------------------------------------------------
# Meldung der Hauptansicht (vier Zustaende, Plan Abschnitt 6)
# ---------------------------------------------------------------------------------------------------
STATE_IRRELEVANT, STATE_PAYS, STATE_HURTS, STATE_UNCLEAR = "irrelevant", "pays", "hurts", "unclear"


def message_state(wait_share_pct: float, gain: Pair) -> str:
    """Wartezeitanteil unter ~5 % -> Blockieren kaum relevant; sonst Vorzeichen des Fenster-Gewinns, nur wenn er ueber
    2 Standardfehlern liegt; sonst kein belastbarer Unterschied."""
    if wait_share_pct < C.WAIT_SHARE_LOW_PCT:
        return STATE_IRRELEVANT
    verdict = gain.verdict()
    if verdict == "pos":
        return STATE_PAYS
    if verdict == "neg":
        return STATE_HURTS
    return STATE_UNCLEAR


# ---------------------------------------------------------------------------------------------------
# Kernabschnitt: Kommissionierer-Sweep und rho-Sweep
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class KRow:
    k: int
    adv_on: Pair          # FIFO minus EDD mit Blockieren
    adv_off: Pair         # FIFO minus EDD ohne Blockieren
    change: Pair          # gepaarte Aenderung (mit minus ohne)
    rel_change_pct: float

    @property
    def verdict(self) -> str:
        return self.change.verdict()


def relative_change_pct(on: float, off: float) -> float:
    return (on - off) / off * 100.0 if off else 0.0


def k_sweep(cfg: Cfg, ks=C.K_SWEEP_RANGE) -> list:
    """Vorteil der Fristenregel (EDD gegenueber FIFO) ohne und mit Blockieren je Kommissionierer-Zahl."""
    rows = []
    for k in ks:
        pop = evaluate_population(replace(cfg, n_pickers=int(k)), 1)
        on, off = pop.advantage_on(), pop.advantage_off()
        rows.append(KRow(k=int(k), adv_on=on, adv_off=off, change=pop.advantage_change(),
                         rel_change_pct=relative_change_pct(on.mean, off.mean)))
    return rows


def rho_sweep(cfg: Cfg, rhos_pct=C.RHO_SWEEP_PCT, windows=C.WINDOW_SWEEP) -> dict:
    """Gewinn des Fensters (EDD minus EDD-w) je Konzentration rho und Fenstergroesse: {rho_pct: {w: Pair}}."""
    out = {}
    for rho in rhos_pct:
        c = replace(cfg, hot_corr=rho / 100.0)
        out[int(rho)] = {int(w): evaluate_population(c, int(w)).gain() for w in windows}
    return out


def verdict_counts(rho_rows: dict) -> dict:
    """Wie viele Zellen des rho-Sweeps sind belastbar positiv / negativ / ohne belastbaren Unterschied?"""
    counts = {"pos": 0, "neg": 0, "none": 0}
    for by_w in rho_rows.values():
        for pair in by_w.values():
            counts[pair.verdict()] += 1
    return counts


# ---------------------------------------------------------------------------------------------------
# Gezeigte Instanz (Gantt) und Exakt-Zusammenfassung
# ---------------------------------------------------------------------------------------------------
def shown_run(cfg: Cfg, seed: int, rule: str, w: int):
    """(Instanz, Simulationsergebnis mit Gangprotokoll) der eingestellten Regel fuer den gezeigten Seed."""
    inst = make_instance(cfg, int(seed))
    return inst, simulate(inst, log=True, **rule_kwargs(rule, w))


def shown_summary(inst: dict, result: dict) -> dict:
    """Kennzahlen der gezeigten Einzelinstanz (qualitativ, ein einzelner Seed)."""
    total = result["work"] + result["wait"]
    return dict(n_batches=len(inst["batches"]), obj_min=result["obj"] / C.MIN_DS,
                wait_share_pct=result["wait"] / total * 100.0 if total else 0.0,
                makespan_min=result["makespan"] / C.MIN_DS, late=result["late"])


def exact_summary(inst: dict, w: int, opt: dict, opt_free: dict) -> dict:
    """Optimum (bzw. beste Loesung samt Schranke) mit und ohne Blockieren gegen EDD und EDD-w derselben Instanz.
    Werte in Minuten, Prozentwerte None bei Nenner 0."""
    edd = simulate(inst, policy="edd")["obj"]
    eddw = simulate(inst, **rule_kwargs(C.RULE_EDDW, w))["obj"]

    def pct(num, den):
        return num / den * 100.0 if den else None

    proven = opt["status"] == "OPTIMAL"
    proven_free = opt_free["status"] == "OPTIMAL"
    return dict(
        status=opt["status"], status_free=opt_free["status"], proven=proven, proven_free=proven_free,
        opt_min=opt["obj"] / C.MIN_DS, bound_min=opt["bound"] / C.MIN_DS,
        opt_free_min=opt_free["obj"] / C.MIN_DS, bound_free_min=opt_free["bound"] / C.MIN_DS,
        edd_min=edd / C.MIN_DS, eddw_min=eddw / C.MIN_DS,
        potential_pct=pct(edd - opt["obj"], edd),                        # Rest-Potenzial gegenueber EDD
        potential_eddw_pct=pct(eddw - opt["obj"], eddw),
        price_pct=pct(opt["obj"] - opt_free["obj"], opt_free["obj"]),    # Preis des Blockierens im Optimum
        wall_s=opt["wall"] + opt_free["wall"],
    )
