# Spike #38: Gemma 4 E2B with Shivya's PyMuPDF text extraction

This file records what the run with Shivya's text extraction showed (log: `results/logs/pymupdf_20261104-012738.log`). It compares the results with the earlier runs that used the spike's own `pdfplumber` extraction ([FINDINGS-baseline.md](FINDINGS-baseline.md), [FINDINGS-strategies.md](FINDINGS-strategies.md)).

## 1. What was tested

| Item | Value |
|---|---|
| Text extraction | Shivya's `extract_pdf_text()` from `src/backend/app/api/outlines.py` on `feat/pdf-outline-upload` (commit 91f35b2), copied unchanged into the spike as `--extractor pymupdf`. PyMuPDF 1.27.2.2, the version her branch pins. |
| Model | `gemma4:e2b`, Ollama, CPU only |
| Strategies | baseline, think, linking (fewshot was dropped after it copied a date from its example) |
| Options | `--postprocess`, `num_ctx` 16384 |
| Outlines | All five: SFWRENG 2OP3, 2XC3, 2DA4, 2DM3 and COMPSCI 2C03 (44 answer-key items in total) |
| Runs | One run per outline per strategy; total run time 87 minutes |

The code rules and prompts were **not changed** from the pdfplumber runs, except that the `linking` line finder now keeps two lines of context before each date instead of one (PyMuPDF puts each table cell on its own line). Differences therefore come mainly from the text extraction.

## 2. How the extracted text differs

| Outline | pdfplumber (spike) | PyMuPDF (Shivya) |
|---|---|---|
| 2XC3 schedule table | Columns interleaved; "Team Final Submission" separated from "Dec 10 (10%)"; "(10%)" for A2 several lines away | Each cell on its own short line, in order: "A2 Due Oct 26 / (10%)", "Team / Development Plan / Due Nov 18 (2%)", "Team Final / Submission Due / Dec 10 (10%)" |
| 2C03 | Most spaces lost ("FinalExam 49.25%ofthefinalgrade") | Normal spacing ("Final Exam 49.25% of the final grade.") |
| 2DM3 | Broken ligatures ("anal exam") | Same broken ligatures; the fault is in the PDF's fonts |
| Page markers | "--- Page N ---" added between pages | No page markers |
| 2DM3 footer | Print timestamp "2026-09-04, 3:24 pm" on each page | Same timestamp, each on its own line |

**PyMuPDF text is clearly better for tables**, which was the biggest extraction problem in the earlier runs.

## 3. Results

Score format: found / dates / TBD / weights, out of the number of key items.

| Outline (key items) | baseline | think | linking |
|---|---|---|---|
| 2OP3 (11) | **11 / 11 / 11 / 11** | **11 / 11 / 11 / 11** | 11 / 4 / 4 / 11 |
| 2XC3 (11) | 4 / 4 / 4 / 4 | **9 / 9 / 8 / 8** | 9 / 9 / 9 / 2 |
| 2DA4 (7) | **7 / 7 / 7 / 7** | 7 / 7 / 7 / 6 | **7 / 7 / 7 / 7** |
| 2DM3 (6) | **6 / 6 / 6 / 6** | **6 / 6 / 6 / 6** | 6 / 6 / 6 / 2 |
| 2C03 (9) | 2 / 1 / 2 / 2 | 9 / 1 / 9 / 9 | 2 / 2 / 2 / 2 |
| **Total (44)** | **30 / 29 / 30 / 30** | **42 / 34 / 41 / 40** | **35 / 28 / 28 / 24** |

Time per outline: baseline 3.5 to 5.3 min, think 5.7 to 6.9 min, linking 5.4 to 6.9 min.

### Compared with pdfplumber (same strategy, same outline)

| Outline | Strategy | pdfplumber | PyMuPDF | Change |
|---|---|---|---|---|
| 2OP3 | baseline (+ rules) | 11 / 5 / 6 / 11 | 11 / 11 / 11 / 11 | **better**: all 6 schedule dates now found |
| 2XC3 | baseline | 4 / 3 / 3 / 3 | 4 / 4 / 4 / 4 | slightly better |
| 2XC3 | think | 8 / 8 / 7 / 4 | 9 / 9 / 8 / 8 | **better**: every assignment weight right, Team Development Plan found |
| 2XC3 | linking | 8 / 7 / 6 / 3 | 9 / 9 / 9 / 2 | better dates, worse weights |
| 2OP3 | think | 11 / 11 / 11 / 11 | 11 / 11 / 11 / 11 | same (perfect) |
| 2OP3 | linking | 11 / 11 / 11 / 11 | 11 / 4 / 4 / 11 | **worse**, caused by a bug in the spike code (section 5.3) |
| 2C03 | baseline (+ rules) | 9 / 9 / 9 / 9 | 2 / 1 / 2 / 2 | **worse** (section 5.1) |
| 2DA4, 2DM3 | baseline | perfect | perfect | same |

## 4. What is good

### 4.1 think with PyMuPDF is the best result so far

42 of 44 items found, 41 TBD flags and 40 weights right. Leaving out 2C03 (section 5.1), it got 33 of 35 dates right.

### 4.2 2XC3 is nearly solved

The scrambled table was the hardest case. With PyMuPDF text, think returned:

| Model item | Date | Weight | Key |
|---|---|---|---|
| Individual Assignment 1 (A1) | 2026-10-05 | 5 | correct |
| Individual Assignment 2 (A2) | 2026-10-26 | 10 | correct |
| Individual Assignment 3 (A3) | 2026-11-09 | 5 | correct |
| Individual Assignment 4 (A4) | 2026-11-23 | 10 | correct |
| Team Development Plan | 2026-11-18 | 2 | correct (never found before) |
| Team Assignment | 2026-12-10 | 15 | date correct; weight should be 10 (Team Final Submission) |
| C Test | TBD | 30 | correct |

