---
name: verify-citations
description: Verifies scientific citations against PubMed/DOI and adds clickable DOI links. Use when user mentions adding references, citing papers, reviewing a reference list, or when documentation files contain citations (author, year, journal format). Also triggers when user says "check citations", "verify sources", or "add DOI links".
---

# Verify Scientific Citations

When adding or reviewing scientific citations in documentation (especially `docs/science/*.md`, `docs/reference/*.md`, or any file with a References section), follow this strict verification process.

## Why This Matters

In prior sessions, AI-generated citations contained errors:
- Quigley 2024 had issue 7 instead of correct issue 9
- Sammito 2024 had article 22 instead of correct 15
- Bernardi 2006 was cited for "segmented HRV" but paper used aggregate measures
- Sacha 2013 was cited for duration dependence but only discusses mean HR dependence

**Never assume a citation is correct because it "looks right".** Always verify.

## Verification Process

For EACH citation, execute these steps in order:

### 1. Find the paper

Use WebSearch or WebFetch with PubMed/Google Scholar:
```
WebFetch https://pubmed.ncbi.nlm.nih.gov/?term=<author>+<year>+<keyword>
```

Or search Google Scholar:
```
WebSearch "<first author surname>" "<year>" "<journal>" "<partial title>"
```

### 2. Verify bibliographic details

Confirm each field matches the source:
- **Authors**: Spelling, initials, order (first + et al. for >6 authors)
- **Year**: Publication year (not submission year)
- **Title**: Full title or shortened with proper indication
- **Journal**: Full name with italics
- **Volume, Issue**: Both must match
- **Pages or article number**: e.g., `178-181` or `e14604`

### 3. Verify the claim

Read the abstract (or full paper if accessible) to confirm:
- Does the paper actually make the claim attributed to it?
- Is the claim in the correct context?
- Is the methodology described accurately?

**Common pitfall**: A paper might discuss topic X but the specific finding attributed may come from a different paper.

### 4. Add clickable DOI link

Format citations with DOI hyperlinks:

```markdown
- Author, A.B., et al. (YYYY). Full title. *Journal Name*, Volume(Issue), pages. [doi:10.xxxx/...](https://doi.org/10.xxxx/...)
```

**Example (correct)**:
```markdown
- Quigley, K.S., et al. (2024). Publication guidelines for human heart rate and heart rate variability studies in psychophysiology. *Psychophysiology*, 61(9), e14604. [doi:10.1111/psyp.14604](https://doi.org/10.1111/psyp.14604)
```

### 5. Cross-check across files

If the same citation appears in multiple files (e.g., `recommended-workflow.md`, `guidelines.md`, `glossary.md`), verify all instances are identical. Use Grep to find all references:

```bash
grep -r "Quigley.*2024" docs/
```

Ensure volume/issue/pages match across all files.

## Output Requirements

After verification, present a table:

| Citation | Verified? | Correct Details | Claim Accurate? | Issues Found |
|----------|-----------|-----------------|-----------------|--------------|
| ... | YES/NO | [correct format] | YES/NO | [details] |

Then:
1. Fix any errors found (wrong year, issue, pages, claim)
2. Add DOI links to ALL references
3. Ensure consistency across all files

## Common DOI Formats

- Journals: `https://doi.org/10.xxxx/yyyyyy`
- Wiley: `https://doi.org/10.1111/xxxx`
- Frontiers: `https://doi.org/10.3389/xxxx.YYYY.NNNNN`
- Springer/Nature: `https://doi.org/10.1038/xxxxx`
- AHA (Circulation): `https://doi.org/10.1161/xx.xxx.x.xxxx`
- Taylor & Francis: `https://doi.org/10.1080/xxxxxxxx.YYYY.NNNNNNN`

## Red Flags — Require Extra Verification

- Paper attributed to author known for adjacent work (could be wrong paper)
- Very specific claims (percentages, thresholds) — check paper uses those exact values
- "et al." citations — verify at least first author
- Papers from memory with no original source (AI hallucination risk)
- Citations without DOI — likely fabricated or transcription error

## Never Do

- Guess DOIs from patterns
- Skip verification for "well-known" papers
- Trust prior AI-generated citations in the codebase
- Assume claim matches just because the paper topic matches
