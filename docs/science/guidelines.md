# State-of-the-art HRV analysis for psychological research

Heart rate variability analysis has undergone significant methodological and interpretive evolution, culminating in the **2024 Quigley et al. Psychophysiology committee report** that fundamentally updates recommendations from the foundational 1996 Task Force guidelines. The field has reached critical consensus on several contested issues: RMSSD and HF-HRV remain the most defensible parasympathetic markers, the LF/HF ratio should not be interpreted as "sympathovagal balance," and **60-second recordings** are now validated for specific metrics in field settings. For psychological researchers, understanding both the technical pipeline—from raw signal to meaningful metric—and the physiological interpretations is essential for rigorous, reproducible science.

## From raw signal to heart rate variability metrics

The HRV analysis pipeline begins with accurate detection of cardiac events. The **Pan-Tompkins algorithm (1985)** remains the foundation of R-peak detection, employing bandpass filtering (5-15 Hz), differentiation, squaring, moving window integration, and adaptive dual thresholds—achieving **99.3% sensitivity and 99.8% positive predictivity** on the MIT-BIH database. Variants including Hamilton-Tompkins and the recent Pan-Tompkins++ (2022) offer refinements: the latter extends bandpass to 5-18 Hz, adds a third adaptive threshold with morphological comparison, reducing false positives by 2.8% while increasing speed by 33%.

NeuroKit2 implements multiple detection algorithms accessible through a unified interface, with its proprietary "neurokit" method benchmarked as outperforming traditional approaches. For **PPG signals**, specialized algorithms are necessary due to slower waveform transitions and greater motion artifact susceptibility—HeartPy and the Aboy++ automatic beat detector address these challenges, though PPG-derived HRV (technically pulse rate variability) introduces ±5 ms timing uncertainty that propagates to approximately **±10% maximum error** in derived metrics.

**Artifact detection and correction** represents a critical pipeline stage where the Lipponen & Tarvainen (2019) algorithm has emerged as the state-of-the-art. This approach uses two time-varying thresholds derived from distributions of successive RR differences and deviations from local medians, creating a subspace where normal and ectopic beats cluster separately. The algorithm classifies beats into six categories—ectopic, long, short, missed, extra, and normal—achieving **96.96% sensitivity and 99.94% specificity** for real ectopic beats, with post-correction HRV parameter errors below 2% for SDNN, RMSSD, LF, and HF power.

Preprocessing requires careful detrending to remove slow non-stationarities. The **Tarvainen smoothness priors approach (2002)** operates as a time-varying high-pass filter using second-order difference regularization, with λ=500 recommended for HRV applications (corresponding to cutoff below 0.04 Hz). For frequency-domain analysis, non-uniformly sampled IBI data must be interpolated—cubic spline at 4 Hz resampling is standard—before FFT or autoregressive spectral estimation.

## Software tools vary substantially in validation status

**Kubios HRV** stands as the field's gold standard, used in approximately **5,900 scientific publications** across 1,800+ universities. It implements validated artifact correction, smoothness priors detrending, comprehensive time-domain (SDNN, RMSSD, pNN50, TINN, HRV triangular index), frequency-domain (FFT and AR methods), and nonlinear metrics (DFA, entropy measures, Poincaré analysis). The Tarvainen et al. (2014) methodology paper has accumulated over 1,000 citations.

Among open-source alternatives, **NeuroKit2** (Python) offers the most comprehensive feature set with 89+ HRV metrics, multiple peak detection algorithms, and excellent documentation—its 2021 Sensors paper provides a definitive tutorial. Validation against Kubios shows strong agreement for most parameters. **pyHRV** underwent explicit Kubios validation, finding 12 parameters identical, 38 with negligible differences, but 26 with significant discrepancies requiring attention. **HeartPy** specifically targets PPG data with noise-resistant algorithms unsuitable for ECG-focused tools. **RHRV** (R package) excels for statistical research workflows, with its RHRVEasy extension automating population-level analysis.

