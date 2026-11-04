# Spike #38: Gemma 4 E2B prompt strategies compared

This file records what `run_strategies.sh` showed (log: `results/logs/strategies_20261103-231531.log`). It compares three new ways of prompting `gemma4:e2b` with the baseline from [FINDINGS-baseline.md](FINDINGS-baseline.md), and ends with a feasibility judgement for the project.

## 1. What was tested

| Strategy | How it works |
|---|---|
| **baseline** | One call: the whole outline in, the full JSON out. (Results from the earlier run.) |
| **think** | Call 1: the model writes free-text notes (grading scheme, then every line that dates each item, then a final list). Call 2: the notes are turned into JSON. |
| **linking** | Call 1: the model lists the graded components only. Code then pulls out every line that mentions a date or TBA. Call 2: the model matches those lines to the components. Code builds the final rows. |
| **fewshot** | The baseline prompt plus one worked example (an invented outline whose dates live in a weekly schedule, with the correct answer). |

All three new strategies ran with `--postprocess` (rules in code: split group rows, fix repeated group weights, TBD for undated tests) and `num_ctx` 16384. Outlines: **SFWRENG 2OP3** and **SFWRENG 2XC3**, the two outlines the baseline failed on. One run each.

Text extraction is the spike's own `pdfplumber` extraction, **not** the PyMuPDF extraction in Shivya's PR (`feat/pdf-outline-upload`).

## 2. Results

### SFWRENG 2OP3 (11 key items; dates only in the weekly schedule)

| Strategy | Found | Dates | TBD | Weights | Weight sum | Time |
|---|---|---|---|---|---|---|
| baseline | 6/11 | 5/11 | 6/11 | 6/11 | 100 | 280 s |
| baseline + rules | 11/11 | 5/11 | 6/11 | 11/11 | 100 | (re-scored, no new run) |
| **think** | **11/11** | **11/11** | **11/11** | **11/11** | 100 | 340 s |
| **linking** | **11/11** | **11/11** | **11/11** | **11/11** | 100 | 1,195 s * |
| fewshot | 10/11 | 9/11 | 10/11 | 10/11 | 85 | 296 s |

\* The second linking step on 2OP3 took 1,054 s at about 2.5 tokens per second, while the same step on 2XC3 took 162 s. The laptop most likely slowed down or slept during that step. Normal time for linking is about 5 minutes per outline.

### SFWRENG 2XC3 (11 key items; scrambled multi-column schedule table)

| Strategy | Found | Dates | TBD | Weights | Weight sum | Time |
|---|---|---|---|---|---|---|
| baseline | 4/11 | 3/11 | 3/11 | 3/11 | 105 | 266 s |
| **think** | **8/11** | **8/11** | **7/11** | 4/11 | 97.5 | 400 s |
| linking | 8/11 | 7/11 | 6/11 | 3/11 | 100 | 306 s |
| fewshot | 8/11 | 7/11 | 6/11 | 5/11 | 90 | 263 s |

## 3. Has it improved?

**Yes, a lot.** The main baseline failure was linking a date in the weekly schedule to an item in the grading table. Two strategies fixed it:

- **2OP3 went from 5/11 dates to 11/11** with both `think` and `linking`. Every assignment date, the project date ("Project due: Thu, December 3th" now linked to "Project Assignment 15%") and every TBD flag is correct.
- **2XC3 went from 0 assignment dates to all 4** with every strategy (A1 Oct 5, A2 Oct 26, A3 Nov 9, A4 Nov 23), even though they sit inside a scrambled table.
- `think` also linked the 2XC3 "Team Assignment" to its Dec 10 final submission date, which no other run found.

Asking the model to reason first (`think`), or giving it a small focused question (`linking`), made it do the "equivalence" work the baseline would not do: "A3" = "Assignment 3", "Project due" belongs to "Project Assignment".

## 4. What is good

- **think and linking are perfect on 2OP3**, the outline type CAS needs most (dates only in a schedule).
- **Types improved with think.** On 2OP3 it typed every item correctly (project, midterm, other for "Floating best"), where the baseline called the midterm a quiz and Floating best a final exam.
- **TBA handled better with think and fewshot.** "The C Test TBA" in 2XC3 was marked TBD. The baseline missed it.
- **linking is traceable.** Every date comes with the exact outline line it was taken from (for example ">> Assignment 3 due: Fri, October 23rd."), because code picks the lines and the model only matches them. A professor or admin can check each date against its source in the UI.
- **Valid JSON every time**, and no context truncation (each call read the whole outline).

## 5. What is bad

### 5.1 fewshot copied a date from the example (hallucination)

On 2OP3, fewshot returned:

| name | due_date | source_text |
|---|---|---|
| Assignment 3 | 2026-03-19 | "Assignment set A3 due Mar 19." |

