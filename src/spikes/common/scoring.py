"""Scoring model output against the hand-made answer keys, and the printed report.

Copied unchanged from the #38 Gemma spike (graduate-attribute parts removed).
"""

from __future__ import annotations

import re

from prompts import ASSESSMENT_SCHEMA


def norm(name: str) -> str:
    """Lowercase, drop plural 's' on words ("Assignments 1" == "Assignment 1"), strip symbols.

    Also treats "A1", "Assignment A1" and "Assignment set A1" as "Assignment 1".
    """
    s = name.lower()
    s = re.sub(r"\bassignments?\s*(?:set\s*)?a\s?(\d+)\b", r"assignment \1", s)
    s = re.sub(r"\ba\s?(\d+)\b", r"assignment \1", s)
    words = re.findall(r"[a-z]+|[0-9]+", s)
    words = [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words]
    return "".join(words)


def match_assessment(key_item: dict, predicted: list[dict], used: set | None = None) -> dict | None:
    """Find the predicted assessment that best matches the key item.

    Each predicted item is used at most once (pass the same `used` set for a
    whole key). Exact name matches win over partial ones, and among several
    candidates the one with the same due date wins. So eight rows all named
    "Assignments" are matched to Assignment 1..8 by their dates.
    """
    used = used if used is not None else set()
    free = [p for p in predicted if id(p) not in used]
    names = [norm(n) for n in [key_item["name"], *key_item.get("aliases", [])]]
    stripped = [re.sub(r"[0-9]+$", "", n) for n in names]

    def pick(cands):
        if not cands:
            return None
        same_date = [p for p in cands if p.get("due_date") == key_item.get("due_date")]
        choice = (same_date or cands)[0]
        used.add(id(choice))
        return choice

    exact = [p for p in free if norm(p.get("name", "")) in names]
    if exact:
        return pick(exact)
    partial = [
        p for p in free
        if (pn := norm(p.get("name", "")))
        and any(len(k) > 2 and (k in pn or pn in k) for k in names)
    ]
    if partial:
        return pick(partial)
    # Generic name with no number ("Assignments") for a numbered key item ("Assignment 3")
    generic = [
        p for p in free
        if (pn := norm(p.get("name", ""))) and not re.search(r"[0-9]", pn)
        and any(k and k == pn for k in stripped)
    ]
    return pick(generic)


def score_assessments(parsed: dict, key: dict) -> dict:
    """Compare model output with a hand-made answer key.

    Answer key format: see answer_key.example.json.
    """
    predicted = parsed.get("assessments", []) if isinstance(parsed, dict) else []
    key_items = key.get("assessments", [])

    found = dates_ok = tbd_ok = weights_ok = 0
    rows = []
    used: set = set()
    for item in key_items:
        p = match_assessment(item, predicted, used)
        row = {"key_name": item["name"], "matched": p.get("name") if p else None}
        if p:
            found += 1
            d_ok = p.get("due_date") == item.get("due_date")
            t_ok = bool(p.get("date_tbd")) == bool(item.get("date_tbd"))
            kw, pw = item.get("weight_percent"), p.get("weight_percent")
            w_ok = (kw is None and pw is None) or (
                kw is not None and pw is not None and abs(float(kw) - float(pw)) < 0.01
            )
            dates_ok += d_ok
            tbd_ok += t_ok
            weights_ok += w_ok
            row.update(date_ok=d_ok, tbd_ok=t_ok, weight_ok=w_ok)
        rows.append(row)

    n = len(key_items) or 1
    extra = max(0, len(predicted) - found)
    weight_sum = sum(
        float(p["weight_percent"])
        for p in predicted
        if p.get("weight_percent") is not None and not p.get("is_bonus")
    )
    return {
        "key_assessments": len(key_items),
        "predicted_assessments": len(predicted),
        "found": found,
        "extra_predicted": extra,
        "date_accuracy": round(dates_ok / n, 3),
        "tbd_accuracy": round(tbd_ok / n, 3),
        "weight_accuracy": round(weights_ok / n, 3),
        "predicted_weight_sum": round(weight_sum, 2),
        "per_assessment": rows,
    }


def check_schema(parsed: object) -> list[str]:
    """Light structural check (no jsonschema dependency)."""
    problems = []
    if not isinstance(parsed, dict):
        return ["output is not a JSON object"]
    for field in ASSESSMENT_SCHEMA["required"]:
        if field not in parsed:
            problems.append(f"missing top-level field: {field}")
    for i, a in enumerate(parsed.get("assessments", []) or []):
        for field in ASSESSMENT_SCHEMA["properties"]["assessments"]["items"]["required"]:
            if field not in a:
                problems.append(f"assessment {i}: missing {field}")
        d = a.get("due_date")
        if d is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d)):
            problems.append(f"assessment {i}: due_date not ISO ({d})")
    return problems


def fmt(v) -> str:
    """Show None as '-' in the printed report."""
    return "-" if v is None else str(v)


def print_report(r: dict, key: dict | None) -> None:
    """Show what the model extracted and how it lines up with the answer key."""
    parsed = r.get("parsed_output") or {}
    print(f"  course_code: {fmt(parsed.get('course_code'))}   term: {fmt(parsed.get('term'))}")

    predicted = parsed.get("assessments", []) or []
    print(f"\n  MODEL FOUND ({len(predicted)} items)")
    print(f"  {'name':<34}{'type':<14}{'due_date':<12}{'tbd':<7}{'weight':<8}source_text")
    for p in predicted:
        src = (p.get("source_text") or "").replace("\n", " ")[:60]
        print(
            f"  {fmt(p.get('name'))[:33]:<34}{fmt(p.get('type'))[:13]:<14}"
            f"{fmt(p.get('due_date'))[:11]:<12}{fmt(p.get('date_tbd')):<7}"
            f"{fmt(p.get('weight_percent')):<8}{src}"
        )

    if key:
        print("\n  KEY vs MODEL  (OK = match, XX = wrong, -- = not found)")
        print(f"  {'key item':<26}{'matched as':<26}{'date (key / model)':<28}{'tbd':<6}{'weight (key / model)':<22}")
        matched_ids: set = set()
        for item in key.get("assessments", []):
            p = match_assessment(item, predicted, matched_ids)
            if not p:
                print(f"  {item['name'][:25]:<26}{'--':<26}{fmt(item.get('due_date')):<28}{'--':<6}{fmt(item.get('weight_percent'))}")
                continue
            d_ok = p.get("due_date") == item.get("due_date")
            t_ok = bool(p.get("date_tbd")) == bool(item.get("date_tbd"))
            kw, pw = item.get("weight_percent"), p.get("weight_percent")
            w_ok = (kw is None and pw is None) or (
                kw is not None and pw is not None and abs(float(kw) - float(pw)) < 0.01
            )
            mark = lambda ok: "OK" if ok else "XX"
            dates = f"{mark(d_ok)} {fmt(item.get('due_date'))} / {fmt(p.get('due_date'))}"
            weights = f"{mark(w_ok)} {fmt(kw)} / {fmt(pw)}"
            print(f"  {item['name'][:25]:<26}{fmt(p.get('name'))[:25]:<26}{dates[:27]:<28}{mark(t_ok):<6}{weights}")
        extras = [p for p in predicted if id(p) not in matched_ids]
        if extras:
            print(f"\n  EXTRA (model found, not in key): " + ", ".join(fmt(p.get("name")) for p in extras))

    missing = parsed.get("missing_fields") or []
    if missing:
        print(f"\n  model says missing: {', '.join(missing)}")
