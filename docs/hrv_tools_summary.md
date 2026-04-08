# HRV-Analyse Tools: Zusammenfassung für Python-App-Entwicklung

## Grundlagen: RR-Intervalle vs. NN-Intervalle

| Begriff | Definition |
|---------|------------|
| **RR-Intervalle** | Zeitabstände zwischen allen R-Zacken im EKG (Rohdaten, inkl. Artefakte) |
| **NN-Intervalle** | Nur Intervalle zwischen *normalen* Sinusschlägen (bereinigt) |

Für HRV-Analysen werden NN-Intervalle benötigt. Die Konvertierung von RR → NN ist ein Preprocessing-Schritt.

---

## Empfohlene Architektur

```
┌─────────────────────────────────────────────────────┐
│                    Python App                       │
├─────────────────────────────────────────────────────┤
│  1. INPUT LAYER                                     │
│     - RR-Intervalle (verschiedene Formate/Quellen)  │
│     - Optional: Roh-EKG → R-Peak-Detektion          │
├─────────────────────────────────────────────────────┤
│  2. PREPROCESSING (hrv-analysis)                   │
│     - remove_outliers()                             │
│     - remove_ectopic_beats()                        │
│     - interpolate_nan_values()                      │
│     → Output: NN-Intervalle                         │
├─────────────────────────────────────────────────────┤
│  3. ANALYSIS (NeuroKit2)                            │
│     - hrv_time()                                    │
│     - hrv_frequency()                               │
│     - hrv_nonlinear()                               │
├─────────────────────────────────────────────────────┤
│  4. OUTPUT/REPORTING                                │
└─────────────────────────────────────────────────────┘
```

---

## Tool-Vergleich

### Für Preprocessing (RR → NN)

| Tool | Stärken | Schwächen | Empfehlung |
|------|---------|-----------|------------|
| **hrv-analysis** | Speziell für RR-Preprocessing gebaut, saubere API, mehrere Ektopen-Methoden (malik, kamath, karlsson, acar) | Weniger Analyse-Features | ✅ **Beste Wahl für Preprocessing** |
| **NeuroKit2** | `signal_fixpeaks()` mit Kubios-Methode | Primär für Peak-Zeitstempel, nicht direkt für RR-Listen | ⚠️ Umständlich für reines RR-Preprocessing |
| **CoRRection** | Semi-automatisch, segment-basiert | GUI-App, kein Python-Paket, nicht öffentlich verfügbar | ❌ Nicht integrierbar |

### Für Analyse

| Tool | HRV-Metriken | Aktiv gepflegt | Dokumentation | Empfehlung |
|------|--------------|----------------|---------------|------------|
| **NeuroKit2** | 124+ | ✅ Ja | Sehr gut + Peer-reviewed Paper | ✅ **Beste Wahl** |
| **hrv-analysis** | ~20 | ✅ Ja | Gut | Gut für Basics |
| **pyHRV** | 78 | ❌ Nein (seit 2019) | Gut | ❌ Veraltet |

---

## Praktische Code-Beispiele

### Preprocessing mit hrv-analysis

```python
from hrvanalysis import (
    remove_outliers,
    remove_ectopic_beats, 
    interpolate_nan_values
)

def preprocess_rr_to_nn(rr_intervals, 
                        low_rri=300, 
                        high_rri=2000,
                        ectopic_method="malik"):
    """
    Konvertiert RR-Intervalle zu NN-Intervallen.
    
    Parameters:
        rr_intervals: Liste von RR-Intervallen in ms
        low_rri: Minimaler physiologisch möglicher Wert (ms)
        high_rri: Maximaler physiologisch möglicher Wert (ms)
        ectopic_method: "malik", "kamath", "karlsson", oder "acar"
    
    Returns:
        nn_intervals, artifact_report
    """
    n_original = len(rr_intervals)
    
    # Step 1: Physiologisch unmögliche Werte entfernen
    rr_clean = remove_outliers(
        rr_intervals=rr_intervals,
        low_rri=low_rri,
        high_rri=high_rri
    )
    
    # Step 2: Interpolation der NaNs
    rr_interpolated = interpolate_nan_values(
        rr_intervals=rr_clean,
        interpolation_method="cubic"
    )
    
    # Step 3: Ektope Schläge erkennen
    nn_intervals = remove_ectopic_beats(
        rr_intervals=rr_interpolated,
        method=ectopic_method
    )
    
    # Step 4: Finale Interpolation
    nn_clean = interpolate_nan_values(rr_intervals=nn_intervals)
    
    # Artefakt-Report
    n_removed = sum(1 for x in nn_intervals if x != x)  # NaN check
    artifact_rate = n_removed / n_original * 100
    
    return nn_clean, {
        "original_count": n_original,
        "artifacts_removed": n_removed,
        "artifact_rate_percent": artifact_rate
    }
```

### Analyse mit NeuroKit2

