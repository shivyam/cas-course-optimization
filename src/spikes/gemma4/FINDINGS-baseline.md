# Spike #38: Gemma 4 E2B baseline results in detail

This file records what the first runs of `spike_gemma.py` showed: every kind of error and mismatch found, with examples taken from the saved results. It covers the **baseline strategy only** (one call, whole outline in, full JSON out). The `think`, `linking` and `fewshot` strategies are tested separately.

## 1. Setup

| Item | Value |
|---|---|
| Model | `gemma4:e2b` through Ollama 0.40.14, 100% CPU (no GPU) |
| Text extraction | Custom, inside the spike script: `pdfplumber`, `page.extract_text()`, one block per page. **Not** the PyMuPDF extraction in Shivya's PR (`feat/pdf-outline-upload`). |
| Prompt | One system prompt with extraction rules, the full outline text, a JSON schema (`format`), temperature 0 |
| Runs | SFWRENG 2DA4 at `num_ctx` 4096; SFWRENG 2DA4, 2DM3, 2OP3, 2XC3 and COMPSCI 2C03 at `num_ctx` 16384; one run each |
| Scoring | Each model row is matched to an item in a hand-made answer key, then date, TBD flag and weight are compared |

All scores below were produced with the corrected scorer (see section 6). The first scorer under-counted correct answers.

## 2. Summary

| Outline | Read / sent (tokens) | Time | Found | Dates | TBD | Weights | Weight sum |
|---|---|---|---|---|---|---|---|
| 2DA4 at 4096 | 2,051 / ~4,064 | 149 s | 0/7 | 0/7 | 0/7 | 0/7 | 0 |
| 2DA4 | 4,231 / ~4,368 | 221 s | 7/7 | 7/7 | 7/7 | 3/7 | 130 |
| 2DM3 | 7,033 / ~6,741 | 374 s | 6/6 | 6/6 | 6/6 | 6/6 | 105 |
| 2C03 | 5,855 / ~5,408 | 365 s | 9/9 | 9/9 | 8/9 | 9/9 | 107.25 |
| 2OP3 | 5,183 / ~5,673 | 280 s | 6/11 | 5/11 | 6/11 | 6/11 | 100 |
| 2XC3 | 5,620 / ~5,926 | 266 s | 4/11 | 3/11 | 3/11 | 3/11 | 105 |

Speed was 7.1 to 11.9 output tokens per second. Every 16384 run returned valid JSON with no schema problems.

**Pattern:** the model does well when each assessment, its date and its weight sit together on one line or in one table (2DM3, 2C03, 2DA4). It does badly when the grading scheme only gives totals and the dates live somewhere else, such as a weekly schedule (2OP3, 2XC3).

## 3. Error types, with examples

### 3.1 Outline cut off by the context window (4096 only)

Ollama's default context is 4096 tokens. It silently drops the **start** of a longer prompt. For 2DA4 the model received 2,051 of about 4,064 tokens: only the back half of the outline (policies and graduate attributes). The grading scheme and dates on page 1 were lost.

What the model returned:

| name | due_date | source_text |
|---|---|---|
| Academic Dishonesty | N/A | "Academic Dishonesty" |
| Course Content/Assessment | N/A | "Graduate Attributes and Indicators" |

Course code: "Not specified (Policy/Syllabus excerpt)". Term: "General Academic Policies and Expectations". It also wrote "N/A" as a date, which broke the ISO date format.

**Lesson:** `num_ctx` must be at least 16384. All five test outlines fit at that size.

### 3.2 Group rows not split into individual items

When the grading scheme lists a group ("Five Assignments 15%"), the model kept it as one row instead of one row per assignment.

| Outline | Model row | Expected |
|---|---|---|
| 2OP3 | "Five Assignments", 15%, no date | Assignment 1 to 5, 3% each, five dates |
| 2XC3 | "Individual Assignments", 30%, no date (source: "Individual Assignments (4): 30%") | Assignment 1 to 4 with 5%, 10%, 5%, 10% |
| 2XC3 | "Team Assignment", 15%, no date | Team Development Plan 2%, Team Increment 2%, Team Final Submission 10%, Teams Formed in Lab 1% |

