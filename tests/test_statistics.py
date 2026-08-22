"""Tests for the statistical significance layer."""

from __future__ import annotations

from evaluation.statistics import (
    bootstrap_ci,
    mcnemar_test,
    pass_at_k,
    wilcoxon_signed_rank,
)

# --- McNemar --------------------------------------------------------------


def test_mcnemar_returns_zero_when_all_concordant() -> None:
    """All identical outcomes -> chi2 = 0, p = 1.0."""
    passes = [True, True, False, False, True, False]
    chi2, p = mcnemar_test(passes, passes)
    assert chi2 == 0.0
    assert p == 1.0


def test_mcnemar_with_strong_signal() -> None:
    """Treatment wins all 10 cases where baseline lost -> very small p."""
    # Baseline loses the first 10, passes the last 10.
    # Treatment passes everything.
    a = [False] * 10 + [True] * 10
    b = [True] * 20
    chi2, p = mcnemar_test(a, b)
    assert chi2 > 3.84  # p < 0.05 threshold for 1 df with continuity correction
    assert p < 0.05


def test_mcnemar_with_strong_signal_no_continuity_correction() -> None:
    """When discordant counts are equal, continuity-corrected chi² collapses to 0.

    Documents the boundary behaviour: with n_01 == n_10, the
    continuity-corrected formula returns chi² = 0, p = 1.0 (no signal).
    """
    a = [True, False, True, False]
    b = [False, True, False, True]
    chi2, p = mcnemar_test(a, b)
    assert chi2 == 0.0
    assert p == 1.0


def test_mcnemar_length_mismatch_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        mcnemar_test([True, False], [True])


# --- Wilcoxon -------------------------------------------------------------


def test_wilcoxon_all_zero_deltas() -> None:
    w, p = wilcoxon_signed_rank([0.0, 0.0, 0.0])
    assert w == 0.0
    assert p == 1.0


def test_wilcoxon_strong_signal() -> None:
    """10 strongly positive deltas -> very small p (n>5 makes scipy approximate)."""
    _w, p = wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert p < 0.01


def test_wilcoxon_balanced_mixed_deltas() -> None:
    """Balanced mixed deltas -> p should be ~ 1.0."""
    _w, p = wilcoxon_signed_rank([1.0, -1.0, 2.0, -2.0, 3.0, -3.0])
    assert p > 0.1  # not significant


# --- Bootstrap ------------------------------------------------------------


def test_bootstrap_ci_brackets_true_mean() -> None:
    """For a small synthetic dataset the 95% CI should contain the true mean."""
    import random as _random

    rng = _random.Random(42)
    values = [rng.gauss(5.0, 1.0) for _ in range(50)]
    lo, hi = bootstrap_ci(values, n_iter=2000, seed=0)
    assert lo <= 5.0 <= hi


def test_bootstrap_ci_too_few_observations() -> None:
    lo, hi = bootstrap_ci([5.0])
    assert lo != lo  # NaN
    assert hi != hi


# --- pass^k ---------------------------------------------------------------


def test_pass_at_k_one_repeat_equals_pass_rate() -> None:
    """3/4 of tasks pass on their single run."""
    passes = [[True], [False], [True], [True]]
    assert pass_at_k(passes, k=1) == 0.75


def test_pass_at_k_all_pass_on_first_repeat() -> None:
    passes = [[True], [True], [True]]
    assert pass_at_k(passes, k=1) == 1.0


def test_pass_at_k_two_repeats_all_pass() -> None:
    passes = [[True, True], [True, True], [True, True]]
    assert pass_at_k(passes, k=2) == 1.0


def test_pass_at_k_two_repeats_one_inconsistent() -> None:
    """Only 1 of 3 tasks passes both runs -> pass^2 = 1/3."""
    passes = [[True, False], [True, True], [False, True]]
    assert abs(pass_at_k(passes, k=2) - 1 / 3) < 1e-5


def test_pass_at_k_empty_input() -> None:
    assert pass_at_k([], k=1) == 0.0


def test_pass_at_k_zero_k() -> None:
    assert pass_at_k([[True, True]], k=0) == 0.0
