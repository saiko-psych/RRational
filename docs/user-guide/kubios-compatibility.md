# Kubios-Compatible Output

How to configure RRational so that the HRV results match Kubios HRV Scientific
output as closely as possible (typically ±5% on LF/HF for properly matched
segments). For the validation evidence, see [Validation](../science/validation.md).

## TL;DR

1. Open the Analysis tab → Group Analysis (or Sequence Comparison)
2. Set **Frequency-domain pipeline** to **"Kubios-compatible (absolute ms²,
   4 Hz interpolation, 180 s Welch)"**
3. Use the same artifact correction in both tools (Kubios "Automatic correction"
   ↔ RRational `nn_correction.method: kubios` in the .rrational file)
4. Run the analysis. LF/HF values are now in absolute ms² — directly comparable
   to Kubios

## Step-by-step

### 1. Match the artifact correction

Kubios offers three beat correction modes:

| Kubios setting | What RRational matches |
|----------------|------------------------|
| `none (0.3)` | Leave `nn_correction.method` empty in your .rrational file |
| `Automatic correction (0.3)` | Use the Kubios-style correction in RRational (Participants tab → "Apply NN correction") |
| `Threshold-based` | Not directly supported — use Automatic instead |

In the .rrational file, check the per-section `nn_correction` block:

```yaml
nn_correction:
  method: kubios
  corrected_at: '2026-01-19T16:24:30.093241'
  intervals_corrected: 2
```

If `method` is `none`, RRational will compute HRV on raw RR intervals — matching
the Kubios "none" beat correction mode.

### 2. Switch to Kubios-compatible frequency pipeline

In the Analysis tab, the new **"Frequency-domain pipeline"** dropdown appears
under each analysis mode (Group Analysis, Sequence Comparison).

Choose:
- **"NeuroKit2 default"** for new projects (normalized PSD, NK2 reference)
- **"Kubios-compatible"** when you want absolute ms² and Kubios cross-comparison

The setting persists in your session and applies to all subsequent analyses
until you change it.

### 3. Use segments of comparable length

Kubios's default Welch window is **180 seconds** with 50% overlap. RRational's
Kubios mode replicates this exactly. To get the most reliable PSD estimates:

- **Recommended segment length**: ≥ 5 minutes (gives 2+ Welch windows)
- **Optimal segment length**: ≥ 10 minutes (gives 5+ Welch windows, lower variance)

Shorter segments will work but produce noisier LF/HF estimates. This is a
fundamental Welch-PSD limitation, not specific to RRational.

### 4. Verify with a known case

Take one participant whose RR data you've also processed with Kubios. Compute
HRV in both tools with matching settings. Expected agreement (from our
[validation](../science/validation.md)):

| Metric | Expected Δ |
|--------|------------|
| MeanNN | < 1% |
| RMSSD | < 2% |
| HF (ms²) | < 5% |
| LF (ms²) | < 10% |
| LF/HF | < 10% |
| **SDNN** | **30–60% higher in RRational** (by design — see below) |

## The pNN50 difference (important!)

You may see large pNN50 discrepancies between Kubios and RRational **only when
beat correction is active in either tool**. Example: Kubios with "Automatic
correction (0.3)" reports pNN50 = 16.45% while RRational reports 49.86% on the
same nominal segment.

This is **not a bug**. pNN50 is a **threshold-based binary counter** (only
diffs > 50 ms count) — every single corrected beat that lands just above or
below the 50 ms cutoff flips the count. Continuous metrics (RMSSD, LF, HF)
remain stable because they integrate over all diffs.