| Tool | Language | Validation | Best Application |
|------|----------|-----------|------------------|
| Kubios HRV | Desktop | Gold standard (5900+ papers) | Clinical research |
| NeuroKit2 | Python | Published validation | Comprehensive analysis |
| pyHRV | Python | Validated vs Kubios | Research with validation needs |
| HeartPy | Python/C | PPG-validated | Wearable/PPG data |
| RHRV | R | Academic validation | Statistical research |

## Technical requirements define metric validity

**Sampling rate** recommendations have evolved substantially. While the 1996 Task Force accepted 250-500 Hz with interpolation, the **Quigley et al. (2024) guidelines now recommend 1000 Hz minimum** for laboratory research to achieve ±1 ms accuracy. For ECG, 250 Hz remains acceptable for all HRV analysis; 100 Hz suffices only for time-domain metrics. PPG requires ≥100 Hz, though 50 Hz with cubic spline interpolation produces acceptable results for basic metrics.

Recording duration determines which metrics are valid. The **5-minute recording** remains the standard for short-term HRV, encompassing at least 10 cycles at the lowest HF frequency boundary. However, ultra-short-term recordings have gained validation:

- **60 seconds**: RMSSD, SDNN, pNN50, mean RR, even HF and LF/HF (emerging standard for athlete monitoring)
- **120 seconds**: All time-domain metrics adequate for RMSSD-focused protocols
- **180-240 seconds**: Minimum for reliable frequency-domain analysis
- **24 hours**: Required for SDANN, SDNNI, VLF, and prognostic applications

Critical insight: metrics cannot be compared across different recording durations, as SDNN reflects fundamentally different processes at 5-minute versus 24-hour timescales.

## What HRV metrics actually reflect physiologically

**RMSSD** (root mean square of successive differences) is the primary time-domain marker of vagal tone, capturing beat-to-beat variance reflecting rapid parasympathetic modulation operating within single cardiac cycles. It is mathematically equivalent to Poincaré SD1 and relatively robust to respiratory influences. Normal ranges vary considerably by age—**19-48 ms for healthy adults aged 38-42**—with values below 16 ms or above 107 ms warranting clinical attention.

**SDNN** represents total HRV, incorporating both sympathetic and parasympathetic influences. When measured over 24 hours, it serves as the clinical gold standard for cardiovascular risk: patients with SDNN >100 ms show **5.3× lower mortality** than those below 50 ms. However, short-term SDNN reflects different physiological processes and should not be compared with 24-hour values.

**Frequency-domain metrics** require nuanced interpretation. HF power (0.15-0.4 Hz) genuinely reflects respiratory sinus arrhythmia and cardiac parasympathetic activity, with strong correlation to direct vagal recordings. However, beta-adrenergic blockade increases HF amplitude by approximately 10%, indicating sympathetic modulation of vagal effects.

**LF power (0.04-0.15 Hz)** interpretation has undergone paradigm shift. The evidence against LF as a sympathetic marker is now overwhelming: cholinergic antagonists reduce LF by at least 50%, direct sympathetic nerve recordings fail to correlate with LF power, and exercise (increasing sympathetic activity) actually decreases LF. Current consensus holds that LF reflects **baroreflex function**—specifically vagal baroreflex responses to blood pressure fluctuations—not sympathetic tone.

## The LF/HF ratio should not measure sympathovagal balance

The traditional interpretation of LF/HF as an index of "sympathovagal balance" is untenable for multiple reasons. First, it requires LF to reflect sympathetic activity—demonstrably false. Second, when both autonomic branches are blocked pharmacologically, LF/HF paradoxically increases from 1.1 to 8.4, falsely suggesting sympathetic dominance during complete autonomic blockade. Third, the same ratio can result from changes in numerator alone, denominator alone, or any combination—making interpretation mathematically indeterminate.

Furthermore, autonomic responses are frequently non-reciprocal. Post-exercise, sympathetic activity remains elevated while parasympathetic rapidly reactivates. Chemoreceptor activation produces parallel reductions in both branches. The diving reflex triggers increased sympathetic outflow alongside profound vagal bradycardia ("accentuated antagonism"). These documented responses violate the reciprocity assumption underlying sympathovagal balance interpretations.

