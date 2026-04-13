# RRational vs. Kubios HRV Validierung

## Studienprotokoll

```
Ruhe (pre)     Messung 1        Pause       Messung 2        Ruhe (post)
|--- 5 min ---|--- 90 min ---|--- 10 min ---|--- 90 min ---|--- 5 min ---|
```

## Analyse-Workflow (nach Prof.-Empfehlung)

### 1. Segmentierung (identisch in beiden Tools!)

Verwende **5-Minuten-Fenster** mit **50% Overlap** (oder ohne Overlap — Hauptsache in beiden Tools GLEICH).

| Section | Dauer | Erwartete Segmente (5 min, kein Overlap) |
|---------|-------|------------------------------------------|
| rest_pre | 5 min | 1 Segment |
| first_measurement | 90 min | 18 Segmente |
| pause | 10 min | 2 Segmente |
| second_measurement | 90 min | 18 Segmente |
| rest_post | 5 min | 1 Segment |

### 2. Artefaktkorrektur

- **Methode**: Threshold-based (Kubios: "Medium" = ~0.25s; RRational: Lipponen & Tarvainen)
- **WICHTIG**: Notiere die exakte Einstellung in beiden Tools!
- **Quigley 2024**: Segmente mit >10% Artefakten ausschließen

### 3. In Kubios analysieren

1. RR-Daten importieren (CSV oder TXT)
2. Segmente manuell setzen (5 min Fenster)
3. Artefaktkorrektur: Medium threshold
4. **Detrending AUS** (RRational hat kein Detrending)
5. Pro Segment exportieren:
   - Time domain: RMSSD, SDNN, pNN50, Mean RR, Mean HR
   - Frequency domain: LF abs, HF abs, LF/HF, Total Power
   - Nonlinear: SD1, SD2

### 4. In RRational analysieren

1. Daten importieren (Data Tab → Analyze Folder)
2. Participants Tab → Events prüfen (rest_pre_start, measurement_start, etc.)
3. Setup Tab → Sections definieren (rest_pre, first_measurement, pause, etc.)
4. Analysis Tab → **Single Participant** → Sections auswählen
5. Window: 5 min, Overlap: wie in Kubios
6. Artifact Correction: signal_fixpeaks
7. Ergebnisse exportieren (CSV Download)

### 5. Vergleich pro Proband

---

## Vergleichstabelle

### Proband: _______________
### Section: _______________
### Segment: ___ von ___

| Metrik | Kubios | RRational | Diff | Diff % | OK? |
|--------|--------|-----------|------|--------|-----|
| **Time Domain** | | | | | |
| Mean RR (ms) | | | | | |
| Mean HR (bpm) | | | | | |
| SDNN (ms) | | | | | |
| RMSSD (ms) | | | | | |
| pNN50 (%) | | | | | |
| **Frequency Domain** | | | | | |
| VLF Power (ms²) | | | | | |
| LF Power (ms²) | | | | | |
| HF Power (ms²) | | | | | |
| LF/HF Ratio | | | | | |
| Total Power (ms²) | | | | | |
| **Nonlinear** | | | | | |
| SD1 (ms) | | | | | |
| SD2 (ms) | | | | | |
| SD1/SD2 | | | | | |
| **Quality** | | | | | |
| Beat Count | | | | | |
| Artifact Count | | | | | |
| Artifact Rate (%) | | | | | |
| Quality Grade | | | | | |

### Akzeptable Abweichungen

| Metrik-Gruppe | Erwartete Diff | Warum? |
|---------------|---------------|--------|
| Time domain (RMSSD, SDNN, pNN50) | <1% | Standardisierte Berechnung |
| Mean RR / Mean HR | <0.1% | Triviale Berechnung |
| Frequency domain (LF, HF) | 5-15% | PSD-Methode (Welch vs AR), Interpolation, Resampling-Rate |
| Nonlinear (SD1, SD2) | <1% | Direkte Berechnung aus Differenzen |
| Artifact Count | Kann variieren | Unterschiedliche Algorithmen (Lipponen vs Kubios threshold) |

---

## Zusammenfassung pro Proband

### Proband: _______________

| Section | Seg. | Beats | Art.% | RMSSD K | RMSSD R | Diff% | SDNN K | SDNN R | Diff% | LF/HF K | LF/HF R | Diff% |
|---------|------|-------|-------|---------|---------|-------|--------|--------|-------|---------|---------|-------|
| rest_pre | 1 | | | | | | | | | | | |
| meas_1 | 1 | | | | | | | | | | | |
| meas_1 | 2 | | | | | | | | | | | |
| meas_1 | ... | | | | | | | | | | | |
| pause | 1 | | | | | | | | | | | |
| meas_2 | 1 | | | | | | | | | | | |
| meas_2 | ... | | | | | | | | | | | |
| rest_post | 1 | | | | | | | | | | | |

K = Kubios, R = RRational

---

## Gesamtbewertung

| Kriterium | Ergebnis |
|-----------|----------|
| Time domain Übereinstimmung (<1%) | [ ] Ja / [ ] Nein |
| Frequency domain Übereinstimmung (<15%) | [ ] Ja / [ ] Nein |
| Nonlinear Übereinstimmung (<1%) | [ ] Ja / [ ] Nein |
| Artefakterkennung vergleichbar | [ ] Ja / [ ] Nein |
| Segmentierung konsistent | [ ] Ja / [ ] Nein |
| **Gesamtergebnis** | [ ] Validiert / [ ] Nacharbeit nötig |

### Notizen
_Platz für Beobachtungen, Probleme, Auffälligkeiten..._