```python
import neurokit2 as nk
import numpy as np

def analyze_hrv(nn_intervals, sampling_rate=1000):
    """
    Führt vollständige HRV-Analyse auf NN-Intervallen durch.
    
    Parameters:
        nn_intervals: Liste von NN-Intervallen in ms
        sampling_rate: Sampling-Rate in Hz (für Frequenzanalyse)
    
    Returns:
        DataFrame mit allen HRV-Metriken
    """
    # NN zu kumulativen Peak-Zeitstempeln konvertieren
    peak_times = np.cumsum(nn_intervals)
    
    # NeuroKit2 erwartet Peak-Indizes
    peaks_dict = {"PPG_Peaks": peak_times}
    
    # Alle HRV-Domänen berechnen
    hrv_results = nk.hrv(peaks_dict, sampling_rate=sampling_rate)
    
    return hrv_results
```

### Eigene Artefakt-Detektion (Tarvainen-Algorithmus)

```python
import numpy as np
from scipy.interpolate import interp1d
from typing import Literal

def detect_artifacts_tarvainen(rr_intervals: np.ndarray, 
                                threshold_factor: float = 5.2) -> np.ndarray:
    """
    Tarvainen-Algorithmus für Artefaktdetektion.
    Basiert auf dRR (Differenzen aufeinanderfolgender RR-Intervalle).
    
    Returns: Boolean-Array (True = Artefakt)
    """
    drr = np.diff(rr_intervals)
    drr = np.insert(drr, 0, 0)
    
    artifacts = np.zeros(len(rr_intervals), dtype=bool)
    
    for i in range(len(rr_intervals)):
        start = max(0, i - 45)
        end = min(len(drr), i + 45)
        local_drr = drr[start:end]
        
        q75, q25 = np.percentile(local_drr, [75, 25])
        qd = (q75 - q25) / 2
        threshold = qd * threshold_factor
        
        if abs(drr[i]) > threshold:
            artifacts[i] = True
    
    return artifacts


def detect_artifacts_quotient(rr_intervals: np.ndarray,
                               threshold: float = 0.2) -> np.ndarray:
    """
    Quotient-Filter: Erkennt Artefakte durch Verhältnis 
    aufeinanderfolgender RR-Intervalle.
    """
    artifacts = np.zeros(len(rr_intervals), dtype=bool)
    
    for i in range(1, len(rr_intervals)):
        ratio = rr_intervals[i] / rr_intervals[i-1]
        if ratio < (1 - threshold) or ratio > (1 + threshold):
            artifacts[i] = True
    
    return artifacts


def correct_artifacts(rr_intervals: np.ndarray,
                      artifacts: np.ndarray,
                      method: Literal["linear", "cubic", "median"] = "cubic"
                     ) -> np.ndarray:
    """
    Korrigiert markierte Artefakte durch Interpolation.
    """
    rr_corrected = rr_intervals.copy().astype(float)
    rr_corrected[artifacts] = np.nan
    
    if method == "median":
        for i in np.where(artifacts)[0]:
            start = max(0, i - 5)
            end = min(len(rr_intervals), i + 5)
            local = rr_intervals[start:end]
            local_clean = local[~artifacts[start:end]]
            if len(local_clean) > 0:
                rr_corrected[i] = np.median(local_clean)
    else:
        valid_idx = np.where(~artifacts)[0]
        valid_vals = rr_intervals[valid_idx]
        
        if len(valid_idx) > 3:
            kind = "cubic" if method == "cubic" else "linear"
            f = interp1d(valid_idx, valid_vals, kind=kind, 
                        fill_value="extrapolate")
            rr_corrected = f(np.arange(len(rr_intervals)))
    
    return rr_corrected
```

---

## Verfügbare Ektopen-Detektions-Methoden

| Methode | Beschreibung | Verfügbar in |
|---------|--------------|--------------|
| **Malik** | Prozentuale Schwelle (default 20%) | hrv-analysis |
| **Kamath** | Ähnlich Malik, andere Parameter | hrv-analysis |
| **Karlsson** | Adaptive Schwelle | hrv-analysis |
| **Acar** | Kombiniert mehrere Ansätze | hrv-analysis |
| **Tarvainen/Kubios** | dRR-basiert mit adaptiver Schwelle | NeuroKit2, selbst implementierbar |
| **Quotient Filter** | Verhältnis aufeinanderfolgender RR | selbst implementierbar |
| **Square Filter** | Quadratische Abweichung | selbst implementierbar |

---

## Wichtige Dokumentationshinweise

Bei >5-10% entfernten Artefakten wird die HRV-Analyse fragwürdig. Immer dokumentieren:

- Welcher Algorithmus/Schwellenwert verwendet wurde
- Wie viel Prozent der Daten entfernt wurden
- Welche Interpolationsmethode angewendet wurde

---

## Installation

```bash
# Preprocessing
pip install hrv-analysis

# Analyse
pip install neurokit2

# Zusätzlich für erweiterte Features
pip install scipy numpy pandas
```

---

## Referenzen

- **hrv-analysis**: https://github.com/Aura-healthcare/hrv-analysis
- **NeuroKit2**: https://github.com/neuropsychology/NeuroKit
- **NeuroKit2 HRV Paper**: Pham et al. (2021). Heart Rate Variability in Psychology: A Review of HRV Indices and an Analysis Tutorial. *Sensors*, 21(12), 3998.
- **Task Force Standards**: Heart rate variability: standards of measurement, physiological interpretation and clinical use (1996). *European Heart Journal*, 17(3), 354-381.