That line is **not in the 2OP3 outline**. It comes from the invented example outline in the prompt. The model copied the example's answer into the real one, and also dropped the Project (weights summed to 85%). This is the most dangerous kind of error, since it looks correct and cites a source. **fewshot should be dropped.**

### 5.2 The equal-split rule gives wrong weights for 2XC3

2XC3's grading scheme says "Individual Assignments (4): 30%", but the schedule gives each one its own weight: A1 5%, A2 10%, A3 5%, A4 10%. Every strategy followed the "split equally" rule instead:

| Strategy | A1 | A2 | A3 | A4 |
|---|---|---|---|---|
| Key | 5 | 10 | 5 | 10 |
| linking | 7.5 | 7.5 | 7.5 | 7.5 |
| think | 5 | 7.5 | 7.5 | 7.5 |
| fewshot | 5 | 5 | 5 | 5 |

The rule is right only when the outline gives no per-item weights anywhere. It needs to change to: "use a per-item weight if the outline gives one; split equally only if it does not."

### 5.3 The 2XC3 team items are still missing

No strategy found Team Development Plan (2%), Team Increment (2%) or Teams Formed in Lab (1%). In the extracted text these cells are separated from their names by the scrambled table (for example "G: Pro Git 3 Due Nov 18 (2%)" has no "Team Development Plan" near it). This is a **text extraction problem**, not a prompt problem. Layout-aware or table extraction is needed.

### 5.4 linking has a bug in code

linking marked the 2XC3 C Test as not TBD even though the line "The C Test TBA" was found. The model typed both tests as "lab", and the code then treated them as recurring items, which are never TBD. Two fixes are needed: do not trust the model's "lab" type for anything named "test" or "exam", and let an explicit TBA in the linked line win.

### 5.5 Names and types still need cleaning

- linking kept the outline's short names ("A1", "A2") instead of "Assignment 1".
- linking typed 2OP3's Project and Tutorial attendance as "assignment".
- think named 2XC3 items "Individual Assignment A1", and fewshot "Individual Assignment 1 (A1)".

The backend will need a name and type normalisation step.

### 5.6 Speed

| Strategy | Typical time per outline (CPU) |
|---|---|
| fewshot | 4 to 5 min |
| linking | about 5 min |
| think | 6 to 7 min |

At about 6 minutes per outline, all 35 Fall 2026 outlines would take about 3.5 hours on this laptop. A CAS server may be faster, especially with a GPU.

### 5.7 Small test

Two outlines, one run each. Temperature is 0, but the consistency of repeated runs has not been tested yet, and neither strategy has been run on the three easier outlines (2DA4, 2DM3, 2C03).

## 6. Debatable key item

The 2XC3 "Linux and Git Test" is "Nov 3 or 4" depending on the student's lab. The key says no date and not TBD. think and fewshot marked it TBD. Either answer is defensible; the team should decide what the system should store for a test held on different days by lab section.

## 7. Is it feasible for the project?

**Yes, as a batch extraction step with human confirmation, using `think` or `linking` plus rules in code. Not as an unattended or real-time system.**

Reasons it is feasible:
- It runs fully locally on CPU, which meets the "must run on CAS servers, no cloud" requirement.
- With `think` or `linking`, it handles the hard case (dates in a separate schedule) perfectly on 2OP3, and gets every individual assignment date on the scrambled 2XC3.
- The remaining errors are mostly fixable in code (weight rule, TBA rule, names, types) or in text extraction (scrambled tables), not in the model.
- `linking` shows the exact source line for each date, which fits the plan that professors confirm or correct extracted data.

Conditions:
1. Every extracted outline must be shown to a person to confirm before it is used for scheduling.
2. Run as a background batch (minutes per outline), not while a professor waits.
3. The weight-sum check must be shown in the UI, so outlines that do not add up to 100% are flagged.
4. Text extraction must handle tables better before 2XC3-style outlines are reliable.

## 8. Recommended next steps

1. **Drop fewshot** (hallucinated a date from its example).
2. **Fix the rules:** per-item weights before equal split; TBA in the linked line always wins; tests and exams are never "recurring".
3. **Run think and linking on all five outlines, three runs each**, to check accuracy on the easy outlines and consistency between runs.
4. **Try better text extraction for tables** (pdfplumber table or layout mode, or the PyMuPDF extraction from `feat/pdf-outline-upload` once merged) and re-run 2XC3.
5. **Pick one strategy.** think was the most accurate here; linking is easier to check because every date cites its source line. A combination (think's reasoning, linking's line citations) is also possible.
6. Optional: try `gemma4:e4b` with the winning strategy on 2XC3 to see if a slightly bigger model handles the scrambled table better.
