# Spike #39: Qwen3 4B compared with Gemma 4 E2B and Llama 3.2 3B

This file records what the Qwen3 4B runs showed and compares them with Gemma 4 E2B (#38) and Llama 3.2 3B (#40, [FINDINGS.md](../llama3_2/FINDINGS.md)). All three spikes use the shared harness in `src/spikes/common/`.

**Status:** smoke test and Phase A (both strategies, all five outlines, one run) done. Phase C (prompt injection) and Phase B (three runs) not run yet.

## 1. Setup

Everything except the model is the same as the Gemma and Llama runs.

| Item | Value |
|---|---|
| Model | `qwen3:4b`, 4.0B parameters, Q4_K_M, trained context 262,144 tokens, digest `359d7dd4bcda` |
| Ollama | 0.40.14, CPU only (same version and laptop as #38 and #40) |
| Harness | `src/spikes/common/` (`run_spike.sh`, `spike_llm.py`), same prompts, JSON schema, `--postprocess` rules and scorer |
| Built-in reasoning | **off** (`--native-think off`, see below) |
| Text extraction | Shivya's PyMuPDF `extract_pdf_text()`, pymupdf 1.27.2.2 |
| Options | `--postprocess`, `num_ctx` 16384, temperature 0 |
| Strategies | baseline (one call) and think (notes first, then JSON) |
| Outlines | SFWRENG 2OP3, 2XC3, 2DA4, 2DM3 and COMPSCI 2C03 (44 answer-key items in total) |
| Logs | `results/qwen3-4b_think-off/logs/phaseA_20261105-224402.log`, `phaseA-rerun_20261106-021747.log` |

**Built-in reasoning.** Qwen3 has its own reasoning mode, which Gemma and Llama did not use. The harness now has `--native-think on|off`, which sends Ollama's `think` field. Without the option nothing is sent, so the Gemma and Llama results are unchanged. These runs use `off`, so Qwen is asked the same way as the other two models. The saved results confirm no reasoning text was produced.

Every run read the whole outline (no context truncation) and returned valid JSON with no schema problems.

## 2. Summary

Totals out of 44 key items, as found / dates / TBD / weights:

| Strategy | Qwen3 4B | Gemma 4 E2B | Llama 3.2 3B |
|---|---|---|---|
| baseline | 31 / 21 / 24 / 28 | 30 / 29 / 30 / 30 | 27 / 18 / 20 / 24 |
| think | **43 / 42 / 43 / 42** | 42 / 34 / 41 / 40 | 36 / 30 / 16 / 21 |

**With think, Qwen is the most accurate of the three models.** It is ahead of Gemma's best single run on every measure (Gemma's three runs ranged 42 / 34-42 / 40-41 / 35-40), and it invented nothing with think.

**It is also by far the slowest:** 23 to 42 minutes per outline with think, against a 5-minute target (section 6).

With baseline, Qwen finds about as many items as Gemma but gets fewer dates and TBD flags right, and it invented two dates.

## 3. Results by outline

Score format: found / dates / TBD / weights.

### baseline

| Outline (key items) | Qwen | Gemma | Llama |
|---|---|---|---|
| 2OP3 (11) | 11 / 5 / 6 / 11 | **11 / 11 / 11 / 11** | 11 / 5 / 6 / 11 |
| 2XC3 (11) | 4 / 2 / 3 / 3 | 4 / 4 / 4 / 4 | 4 / 4 / 3 / 3 |
| 2DA4 (7) | 4 / 3 / 4 / 3 | **7 / 7 / 7 / 7** | 4 / 2 / 3 / 3 |
| 2DM3 (6) | 3 / 3 / 3 / 2 | **6 / 6 / 6 / 6** | **6 / 6 / 6 / 6** |
| 2C03 (9) | **9 / 8 / 8 / 9** | 2 / 1 / 2 / 2 | 2 / 1 / 2 / 1 |
| **Total (44)** | **31 / 21 / 24 / 28** | **30 / 29 / 30 / 30** | **27 / 18 / 20 / 24** |

The smoke test on 2DA4 (baseline) scored 4 / 3 / 3 / 3: the same rows as the Phase A run except one TBD flag.

### think

| Outline (key items) | Qwen | Gemma (run 1) | Llama |
|---|---|---|---|
| 2OP3 (11) | **11 / 11 / 11 / 11** | **11 / 11 / 11 / 11** | 11 / 11 / 11 / 5 |
| 2XC3 (11) | **10 / 9 / 10 / 10** | 9 / 9 / 8 / 8 | 4 / 4 / 3 / 3 |
| 2DA4 (7) | **7 / 7 / 7 / 6** | **7 / 7 / 7 / 6** | 7 / 6 / 1 / 3 |
| 2DM3 (6) | **6 / 6 / 6 / 6** | **6 / 6 / 6 / 6** | 6 / 1 / 1 / 2 |
| 2C03 (9) | **9 / 9 / 9 / 9** | 9 / 1 / 9 / 9 | 8 / 8 / 0 / 8 |
| **Total (44)** | **43 / 42 / 43 / 42** | **42 / 34 / 41 / 40** | **36 / 30 / 16 / 21** |

The biggest difference is 2C03, where the dates are a single comma-separated line ("The preliminary deadlines are as follows: September 25; October 9; ..."). Qwen matched all eight dates to the right assignments with both strategies. Gemma got this right in only one of its three think runs.

## 4. Error types, with examples

### 4.1 Invented dates (baseline only)

Checked against the text the model was given (`*_input.txt`).

| Outline | Model row | What the outline says |
|---|---|---|
| 2XC3 | "C Test", 2026-12-04 | "The C Test TBA". December 4 is the last day of classes |
| 2C03 | "Final Exam", 2026-12-10 | No exam date. December 10 is the last day of lectures |

Both are the last day of term, the same kind of guess Llama made ("Assignment 9", 2026-12-10). **With think, Qwen invented no items or dates.** It also did not add the "Assignment 9" row on 2C03 that Gemma and Llama both added.

### 4.2 Prompt example copied into the output

The same problem as Llama (#40 findings, 4.2): `missing_fields` returned the prompt's example, "Midterm date, Assessment weights, Learning outcomes", word for word.

| Strategy | Outlines where this happened |
|---|---|
| baseline | all five |
| think | 2C03 (word for word), 2XC3 (first two of the three) |

On the other three think outlines it returned real gaps (for example "Lab due dates, Final exam date" for 2DA4). `missing_fields` cannot be trusted with this model either.

### 4.3 Group rows not split (baseline)

| Outline | Model row | Expected |
|---|---|---|
| 2DA4 | "Assignments" 10%, no date | Assignment 1 to 4, 2.5% each, four dates |
| 2DM3 | "Assignments" 15%, dated 2026-09-25 | Assignment 1 to 4, 5% each, four dates |
| 2XC3 | "Individual Assignments" 30%; "Team Assignment" 15% | Four assignments and three team items with their own weights and dates |

In 2OP3 (baseline) the "Five Assignments 15%" row was split into five 3% rows by `--postprocess`, but the model gave none of the five dates, which are only in the weekly schedule.

### 4.4 One group row kept next to its items (think, 2DA4)

The model returned "Assignments" 10% dated Oct 5, followed by Assignment 2, 3 and 4 at 2.5% each. The first row should have been "Assignment 1" at 2.5%, so the weights summed to 107.5%. The weight-sum warning caught it.

The other weight-sum warnings are correct outputs, not errors: 2C03 sums to 107.25% (eight assignments listed, best seven count) and 2DM3 to 105% (four assignments listed, best three count). The answer keys have the same totals.

### 4.5 Notes cut off (think)

The think strategy's first call is limited to 2500 output tokens. Qwen hit that limit on **all five outlines**, so its notes stopped partway. On 2XC3 and 2DA4 the notes never reached PART 3 (the final list). The second call still produced good JSON from what was there. Gemma's notes were shorter (about 1350 tokens on 2C03) and finished. The limit was kept for a fair comparison; raising it would make Qwen even slower.

### 4.6 Course code, term and type

| Outline | Strategy | Problem |
|---|---|---|
| 2DA4 | both | course_code "2DA4" (subject missing) |
| 2OP3 | baseline | every item typed "assignment", including the midterm and final exam |
| 2OP3 | think | midterm typed "quiz"; tutorial attendance typed "assignment" |

"Winter 2026" (2DA4) and "COMPSCI 2CO3" (2C03) are copied from errors in the outlines themselves (#38 findings, section 5), so they are not counted against the model.

## 5. What Qwen did well

- **The best think scores of the three models**, including all nine dates on 2C03 and all six on 2DM3 (broken ligatures included).
- **No invented items or dates with think.**
- **Same-line dates found:** "MIDTERM: Friday Nov 6, 2026." was read correctly in every run, which Llama missed.
- **Valid JSON every time**, with no context truncation.

## 6. Speed

| Strategy | Qwen3 4B per outline | Gemma 4 E2B | Llama 3.2 3B |
|---|---|---|---|
| baseline | 4.7 to 20.2 min (279 to 1211 s) | 3.5 to 5.3 min | 3.6 to 7.9 min |
| think | **22.7 to 41.9 min** (1360 to 2514 s) | 4.9 to 11.9 min | 6.1 to 9.2 min |

Qwen wrote 0.8 to 3.2 output tokens per second (Gemma 8.2 to 10.6 in its three-run check; Llama 2.5 to 5.9). The fastest run was the afternoon smoke test (3.2 tok/s); the Phase A runs were overnight, when Gemma was also slower (#40 findings, section 8), so part of this is the laptop. Even so, Qwen's think strategy is roughly four to eight times over the 5-minute target (NFR_Performance), and its first call alone took 18 to 36 minutes.

The 2DM3 think run's first call took more than 30 minutes and hit the harness's HTTP timeout, which also stopped the 2C03 run. The timeout was raised to one hour (`ollama_client.py`) and both outlines were re-run (`phaseA-rerun` log).

The built-in reasoning mode (`--native-think on`) was not tried. It would add thousands of output tokens per call at these speeds.

## 7. Conclusion so far

1. **Qwen3 4B with think is the most accurate model tested** (43 / 42 / 43 / 42 of 44), slightly ahead of Gemma and well ahead of Llama, and it invented nothing with think.
2. **It is too slow on this laptop to meet the 5-minute target**, by a wide margin. Whether it is usable depends on CAS server hardware.
3. **Like Llama, it copies the prompt's example into `missing_fields`**, so that field is unreliable.
4. **One run per outline only.** Gemma's results varied between identical runs, so Qwen needs the three-run check (Phase B) before its lead over Gemma can be trusted.

## 8. Still to run

| Phase | Command | Approximate time at Phase A speed |
|---|---|---|
| C: prompt-injection gate (first in the team's order) | `bash src/spikes/common/run_spike.sh --model qwen3:4b --native-think off --strategies think --outlines "2OP3 2DA4" --inject "ignore alter disguised" --label phaseC` then `python src/spikes/common/compare_inject.py src/spikes/common/results/qwen3-4b_think-off --strategy think` | 2.5 to 4 h |
| B: consistency, three runs | `bash src/spikes/common/run_spike.sh --model qwen3:4b --native-think off --strategies think --runs 3 --label phaseB` | 6 to 10 h |
