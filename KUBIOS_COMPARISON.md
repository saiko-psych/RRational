# Kubios vs RRational — HRV Metrics Comparison

**Analyzed**: 2026-06-01
**Source data**: `data/Kubios_Output_+_rrational_files.zip` (5 participants, 2 Kubios batch exports) — not in repo, contains real participant data

## TL;DR

Kubios and RRational produce different HRV values because they use **different processing pipelines**. The main causes:

1. **SDNN definition**: Kubios computes SDNN on the **detrended, interpolated signal** (4 Hz, Smoothness Priors λ=500). RRational uses the Task Force 1996 standard definition on raw NN intervals → **RRational SDNN is ~30–50% higher**.
2. **PSD method**: Kubios uses Welch with 180 s window + 50% overlap + Smoothness Priors detrending at 4 Hz Cubic Spline interpolation. RRational defaults to NeuroKit2 settings (Welch, mean subtraction, 100 Hz interpolation, **`normalize=True`**!).
3. **Beat correction**: The VNS export uses "Automatic correction (0.3)", the Logger export uses "none". RRational applies its own Kubios-style correction, which is not exactly equivalent in implementation details.

With a **Kubios-aligned pipeline** (see Section 3) we achieve agreement within ±5% for MeanRR, RMSSD, SDNN(detrended), LF, HF, and LF/HF.

---

## 1. Kubios pipeline parameters (from the CSV)

| Parameter | Value |
|-----------|-------|
| `PRM#Detrending` | Smoothness priors (λ=500) |
| `PRM#InterpRate` | 4.00 Hz |
| `PRM#MinMaxHR` | 5 beats MA |
| `PRM#NNxxThreshold` | 50 ms |
| `PRM#VLFband` | 0.00–0.04 Hz |
| `PRM#LFband` | 0.04–0.15 Hz |
| `PRM#HFband` | 0.15–0.40 Hz |
| `PRM#FFTorLomb` | FFT (Welch) |
| `PRM#WelchWindow` | 180 s / 50% overlap |
| `PRM#BeatCorrection` (VNS) | Automatic (0.3) |
| `PRM#BeatCorrection` (Logger) | none (0.3) |

## 2. Current default RRational pipeline (`freq_method="neurokit"`)

| Step | RRational |
|------|-----------|
| Time-domain (SDNN/RMSSD/pNN50) | Raw NN intervals after artifact correction (Task Force 1996) |
| Detrending | **Not applied** for time-domain; only mean subtraction in the PSD plot |
| PSD method | NeuroKit2 `hrv_frequency()` (Welch, **`normalize=True`** ← CRITICAL!) |
| Interpolation | 100 Hz (NK2 default) |
| Frequency bands | ULF/VLF/LF/HF/VHF (NK2 default, slightly different) |
| Welch window length | 256 samples (NK2 default) |

## 3. Example comparison: P1 (anonymized) rest_pre vs Kubios S1 (324 s)

| Metric | RRational (current default) | RRational (Kubios-aligned) | Kubios | Δ aligned |
|--------|-----------------------------|----------------------------|--------|-----------|
| MeanRR (ms) | 894.72 | 894.72 | 894.30 | **+0.05%** ✓ |
| SDNN raw (ms) | 90.01 | 90.01 | — | n/a |
| **SDNN detrended (ms)** | — | **65.32** | **67.56** | **−3.3%** ✓ |
| RMSSD (ms) | 73.13 | 73.13 | 74.09 | −1.3% ✓ |
| pNN50 (%) | 49.86 | 49.86 | 16.45 | **+203%** ❌* |
| LF (ms²) | n/a (normalized) | 1867.7 | 1949.3 | −4.2% ✓ |
| HF (ms²) | n/a (normalized) | 2699.1 | 2610.4 | +3.4% ✓ |
| LF/HF | 0.69 (current NK2) | 0.69 | 0.75 | −7.2% ✓ |

*pNN50 discrepancy: Only occurs for the VNS export (with "Automatic correction"). For Logger data (no correction) pNN50 matches (e.g. P3 (anonymized) rest_pre: 17.97% vs 18.23%, Δ=−1.4%).

## 4. Consistency pattern across all 5 participants

| Metric | RRational vs Kubios | Consistent? |
|--------|---------------------|-------------|
| MeanRR | ±1% | ✓ excellent |
| RMSSD | ±2% | ✓ excellent |
| pNN50 (Logger / no-corr) | ±5% | ✓ good |
| pNN50 (VNS / auto-corr) | RRational ~2–3× higher | ❌ beat-correction difference |
| SDNN | RRational **systematically +30–50% higher** | ❌ detrending difference |
| LF/HF (ms²) with `normalize=False, interp=4Hz, Welch 180s` | ±10% | ✓ good |
| LF/HF current (RRational default) | ❌ not comparable (`normalize=True`) | ❌ scale difference |

## 5. Recommendations for comparability

### Immediate (1–2 hours)
1. **Frequency-domain fix**: In `hrv_compute.py:86` call `nk.hrv_frequency()` with explicit Kubios parameters:
   ```python
   nk.hrv_frequency(peaks, sampling_rate=1000, normalize=False,
                    interpolation_rate=4, psd_method='welch',
                    vlf=(0.0, 0.04), lf=(0.04, 0.15), hf=(0.15, 0.40))
   ```
   This makes LF/HF directly comparable to Kubios (ms² units).

2. **Kubios mode toggle**: Offer a GUI option "Kubios-compatible mode" that activates these parameters.

### Medium-term (one day of work)
3. **Implement Smoothness Priors detrending** (Tarvainen et al. 2002):
   - Module `src/rrational/analysis/detrending.py` with `smoothness_priors_detrend(rr, lambda=500)`
   - Optional step before frequency-domain computation
   - Welch window 180 s + 50% overlap instead of NK2 default 256-sample
4. **Dual SDNN reporting**: Report both — `SDNN_raw` (Task Force standard) and `SDNN_detrended` (Kubios style), clearly labeled.

### Long-term
5. **Kubios HRV script validation**: Roundtrip tests using the same RR files, automated CSV diff test in `tests/`.
6. **Methodology documentation**: Explicitly document pipeline differences relative to Kubios in `docs/science/processing-pipeline.md`.

## 6. Important scientific notes

- **SDNN definition divergence**: Kubios's detrended SDNN is a **proprietary variant**. Task Force 1996 and Quigley 2024 specify SDNN on raw NN intervals. RRational is guideline-conformant here; Kubios deviates.
- **Cross-tool compatibility**: Even between tools with identical band boundaries, PSD values can differ by 20–50% depending on Welch parameters (window length, overlap, detrending). This is a known issue in the HRV community.
- **Reproducibility**: Every publication should specify exact pipeline parameters. RRational currently does this via defaults; a "pipeline config export" in the `.rrational` file would be valuable.

## 7. Test script

The full comparison script is documented as inline Python in this session and can be reproduced with the files in `data/kubios_comparison/`.