**Current recommendation**: Avoid LF/HF ratio as a sympathovagal index. Report HF and LF powers separately, consider joint two-dimensional analysis, or use RMSSD/HF as primary parasympathetic markers. Normalized units (LFnu, HFnu) are algebraically redundant with LF/HF and contain identical information.

## Nonlinear metrics capture complexity beyond traditional indices

**Detrended fluctuation analysis (DFA)** characterizes fractal scaling properties of IBI series. Alpha1 (short-term, 4-16 beats) values around 1.0-1.5 indicate healthy dynamics; reduced values predict cardiac pathology. Alpha2 captures longer-term fluctuations influenced by circadian rhythms. However, basic DFA provides only monofractal description, while heart rate is recognized as a multifractal time series potentially requiring a spectrum of exponents.

**Sample entropy and approximate entropy** quantify predictability and complexity—higher values indicate greater irregularity characteristic of healthy systems. Pathological states often show reduced entropy (increased predictability). Sample entropy can predict vagal withdrawal after exercise.

**Poincaré analysis** plots each RR interval against its successor. SD1 (perpendicular to identity line) is mathematically equivalent to RMSSD; SD2 (parallel) correlates with SDNN. The SD1/SD2 ratio relates to Hurst exponent and DFA alpha1, potentially serving as a computationally simpler nonlinear surrogate. Visual pattern analysis—healthy "comet" shapes versus pathological "torpedo" or "fan" patterns—provides qualitative diagnostic information.

Nonlinear metrics excel at detecting hidden autonomic changes that linear methods miss, particularly useful in diabetes, cardiac disease, and aging studies where complexity loss marks deterioration.

## Respiratory sinus arrhythmia requires careful interpretation

RSA—rhythmic HR fluctuations synchronized to breathing—is often equated with HF-HRV, but this conflation is problematic. RSA is **neither an invariably reliable index of cardiac vagal tone nor of central vagal outflow**. Respiratory parameters significantly confound RSA-vagal relationships: lower respiratory frequency increases HRV, while lower tidal volume decreases it. Only approximately 51% of human HRV studies control respiratory rate; merely 11% control tidal volume.

The Quigley et al. (2024) guidelines explicitly state that RSA and HF-HRV should not be used interchangeably—HF-HRV reflects power in a specific frequency band regardless of whether breathing occurs within that band. When respiratory rate falls outside 0.12-0.4 Hz (7-24 breaths/minute), HF power no longer captures respiratory-linked variability.

Quantification methods vary: peak-valley (P2T) measures the difference between longest and shortest RR intervals during respiratory cycles; spectral methods extract HF power; the **Porges-Bohrer method** using moving polynomial filters has been shown more sensitive to vagal mechanisms than either alternative. Transfer function analysis provides the most sophisticated approach by explicitly modeling respiratory influences.

## Psychological applications show consistent vagal-emotion links

The **neurovisceral integration model** (Thayer & Lane, 2000, 2009) provides the theoretical framework linking HRV to psychological function. Higher resting HRV reflects greater functional capacity of cortico-subcortical circuits underlying flexible self-regulation—particularly prefrontal-amygdala pathways. Meta-analyses confirm HRV association with medial prefrontal cortex activation during emotional processing. Greater HRV predicts better recruitment of prefrontal regions to modulate amygdala during cognitive reappraisal.

**Anxiety disorders** show small-to-moderate reductions in HRV across diagnoses including PTSD, panic disorder, GAD, and social anxiety. A 2025 umbrella review found suggestive evidence for decreased HRV in PTSD specifically. **Depression** is associated with reduced vagal tone, though evidence falls below "suggestive" thresholds in umbrella reviews. Critically, greater baseline RMSSD predicts improvement in both depression and PTSD symptoms with treatment—suggesting HRV indexes recovery capacity.

**Emotion regulation capacity** correlates with resting vagal tone: higher HRV individuals show greater cognitive flexibility, better executive function performance, and superior emotional processing. HRV biofeedback meta-analyses demonstrate medium effect sizes (g ≈ 0.38-0.41) for reducing depressive and anxiety symptoms.

**Stress reactivity** studies consistently find that low parasympathetic activity (decreased HF, RMSSD) characterizes stress responses. The "three Rs" paradigm—Rest, Reactivity, Recovery—provides essential experimental structure: baseline HRV indexes tonic vagal capacity, reactivity captures phasic withdrawal during stressors, and recovery reflects parasympathetic rebound indicating autonomic flexibility.

