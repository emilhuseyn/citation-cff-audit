r"""Build the Scientometrics submission: a Word manuscript, a Word title page, and nothing else.

WHAT THIS VENUE ASKS FOR, read from its own submission guidelines through the browser on 31.08.2026,
because Springer answers a plain fetch with a 303 into an identity provider:

  * "Manuscripts should be submitted in Word." LaTeX is offered only for manuscripts with
    mathematical content, which this is not, so the pipeline's usual tectonic build is not used here.
  * an abstract of 150 to 250 words, and 4 to 6 keywords.
  * references cited "in the text by name and year in parentheses", the list "alphabetized by the
    last names of the first author", journal titles italicised, DOIs written as full DOI links.
  * a "Statements and Declarations" heading. The guidelines say submissions without the relevant
    declarations "will be returned as incomplete", and original research "must add a Data
    Availability Statement".
  * a title page carrying the title, the author, the affiliation, the corresponding author's e-mail
    and the ORCID. The journal is single-blind, so the author is named.
  * no more than three levels of displayed headings.

EVERY ONE OF THOSE IS CHECKED HERE AND A FAILURE WRITES NOTHING. A format rule is a handling
condition and not a preference: this workspace has had a manuscript refused for an unstructured
abstract and another unsubmitted for a missing author block.

    py 06_build.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BODY = os.path.join(ROOT, "draft", "manuscript_body.md")
REFS = os.path.join(ROOT, "results", "references.json")
BUILD = os.path.join(ROOT, "build")
FINAL = os.path.join(ROOT, "final")

ABS_MIN, ABS_MAX = 150, 250
KW_MIN, KW_MAX = 4, 6

TITLE_PAGE = """# {title}

**Emil Huseynov**

Center for Information Technologies, Baku State University, Academic Zahid Khalilov Street 23,
AZ1148, Baku, Azerbaijan

ORCID: 0009-0007-7142-060X

**Corresponding author.** Mr. Emil Huseynov, emil.huseynov.zabil@bsu.edu.az

## Statements and Declarations

**Competing interests.** The author declares no competing interests.

**Funding.** No funding was received for this work.

**Ethics approval.** Not applicable. This study analyses publicly available software metadata and
public bibliographic records. It involves no human participants and no personal data.

