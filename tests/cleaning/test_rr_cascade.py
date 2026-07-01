"""Regression tests for the sudden-change cascade-drop fix in ``clean_rr_intervals``.

Round 30 fixed a bug where a single legitimate RR jump would leave
``previous_rr`` stale at the *pre-jump* value. Every subsequent (physiologically
normal) beat was then compared against that stale baseline and, if it happened
to exceed the relative threshold against it, was dropped too -- cascading a
single artefact into a long run of discarded good beats.

The fix updates ``previous_rr`` to the flagged beat's value before continuing,
matching the behaviour ``clean_rr_intervals_with_flags`` already had. These
tests lock that in: after one sudden jump the following normal beats must be
RETAINED, and the two cleaning variants must agree on the sudden-change count.
"""

from rrational.cleaning.rr import (
    CleaningConfig,
    clean_rr_intervals,
    clean_rr_intervals_with_flags,
)
from rrational.io.hrv_logger import RRInterval


def _mk(rr_values):
    """Build an RRInterval series with monotonically summed elapsed_ms."""
    samples = []
    elapsed = 0
    for rr in rr_values:
        samples.append(RRInterval(timestamp=None, rr_ms=rr, elapsed_ms=elapsed))
        elapsed += rr
    return samples


def test_single_jump_does_not_cascade_drop_following_beats():
    """A lone upward jump must not drop the normal beats that follow it.

    Series: baseline 400ms, one jump to 1600ms (>100% change -> sudden), then
    three normal 1000ms beats. Against the *stale* pre-jump value (400) each
    1000ms beat is a 150% change and, under the old bug, was cascade-dropped.
    Against the correctly-updated previous value it is a benign 37.5% change
    and must be retained.
    """
    samples = _mk([400, 400, 1600, 1000, 1000, 1000])

    cleaned, stats = clean_rr_intervals(samples)  # default CleaningConfig

    # Only the single 1600ms jump is removed; the three trailing 1000ms beats
    # survive. Under the buggy behaviour cleaned would be just [400, 400].
    assert [c.rr_ms for c in cleaned] == [400, 400, 1000, 1000, 1000]
    assert stats.retained_samples == 5
    assert stats.removed_samples == 1
    assert stats.reasons["sudden_change"] == 1
    assert stats.reasons["out_of_range"] == 0


def test_cascade_fix_matches_with_flags_variant():
    """Both cleaning variants must agree on the sudden-change count.

    The with-flags path always updated ``previous_rr`` correctly; the fix
    brings the drop path into line. Consistency between the two is the
    invariant we guard here.
    """
    samples = _mk([400, 400, 1600, 1000, 1000, 1000])

    cleaned, stats = clean_rr_intervals(samples)
    flagged, fstats = clean_rr_intervals_with_flags(samples)

    # with-flags keeps every interval but flags exactly the one jump.
    assert len(flagged) == len(samples)
    assert [f.is_flagged for f in flagged] == [False, False, True, False, False, False]
    assert flagged[2].flag_reason == "sudden_change"

    # The two variants must report identical bookkeeping.
    assert fstats.retained_samples == stats.retained_samples == len(cleaned)
    assert fstats.removed_samples == stats.removed_samples
    assert fstats.reasons["sudden_change"] == stats.reasons["sudden_change"] == 1


def test_task_series_retains_normal_beats_after_jump():
    """The reported series [800, 800, 1700, 800, 800, 800] keeps all normals.

    Here the post-jump beats equal the pre-jump baseline, so the count is the
    same under both old and fixed code -- but this pins the documented case:
    one sudden 1700ms beat removed, the five 800ms beats retained, and the
    two variants in agreement.
    """
    samples = _mk([800, 800, 1700, 800, 800, 800])

    cleaned, stats = clean_rr_intervals(samples)
    flagged, fstats = clean_rr_intervals_with_flags(samples)

    assert [c.rr_ms for c in cleaned] == [800, 800, 800, 800, 800]
    assert stats.retained_samples == 5
    assert stats.reasons["sudden_change"] == 1

    assert [f.is_flagged for f in flagged] == [False, False, True, False, False, False]
    assert fstats.retained_samples == stats.retained_samples
    assert fstats.reasons["sudden_change"] == stats.reasons["sudden_change"]
