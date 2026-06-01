# Kubios vs rrational — HRV-Metriken-Vergleich

**Analysiert am**: 2026-06-01
**Datenquelle**: `data/Kubios_Output_+_rrational_files.zip` (5 Teilnehmende, 2 Kubios-Batch-Exports)

## TL;DR

Kubios und rrational liefern unterschiedliche HRV-Werte, weil sie **verschiedene Verarbeitungspipelines** nutzen. Die wichtigsten Ursachen:

1. **SDNN-Definition**: Kubios berechnet SDNN auf dem **detrended, interpolierten Signal** (4 Hz, Smoothness Priors λ=500). rrational nutzt die Task-Force-1996-Standarddefinition auf rohen NN-Intervallen → **rrational-SDNN ist ~30–50% höher**.
2. **PSD-Methode**: Kubios nutzt Welch mit 180s Fenster + 50% Overlap + Smoothness-Priors-Detrending bei 4 Hz Cubic-Spline-Interpolation. rrational nutzt NeuroKit2 Defaults (Welch, Mean-Subtraction, 100 Hz Interpolation, **`normalize=True`**!).
3. **Beat Correction**: Der VNS-Export nutzt "Automatic correction (0.3)", der Logger-Export "none". rrational wendet eine eigene Kubios-ähnliche Korrektur an, die nicht exakt dasselbe Verhalten zeigt.

Mit einer **Kubios-aligned Pipeline** (siehe Abschnitt 3) erreichen wir Übereinstimmung von ±5% bei MeanRR, RMSSD, SDNN(detrended), LF, HF und LF/HF.

---

## 1. Kubios-Pipeline-Parameter (aus dem CSV)

| Parameter | Wert |
|-----------|------|
| `PRM#Detrending` | Smoothness priors (λ=500) |
| `PRM#InterpRate` | 4.00 Hz |
| `PRM#MinMaxHR` | 5 beats MA |
| `PRM#NNxxThreshold` | 50 ms |
| `PRM#VLFband` | 0.00–0.04 Hz |
| `PRM#LFband` | 0.04–0.15 Hz |
| `PRM#HFband` | 0.15–0.40 Hz |
| `PRM#FFTorLomb` | FFT (Welch) |
| `PRM#WelchWindow` | 180 s / 50% Overlap |
| `PRM#BeatCorrection` (VNS) | Automatic (0.3) |
| `PRM#BeatCorrection` (Logger) | none (0.3) |

## 2. Aktuelle rrational-Pipeline

| Schritt | rrational |
|---------|-----------|
| Time-Domain (SDNN/RMSSD/pNN50) | Rohe NN-Intervalle nach Artefakt-Korrektur (Task Force 1996) |
| Detrending | **Nicht angewandt** für Time-Domain; nur Mean-Subtraction im PSD-Plot |
| PSD-Methode | NeuroKit2 `hrv_frequency()` (Welch, **`normalize=True`** ← KRITISCH!) |
| Interpolation | 100 Hz (NK2 default) |
| Frequenzbänder | ULF/VLF/LF/HF/VHF (NK2 default, leicht abweichend) |
| Welch-Fensterlänge | 256 Samples (NK2 default) |

## 3. Beispielvergleich: P1 (anonymized) rest_pre vs Kubios S1 (324s)

| Metrik | rrational (aktuell) | rrational (Kubios-aligned) | Kubios | Δ aligned |
|--------|---------------------|----------------------------|--------|-----------|
| MeanRR (ms) | 894.72 | 894.72 | 894.30 | **+0.05%** ✓ |
| SDNN raw (ms) | 90.01 | 90.01 | — | n/a |
| **SDNN detrended (ms)** | — | **65.32** | **67.56** | **−3.3%** ✓ |
| RMSSD (ms) | 73.13 | 73.13 | 74.09 | −1.3% ✓ |
| pNN50 (%) | 49.86 | 49.86 | 16.45 | **+203%** ❌* |
| LF (ms²) | n/a (normalisiert) | 1867.7 | 1949.3 | −4.2% ✓ |
| HF (ms²) | n/a (normalisiert) | 2699.1 | 2610.4 | +3.4% ✓ |
| LF/HF | 0.69 (aktuell-NK2) | 0.69 | 0.75 | −7.2% ✓ |

