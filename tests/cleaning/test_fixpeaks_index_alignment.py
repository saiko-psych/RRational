"""Regression test for the peak-space -> RR-space index fix in
``detect_artifacts_fixpeaks`` (Round 30).

NK2's Kubios detector runs on ``rr = ediff1d(peaks, to_begin=0)``, which is
peaks-space (length N+1); ``rr_nk[i] == rr_values[i-1]``. An NK2 artifact
index ``k`` therefore refers to ``rr_values[k-1]``. The pre-Round-30 code
stored ``k`` directly, shifting every flagged beat one position to the
right (and dropping any artifact NK2 reported at peaks index N).

The core guard here injects an unmistakable premature/compensatory pair at
KNOWN positions and asserts those exact positions are flagged. Under the
old off-by-one the injected beats were absent and the beats one-past them
were marked instead. Pure logic, no Qt.

Note on tail beats: NK2's Kubios detector uses a 91-sample median filter
and reliably flags the final 1-2 beats only with symmetric context, so a
"last beat" scenario is not a dependable regression fixture — the -1 shift
that keeps peaks-index N (-> rr N-1) in-bounds is exercised implicitly by
the alignment case instead.
"""

from __future__ import annotations

import numpy as np

from rrational.cleaning.quality import detect_artifacts_fixpeaks


def _clean_rr(n: int = 200, mean: float = 800.0, seed: int = 0) -> list[int]:
    rng = np.random.default_rng(seed)
    return [int(round(x)) for x in (mean + 10 * rng.standard_normal(n))]


def test_injected_ectopic_index_is_aligned_not_off_by_one():
    """An ectopic pair at rr_values[100:102] is flagged AT 100/101, not 101/102.

    Verified against NK2 0.2.13: the detector reports the anomaly at
    peaks-space indices 101/102, which the -1 shift maps back to RR-space
    100/101. Under the pre-fix code the flagged set contained 101/102 and
    the true position 100 was absent — so ``100 in flagged`` is the exact
    regression guard.
    """
    rr = _clean_rr(200)
    inject = 100
    rr[inject] = 400  # premature (very short)
    rr[inject + 1] = 1200  # compensatory pause (very long)

    flagged = set(detect_artifacts_fixpeaks(rr_values=rr)["artifact_indices"])

    assert flagged, "detector should flag the injected ectopic"
    # Exact alignment: the injected beats themselves are flagged.
    assert inject in flagged, "injected short beat must be flagged at its own index"
    assert inject + 1 in flagged, "compensatory beat must be flagged at its own index"
    # The off-by-one signature: the beat one PAST the pair must NOT be the
    # only thing marked (the pre-fix code marked inject+1/inject+2).
    assert not (inject not in flagged and (inject + 2) in flagged), (
        "flagged set shows the old peaks-space off-by-one drift"
    )


def test_indices_never_exceed_rr_length():
    """No returned index may equal or exceed len(rr) (peaks-space leak guard)."""
    rng = np.random.default_rng(7)
    rr = [int(round(x)) for x in (800 + 20 * rng.standard_normal(300))]
    for idx in (50, 150, 250):
        rr[idx] = 250  # flagrant artifacts

    result = detect_artifacts_fixpeaks(rr_values=rr)
    for idx in result["artifact_indices"]:
        assert 0 <= idx < len(rr)