**Quantitative evidence** ([Rohr et al. 2024](https://doi.org/10.1038/s41598-023-50701-4)):

| Metric | Error sensitivity (% per ms noise SD) |
|--------|---------------------------------------|
| LF | 0.24% |
| SDNN | 0.61% |
| HF | 0.71% |
| RMSSD | 1.57% |
| **pNN50** | **2.75%** (highest!) |

Rohr et al. recommend pNN50 *"be used with caution"*. Berntson & Lozano 2005
([DOI](https://doi.org/10.1111/j.1469-8986.2005.00277.x)) showed mathematically
that RMSSD acts as a robust high-pass filter while pNN50's discrete cutoff
makes it fragile.

**Recommendations**:

1. **Prefer RMSSD** over pNN50 for parasympathetic activity — same physiological
   information, ~4× more robust to artifact correction
2. **For Kubios-comparable pNN50**: Use `BeatCorrection: none` in both tools
   (RRational then reports identical pNN50 to ±2%)
3. **For publication**: Always state the exact beat correction pipeline if you
   report pNN50 (Quigley et al. 2024 reporting guidelines)
4. **Alternative**: Report pNN20 ([Mietus et al. 2002](https://doi.org/10.1136/heart.88.4.378))
   — less floor effect, more robust to single corrected beats

## The SDNN difference (important!)

You **will** see a noticeable SDNN difference between Kubios and RRational.
This is **not a bug** — it's two different definitions:

- **RRational SDNN**: Standard deviation of raw NN intervals after artifact
  correction. This is the **Task Force 1996 definition** and matches every
  textbook formula.
- **Kubios SDNN**: Standard deviation of the **detrended interpolated signal**
  (after Smoothness Priors λ=500 detrending applied to 4 Hz resampled RR).
  This is a Kubios-proprietary variant.

The Kubios SDNN is **typically 30–60% lower** than the standard SDNN, because
detrending removes low-frequency variance.

**Recommendation for papers**: Always state which SDNN definition you used.
RRational reports the international standard (Task Force 1996). If you need
the Kubios variant for direct comparison with Kubios output, mention this
explicitly in your methods section.

## Frequency band differences

| Band | RRational Kubios mode | RRational NeuroKit2 default | Kubios default |
|------|----------------------|-----------------------------|----------------|
| VLF | 0.0–0.04 Hz | 0.0033–0.04 Hz | 0.0–0.04 Hz |
| LF | 0.04–0.15 Hz | 0.04–0.15 Hz | 0.04–0.15 Hz |
| HF | 0.15–0.40 Hz | 0.15–0.40 Hz | 0.15–0.40 Hz |
| ULF | — | 0–0.0033 Hz | — |
| VHF | — | 0.4–0.5 Hz | — |

Kubios does not report ULF / VHF by default.

## What if my values still don't match?

Common causes of remaining discrepancies (in order of likelihood):

1. **Different segment boundaries**: Verify both tools analyze the *exact same*
   time range. A 1-second shift can change LF/HF by 5%.
2. **Different beat correction outcome**: Even with both set to "Kubios-style",
   the corrected NN intervals can differ slightly because of implementation
   details. Open the `.rrational` file and check `intervals_corrected` vs
   Kubios's `S{N}_Beats corrected (%)`.
3. **Short segments (< 5 min)**: PSD variance dominates — you'll see ±10–20%
   differences purely from finite-window effects.
4. **Different RR series**: If you used different export options from your
   recording device (e.g., raw vs Kubios-format), the NN intervals themselves
   differ.

## Caveats

- The `freq_method` setting is **stored in session state** and is **not**
  persisted to the project YAML or .rrational files. If you close and reopen
  RRational, the default reverts to `neurokit`.
- Existing cached `group_analysis_results.yml` files were computed with whichever
  `freq_method` was active at the time. Re-run the analysis after switching
  modes to refresh cached values.
- The Participants tab's PSD plot uses a separate computation
  (see `analysis_plots.py`). It does not yet honor the `freq_method` setting —
  this affects only the displayed graph, not the metrics in the tables.

## References

- [Validation report with cross-validation evidence](../science/validation.md)
- [Processing Pipeline overview](../science/processing-pipeline.md)
- Tarvainen, M.P., Niskanen, J.P., Lipponen, J.A., et al. (2014).
  *Kubios HRV — Heart rate variability analysis software.*
  Computer Methods and Programs in Biomedicine, 113(1), 210–220.
  [doi:10.1016/j.cmpb.2013.07.024](https://doi.org/10.1016/j.cmpb.2013.07.024)