## Polyvagal theory remains scientifically contested

Stephen Porges' polyvagal theory has profoundly influenced trauma therapy, proposing three hierarchical autonomic states: ventral vagal (social engagement), sympathetic (fight/flight), and dorsal vagal (freeze/shutdown). However, scientific consensus among physiologists holds that **each basic physiological assumption has been refuted**.

Key critiques: No evidence supports dorsal vagal motor nucleus influence on bradycardia; emotional freezing predominantly involves ventral nucleus ambiguus. RSA is not unique to mammals—cardiorespiratory interactions appear across vertebrates. Myelinated vagal pathways exist in lungfish, contradicting claims of mammalian uniqueness. Most problematically, Porges (2021) stated the theory "was not proposed to be either proven or falsified"—raising fundamental epistemological concerns.

Current status: The scientific community rejects specific neuroanatomical and evolutionary claims while acknowledging the framework's clinical utility for conceptualizing trauma responses. Practitioners may find value in the body-based approach while recognizing physiological mechanisms differ substantially from those proposed.

## Confounding factors demand rigorous control

**Respiration** is the most critical confounder—respiratory parameters alter both HF and LF power substantially. Recommended practice: monitor respiration during HRV assessment; consider statistical control or paced breathing protocols, though the latter introduces non-naturalistic constraints.

**Body position** profoundly affects HRV: supine increases vagal tone versus seated or standing. Standardize position within studies and include 5-10 minute adaptation periods after position changes.

**Time of day** introduces circadian variability; standardize recording times for short-term studies. Twenty-four-hour recordings should contain at least 18 hours of analyzable ECG including the complete night.

**Medications** warrant careful consideration. Beta-blockers increase RSA amplitude. Importantly, SSRIs and newer antidepressants show no significant HRV impact in meta-analyses, though tricyclic antidepressants and antipsychotics with anticholinergic properties (olanzapine, quetiapine, clozapine) do affect cardiac autonomic function.

**Participant factors** requiring statistical control include age (HRV declines linearly with aging), BMI, fitness level (athletes show elevated vagal tone), and sex (young women show slightly higher parasympathetic HRV). Abstinence requirements before testing typically include 24 hours for caffeine, alcohol, nicotine, and intense exercise; 2 hours for heavy meals.

## The 2024 guidelines introduce critical updates

The **Quigley et al. (2024) Psychophysiology committee report** represents the authoritative update to Society for Psychophysiological Research guidance, replacing recommendations from Jennings et al. (1981) and Berntson et al. (1997). Key changes from the 1996 Task Force include:

- **Sampling rate**: Minimum **1000 Hz** recommended (previously 250-500 Hz acceptable)
- **Autonomic space**: Challenges simplistic sympathovagal balance—sympathetic and parasympathetic activity vary independently, showing coactivation or coinhibition
- **LF interpretation**: "No longer tenable without independent autonomic validation" as sympathetic marker
- **Degeneracy**: Same HR/HRV outcomes can emerge from multiple autonomic pathways—requiring independent validation rather than relying on HRV alone

The guidelines conclude with formal checklist-style reporting requirements covering participant characteristics, electrode configuration, sampling rate, artifact correction algorithms and percentages, epoch durations, and complete analytic pipelines.

The **GRAPH checklist** (Quintana et al., 2016) provides 13 items spanning participant selection, IBI collection, data preparation, and HRV calculation. The Catai et al. (2020) procedural checklist adds environmental requirements (quiet room, 20-24°C, 40-60% humidity), pre-collection abstinence, and familiarization procedures.

## Common methodological errors compromise reproducibility

**Recording duration errors** include using ultra-short recordings (<1 minute) for frequency-domain metrics and comparing recordings of mismatched durations. **Artifact handling problems** involve inadequate algorithm reporting, over-correction biasing results, under-correction leaving ectopic beats, and neglecting visual inspection of automated detection.

