"""Statistical significance tests + multi-run consistency.

Adopted from §5 of the Gemini deep-research report. All routines are
deterministic given fixed inputs (no random seeds beyond the explicit
``n_iter`` for the bootstrap, which is also fixed by default).

The convention is: when there isn't enough data to compute a meaningful
statistic, return ``(0.0, 1.0)`` so the comparator can still render a
row instead of raising.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

from scipy import stats

# --- McNemar's test --------------------------------------------------------


def mcnemar_test(
    passes_a: Sequence[bool],
    passes_b: Sequence[bool],
) -> tuple[float, float]:
    """McNemar's test with continuity correction on paired pass/fail.

    Returns ``(chi2, p_value)``. Discards concordant pairs (both pass or
    both fail) per the standard formulation; only discordant pairs
    contribute to the chi-square statistic.

    When there are fewer than 1 discordant pair, returns ``(0.0, 1.0)``
    (no signal).
    """
    if len(passes_a) != len(passes_b):
        raise ValueError("passes_a and passes_b must be the same length")
    n_01 = sum(1 for a, b in zip(passes_a, passes_b, strict=True) if a and not b)
    n_10 = sum(1 for a, b in zip(passes_a, passes_b, strict=True) if not a and b)
    if n_01 + n_10 == 0:
        return 0.0, 1.0
    # Continuity-corrected chi-square with 1 df.
    diff = abs(n_01 - n_10) - 1
    if diff < 0:
        diff = 0
    chi2 = (diff * diff) / (n_01 + n_10)
    p_value = 1.0 - stats.chi2.cdf(chi2, df=1)
    return round(float(chi2), 4), round(float(p_value), 6)


# --- Wilcoxon signed-rank ---------------------------------------------------


def wilcoxon_signed_rank(
    deltas: Sequence[float],
) -> tuple[float, float]:
    """Wilcoxon signed-rank test on paired continuous deltas.

    Returns ``(W, p_value)``. Two-sided test by default. Returns
    ``(0.0, 1.0)`` when all deltas are zero or when there are no
    non-zero deltas (the scipy convention).

    Deltas of zero are dropped before ranking (the standard signed-rank
    behaviour); we drop ties on top of that to avoid the resulting
    warning spam. Tests against ``mu=0``.
    """
    nonzero = [d for d in deltas if d != 0.0]
    if len(nonzero) == 0:
        return 0.0, 1.0
    try:
        result = stats.wilcoxon(nonzero, zero_method="wilcox", correction=False, alternative="two-sided")
    except ValueError:
        # All remaining deltas are tied at one value: scipy raises.
        return 0.0, 1.0
    return round(float(result.statistic), 4), round(float(result.pvalue), 6)


# --- Bootstrap CI ----------------------------------------------------------


def bootstrap_ci(
    values: Sequence[float],
    n_iter: int = 10_000,
    alpha: float = 0.05,
    seed: int | None = 0,
) -> tuple[float, float]:
    """Empirical bootstrap 95% confidence interval on a list of scalars.

    Resamples with replacement and computes the percentile interval.
    Returns ``(lower, upper)``. The ``seed`` argument keeps the routine
    deterministic for tests; pass ``None`` to opt out.

    For fewer than 2 observations, returns ``(nan, nan)`` — there is no
    CI to compute.
    """
    if len(values) < 2:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_iter):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = max(0, math.floor((alpha / 2) * n_iter))
    hi_idx = min(n_iter - 1, math.ceil((1 - alpha / 2) * n_iter) - 1)
    return round(means[lo_idx], 6), round(means[hi_idx], 6)


# --- pass^k ----------------------------------------------------------------


def pass_at_k(
    passes_per_task: Sequence[Sequence[bool]],
    k: int,
) -> float:
    """Consistency metric: fraction of tasks passing every one of k runs.

    Each element of ``passes_per_task`` is the per-run pass vector for
    one task (length >= k). A task "pass^k"s if every one of its first
    k runs passed.

    Empty input or k <= 0 returns ``0.0``.
    """
    if k <= 0 or not passes_per_task:
        return 0.0
    successes = 0
    valid = 0
    for task_passes in passes_per_task:
        if len(task_passes) < k:
            continue
        valid += 1
        if all(task_passes[i] for i in range(k)):
            successes += 1
    if valid == 0:
        return 0.0
    return round(successes / valid, 6)


__all__ = [
    "bootstrap_ci",
    "mcnemar_test",
    "pass_at_k",
    "wilcoxon_signed_rank",
]