This alone accounts for most of the "not found" items in 2OP3 (5 of 5 missing) and 2XC3 (7 of 11 missing).

### 3.3 Group weight copied onto every item

In 2DA4 the model did split the assignments into four rows, but gave each the **group** weight.

| Key | Model |
|---|---|
| Assignment 1: 2.5% | "Assignments 1": 10% |
| Assignment 2: 2.5% | "Assignments 2": 10% |
| Assignment 3: 2.5% | "Assignments 3": 10% |
| Assignment 4: 2.5% | "Assignments 4": 10% |

Total: 130%. The prompt explicitly said "split it equally", and the model ignored it.

### 3.4 Dates in a separate schedule not linked to their item

This is the most important failure. In 2OP3 every assignment date and the project date appear only in the weekly schedule, for example:

> Assignment 3 due: Fri, October 23rd.
> Project due: Thu, December 3th.

The model returned no date for any assignment or the project. It clearly read the project line, because its own `missing_fields` says:

> "Specific due date for the Project due (Thu, December 3th)"

So it saw the date, but did not connect "Project due" in the schedule to "Project Assignment 15%" in the grading table. It also listed "Specific due dates for Assignments 1, 2, 3, 4, and 5" as missing, although all five are in the outline.

In 2XC3 the schedule is a multi-column table (lines such as "A1 Due Oct 5 (5%)", "A3 Due Nov 9", "Test Nov 3 or 4"). The model used only the grading summary and returned **no dates at all**.

### 3.5 TBA and TBD handled inconsistently

| Outline | Item | Outline text | Model `date_tbd` | Expected |
|---|---|---|---|---|
| 2XC3 | C Test | "The C Test TBA" | false | true |
| 2C03 | Final Exam | no date (set by the university) | false | true |
| 2DA4, 2DM3, 2OP3 | Final Exam | no date (set by the university) | true | true |

The same situation (a final exam with no date) was marked TBD in three outlines and not TBD in one. An explicit "TBA" in 2XC3 was missed.

### 3.6 The same marks counted twice

2XC3 mentions the lab marks in two places: a note under the schedule table ("Weekly lab submissions (5% total) not shown") and the grading scheme ("Lab Milestones (~1 per week): 5%"). The model returned both as separate 5% items, so the weights summed to 105%.

### 3.7 Ungraded items included

| Outline | Model row | Why it is wrong |
|---|---|---|
| 2C03 | "Try-Out Exam" (quiz, TBD, no weight) | A practice exam; not graded |
| 2DM3 | "Tutorial Sessions" (lab, no weight; source "12 tutorials*") | Tutorials are not graded in 2DM3 |

Both have no weight, so they are easy to filter out in code.

### 3.8 Generic or inconsistent names

| Outline | Model names | Problem |
|---|---|---|
| 2C03 | "Assignments" (eight rows, all the same name) | Correct dates and weights, but rows cannot be told apart by name; seven of the eight rows quote the same source line |
| 2DM3 | "Assignment A1" to "Assignment A4" | Mix of the outline's "A1" and the word "Assignment" |
| 2DA4 | "Assignments 1" to "Assignments 4" | Plural name for a single item |

These were scored as correct after the scorer was fixed (section 6), but the backend will need to normalise names before storing them.

### 3.9 Wrong assessment types

Type is not scored, but the scheduler will need it (a test is placed differently from a lab).

| Outline | Item | Model type | Expected |
|---|---|---|---|
| 2XC3 | Linux and Git Test | lab | midterm or quiz |
| 2XC3 | C Test | lab | final_exam |
| 2OP3 | Midterm test | quiz | midterm |
| 2OP3 | Floating best | final_exam | other (grading rule) |
| 2OP3 | Research Surveys Bonus | assignment | other |

### 3.10 `missing_fields` is unreliable

| Outline | Model says missing | Reality |
|---|---|---|
| 2C03 | "Midterm date" | The course has no midterm |
| 2OP3 | Due dates for Assignments 1 to 5 and the Project | All six are in the weekly schedule |
| 2XC3 | "Specific due dates for tests and assignments" | Most are in the schedule table |
| 2DA4 | "Specific Learning Outcomes" | The outline has an Objectives section and the model listed 5 learning outcomes |

