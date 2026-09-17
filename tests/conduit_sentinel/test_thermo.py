import numpy as np
import pytest

from conduit_sentinel.thermo import nws_heat_index_c, stull_wet_bulb_c


def to_c(fahrenheit):
    return (fahrenheit - 32) * 5 / 9


def to_f(celsius):
    return celsius * 9 / 5 + 32


def test_stull_wet_bulb_matches_the_paper_example():
    # Stull (2011): T = 20 °C and RH = 50 % give Tw = 13.7 °C
    assert stull_wet_bulb_c(20.0, 50.0) == pytest.approx(13.7, abs=0.05)


def test_stull_wet_bulb_is_vectorised():
    result = stull_wet_bulb_c([20.0, 12.6], [50.0, 86.7])
    assert result.shape == (2,)
    assert result[1] < 12.6


@pytest.mark.parametrize(
    ("t_f", "rh", "chart_f"),
    [(80, 40, 80), (90, 70, 106), (100, 50, 118), (86, 90, 105), (96, 65, 121)],
)
def test_heat_index_agrees_with_the_nws_chart(t_f, rh, chart_f):
    assert to_f(nws_heat_index_c(to_c(t_f), rh)) == pytest.approx(chart_f, abs=1.0)


def test_heat_index_uses_the_simple_formula_in_cool_air():
    # 20 °C and 50 %: 0.5 * (68 + 61 + 0 + 4.7) = 66.85 °F
    assert nws_heat_index_c(20.0, 50.0) == pytest.approx(to_c(66.85))


def test_heat_index_handles_dry_heat_without_warnings():
    with np.errstate(all="raise"):
        result = nws_heat_index_c([to_c(100), 12.0], [10.0, 90.0])
    assert np.isfinite(result).all()
