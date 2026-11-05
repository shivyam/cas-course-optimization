"""Fixed rules applied in code after the model (--postprocess), and the weight check.

Copied unchanged from the #38 Gemma spike. The same rules run for every model.
"""

from __future__ import annotations

import re

from scoring import norm

RECURRING_WORDS = ("lab", "tutorial", "participation", "attendance", "floating", "milestone", "survey")
COUNT_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
               "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def is_iso(d) -> bool:
    """True for a date written as YYYY-MM-DD."""
    return isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) is not None


def is_recurring(name: str, typ: str | None = None) -> bool:
    """True for items that repeat through the term (labs, tutorials, participation...).
    These have no single due date, so they are never marked TBD.
    """
    n = (name or "").lower()
    return typ in ("lab", "participation") or any(w in n for w in RECURRING_WORDS)


def is_test_like(name: str, typ: str | None = None) -> bool:
    """True for tests, exams, midterms and quizzes (by type, or by name if the type is wrong)."""
    n = (name or "").lower()
    return typ in ("midterm", "final_exam", "quiz") or any(w in n for w in ("test", "exam", "midterm", "quiz"))


def base_name(name: str) -> str:
    """Strip counts and numbers from a group name so its items can be named and grouped:
    'Five Assignments' / 'Individual Assignments (4)' / 'Assignment 3' -> 'Assignment'.
    """
    n = re.sub(r"\(\s*\d+\s*\)", "", name or "")
    n = re.sub(r"^\s*(?:\d+|" + "|".join(COUNT_WORDS) + r")\s+", "", n, flags=re.IGNORECASE)
    n = re.sub(r"\s*\d+\s*$", "", n).strip()
    words = n.split()
    if words and len(words[-1]) > 3 and words[-1].lower().endswith("s") and not words[-1].lower().endswith("ss"):
        words[-1] = words[-1][:-1]
    return " ".join(words) or (name or "Item")


def postprocess(parsed: dict) -> dict:
    """Fixed rules applied in code after the model (--postprocess). Same for every model.

    1. Split group rows ('Five Assignments 15%') into one row per item, weight split equally.
    2. If rows repeat a group weight and that pushes the total over 100%, divide it.
    3. Clean dates: non-ISO dates become null; undated tests and exams are TBD;
       recurring and bonus items are never TBD.
    """
    rows = list(parsed.get("assessments", []) or [])
    # 1. Split group rows like "Five Assignments 15%" or "Individual Assignments (4)"
    out = []
    for r in rows:
        nm = r.get("name") or ""
        m = re.match(r"^\s*(\d+|" + "|".join(COUNT_WORDS) + r")\s+\S", nm, re.IGNORECASE)
        m2 = re.search(r"\(\s*(\d+)\s*\)", nm)
        n = int(m.group(1)) if m and m.group(1).isdigit() else COUNT_WORDS.get(m.group(1).lower(), 0) if m else 0
        n = n or (int(m2.group(1)) if m2 else 0)
        if n > 1 and not is_recurring(nm, r.get("type")):
            base, w = base_name(nm), r.get("weight_percent")
            for k in range(n):
                out.append({**r, "name": f"{base} {k + 1}", "due_date": None, "date_tbd": True,
                            "weight_percent": round(w / n, 4) if w is not None else None})
        else:
            out.append(r)
    rows = out
    # 2. Rows that repeat a group weight ("Assignments 1..4" each 10%) when that pushes the total over 100
    total = sum(float(r["weight_percent"]) for r in rows if r.get("weight_percent") is not None and not r.get("is_bonus"))
    groups: dict[tuple, list] = {}
    for r in rows:
        if r.get("weight_percent") is not None and not r.get("is_bonus"):
            groups.setdefault((norm(base_name(r.get("name", ""))), float(r["weight_percent"])), []).append(r)
    for (_, w), grp in groups.items():
        k = len(grp)
        if k > 1 and total > 100.5 and abs(total - w * k + w - 100) < 0.5:
            for r in grp:
                r["weight_percent"] = round(w / k, 4)
            total = total - w * k + w
    # 3. Dates: non-ISO -> null; undated tests/exams are TBD; recurring items are not
    for r in rows:
        if not is_iso(r.get("due_date")):
            r["due_date"] = None
        if r["due_date"] is None:
            if is_recurring(r.get("name"), r.get("type")) or r.get("is_bonus"):
                r["date_tbd"] = False
            elif is_test_like(r.get("name"), r.get("type")):
                r["date_tbd"] = True
    parsed["assessments"] = rows
    return parsed


def weight_warnings(parsed: dict | None) -> list[str]:
    """Warn when the graded weights (bonus marks left out) do not add up to 100%."""
    if not parsed:
        return []
    rows = parsed.get("assessments", []) or []
    total = sum(float(r["weight_percent"]) for r in rows if r.get("weight_percent") is not None and not r.get("is_bonus"))
    return [] if abs(total - 100) < 0.5 else [f"weights sum to {round(total, 2)}%, not 100%"]
