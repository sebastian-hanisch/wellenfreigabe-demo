"""Jedes Preset-Abnahmekriterium einzeln an kuenstlichen Werten pruefen, die genau an seiner Schwelle kippen (Detailplan
Abschnitt 7/12), und Vorzeichen-Kriterien nur zusammen mit der Standardfehler-Bedingung."""
import pytest

import wfg_stories as ST
from wfg_evaluation import Pair


def _m(wait=10.0, edd=200.0, free=100.0, adv_on=Pair(100.0, 5.0), adv_off=Pair(100.0, 5.0), gain=Pair(0.0, 1.0)):
    return ST.PresetMetrics(wait_share_pct=wait, edd_min=edd, edd_free_min=free, adv_on=adv_on, adv_off=adv_off, gain=gain)


def _ok(name, m):
    return all(ok for ok, _ in ST.criteria(name, m))


def _oks(name, m):
    return [ok for ok, _ in ST.criteria(name, m)]


# --- Standard: Wartezeitanteil >= 10 %, Verspaetung mit >= 1,5 x ohne, Gewinn positiv UND > 2 SE ---------------------
GOOD_STD = dict(wait=16.0, edd=280.0, free=140.0, gain=Pair(11.9, 3.6))


def test_standard_all_three_criteria_hold_for_good_values():
    assert _oks("Standard", _m(**GOOD_STD)) == [True, True, True]


def test_standard_wait_share_tips_at_ten_percent():
    assert _oks("Standard", _m(**{**GOOD_STD, "wait": 10.0}))[0]
    assert not _oks("Standard", _m(**{**GOOD_STD, "wait": 9.999}))[0]


def test_standard_ratio_tips_at_one_point_five():
    assert _oks("Standard", _m(**{**GOOD_STD, "edd": 150.0, "free": 100.0}))[1]
    assert not _oks("Standard", _m(**{**GOOD_STD, "edd": 149.9, "free": 100.0}))[1]
    assert _oks("Standard", _m(**{**GOOD_STD, "free": 0.0}))[1]                    # Nenner 0 -> unendlich, erfuellt


def test_standard_gain_needs_sign_and_two_standard_errors():
    assert _oks("Standard", _m(**{**GOOD_STD, "gain": Pair(2.001, 1.0)}))[2]
    assert not _oks("Standard", _m(**{**GOOD_STD, "gain": Pair(2.0, 1.0)}))[2]      # genau 2 SE reicht nicht
    assert not _oks("Standard", _m(**{**GOOD_STD, "gain": Pair(-10.0, 1.0)}))[2]    # negativ, aber belastbar: falsches Vorzeichen
    assert not _oks("Standard", _m(**{**GOOD_STD, "gain": Pair(5.0, 3.0)}))[2]      # positiv, aber im Rauschen


# --- Wenige Kommissionierer: Wartezeitanteil <= 6 %, Fristenvorteil mit ~ ohne, Gewinn negativ UND > 2 SE --------------
GOOD_FEW = dict(wait=4.0, adv_on=Pair(240.5, 12.0), adv_off=Pair(240.8, 11.0), gain=Pair(-11.0, 3.5))


def test_wenige_all_three_criteria_hold_for_good_values():
    assert _oks("Wenige Kommissionierer", _m(**GOOD_FEW)) == [True, True, True]


def test_wenige_wait_share_tips_at_six_percent():
    assert _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "wait": 6.0}))[0]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "wait": 6.001}))[0]


def test_wenige_advantage_equality_tips_at_five_percent_in_both_directions():
    assert _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "adv_on": Pair(95.0, 1.0), "adv_off": Pair(100.0, 1.0)}))[1]
    assert _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "adv_on": Pair(105.0, 1.0), "adv_off": Pair(100.0, 1.0)}))[1]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "adv_on": Pair(94.9, 1.0), "adv_off": Pair(100.0, 1.0)}))[1]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "adv_on": Pair(105.1, 1.0), "adv_off": Pair(100.0, 1.0)}))[1]


def test_wenige_gain_needs_negative_sign_and_two_standard_errors():
    assert _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "gain": Pair(-2.001, 1.0)}))[2]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "gain": Pair(-2.0, 1.0)}))[2]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "gain": Pair(10.0, 1.0)}))[2]
    assert not _oks("Wenige Kommissionierer", _m(**{**GOOD_FEW, "gain": Pair(-3.0, 3.0)}))[2]


# --- Viele Kommissionierer: Wartezeitanteil >= 25 %, Fristenvorteil mit <= 50 % des Vorteils ohne -----------------------
def test_viele_wait_share_tips_at_twenty_five_percent():
    good = dict(wait=30.0, adv_on=Pair(28.0, 6.0), adv_off=Pair(66.0, 4.0))
    assert _oks("Viele Kommissionierer", _m(**good)) == [True, True]
    assert _oks("Viele Kommissionierer", _m(**{**good, "wait": 25.0}))[0]
    assert not _oks("Viele Kommissionierer", _m(**{**good, "wait": 24.999}))[0]


def test_viele_advantage_share_tips_at_fifty_percent():
    base = dict(wait=30.0, adv_off=Pair(100.0, 4.0))
    assert _oks("Viele Kommissionierer", _m(**base, adv_on=Pair(50.0, 4.0)))[1]
    assert not _oks("Viele Kommissionierer", _m(**base, adv_on=Pair(50.001, 4.0)))[1]
    assert not _oks("Viele Kommissionierer", _m(wait=30.0, adv_off=Pair(0.0, 1.0), adv_on=Pair(5.0, 1.0)))[1]


# --- Enge Fristen: Gewinn >= 10 Minuten UND > 2 SE ----------------------------------------------------------------------
def test_enge_fristen_tips_at_ten_minutes_and_two_standard_errors():
    assert _ok("Enge Fristen, heiße Gänge", _m(gain=Pair(10.0, 3.0)))
    assert not _ok("Enge Fristen, heiße Gänge", _m(gain=Pair(9.999, 3.0)))
    assert not _ok("Enge Fristen, heiße Gänge", _m(gain=Pair(12.0, 6.0)))          # >= 10, aber nur 2 SE
    assert _ok("Enge Fristen, heiße Gänge", _m(gain=Pair(12.0, 5.999)))


# --- Lockere Fristen: Gewinn <= -20 Minuten UND < -2 SE -----------------------------------------------------------------
def test_lockere_fristen_tips_at_minus_twenty_minutes_and_two_standard_errors():
    assert _ok("Lockere Fristen", _m(gain=Pair(-20.0, 3.0)))
    assert not _ok("Lockere Fristen", _m(gain=Pair(-19.999, 3.0)))
    assert not _ok("Lockere Fristen", _m(gain=Pair(-25.0, 12.5)))                   # <= -20, aber genau 2 SE
    assert _ok("Lockere Fristen", _m(gain=Pair(-25.0, 12.4)))
    assert not _ok("Lockere Fristen", _m(gain=Pair(30.0, 3.0)))


def test_unknown_preset_name_raises():
    with pytest.raises(KeyError):
        ST.criteria("Nicht vorhanden", _m())


def test_criteria_texts_are_german_with_decimal_comma():
    import re
    for ok, text in ST.criteria("Standard", _m(**GOOD_STD)):
        assert "," in text and not re.search(r"\d\.\d", text)