The per-assignment weights (5/10/5/10) were wrong in every pdfplumber run because "(10%)" was cut away from its assignment. With PyMuPDF the weight sits on the line right after the date, and the model read it correctly instead of splitting 30% equally.

### 4.3 Plain baseline now handles 2OP3

With PyMuPDF text, the simple one-call baseline got every 2OP3 schedule date, which it could not do with pdfplumber text. Cleaner text helps even without a better prompt.

### 4.4 The easy outlines stay perfect

2DA4 and 2DM3 were perfect with baseline, and 2DM3 also with think, even with "anal exam" in the text.

## 5. What is bad

### 5.1 2C03: a list of dates on one line is not split into items

2C03 lists all eight deadlines in one sentence that wraps onto a second line:

> The preliminary deadlines are as follows: September 25; October 9; October 23; October 30; November
> 6; November 13; November 24; and December 1.

| Strategy | What it returned |
|---|---|
| baseline | One row, "Assignments", 7.25%, no date (weights sum to 56.5%) |
| think | Nine rows, Assignment 1 to 9, correct weights, **no dates**, plus an invented **Assignment 9** |
| linking | "Assignments" with Sep 25, then "Assignments (Best 7) 2" to "7" with no dates |

The pdfplumber baseline run got all eight dates from the same sentence, so this is partly run-to-run variation and partly the line break after "November". Pairing "the Nth date in a list" with "Assignment N" is a step the small model does not do reliably.

**Invented item:** think's Assignment 9 comes from an inconsistency in the outline itself, which says "The nine assignments" in one place and "Eight assignments" in another. The model followed the wrong one.

### 5.2 Equal split is still applied where it should not be

| Outline | Strategy | Problem |
|---|---|---|
| 2DA4 | think | Split "Labs 10%" into Lab 1 to 5 at 2% each. Reasonable, but the key has one "Labs" row, so it scored as a weight error. |
| 2XC3 | linking | Assignments 7.5% each (should be 5/10/5/10); Team items 5% each (should be 2 and 10); C Test 10% (should be 30%) |
| 2DM3 | linking | Assignments 1.5% each (should be 5%); weights sum to 85% |

### 5.3 linking failures are mostly bugs in the spike's own code

The `linking` model calls were often right; the code around them was not.

| Outline | What happened | Cause |
|---|---|---|
| 2OP3 | The model linked all 8 dates correctly, but the output lost 7 of them | The model returned component **names** ("Project Assignment", "Assignment 3") instead of the IDs it was asked for ("G3"). The code only accepts IDs, so those links were dropped. **Spike code bug.** |
| 2DM3 | Six extra "Assignment set 1 to 6" rows, all dated 2026-09-04 | The page footer "2026-09-04, 3:24 pm" (the date the outline was printed) was picked up as a dated line. **Line finder needs to skip footers.** |
| 2XC3 | Items named "1" and "2" dated Sep 16 and Sep 23 | Week headers such as "1 (Sep 10 – 16)" were picked up and linked as items. **Line finder needs to skip week ranges.** |
| 2C03 | Only the first deadline linked | All eight dates are on one line, but linking expects one date per line. **Design limit.** |

These are fixable, but as it stands linking is not ready.

### 5.4 Baseline still reads only the grading summary for 2XC3

Even with better text, the one-call baseline returned "Individual Assignments 30%" and "Team Assignment 15%" as single rows, and counted the lab marks twice ("Weekly lab submissions" and "Lab Milestones"), so weights summed to 115%. Better text alone does not fix this; the think strategy does.

### 5.5 Smaller issues

- **Course code:** 2DA4's PyMuPDF text starts with "Software Eng. 2DA4", and the model used that. 2C03 is still "COMPSCI 2CO3" (an error in the outline itself).
- **Types:** baseline still typed the 2OP3 midterm as "quiz" and the 2XC3 Linux and Git Test as "lab".
- **One run each:** these results are single runs at temperature 0. The 2C03 difference between extractors shows that results can change a lot between runs, so consistency still needs testing.

## 6. Conclusions

1. **Use Shivya's PyMuPDF extraction.** It keeps table cells in order, which fixed the 2XC3 weights and team items and let even the plain baseline find 2OP3's schedule dates. There is no reason to keep the spike's pdfplumber extraction.
2. **think is the strategy to continue with.** With PyMuPDF it found 42 of 44 items and got 40 weights right. Its remaining weak spots are lists of dates on one line (2C03) and inconsistent outlines.
3. **linking needs code fixes before it can be judged.** Its model step was often correct, but the spike code dropped or invented rows (name vs ID, footers, week headers).
4. **Feasibility improves.** With PyMuPDF and think, four of the five outlines are perfect or nearly perfect, all locally on a laptop CPU in about 6 to 7 minutes each. The plan still needs a person to confirm each outline, and the weight-sum warning would have flagged the bad 2C03 and 2XC3 results automatically.

## 7. Next steps

1. **Fix linking code:** accept component names as well as IDs; skip page footers and week-range headers; allow one line to give several dates.
2. **Add a count check in code:** if the outline says "Eight assignments" but the result has a different number of rows (or rows without dates), flag it for review.
3. **Consistency test:** run think with PyMuPDF three times on all five outlines and compare.
4. **2C03 follow-up:** test whether joining wrapped lines before sending (so the date list is on one line) helps think pair dates with assignments.
5. **Update the issue #38 comment** with the PyMuPDF results, since they change the recommendation from "not reliable for schedule-table outlines" to "reliable for most outlines with think and PyMuPDF, with human confirmation".
