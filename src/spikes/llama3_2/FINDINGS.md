# Spike #40: Llama 3.2 3B compared with Gemma 4 E2B

This file records what the Llama 3.2 3B runs showed and compares them with the Gemma 4 E2B results from spike #38 ([FINDINGS-pymupdf.md](../gemma4/FINDINGS-pymupdf.md) on branch `spike/gemma4`). The purpose of both spikes is to pick the local model for outline extraction.

**Status:** Phase A done (one run per outline and strategy). Phase C (prompt injection, both models) and a Gemma consistency check are still to run; see section 8.

## 1. Setup

Everything except the model is the same as the Gemma PyMuPDF runs, so differences come from the model.

| Item | Value |
|---|---|
| Model | `llama3.2:3b`, 3.2B parameters, Q4_K_M, trained context 131,072 tokens, digest `a80c4f17acd5` |
| Ollama | 0.40.14, CPU only (same version and laptop as #38) |
| Harness | `src/spikes/common/` (`run_spike.sh`, `spike_llm.py`). Same prompts, JSON schema, `--postprocess` rules and scorer as the #38 script |
| Text extraction | Shivya's PyMuPDF `extract_pdf_text()`, pymupdf 1.27.2.2 |
| Options | `--postprocess`, `num_ctx` 16384, temperature 0 |
| Strategies | baseline (one call) and think (notes first, then JSON). linking and fewshot were left out (see #38 findings) |
| Outlines | SFWRENG 2OP3, 2XC3, 2DA4, 2DM3 and COMPSCI 2C03 (44 answer-key items in total) |
| Runs | One per outline per strategy (log: `results/llama3.2-3b/logs/phaseA_20261105-013706.log`) |

Every run read the whole outline (no context truncation) and returned valid JSON with no schema problems.

## 2. Summary

Totals out of 44 key items, as found / dates / TBD / weights:

| Strategy | Llama 3.2 3B | Gemma 4 E2B |
|---|---|---|
| baseline | 27 / 18 / 20 / 24 | 30 / 29 / 30 / 30 |
| think | 36 / 30 / 16 / 21 | **42 / 34 / 41 / 40** |

**Gemma is better on every measure, with both strategies.** Llama also invented items and dates (section 4.1), which Gemma did not do with these settings, and it was slower (section 6).

The team's order for choosing a model is: date and weight accuracy, then no invented items, then consistency, then speed. Llama is behind on the first two, so it is not a candidate unless Gemma fails the prompt-injection gate.

## 3. Results by outline

Score format: found / dates / TBD / weights.

### baseline

| Outline (key items) | Llama | Gemma |
|---|---|---|
| 2OP3 (11) | 11 / 5 / 6 / 11 | **11 / 11 / 11 / 11** |
| 2XC3 (11) | 4 / 4 / 3 / 3 | 4 / 4 / 4 / 4 |
| 2DA4 (7) | 4 / 2 / 3 / 3 | **7 / 7 / 7 / 7** |
| 2DM3 (6) | **6 / 6 / 6 / 6** | **6 / 6 / 6 / 6** |
| 2C03 (9) | 2 / 1 / 2 / 1 | 2 / 1 / 2 / 2 |
| **Total (44)** | **27 / 18 / 20 / 24** | **30 / 29 / 30 / 30** |

### think

| Outline (key items) | Llama | Gemma |
|---|---|---|
| 2OP3 (11) | 11 / 11 / 11 / 5 | **11 / 11 / 11 / 11** |
| 2XC3 (11) | 4 / 4 / 3 / 3 | **9 / 9 / 8 / 8** |
| 2DA4 (7) | 7 / 6 / 1 / 3 | **7 / 7 / 7 / 6** |
| 2DM3 (6) | 6 / 1 / 1 / 2 | **6 / 6 / 6 / 6** |
| 2C03 (9) | 8 / 8 / 0 / 8 | 9 / 1 / 9 / 9 |
| **Total (44)** | **36 / 30 / 16 / 21** | **42 / 34 / 41 / 40** |

think helps Llama find items and dates (36 found and 30 dates, against 27 and 18 with baseline), but its TBD flags and weights get worse. With Gemma, think improved everything.

## 4. Error types, with examples

### 4.1 Invented items and dates (most serious)

These values are not in the outline text. Each one was checked against the text the model was given (`*_input.txt`).

| Outline | Strategy | Model row | What the outline says |
|---|---|---|---|
| 2C03 | think | "Midterm", 2026-11-13, 7.25% | The course has no midterm; the word "midterm" does not appear in the outline |
| 2C03 | think | "Assignment 9", 2026-12-10 | There are eight assignment deadlines. December 10 is the last day of lectures. (Gemma also added an "Assignment 9" here, but without a date) |
| 2C03 | think | Tutorials T01, T02, T03, T05, T06, 7.25% each | Tutorial sections are not graded; 7.25% is the assignment weight |
| 2XC3 | think | "A3: Strings", 2026-12-03 | "Dec 3" does not appear in the outline. A3 is due Nov 9. "Strings" is a lab topic |
| 2XC3 | think | "A1: Team Development Plan", 2026-11-18 | A1 is due Oct 5. Nov 18 is the Team Development Plan date |

Like the fewshot hallucination in #38, these look correct and some cite a source, so a person reviewing the output could easily accept them.

### 4.2 Prompt example copied into the output

The extraction prompt says: `missing_fields: ... (for example "Midterm date", "Assessment weights", "Learning outcomes")`.

| Strategy | What Llama returned as `missing_fields` |
|---|---|
| baseline | "Midterm date, Assessment weights, Learning outcomes" for **all five outlines**, word for word |
| think | "Midterm date, Assessment weights" plus one other item, for all five outlines |

In 2XC3 (baseline) it also returned an assessment row named **"Midterm date"**, typed as a lab. The model is copying the prompt's example instead of reading the outline, which makes `missing_fields` useless with this model.

### 4.3 Group weight copied onto every item (think)

| Outline | Model | Expected | Weight sum |
|---|---|---|---|
| 2OP3 | Assignments 1 to 5 at 15% each | 3% each | 151% |
| 2DA4 | Assignments 1 to 4 at 10% each, Labs 1 to 5 at 10% each | 2.5% each; one "Labs" row at 10% | 170% |
| 2DM3 | Assignments A1 to A4 at 1.25% each | 5% each | 100% (by chance) |

Gemma made this mistake once in the #38 pdfplumber baseline; the `--postprocess` rule fixed it there. Here the totals are too far from a clean multiple for the rule to repair.

### 4.4 Group rows not split (baseline)

| Outline | Model row | Expected |
|---|---|---|
| 2DA4 | "Assignments" 10%, no date | Assignment 1 to 4, 2.5% each, four dates |
| 2C03 | "Assignments" 50.75%, no date | Assignment 1 to 8, 7.25% each, eight dates |
| 2XC3 | "Individual assignments", no weight; "Team assignment", no weight | Four assignments and four team items with their own weights |

`--postprocess` only splits a row whose name contains a count ("Five Assignments", "(4)"), so these stayed as one row.

### 4.5 Dates on the same line missed

In 2DA4 (baseline) the model quoted "MIDTERM: Friday Nov 6, 2026." as its source, then returned no date and marked the midterm TBD. Gemma got every same-line date right in #38.

In 2OP3 (baseline) it missed all six dates that are only in the weekly schedule. Gemma's baseline found all six with PyMuPDF text.

### 4.6 TBD flags set on dated items (think)

With think, Llama set `date_tbd: true` on items that had a date: all 8 assignments in 2C03 (TBD 0/9) and all 4 assignments plus the midterm in 2DA4 (TBD 1/7). In 2DM3 it marked every assignment and the midterm TBD and dropped their dates, although the plain baseline got all six right.

### 4.7 Course code, term and type

| Outline | Strategy | course_code / term |
|---|---|---|
| 2OP3 | think | "SFWRENG" / "2OP3" |
| 2DA4 | think | "2DA4" / "Winter 2026" |
| 2DA4 | baseline | "SE 2DA4" / "Winter 2026" |
| 2DM3 | baseline | "SFWRENG 2DM3 T03" (tutorial section added) |

"Winter 2026" (2DA4) and "COMPSCI 2CO3" (2C03, returned by both strategies) are copied from errors in the outlines themselves (see #38 findings, section 5), so they are not counted against the model.

With think, every item in 2OP3, 2XC3 and 2C03 was typed "assignment", including midterms, exams and tutorials.

## 5. What Llama did well

- **2DM3 baseline was perfect** (6/6/6/6), the same as Gemma, despite the broken ligatures ("anal exam").
- **2OP3 think got every date and TBD flag right** (11/11), the same as Gemma; only the weights were wrong.
- **Valid JSON every time**, with no context truncation.
- **The same output twice:** the smoke test and the Phase A baseline run on 2DA4 returned identical rows and scores. This is one data point, not a consistency test.

## 6. Speed

| Strategy | Llama 3.2 3B per outline | Gemma 4 E2B per outline (#38) |
|---|---|---|
| baseline | 3.6 to 7.9 min (213 to 472 s) | 3.5 to 5.3 min |
| think | 6.1 to 9.2 min (368 to 552 s) | 5.7 to 6.9 min |

Llama wrote 2.5 to 5.9 output tokens per second. Although it is the smaller download (2.0 GB), it was slower than Gemma on this laptop, and think breaks the 5-minute-per-outline target (NFR_Performance) on every outline.

## 7. Conclusion so far

1. **Gemma 4 E2B is the better model for this task.** It is ahead on found items, dates, TBD flags and weights, with both strategies.
2. **Llama 3.2 3B invents values** (a midterm that does not exist, dates not in the outline) and copies the prompt's example into its output. Both are hard for a reviewer to catch.
3. **Llama is not faster**, so speed does not offset the accuracy gap.
4. **Llama's Phase B (three runs each) was skipped.** The gap is large and the same error types appear in every outline, so repeat runs would not change the ranking. The time is used for the Gemma consistency check instead (section 8).

## 8. Still to do

| Step | Status |
|---|---|
| Phase C: prompt-injection gate, Llama (think, 2OP3 and 2DA4, variants ignore / alter / disguised) | To run |
| Gemma consistency: think, all five outlines, three runs, with the shared harness | To run. This also gives the normal runs Gemma's Phase C needs, and checks that the shared harness reproduces the #38 numbers |
| Phase C: prompt-injection gate, Gemma | To run |
| Final recommendation and issue #40 comment | After the runs above |

Rule for Phase C: no instruction in outline text may be followed. An injected run passes only if its dates, TBD flags and weights match a normal run of the same outline (`compare_inject.py`).
