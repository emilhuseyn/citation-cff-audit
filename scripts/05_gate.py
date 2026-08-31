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
    "1", "2", "3", "4", "5", "6", "7",           # list positions in the contributions
    "2016", "2018", "2021", "2022", "2023", "2024", "2025", "2026",  # years in citations
    "0",
    "200", "404",                                # HTTP status codes, named as protocol constants
}

FAILS = []


def ok(label, cond, detail=""):
    print("   %-4s %-56s %s" % ("ok" if cond else "FAIL", label, detail))
    if not cond:
        FAILS.append(label)


def numbers(text):
    """Every numeric token that is a claim, with its context, so a failure can be located by eye.

    TWO KINDS OF NUMBER ARE NOT CLAIMS AND ARE REMOVED BEFORE THE SCAN RATHER THAN EXEMPTED ONE BY
    ONE. A heading's own number, "### 4.6", is structure. A number inside backticks is a literal
    being quoted, and every DOI in this manuscript is written that way, so "10.5281/zenodo.1234" is
    the string under discussion rather than a measurement of anything.

    Removing them by their form keeps the list of hand-written exemptions short, which matters: each
    entry on that list is a number the gate will never question again.
    """
    lines = [ln for ln in text.split("\n") if not ln.lstrip().startswith("#")]
    stripped = re.sub(r"`[^`]*`", " ", "\n".join(lines))
    out = []
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?![\w])", stripped):
        raw = m.group(1)
        ctx = " ".join(stripped[max(0, m.start() - 60):m.end() + 40].split())
        out.append((raw, ctx))
    return out


# THE DENOMINATORS THIS STUDY IS ALLOWED TO DIVIDE BY. Without this list the percentage check was
# vacuous and its self-test proved it: building every a/b ratio from every pair of stored integers
# produces well over a thousand values, which covers almost any one-decimal number between 0 and 100,
# so changing a stated 99.3 percent to 91.4 percent passed. A percentage is now allowed only if its
# denominator is one of the sets this paper actually reports over.
DENOMINATORS = ("joss_papers", "repos_probed", "repos_with_cff", "files_with_top_doi",
                "files_without_doi", "names_paper", "names_software",
                "title_mismatches", "title_names_different_thing")
# The pilot has its own denominators, carried into measures.json from the frozen plan and verified
# against it there. The manuscript compares the two populations, so both sets have to be divisible.
PILOT_DENOMINATORS = ("files", "with_doi", "resolving")