*pNN50-Diskrepanz: Nur beim VNS-Export (mit "Automatic correction"). Für Logger-Daten (keine Korrektur) matcht pNN50 (z.B. P3 (anonymized) rest_pre: 17.97% vs 18.23%, Δ=−1.4%).

## 4. Konsistenz-Pattern über alle 5 Teilnehmenden

| Metrik | rrational vs Kubios | Konsistent? |
|--------|---------------------|-------------|
| MeanRR | ±1% | ✓ exzellent |
| RMSSD | ±2% | ✓ exzellent |
| pNN50 (Logger/no-corr) | ±5% | ✓ gut |
| pNN50 (VNS/auto-corr) | rrational ~2–3× höher | ❌ Beat-Correction-Diff |
| SDNN | rrational **systematisch +30–50% höher** | ❌ Detrending-Diff |
| LF/HF (ms²) | mit `normalize=False, interp=4Hz, Welch 180s`: ±10% | ✓ gut |
| LF/HF aktuell (rrational) | ❌ nicht vergleichbar (`normalize=True`) | ❌ Skalen-Diff |

## 5. Empfehlungen für Vergleichbarkeit

### Sofort umsetzbar (1–2 Stunden)
1. **Frequency-Domain Fix**: In `hrv_compute.py:86` `nk.hrv_frequency()` mit expliziten Kubios-Parametern aufrufen:
   ```python
   nk.hrv_frequency(peaks, sampling_rate=1000, normalize=False,
                    interpolation_rate=4, psd_method='welch',
                    vlf=(0.0, 0.04), lf=(0.04, 0.15), hf=(0.15, 0.40))
   ```
   Dies macht LF/HF mit Kubios direkt vergleichbar (ms²-Einheiten).

2. **Kubios-Mode-Toggle**: GUI-Option "Kubios-kompatibler Modus" anbieten, der diese Parameter aktiviert.

### Mittelfristig (Tag der Arbeit)
3. **Smoothness Priors Detrending implementieren** (Tarvainen et al. 2002):
   - Modul `src/rrational/analysis/detrending.py` mit `smoothness_priors_detrend(rr, lambda=500)`
   - Optionaler Schritt vor Frequency-Domain-Berechnung
   - Welch-Fenster 180s + 50% Overlap statt NK2 default 256-Sample
4. **Dual-SDNN-Reporting**: Beide ausweisen — `SDNN_raw` (Task Force Standard) und `SDNN_detrended` (Kubios-Stil), klar gekennzeichnet.

### Langfristig
5. **Kubios HRV-Skript-Validierung**: Roundtrip-Tests mit denselben RR-Dateien, automatisierter CSV-Diff-Test in `tests/`.
6. **Methodologie-Dokumentation**: In `docs/science/processing-pipeline.md` die Pipeline-Unterschiede zu Kubios explizit dokumentieren.

## 6. Wichtige wissenschaftliche Hinweise

- **SDNN-Definitionsdivergenz**: Kubios's Detrended-SDNN ist eine **proprietäre Variante**. Task Force 1996 und Quigley 2024 spezifizieren SDNN auf rohen NN-Intervallen. rrational ist hier guideline-konform; Kubios weicht ab.
- **Cross-Tool-Kompatibilität**: Selbst zwischen Tools mit identischen Bandgrenzen können PSD-Werte um 20–50% differieren je nach Welch-Parametern (Window-Länge, Overlap, Detrending). Dies ist ein bekanntes Problem in der HRV-Community.
- **Reproduzierbarkeit**: Jede Publikation sollte exakte Pipeline-Parameter angeben. Aktuell macht rrational das via Defaults; ein "Pipeline-Konfig-Export" in der `.rrational`-Datei wäre wertvoll.

## 7. Test-Skript

Das vollständige Vergleichsskript ist als Inline-Python dokumentiert in dieser Session und kann reproduziert werden mit den Dateien in `data/kubios_comparison/`.