**Metric selection errors** include using LF/HF as sympathovagal balance, confusing HF-HRV with RSA when respiratory rate lies outside the HF band, and using SDNN inappropriately for short recordings. **Statistical errors** encompass failing to report both absolute and relative spectral power, ignoring baseline dependency in change scores, multiple testing without correction, and inadequate sample sizes (medium effects typically require n≥61).

**Reproducibility solutions** include pre-registration of hypotheses and analysis plans, sharing raw IBI files and analysis scripts, using validated open-source pipelines with documented parameters, and adhering to reporting checklists.

## Recent advances reshape the field

**Wearable validation studies (2022-2025)** reveal substantial accuracy differences. The **Oura Ring Gen 4** achieves best-in-class performance (CCC=0.99, MAPE=5.96%), followed by Oura Gen 3 and WHOOP 4.0. Apple Watch Series 9/Ultra 2 showed concerning underestimation averaging 8.31 ms with MAPE of 28.88%—failing to meet ±10 ms equivalence margins. Polar H10 chest strap remains the reference standard for wearable research. PPG accuracy degrades substantially during activity, with variable skin tones, loose fitting, and ambient light interference.

**Machine learning applications** include deep learning R-peak detection (RPnet combining U-Net with Inception/Residual blocks), stationary wavelet transform with separable convolution achieving robust cross-database performance, and parameter-specific quality assessment recognizing that different artifacts impact different HRV metrics differently.

**Ultra-short-term HRV** has gained mainstream acceptance: **60-second recordings** are now validated for RMSSD, forming the basis for daily athlete monitoring protocols (1-minute stabilization + 1-minute recording). Weekly averages of lnRMSSD combined with coefficient of variation track chronic adaptation and acute perturbations respectively.

**NeuroKit2** continues active development (version 0.2.12, receiving 2024 SIPS Commendation Award), adding MSPTDfast PPG detection and improved frequency-domain methods for unevenly spaced data. RHRVEasy (2024) automates hypothesis testing and post-hoc analysis for group comparisons.

## Practical recommendations for psychological researchers

For recording protocols, use **5-minute seated recordings** with standardized environment (quiet, 20-24°C), consistent time of day, and 5-10 minute adaptation. Consider 60-second protocols only for RMSSD-focused field studies. Sample at ≥1000 Hz when possible; minimum 250 Hz for ECG, 100 Hz for PPG.

For artifact correction, implement **Lipponen-Tarvainen algorithm** (available in Kubios, NeuroKit2) and keep corrections below 5% of total beats. Always visually inspect automated detection and report correction percentage.

For metric selection, use **RMSSD as primary vagal index**—it is robust, validated for short recordings, and equivalent to SD1. Report HF power but do not equate with RSA unless respiratory rate is controlled within 0.12-0.4 Hz. **Avoid interpreting LF as sympathetic or LF/HF as sympathovagal balance**. Consider nonlinear metrics (DFA alpha1, sample entropy) for complexity assessment.

For experimental design, follow the **"three Rs" framework**: Rest (baseline), Reactivity (task), Recovery. Control for respiration, body position, time of day, and relevant medications. Report all confound controls and consider statistical adjustment for age, BMI, and fitness.

For reporting, follow the **GRAPH checklist** (13 items) and Quigley et al. (2024) recommendations. Pre-register analysis plans, share raw IBI data and scripts, and report complete preprocessing pipelines including software versions and all parameter choices.

## Conclusion

HRV analysis for psychological research has matured substantially, with the 2024 guidelines codifying lessons from decades of methodological refinement. The central interpretive insight—that **RMSSD and HF-HRV index vagal function while LF/HF ratio does not measure sympathovagal balance**—has achieved consensus status. Technical advances including validated artifact correction algorithms, ultra-short-term metric validation, and consumer wearable accuracy data enable more flexible data collection than ever before.

The field's most significant remaining challenges involve ensuring reproducibility through standardized protocols and transparent reporting, understanding individual differences in HRV-psychology relationships, and integrating HRV with other autonomic measures to address the degeneracy problem—identical HRV values arising from different underlying autonomic states. For psychological researchers, these developments underscore both the promise of HRV as an accessible window into autonomic function and the necessity of methodological rigor in drawing valid inferences about psychological states and traits.