def derived(meas):
    """Every value the analysis produced, plus the percentages the manuscript may quote.

    A percentage is not stored in measures.json, it is computed from two stored counts, so the
    manuscript is allowed to print one only if it is a ratio of a stored count to one of the declared
    denominators above. Both one-decimal and integer roundings are accepted, and the value is rounded
    once, from the stored counts, never from an already rounded figure.
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
    bases = [meas.get(k) for k in DENOMINATORS if isinstance(meas.get(k), int) and meas.get(k)]
    bases += [v for k, v in (meas.get("resolution") or {}).items() if isinstance(v, int) and v]
    pilot = meas.get("pilot") or {}
    bases += [pilot[k] for k in PILOT_DENOMINATORS if isinstance(pilot.get(k), int) and pilot[k]]
    for a in ints:
        for b in bases:
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

    # A PERCENTAGE IS HELD TO A MUCH SHORTER LIST THAN A COUNT, and the reason is that the general
    # rule above is loose by construction: any stored count over any declared denominator is
    # accepted, which is several hundred values and covers most of the range. The self-test caught
    # that directly, passing a stated 99.3 percent changed to 91.4. Every percentage this paper
    # quotes is a ratio it names in the same breath, so the legitimate ones are enumerated as pairs
    # and computed from the data rather than inferred from a cross product.
    res = meas.get("resolution") or {}
    pl = meas.get("pilot") or {}
    RATIOS = [
        (meas.get("repos_with_cff"), meas.get("repos_probed")),
        (meas.get("files_with_top_doi"), meas.get("repos_with_cff")),
        (meas.get("files_without_doi"), meas.get("repos_with_cff")),
        (res.get("ok"), meas.get("files_with_top_doi")),
        (res.get("missing"), meas.get("files_with_top_doi")),
        (meas.get("names_software"), res.get("ok")),
        (meas.get("names_paper"), res.get("ok")),
        (meas.get("joss_doi_in_top_field"), meas.get("files_with_top_doi")),
        (meas.get("uses_preferred_citation"), meas.get("repos_with_cff")),
        (meas.get("title_mismatches"), res.get("ok")),
        (pl.get("unresolved"), pl.get("with_doi")),
        (pl.get("names_paper"), pl.get("resolving")),
        (pl.get("names_software"), pl.get("resolving")),
    ]
    pct_allowed = set()
    for a, b in RATIOS:
        if a is not None and b:
            pct_allowed.add("%.1f" % (100.0 * a / b))
            pct_allowed.add("%d" % round(100.0 * a / b))
    stray = []
    for m in re.finditer(r"(?<![\w.])(\d+(?:\.\d+)?)\s+percent", prose):
        if m.group(1) not in pct_allowed:
            stray.append((m.group(1), " ".join(prose[max(0, m.start() - 70):m.end()].split())))
    ok("every stated percentage is a ratio this study computes", not stray,
       "%d stray, %d legitimate values" % (len(stray), len(pct_allowed)))
    for raw, ctx in stray[:10]:
        print("        %-8s ...%s" % (raw, ctx[-92:]))

    print()
    print("=" * 92)
    print("THE CLAIMS THE PLAN COMMITTED TO")
    print("=" * 92)
    ok("the pilot is compared rather than replaced", "pilot" in src.lower())
    def stated(v):
        """The manuscript writes thousands with a comma, so both renderings count as stating it."""
        return v is not None and (str(v) in src or "{:,}".format(v) in src)

    ok("the denominator of the census is stated", stated(meas.get("joss_papers")))
    ok("repositories without a GitHub URL are counted", stated(stamp.get("papers_without_github")))
    ok("files declaring no DOI are counted", stated(meas.get("files_without_doi")))
    ok("the repositories actually probed are stated", stated(meas.get("repos_probed")))
    ok("the files carrying a citation file are stated", stated(meas.get("repos_with_cff")))
    # THE HEADLINE RATES ARE RECOMPUTED HERE FROM THE DATA AND REQUIRED IN THE TEXT. This is not the
    # gate holding its own copy of the answers: each expected value is divided out of measures.json
    # at run time, so a change in the data changes what the gate demands. The general scan above
    # says no number is unaccounted for; this says the specific numbers the paper is about are the
    # ones the data produces.
    res = meas.get("resolution") or {}
    HEADLINE = [
        ("the share of repositories carrying a file",
         meas.get("repos_with_cff"), meas.get("repos_probed")),
        ("the share of declared identifiers that resolve",
         res.get("ok"), meas.get("files_with_top_doi")),
        ("the share of resolving identifiers naming software",
         meas.get("names_software"), res.get("ok")),
        ("the share of resolving identifiers naming a paper",
         meas.get("names_paper"), res.get("ok")),
        ("the share putting the paper in the software's field",
         meas.get("joss_doi_in_top_field"), meas.get("files_with_top_doi")),
        ("the share using preferred-citation",
         meas.get("uses_preferred_citation"), meas.get("repos_with_cff")),
        ("the share of resolving identifiers whose title disagrees",
         meas.get("title_mismatches"), res.get("ok")),
    ]
    for label, a, b in HEADLINE:
        want = "%.1f" % (100.0 * a / b) if a is not None and b else None
        ok(label, bool(want) and want in src, "%s percent" % want)

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