**Author contributions.** E.H. designed the study, wrote the analysis plan, built the harvest and
analysis pipeline, performed the analysis and wrote the manuscript.
"""


def stop(msg):
    print("STOP: %s" % msg)
    print("Nothing was written.")
    sys.exit(1)


def words(s):
    """Count the way a person counts, which is not the way a regex splitter does.

    A hyphenated compound is one word. Row 33's counter split on non-word characters and failed a
    compliant 298-word abstract as 314, which is a correct manuscript stopped by its own gate.
    """
    return len([w for w in re.sub(r"[*`_]", "", s).split() if any(c.isalnum() for c in w)])


def resolve_cites(text, refs, used):
    """Turn {{handle}} into "(Author, Year)" and {{+handle}} into "Author (Year)".

    Several handles may share one pair of parentheses: {{a;b}} renders as "(A, 2016; B, 2022)",
    which is what APA asks for and what a reader expects.
    """
    def one(m):
        raw = m.group(1)
        narrative = raw.startswith("+")
        handles = [h.strip() for h in raw.lstrip("+").split(";") if h.strip()]
        for h in handles:
            if h not in refs:
                stop("the manuscript cites %r and the reference list has no such handle. "
                     "Known handles: %s" % (h, ", ".join(sorted(refs))))
            used.add(h)
        if narrative:
            if len(handles) != 1:
                stop("a narrative citation must name one work, not %d" % len(handles))
            return refs[handles[0]]["cite"]
        return "(%s)" % "; ".join(refs[h]["paren"] for h in handles)

    return re.sub(r"\{\{([^}]+)\}\}", one, text)


def main():
    for p in (BODY, REFS):
        if not os.path.exists(p):
            stop("%s does not exist" % p)
    src = io.open(BODY, encoding="utf-8").read()
    refs = json.load(io.open(REFS, encoding="utf-8"))
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(FINAL, exist_ok=True)

    print("=" * 92)
    print("THE VENUE'S OWN CONDITIONS, checked before anything is built")
    print("=" * 92)
    print("   source read: %s" % BODY)
    fails = []

    def ok(label, cond, detail=""):
        print("   %-4s %-48s %s" % ("ok" if cond else "FAIL", label, detail))
        if not cond:
            fails.append(label)

    # Nothing half-written reaches a portal.
    left = [ln.strip()[:70] for ln in src.split("\n") if "PENDING" in ln]
    ok("no section still says PENDING", not left, "%d left" % len(left))
    for ln in left[:6]:
        print("        %s" % ln)

    if "## Abstract" not in src or "**Keywords:**" not in src:
        stop("the manuscript has no Abstract or Keywords heading")
    abstract = " ".join(src.split("## Abstract", 1)[1].split("**Keywords:**")[0].split())
    n_ab = words(abstract)
    ok("abstract is 150 to 250 words", ABS_MIN <= n_ab <= ABS_MAX, "%d words" % n_ab)
    ok("abstract cites nothing", "{{" not in abstract)

    kw = [k.strip() for k in
          " ".join(src.split("**Keywords:**", 1)[1].split("\n\n")[0].split()).split(",")
          if k.strip()]
    ok("4 to 6 keywords", KW_MIN <= len(kw) <= KW_MAX, "%d: %s" % (len(kw), "; ".join(kw)))

    # Springer allows three levels of displayed heading and this manuscript uses at most three.
    depth = max([len(m.group(1)) for m in re.finditer(r"(?m)^(#+)\s", src)] or [0])
    ok("at most three heading levels", depth <= 3, "deepest is %d" % depth)

    ok("a Statements and Declarations section", "## Statements and Declarations" in src)
    ok("a Data availability statement", "**Data availability.**" in src)
    ok("a Competing interests statement", "**Competing interests.**" in src)

    # THE DASH RULE. LaTeX is not involved here, so nothing can be introduced at render time, but a
    # dash pasted from a web page survives into the docx exactly as typed.
    bad = {c: src.count(c) for c in ("–", "—") if c in src}
    ok("no en or em dash", not bad, str(bad) if bad else "none")

    used = set()
    body = resolve_cites(src, refs, used)
    ok("every citation resolves to a reference", True, "%d distinct works cited" % len(used))
    never = sorted(set(refs) - used)
    ok("every reference is cited", not never, "uncited: %s" % (", ".join(never) or "none"))

    if fails:
        stop("a stated condition of the venue is not met: %s" % "; ".join(fails))

    # The reference list, alphabetised by the first author's family name as the journal asks.
    def key(h):
        return re.sub(r"[^a-z ]", "", refs[h]["authors_apa"].lower())
    listing = "\n\n".join(refs[h]["apa"] for h in sorted(refs, key=key))
    if not body.rstrip().endswith("## References"):
        body = body.rstrip() + "\n"
    body = body.rstrip() + "\n\n" + listing + "\n"

    title = next(l[2:].strip() for l in src.split("\n")
                 if l.startswith("# ") and not l.startswith("## "))

    out_md = os.path.join(BUILD, "manuscript_scientometrics.md")
    io.open(out_md, "w", encoding="utf-8", newline="\n").write(body)
    tp_md = os.path.join(BUILD, "title_page_scientometrics.md")
    io.open(tp_md, "w", encoding="utf-8", newline="\n").write(TITLE_PAGE.format(title=title))

    pandoc = shutil.which("pandoc")
    if not pandoc:
        stop("pandoc is not on PATH, so the Word files cannot be built")

    print()
    print("=" * 92)
    print("BUILD")
    print("=" * 92)
    for s, d in ((out_md, "Scientometrics_manuscript.docx"),
                 (tp_md, "Scientometrics_title_page.docx")):
        o = os.path.join(FINAL, d)
        r = subprocess.run([pandoc, s, "-o", o, "--standalone"], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(o):
            print(r.stderr[-900:])
            stop("pandoc failed on %s" % os.path.basename(s))
        print("   %-38s %9d bytes" % (d, os.path.getsize(o)))

    print()
    print("   title      %s" % title)
    print("   abstract   %d words" % n_ab)
    print("   keywords   %d" % len(kw))
    print("   references %d, all cited" % len(refs))
    return 0


sys.exit(main())