This field should not be used to warn professors without a check in code.

### 3.11 "Best N of M" rules cannot be shown

2C03 counts the best 7 of 8 assignments (8 × 7.25% listed, 7 count) and 2DM3 the best 3 of 4 (4 × 5% listed, 3 count). Listing each item's weight gives totals of 107.25% and 105%. This is a limit of the output format rather than a model error, but the weight check will flag these outlines, and the final schema needs a way to store the rule.

## 4. What the model did well

- **Dates on the same line as the item** were right every time: all 6 in 2DM3, all 8 assignment dates in 2C03, all 6 dated items in 2DA4.
- **Weights in a clear grading table** were right every time, including decimals (7.25%, 49.25%) and bonus marks (2OP3 "Research Surveys Bonus" marked `is_bonus: true`).
- **Messy text.** 2DM3's PDF text has broken ligatures ("anal exam" for "final exam", "Xnal" for "final"), and 2C03's text lost most spaces ("FinalExam 49.25%ofthefinalgrade"). The model read both correctly.
- **Valid JSON every time** at 16384, with ISO dates and no schema errors.

## 5. Not model errors: problems in the outlines themselves

| Outline | Outline text | Model output |
|---|---|---|
| COMPSCI 2C03 | Header reads "COMPSCI 2CO3" (letter O, not zero) | "COMPSCI 2CO3", a faithful copy |
| SFWRENG 2DA4 | "Session and Term: 2026 Winter" on a Fall 2026 outline | "2026 Winter", a faithful copy |
| COMPSCI 2C03 | Says "nine assignments" in one place and "Eight assignments" in another | Used eight, which matches the deadlines |

These are worth reporting to CAS as data quality issues: the system will reproduce whatever the outline says.

## 6. Scorer problems found and fixed during the spike

The first scores under-counted correct answers. Three matching bugs were fixed and all results were re-scored with `--rescore`:

1. "Assignments 1" did not match the key's "Assignment 1" (plural).
2. "Assignment A1" did not match "Assignment 1" or the alias "A1".
3. One model row could match several key items, so eight rows named "Assignments" were all matched to Assignment 1. Each row is now used once, and ties are broken by date.

Example: 2C03 went from "dates 0.222" to "dates 1.0" after fix 3; 2DM3 went from "found 2/6" to "found 6/6" after fix 2.

## 7. Effect of the `--postprocess` rules on these same results

The `--postprocess` option applies fixed rules in code after the model: split group rows, fix repeated group weights when they push the total over 100%, and mark undated tests and exams as TBD. Re-scoring the baseline output with these rules (no new model run):

| Outline | Baseline | Baseline + rules |
|---|---|---|
| 2DA4 | weights 3/7, sum 130 | **weights 7/7, sum 100** |
| 2OP3 | found 6/11, weights 6/11 | **found 11/11, weights 11/11** (dates still 5/11) |
| 2C03 | TBD 8/9 | **TBD 9/9** |
| 2DM3 | already perfect | unchanged |
| 2XC3 | found 4/11 | unchanged (the group rows have uneven weights, so they cannot be split equally) |

Code fixes the weight and TBD errors (3.3, 3.5) and the simple group rows (3.2). It cannot fix the date-linking failure (3.4), which is what the `think`, `linking` and `fewshot` strategies target.

## 8. Text extraction notes (pdfplumber)

- **2XC3:** the multi-column schedule table is scrambled. Cells from different columns are interleaved, so for example "Team Final Submission" and its "Dec 10 (10%)" end up several lines apart. No prompt can fully fix this; layout-aware or table extraction would be needed.
- **2DM3:** ligatures are broken ("anal", "Xnal").
- **2C03:** most spaces between words are lost.
- **2XC3:** pdfminer printed repeated "Could not get FontBBox" warnings. They are harmless and are now hidden.

All of this should be re-checked with the PyMuPDF extraction from `feat/pdf-outline-upload` once it is merged, since a different extractor may produce cleaner or worse text.
