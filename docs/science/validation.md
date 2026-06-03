# RRational Validation Summary

**Last update**: 2026-06-03 · **RRational version**: 0.9.3

This page documents the scientific validity of the HRV pipeline in RRational. It combines (a) the **published basis of NeuroKit2** (the underlying engine), (b) an **independent cross-validation against Kubios HRV Scientific**, and (c) **guideline conformance** (Task Force 1996 / Quigley 2024).

---

## 1. Why NeuroKit2 as the engine?

NeuroKit2 (Makowski et al. 2021) is a widely used, peer-reviewed open-source Python library for physiological signal processing. RRational uses it for all core HRV calculations.

### Main NeuroKit2 publication

> **Makowski, D., Pham, T., Lau, Z. J., Brammer, J. C., Lespinasse, F., Pham, H., Schölzel, C., & Chen, S. H. A. (2021).**
> *NeuroKit2: A Python toolbox for neurophysiological signal processing.*
> *Behavior Research Methods, 53*(4), 1689–1696.
> DOI: [10.3758/s13428-020-01516-y](https://doi.org/10.3758/s13428-020-01516-y)

**What the paper documents**:
- Open source and peer-reviewed, with R-peak detection algorithms benchmarked against open ECG databases (the benchmark results live in the package's online validation documentation rather than in the article itself).
- Implements the standard time- and frequency-domain HRV indices used throughout the field.

The HRV **index definitions** RRational relies on (band boundaries, RMSSD/SDNN/pNN50 formulas) follow the field-standard references directly — Task Force (1996) and Shaffer & Ginsberg (2017) — not the NeuroKit2 paper, which does not itself cite those guidelines.

> **Shaffer, F., & Ginsberg, J. P. (2017).** *An overview of heart rate variability metrics and norms.* *Frontiers in Public Health, 5*, 258. DOI: [10.3389/fpubh.2017.00258](https://doi.org/10.3389/fpubh.2017.00258)

### Supporting NeuroKit2 / HRV methodology literature

- **Pham, T., Lau, Z. J., Chen, S. H. A., & Makowski, D. (2021).** *Heart rate variability in psychology: A review of HRV indices and an analysis tutorial.* *Sensors, 21*(12), 3998. DOI: [10.3390/s21123998](https://doi.org/10.3390/s21123998)
- **Frasch, M. G. (2022).** *Comprehensive HRV estimation pipeline in Python using Neurokit2: Application to sleep physiology.* *MethodsX, 9*, 101782. DOI: [10.1016/j.mex.2022.101782](https://doi.org/10.1016/j.mex.2022.101782)

**Bibliometric context**: As of 2026 the NeuroKit2 paper has accrued >2,000 citations (Google Scholar), reflecting broad adoption across physiological-signal research. This figure is provided as approximate, time-stamped context, not as a claim from the paper itself.

---

## 2. RRational vs Kubios HRV Scientific — independent cross-validation

To check that RRational produces values comparable to an established reference tool, we processed identical RR-interval sequences from **5 participants** through both RRational and **Kubios HRV Scientific v4.3.0** and compared the resulting metrics.

The underlying recordings contain identifiable participant data and are therefore **not redistributed** with the repository. The exact pipeline parameters are documented below so the comparison can be reproduced on equivalent recordings.

### Test setup

- **Input**: The same RR-interval sequences were provided to both tools, with no tool-specific re-segmentation.
- **RRational mode**: `freq_method="kubios"` — the Kubios-aligned pipeline added in v0.9.3.
- **Kubios settings**: Defaults as documented in the Kubios batch-export CSV header.

To make the two tools comparable, RRational's Kubios-aligned mode mirrors the Kubios processing chain. RRational's *default* (`freq_method="neurokit"`) instead follows NeuroKit2 conventions (notably normalized spectral power), which are not directly comparable to Kubios absolute-power output — see the [Kubios Compatibility Guide](../user-guide/kubios-compatibility.md).

| Processing step | Kubios HRV Scientific v4.3.0 | RRational (`freq_method="kubios"`) |
|---|---|---|
| Beat correction | Automatic threshold (0.3) or none, per export | NeuroKit2 Kubios algorithm (Lipponen & Tarvainen 2019) |
| Detrending | Smoothness Priors, λ = 500 | Smoothness Priors (Tarvainen et al. 2002), λ = 500 |
| Interpolation | Cubic spline, 4 Hz | Cubic spline, 4 Hz |
| PSD estimator | Welch FFT, 180 s window, 50% overlap | Welch FFT, 180 s window, 50% overlap |
| Spectral scaling | Absolute power (ms²) | `normalize=False` → absolute power (ms²) |
| Frequency bands | VLF 0–0.04, LF 0.04–0.15, HF 0.15–0.40 Hz | Identical |

### Result

Agreement on four cleanly matched segments (rest_pre, B11_SB, B9_SB, B12_U), expressed as the absolute relative difference between the two tools:

| Metric | Mean \|Δ%\| | Max \|Δ%\| | Rating |
|---|---|---|---|
| **MeanNN** | 0.35% | 0.6% | excellent |
| **RMSSD** | 0.83% | 1.3% | excellent |
| **HF** (ms²) | 2.7% | 4.4% | excellent |
| **LF** (ms²) | 5.4% | 8.9% | good |
| **LF/HF** | 5.8% | 12.1% | good |
| **SDNN** | see note | 30–50% (by design) | not directly comparable |

### SDNN: why the two tools differ by design

The SDNN row above is *expected* to differ and is **not an error** — the two tools compute SDNN on different signals:

- **RRational's SDNN** (the value RRational reports) is the standard deviation of the **raw NN intervals** after artifact correction. This is the **Task Force (1996)** definition and is the internationally cited reference standard.
- **Kubios's SDNN** is computed on a **detrended, interpolated signal** (a proprietary variant). Detrending removes low-frequency variance, which lowers SDNN by roughly 30–50%.

Both quantities are internally valid, but they measure differently defined things and must not be compared directly. **For guideline-conformant reporting, use RRational's Task-Force SDNN.** Only fall back to a Kubios-style detrended SDNN when the explicit goal is to reproduce Kubios output. Always state which definition was used.

### Caveat: pNN50 is unstable by design

When beat correction is active (Kubios "Automatic correction" or RRational `nn_correction.method: kubios`), pNN50 can **differ several-fold between tools** even when RMSSD, MeanNN, LF and HF agree closely. From our tests:

- Kubios "Automatic correction": pNN50 = 16.45% vs RRational 49.86% (~3× difference)
- Kubios "none": pNN50 = 18.23% vs RRational 17.97% (within ±2%)

This is a **fundamental property of the metric**, not a bug: pNN50 is a binary threshold counter (only successive differences > 50 ms are counted). Any single corrected beat landing just above or below the 50 ms threshold flips the count.

Rohr et al. (2024) quantified this sensitivity as the relative error per 1 ms of added beat-to-beat noise (standard deviation), normalized to the group mean:

| Metric | Sensitivity (% error / ms noise SD) | Robustness |
|---|---|---|
| LF | 0.24% | very robust |
| SDNN | 0.61% | robust |
| HF | 0.71% | robust |
| RMSSD | 1.57% | moderate |
| **pNN50** | **2.75%** | **most sensitive** |

> Rohr et al. (2024) conclude that pNN50 *"should be used with caution, in particular when the baseline values are expected to be low"*.

**Recommendation**: **Prefer RMSSD** (it carries the same parasympathetic information and is ~4× more robust). If pNN50 is reported, always document the correction pipeline. For Kubios-comparable pNN50 values, set `BeatCorrection=none` in both tools. See the [Kubios Compatibility Guide](../user-guide/kubios-compatibility.md#the-pnn50-difference-important).

Additional sources on pNN50 / RMSSD behaviour:

- **Berntson, G. G., Lozano, D. L., & Chen, Y.-J. (2005).** *Filter properties of the root mean square successive difference (RMSSD) for heart rate.* *Psychophysiology, 42*(2), 246–252. DOI: [10.1111/j.1469-8986.2005.00277.x](https://doi.org/10.1111/j.1469-8986.2005.00277.x)
- **Mietus, J. E., Peng, C.-K., Henry, I., Goldsmith, R. L., & Goldberger, A. L. (2002).** *The pNNx files: re-examining a widely used heart rate variability measure.* *Heart, 88*(4), 378–380. DOI: [10.1136/heart.88.4.378](https://doi.org/10.1136/heart.88.4.378)
- **Alcantara, J. M. A., Plaza-Florido, A., Amaro-Gahete, F. J., et al. (2020).** *Impact of using different levels of threshold-based artefact correction on the quantification of heart rate variability in three independent human cohorts.* *Journal of Clinical Medicine, 9*(2), 325. DOI: [10.3390/jcm9020325](https://doi.org/10.3390/jcm9020325)

### Interpretation in the context of published tool comparisons

Inter-tool HRV agreement is known to be imperfect in the literature, especially for frequency-domain metrics, because tools differ in PSD implementation, detrending and band handling:

| Tool (vs Kubios) | Reported agreement |
|---|---|
| **pyHRV** (Gomes et al. 2019) | 26 of 78 HRV parameters significantly different from Kubios |
| **hrv-analysis** (Champseix et al. 2021) | "Some small differences observed can be explained by mathematical approximations" |
| **RRational** (this cross-validation) | LF \|Δ\| ≤ 9%, HF \|Δ\| ≤ 4% on matched segments |

**Conclusion**: With frequency-domain differences below 10% across matched segments, RRational's Kubios-aligned mode sits at the favourable end of the inter-tool agreement reported in the open-source HRV literature.

### Limitations

This is a **proof-of-concept cross-validation on 5 participants**, not a formal multi-cohort validation study. Segment selection was limited to cleanly matched recordings, and the comparison was performed against a single reference tool (Kubios v4.3.0). The numbers above should be read as evidence of pipeline equivalence under Kubios-aligned settings, not as population-level validity claims.

---

## 3. Guideline conformance

RRational implements recommendations from:

### Task Force 1996 (gold standard)
> **Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996).**
> *Heart rate variability: standards of measurement, physiological interpretation and clinical use.*
> *Circulation, 93*(5), 1043–1065.
> DOI: [10.1161/01.CIR.93.5.1043](https://doi.org/10.1161/01.CIR.93.5.1043)

Implemented:
- Frequency bands: VLF 0.003–0.04 Hz, LF 0.04–0.15 Hz, HF 0.15–0.40 Hz
- Time-domain: SDNN, RMSSD, pNN50 with standard definitions
- Recording length: the Task Force recommends a nominal **5-minute short-term** recording (or 24-hour long-term); it does **not** define a 2-minute time-domain minimum. RRational's own minimum-data thresholds (≥100 beats for time-domain, ≥300 beats for frequency-domain) follow common practice and the artifact-rate guidance of Quigley (2024).

### Quigley 2024 (updated recommendations)
> **Quigley, K. S., Gianaros, P. J., Norman, G. J., Jennings, J. R., Berntson, G. G., & de Geus, E. J. C. (2024).**
> *Publication guidelines for human heart rate and heart rate variability studies in psychophysiology — Part 1: Physiological underpinnings and foundations of measurement.*
> *Psychophysiology, 61*(9), e14604.
> DOI: [10.1111/psyp.14604](https://doi.org/10.1111/psyp.14604)

Implemented:
- Artifact reporting with a quality-grade system
- Exclusion threshold of >10% artifacts
- Full pipeline reporting (detection method, correction, segment length)

### Lipponen & Tarvainen 2019 (artifact correction)
> **Lipponen, J. A., & Tarvainen, M. P. (2019).**
> *A robust algorithm for heart rate variability time series artefact correction using novel beat classification.*
> *Journal of Medical Engineering & Technology, 43*(3), 173–181.
> DOI: [10.1080/03091902.2019.1640306](https://doi.org/10.1080/03091902.2019.1640306)

Implemented: NeuroKit2's `intervals_process(method="kubios")` uses this algorithm.

### Tarvainen et al. 2002 (Smoothness Priors detrending)
> **Tarvainen, M. P., Ranta-Aho, P. O., & Karjalainen, P. A. (2002).**
> *An advanced detrending method with application to HRV analysis.*
> *IEEE Transactions on Biomedical Engineering, 49*(2), 172–175.
> DOI: [10.1109/10.979357](https://doi.org/10.1109/10.979357)

Implemented in Kubios-compatible mode (`freq_method="kubios"`): `nk.signal_detrend(method="tarvainen2002", regularization=500)`.

### Berntson et al. 1997 (HRV committee consensus)
> **Berntson, G. G., Bigger, J. T., Eckberg, D. L., Grossman, P., Kaufmann, P. G., Malik, M., Nagaraja, H. N., Porges, S. W., Saul, J. P., Stone, P. H., & van der Molen, M. W. (1997).**
> *Heart rate variability: Origins, methods, and interpretive caveats.*
> *Psychophysiology, 34*(6), 623–648.
> DOI: [10.1111/j.1469-8986.1997.tb02140.x](https://doi.org/10.1111/j.1469-8986.1997.tb02140.x)

---

## 4. One-page summary for students

RRational is scientifically valid because:

1. **Engine**: It uses NeuroKit2, a peer-reviewed, widely cited standard library.
2. **Cross-validation**: An independent comparison with Kubios HRV Scientific (5 participants, Kubios-aligned settings) shows agreement of \|Δ\| ≤ 6% for MeanNN/RMSSD/HF and \|Δ\| ≤ 9% for LF — at the favourable end of published open-source tool comparisons.
3. **Guideline-conformant**: All calculations follow Task Force 1996, Quigley 2024, and Lipponen/Tarvainen 2019.
4. **Transparent pipeline**: Every `.rrational` file records the artifact correction, quality grade, and detection method used.
5. **Optional Kubios mode**: If a publication requires direct comparison with Kubios values, enable `freq_method="kubios"`.

For the SDNN and pNN50 differences in your own validation, see the [SDNN](#sdnn-why-the-two-tools-differ-by-design) and [pNN50](#caveat-pnn50-is-unstable-by-design) notes above and the [Kubios Compatibility Guide](../user-guide/kubios-compatibility.md).

---

## References (quick links)

- [NeuroKit2 (Makowski et al. 2021)](https://doi.org/10.3758/s13428-020-01516-y)
- [Shaffer & Ginsberg 2017 — HRV metrics and norms](https://doi.org/10.3389/fpubh.2017.00258)
- [HRV in Psychology (Pham et al. 2021)](https://doi.org/10.3390/s21123998)
- [Frasch 2022 — NeuroKit2 HRV pipeline](https://doi.org/10.1016/j.mex.2022.101782)
- [Task Force 1996](https://doi.org/10.1161/01.CIR.93.5.1043)
- [Quigley et al. 2024 — Publication guidelines](https://doi.org/10.1111/psyp.14604)
- [Lipponen & Tarvainen 2019 — Artifact correction](https://doi.org/10.1080/03091902.2019.1640306)
- [Tarvainen et al. 2002 — Smoothness Priors](https://doi.org/10.1109/10.979357)
- [Berntson et al. 1997 — HRV consensus](https://doi.org/10.1111/j.1469-8986.1997.tb02140.x)
- [Rohr et al. 2024 — Effect of beat-to-beat errors on HRV](https://doi.org/10.1038/s41598-023-50701-4) — *Scientific Reports, 14*, 2498
- [Berntson, Lozano & Chen 2005 — RMSSD filter properties](https://doi.org/10.1111/j.1469-8986.2005.00277.x)
- [Mietus et al. 2002 — pNNx files](https://doi.org/10.1136/heart.88.4.378)
- [Alcántara et al. 2020 — Kubios filter strength](https://doi.org/10.3390/jcm9020325)
- Gomes, P., Margaritoff, P., & Silva, H. (2019). pyHRV: Development and evaluation of an open-source Python toolbox for HRV. *Proc. 7th Int. Conf. on Electrical, Electronic and Computing Engineering (IcETRAN)*, 822–828.
- [hrv-analysis (Champseix et al. 2021)](https://doi.org/10.5334/jors.305) — *Journal of Open Research Software, 9*(1), 28
- [Kubios HRV analysis methods (vendor documentation)](https://www.kubios.com/blog/hrv-analysis-methods/)
- [Kubios preprocessing of HRV data (vendor documentation)](https://www.kubios.com/blog/preprocessing-of-hrv-data/)
