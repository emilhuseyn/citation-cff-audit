r"""Check the manuscript against the data it claims to report. Nothing here trusts the prose.

THE DESIGN, and it is the opposite of the obvious one. A gate that holds its own copy of the expected
numbers checks that the author typed what the author typed. Row 34 had exactly that: a cross-check
whose expected values were hardcoded in its own source, and it passed a reference that had been
corrupted on purpose. So this gate reads **every number in the manuscript** and requires each one to
be accounted for, either by a value in `results/measures.json` or by appearing on a short list of
numbers that are not data at all: section numbers, years, research question numbers.

An unaccounted number is a failure. That is deliberately strict, and it is the point: a number in a
results section that no measurement produced is either a typo or an invention, and neither should
reach a reviewer.

IT ALSO REFUSES A STALE MEASURES FILE. Four checkers in this workspace once reported confidently
about a file that was no longer live, so this one prints the path it read, the timestamp inside it,
and refuses to run if the analysis covers fewer repositories than the harvest cached.

    py 05_gate.py
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BODY = os.path.join(ROOT, "draft", "manuscript_body.md")
MEAS = os.path.join(ROOT, "results", "measures.json")
REFS = os.path.join(ROOT, "results", "references.json")
CFFDIR = os.path.join(ROOT, "research", "cff")
PLAN = os.path.join(ROOT, "analysis_plan.md")

# Numbers that are not measurements. Kept short on purpose: every addition is a hole in the gate.
NOT_DATA = {
    "1", "2", "3", "4", "5", "6", "7",           # section and list numbers
    "2016", "2018", "2021", "2022", "2023", "2024", "2025", "2026",  # years in citations
    "0", "404", "7", "20", "19",                 # HTTP status, APA's author cutoffs
}

FAILS = []


def ok(label, cond, detail=""):
    print("   %-4s %-56s %s" % ("ok" if cond else "FAIL", label, detail))
    if not cond:
        FAILS.append(label)


def numbers(text):
    """Every numeric token, with its surrounding words, so a failure can be located by eye."""
    out = []
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w])", text):
        raw = m.group(1)
        ctx = " ".join(text[max(0, m.start() - 60):m.end() + 40].split())
        out.append((raw, ctx))
    return out


def derived(meas):
    """Every value the analysis produced, plus the percentages the manuscript may quote.

    A percentage is not stored in measures.json, it is computed from two stored counts, so the
    manuscript is allowed to print one only if it is a ratio of two numbers that are actually there.
    Both one-decimal and integer roundings are accepted, and the value is rounded once, from the
    stored counts, never from an already rounded figure.
    """
    vals = set()

    def add(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            vals.add("%g" % v)
            vals.add("{:,}".format(int(v)) if float(v).is_integer() else "%g" % v)

    def walk(o):
        if isinstance(o, dict):
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
        else:
            add(o)

    walk(meas)
    ints = [v for v in _flat(meas) if isinstance(v, int) and not isinstance(v, bool)]
    for a in ints:
        for b in ints:
            if b:
                pct = 100.0 * a / b
                if 0 <= pct <= 100:
                    vals.add("%.1f" % pct)
                    vals.add("%d" % round(pct))
    return vals


def _flat(o):
    if isinstance(o, dict):
        for x in o.values():
            for y in _flat(x):
                yield y
    elif isinstance(o, list):
        for x in o:
            for y in _flat(x):
                yield y
    else:
        yield o


def main():
    for p in (BODY, MEAS, REFS):
        if not os.path.exists(p):
            print("STOP: %s does not exist" % p)
            return 1
    src = io.open(BODY, encoding="utf-8").read()
    meas = json.load(io.open(MEAS, encoding="utf-8"))
    refs = json.load(io.open(REFS, encoding="utf-8"))

    print("=" * 92)
    print("WHAT THIS GATE READ")
    print("=" * 92)
    print("   manuscript  %s" % BODY)
    print("   measures    %s" % MEAS)
    print("   analysed    %s" % meas.get("analysed_utc"))
    print("   harvested   %s" % (meas.get("harvest") or {}).get("harvested_utc"))
    print("   references  %s (%d entries)" % (REFS, len(refs)))
    print()

    print("=" * 92)
    print("IS THE MEASURES FILE THE LIVE ONE")
    print("=" * 92)
    cached = len([f for f in os.listdir(CFFDIR) if f.endswith(".json")]) \
        if os.path.isdir(CFFDIR) else 0
    ok("the analysis covers every cached repository",
       meas.get("repos_probed") == cached,
       "analysed %s, cached %d" % (meas.get("repos_probed"), cached))
    stamp = meas.get("harvest") or {}
    ok("the harvest reports itself complete",
       stamp.get("cached") == stamp.get("distinct_repos") and stamp.get("distinct_repos"),
       "cached %s of %s" % (stamp.get("cached"), stamp.get("distinct_repos")))
    ok("no DOI is still unresolved in the analysis",
       not (meas.get("resolution") or {}).get("not yet resolved"),
       "%s left" % (meas.get("resolution") or {}).get("not yet resolved", 0))

    print()
    print("=" * 92)
    print("EVERY NUMBER IN THE MANUSCRIPT IS ACCOUNTED FOR")
    print("=" * 92)
    allowed = derived(meas) | NOT_DATA
    prose = src.split("## References")[0]
    unaccounted = []
    for raw, ctx in numbers(prose):
        if raw in allowed or raw.replace(",", "") in allowed:
            continue
        unaccounted.append((raw, ctx))
    ok("no number lacks a measurement behind it", not unaccounted,
       "%d unaccounted" % len(unaccounted))
    for raw, ctx in unaccounted[:14]:
        print("        %-10s ...%s..." % (raw, ctx[:96]))

    print()
    print("=" * 92)
    print("THE CLAIMS THE PLAN COMMITTED TO")
    print("=" * 92)
    ok("the pilot is compared rather than replaced", "pilot" in src.lower())
    ok("the denominator of the census is stated", str(meas.get("joss_papers")) in src)
    ok("repositories without a GitHub URL are counted",
       str(stamp.get("papers_without_github", "")) in src)
    ok("files declaring no DOI are counted", str(meas.get("files_without_doi")) in src)
    ok("the population bias is stated as a lower bound", "lower bound" in src)
    ok("the generous title rule is stated as such",
       "generous" in src and "lower bound" in src)

    print()
    print("=" * 92)
    print("SHAPE")
    print("=" * 92)
    ok("nothing still says PENDING", "PENDING" not in src)
    ok("no en or em dash", not any(c in src for c in ("–", "—")))
    cited = set(re.findall(r"\{\{\+?([^}]+)\}\}", src))
    handles = set()
    for c in cited:
        handles.update(h.strip() for h in c.lstrip("+").split(";"))
    ok("every citation names a resolved reference", handles <= set(refs),
       "unknown: %s" % (", ".join(sorted(handles - set(refs))) or "none"))
    ok("every resolved reference is cited", set(refs) <= handles,
       "uncited: %s" % (", ".join(sorted(set(refs) - handles)) or "none"))
    ok("the frozen plan is present and amended in place", os.path.exists(PLAN)
       and "Amendment 1" in io.open(PLAN, encoding="utf-8").read())

    print()
    if FAILS:
        print("FAILED %d check(s): %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("all checks pass")
    return 0


sys.exit(main())
