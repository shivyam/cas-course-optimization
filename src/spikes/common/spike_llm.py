"""Shared spike harness: run and test a small local LLM on course outlines through Ollama.

Throwaway script for the model-selection spikes, not production code. It sends course
outline text to a local Ollama model and records what comes back, so the team can
judge which small local model is good enough for outline extraction.

Origin: spike #38 (Gemma 4 E2B, src/spikes/gemma4/spike_gemma.py on branch spike/gemma4).
The prompts, JSON schema, --postprocess rules, extraction code and scorer are copied
unchanged from that script, so results for different models can be compared directly.
Only these things were added: --model is required, results go to results/<model>/,
and --inject takes a variant name (ignore, alter, disguised).
Unused parts of the #38 script (linking, fewshot, graduate attributes, pdfplumber)
were removed; they are still on branch spike/gemma4.

Files:
    spike_llm.py      this file: command-line options, one run, saving results
    config.py         Ollama address, where the outline PDFs are
    extraction.py     PDF to text (Shivya's PyMuPDF code)
    prompts.py        prompts, JSON schema, prompt-injection lines
    ollama_client.py  calls to Ollama
    strategies.py     baseline and think
    rules.py          --postprocess rules and the weight check
    scoring.py        scoring against keys/ and the printed report

Spikes using this harness: #38 Gemma 4 E2B (gemma4:e2b), #40 Llama 3.2 3B (llama3.2:3b).

Setup (once):
    pip install pymupdf==1.27.2.2
    ollama pull llama3.2:3b          (or whichever model you are testing)
    (Ollama must be running; it listens on http://localhost:11434)
    Copy .env.example to .env and set SPIKE_OUTLINES_DIR to your folder of outline PDFs
    (or set the SPIKE_OUTLINES_DIR environment variable, or pass --outlines-dir).
    PDF arguments below are relative to that folder.

Typical runs:
    # 1. One outline, baseline strategy, scored against its key
    python spike_llm.py Fall_2026/SFWRENG2DA4_RyanLeduc_Fall2026.pdf --model llama3.2:3b \
        --postprocess --num-ctx 16384 --key-dir keys

    # 2. Same, think strategy, 3 runs (consistency)
    python spike_llm.py Fall_2026/SFWRENG2DA4_RyanLeduc_Fall2026.pdf --model llama3.2:3b \
        --postprocess --num-ctx 16384 --key-dir keys --strategy think --runs 3

    # 3. Prompt-injection check (variants: ignore, alter, disguised)
    python spike_llm.py Fall_2026/SFWRENG2DA4_RyanLeduc_Fall2026.pdf --model llama3.2:3b \
        --postprocess --num-ctx 16384 --key-dir keys --inject alter
    then: python compare_inject.py results/llama3.2-3b

Every run writes a JSON file to results/<model>/ (raw model output, parsed output,
timings, token counts, score) and appends one line to results/<model>/summary.csv.
run_spike.sh wraps these commands with the fixed settings and saves a log.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

from config import OUTLINES_ENV, model_slug, outlines_dir, resolve_pdf
from extraction import extract_pdf_text
from prompts import ASSESSMENT_SYSTEM, INJECTIONS, inject
from rules import postprocess, weight_warnings
from scoring import check_schema, print_report, score_assessments
from strategies import STRATEGIES, run_strategy


def run_one(pdf: Path, args, run_no: int, out_dir: Path) -> dict:
    """Run one outline once: extract text, optionally insert an injection line, call the
    model, apply --postprocess, score against the key, and save two files in out_dir:
    the exact text given to the model (*_input.txt) and the full result (*.json).
    """
    text = extract_pdf_text(pdf)
    # Prompt-injection test: plant one hostile line (variant chosen with --inject)
    # in the middle of the text. The planted text is saved in *_input.txt too.
    if args.inject:
        text = inject(text, args.inject)
    est_tokens = len(text) // 4  # rough estimate, about 4 characters per token

    parsed, steps = run_strategy(text, args)
    first_system = ASSESSMENT_SYSTEM
    if parsed and args.postprocess:
        parsed = postprocess(parsed)

    model_steps = [st for st in steps if "raw" in st]
    json_ok = parsed is not None
    raw = model_steps[-1]["raw"] if model_steps else ""
    prompt_tokens = model_steps[0]["prompt_tokens"] if model_steps else None  # the call that read the outline
    out_tokens = sum(st["output_tokens"] or 0 for st in model_steps)
    eval_s = sum(st["eval_seconds"] or 0 for st in model_steps)
    tok_per_s = round(out_tokens / eval_s, 1) if out_tokens and eval_s else None
    wall = round(sum(st["seconds"] or 0 for st in model_steps), 2)
    # Ollama silently drops the start of a prompt that does not fit the context,
    # so compare what the model actually read with what we sent.
    expected_tokens = (len(first_system) + len(text) + 40) // 4
    likely_truncated = bool(prompt_tokens) and (
        prompt_tokens < 0.8 * expected_tokens or prompt_tokens >= args.num_ctx - 64
    )

    result = {
        "pdf": str(pdf),
        "model": args.model,
        "task": "assessments",
        "strategy": args.strategy,
        "extractor": "pymupdf",
        "postprocess": bool(args.postprocess),
        "num_ctx": args.num_ctx,
        "run": run_no,
        "injected": args.inject or False,  # variant name, or False for a normal run
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "text_chars": len(text),
        "est_prompt_tokens": est_tokens,
        "expected_prompt_tokens": expected_tokens,
        "prompt_tokens": prompt_tokens,
        "output_tokens": out_tokens,
        "tokens_per_second": tok_per_s,
        "wall_seconds": wall,
        "likely_truncated": likely_truncated,
        "json_valid": json_ok,
        "schema_problems": check_schema(parsed) if json_ok else ["invalid JSON"],
        "warnings": weight_warnings(parsed),
        "steps": steps,
        "raw_output": raw,
        "parsed_output": parsed,
    }

    key_path = None
    if args.key:
        key_path = Path(args.key)
    elif args.key_dir:
        candidate = Path(args.key_dir) / f"{pdf.stem}.json"
        if candidate.exists():
            key_path = candidate
    if key_path and json_ok:
        key = json.loads(key_path.read_text(encoding="utf-8"))
        result["score"] = score_assessments(parsed, key)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"{pdf.stem}_{args.model.replace(':', '-')}_pymupdf_{args.strategy}{'-pp' if args.postprocess else ''}_ctx{args.num_ctx}_r{run_no}"
    if args.inject:
        tag += f"_inject-{args.inject}"  # e.g. ..._r1_inject-alter, so compare_inject.py can pair runs
    (out_dir / f"{tag}_{stamp}_input.txt").write_text(text, encoding="utf-8")
    (out_dir / f"{tag}_{stamp}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def append_summary(result: dict, out_dir: Path) -> None:
    """Add one row for this run to summary.csv. If the CSV has an older header, it is
    renamed to summary_old_<time>.csv and a new one is started.
    """
    path = out_dir / "summary.csv"
    s = result.get("score", {})
    row = {
        "timestamp": result["timestamp"],
        "pdf": Path(result["pdf"]).name,
        "model": result["model"],
        "task": result["task"],
        "extractor": result.get("extractor", "pdfplumber"),
        "strategy": result.get("strategy", "baseline"),
        "postprocess": result.get("postprocess", False),
        "num_ctx": result["num_ctx"],
        "run": result["run"],
        "injected": result["injected"],
        "prompt_tokens": result["prompt_tokens"],
        "likely_truncated": result["likely_truncated"],
        "wall_seconds": result["wall_seconds"],
        "tokens_per_second": result["tokens_per_second"],
        "json_valid": result["json_valid"],
        "schema_problems": len(result["schema_problems"]),
        "found": s.get("found", ""),
        "key_assessments": s.get("key_assessments", ""),
        "date_accuracy": s.get("date_accuracy", ""),
        "tbd_accuracy": s.get("tbd_accuracy", ""),
        "weight_accuracy": s.get("weight_accuracy", ""),
        "predicted_weight_sum": s.get("predicted_weight_sum", ""),
    }
    if path.exists():
        with path.open(encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != list(row):
            path.rename(out_dir / f"summary_old_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv")
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> None:
    """Parse options, then either re-score saved results (--rescore) or run the outlines."""
    ap = argparse.ArgumentParser(description="Model-selection spikes: test a local Ollama model on course outlines.")
    ap.add_argument("pdfs", nargs="*", help="Course outline PDF(s)")
    ap.add_argument("--rescore", nargs="+", metavar="RESULT_JSON",
                    help="Re-score saved result JSON file(s) against current keys (no model call)")
    ap.add_argument("--model", help="Ollama model tag, for example llama3.2:3b or gemma4:e2b (required for runs)")
    ap.add_argument("--strategy", choices=STRATEGIES, default="baseline",
                    help="How to ask the model (see strategies.py)")
    ap.add_argument("--outlines-dir",
                    help=f"Folder with the outline PDFs (overrides {OUTLINES_ENV} and .env)")
    ap.add_argument("--postprocess", action="store_true",
                    help="Apply fixed rules in code after the model (split group weights, TBD for undated tests)")
    ap.add_argument("--num-ctx", type=int, default=4096, help="Context window (Ollama default is 4096)")
    ap.add_argument("--runs", type=int, default=1, help="Repeat each outline this many times")
    ap.add_argument("--inject", nargs="?", const="ignore", choices=sorted(INJECTIONS),
                    help="Insert a prompt-injection line into the text (default variant: ignore)")
    ap.add_argument("--key", help="Answer key JSON (single outline)")
    ap.add_argument("--key-dir", help="Folder of answer keys named <pdf stem>.json")
    ap.add_argument("--out", default="results", help="Output folder (a subfolder per model is added)")
    args = ap.parse_args()

    # A model must be named for real runs (not needed for --rescore), so every
    # result file says exactly which model produced it.
    if args.pdfs and not args.model:
        ap.error("--model is required, for example --model llama3.2:3b")
    # Each model gets its own folder, e.g. results/llama3.2-3b/, so summary.csv and the
    # injection check never mix models.
    out_dir = Path(args.out)
    if args.model:
        out_dir = out_dir / model_slug(args.model)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.rescore:
        for rp in args.rescore:
            r = json.loads(Path(rp).read_text(encoding="utf-8"))
            stem = re.split(r"[\\/]", r["pdf"])[-1].rsplit(".", 1)[0]  # works for Windows or POSIX paths
            kp = Path(args.key) if args.key else Path(args.key_dir or "keys") / f"{stem}.json"
            key_data = json.loads(kp.read_text(encoding="utf-8")) if kp.exists() else None
            print(f"[rescore] {Path(rp).name}")
            print_report(r, key_data)
            if key_data and r.get("json_valid") and r.get("task", "assessments") == "assessments":
                sc = score_assessments(r["parsed_output"], key_data)
                r["score"] = sc
                Path(rp).write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
                print(
                    f"\n  SCORE\n  found {sc['found']}/{sc['key_assessments']}, dates {sc['date_accuracy']}, "
                    f"TBD {sc['tbd_accuracy']}, weights {sc['weight_accuracy']}, "
                    f"weight sum {sc['predicted_weight_sum']}\n"
                )
        return
    if not args.pdfs:
        ap.error("give at least one PDF, or use --rescore")

    base, source = outlines_dir(args.outlines_dir)
    print(f"Outlines folder: {base}  [{source}]")
    if not base.is_dir():
        print(f"WARNING: that folder does not exist. Set {OUTLINES_ENV} (see .env.example) "
              "or pass --outlines-dir.")
    for pdf_arg in args.pdfs:
        pdf = resolve_pdf(pdf_arg, base)
        if pdf is None:
            print(f"Skipping {pdf_arg}: not found as given or under {base}")
            continue
        for run_no in range(1, args.runs + 1):
            print(f"[{pdf.name}] {args.model} strategy={args.strategy}"
                  f"{' +postprocess' if args.postprocess else ''} ctx={args.num_ctx} run {run_no}/{args.runs} ...")
            r = run_one(pdf, args, run_no, out_dir)
            append_summary(r, out_dir)
            line = (
                f"  {r['wall_seconds']}s, {r['tokens_per_second']} tok/s, "
                f"model read {r['prompt_tokens']} of ~{r['expected_prompt_tokens']} tokens sent, "
                f"JSON valid: {r['json_valid']}"
            )
            for st in r["steps"]:
                if "raw" in st:
                    print(f"    step '{st['step']}': {st['seconds']}s, read {st['prompt_tokens']} tokens, wrote {st['output_tokens']}")
                elif "count" in st:
                    print(f"    step '{st['step']}': {st['count']} lines")
            for w in r.get("warnings", []):
                line += f"\n  WARNING: {w}"
            if r["likely_truncated"]:
                line += "\n  WARNING: input was cut to fit the context window; the model did not see the whole outline"
            if r["schema_problems"]:
                line += f"  schema problems: {len(r['schema_problems'])}"
            print(line)
            key_data = None
            kp = Path(args.key) if args.key else (Path(args.key_dir) / f"{pdf.stem}.json" if args.key_dir else None)
            if kp and kp.exists():
                key_data = json.loads(kp.read_text(encoding="utf-8"))
            if r["json_valid"]:
                print_report(r, key_data)
            else:
                print("  Model output was not valid JSON. Raw output starts with:")
                print("  " + r["raw_output"][:500])
            if "score" in r:
                s = r["score"]
                print("\n  SCORE")
                print(
                    f"  found {s['found']}/{s['key_assessments']}, dates {s['date_accuracy']}, "
                    f"TBD {s['tbd_accuracy']}, weights {s['weight_accuracy']}, "
                    f"weight sum {s['predicted_weight_sum']}"
                )

    print(f"\nDone. Per-run JSON, the text the model was given (*_input.txt) and summary.csv are in {out_dir.resolve()}")


if __name__ == "__main__":
    main()
