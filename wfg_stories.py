"""Abnahmekriterien der Presets (Detailplan plan_wellen_konflikt.html, Abschnitt 7): welche Geschichte erzaehlt
jedes Beispielszenario, und woran erkennt man, dass sie traegt?

Einzige Quelle fuer `tools/tune_presets.py` (Abstimmung) und `tests/test_stories.py` / `tests/test_preset_stories.py`
(Abnahme). Alle Kriterien stehen auf der 80-Instanzen-Population (Seeds 0..79), Vorzeichen-Kriterien IMMER zusammen
mit der Standardfehler-Bedingung (Betrag > 2 SE). Der gezeigte Seed (Gantt) ist eine einzelne Instanz und bleibt
qualitativ; er liegt bewusst ausserhalb der Stichprobe-Seeds. Kein Loeser mit Wall-Clock-Grenze in den Kriterien
(CP-SAT laeuft nur im Exakt-Tab)."""
from dataclasses import dataclass

import wfg_constants as C
from wfg_evaluation import Pair, Population


@dataclass(frozen=True)
class PresetMetrics:
    """Die Kennzahlen, auf denen die Kriterien stehen."""
    wait_share_pct: float      # Wartezeitanteil der Regel EDD
    edd_min: float             # gewichtete Verspaetung EDD mit Blockieren
    edd_free_min: float        # ... ohne Blockieren
    adv_on: Pair               # Vorteil der Fristenregel (FIFO minus EDD) mit Blockieren
    adv_off: Pair              # ... ohne Blockieren
    gain: Pair                 # Gewinn des Fensters (EDD minus EDD-w) beim Fenster des Presets


def metrics_from_population(pop: Population) -> PresetMetrics:
    return PresetMetrics(wait_share_pct=pop.wait_share_pct(C.RULE_EDD), edd_min=pop.mean_min(C.RULE_EDD),
                         edd_free_min=pop.mean_min("edd_free"), adv_on=pop.advantage_on(),
                         adv_off=pop.advantage_off(), gain=pop.gain())


def _de(v, digits=1):
    return f"{v:.{digits}f}".replace(".", ",")


def _gain_text(g: Pair):
    return f"{g.mean:+.1f} ± {g.se:.1f}".replace(".", ",")


def criteria(name, m: PresetMetrics):
    """m: PresetMetrics. Rueckgabe: Liste (erfuellt, Text)."""
    if name == "Standard":
        ratio = m.edd_min / m.edd_free_min if m.edd_free_min else float("inf")
        return [(m.wait_share_pct >= 10.0, f"Wartezeitanteil >= 10 %: {_de(m.wait_share_pct)} %"),
                (ratio >= 1.5, f"Verspätung mit Blockieren >= 1,5 x ohne: {_de(ratio)} x"),
                (m.gain.verdict() == "pos",
                 f"Gewinn des Fensters positiv und > 2 SE: {_gain_text(m.gain)} Min.")]
    if name == "Wenige Kommissionierer":
        rel = abs(m.adv_on.mean - m.adv_off.mean) / m.adv_off.mean if m.adv_off.mean else float("inf")
        return [(m.wait_share_pct <= 6.0, f"Wartezeitanteil <= 6 %: {_de(m.wait_share_pct)} %"),
                (rel <= 0.05, f"Fristenvorteil mit ≈ ohne Blockieren (Abweichung <= 5 %): {_de(m.adv_on.mean)} vs. "
                              f"{_de(m.adv_off.mean)} Min."),
                (m.gain.verdict() == "neg",
                 f"Gewinn des Fensters negativ und > 2 SE: {_gain_text(m.gain)} Min.")]
    if name == "Viele Kommissionierer":
        share = m.adv_on.mean / m.adv_off.mean if m.adv_off.mean else float("inf")
        return [(m.wait_share_pct >= 25.0, f"Wartezeitanteil >= 25 %: {_de(m.wait_share_pct)} %"),
                (share <= 0.5, f"Fristenvorteil mit Blockieren <= 50 % des Vorteils ohne: {_de(share * 100)} %")]
    if name == "Enge Fristen, heiße Gänge":
        return [(m.gain.mean >= 10.0 and m.gain.verdict() == "pos",
                 f"Gewinn des Fensters >= 10 Min. und > 2 SE: {_gain_text(m.gain)} Min.")]
    if name == "Lockere Fristen":
        return [(m.gain.mean <= -20.0 and m.gain.verdict() == "neg",
                 f"Gewinn des Fensters <= -20 Min. und > 2 SE: {_gain_text(m.gain)} Min.")]
    raise KeyError(name)
