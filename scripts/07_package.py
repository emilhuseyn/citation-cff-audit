r"""Stage the replication package, run it, and refuse to ship it if it does not reproduce the paper.

WHAT GOES IN. The frozen analysis plan with its amendment, both pilots including the one that killed
a topic, every cached GitHub answer and every cached registry answer, the analysis and gate scripts,
and the computed results. About 19 megabytes, small enough to publish whole.

WHAT STAYS OUT, and it is checked rather than assumed. Nothing outside this paper's directory is
copied, so no credential can reach the package, and the check below refuses to stage a path whose
name suggests one anyway. The manuscript stays out: the package is the evidence for the paper, not a
second copy of it.

THE PACKAGE IS RUN BEFORE IT IS PUBLISHED. `03_analyse.py` is executed against the staged copy, with
no network, and its output is compared field by field against `results/measures.json`. A package that
does not reproduce the paper is not a replication package, and the only way to know is to run it.

    py 07_package.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STAGE = os.path.join(ROOT, "build", "replication")

ITEMS = [("analysis_plan.md", "analysis_plan.md"),
         ("research", "research"),
         ("scripts", "scripts"),
         ("results/measures.json", "results/measures.json"),
         ("results/references.json", "results/references.json")]

# WHAT MUST NOT BE PUBLISHED, checked two ways, and the first version of this check was wrong in the
# direction that matters least but still matters. It tested those words as substrings of the whole
# staged path, and the corpus is full of repositories legitimately named for them: profileR,
# LikelihoodProfiler.jl, WordTokenizers.jl, taxprofiler. Thirteen real data files were refused as
# credentials. A filter that drops records the manuscript never mentions is the defect that cost this
# workspace a rejection once already, so it is made exact rather than relaxed.
#
# The path test now looks at the BASENAME against names a credential actually has. The content test
# is the one that would catch a secret pasted anywhere, and it is the real guard.
FORBIDDEN_NAMES = ("credentials.md", "credentials.json", ".env", "cookies.json", "cookies.sqlite",
                   "id_rsa", "id_ed25519", "author_profile.md")
FORBIDDEN_SUFFIX = (".pem", ".key", ".pfx", ".p12", ".keystore")
# Markers of a secret in a file's text, matched case-insensitively against staged text files.
#
# THEY ARE BUILT FROM PIECES SO THIS FILE PASSES ITS OWN SCAN. Written as literals, the list matched
# the script that holds it, and the obvious repair is to exempt this file by name. That would be a
# hole: the one file guaranteed never to be checked is the one an editor is most likely to paste a
# token into while debugging. Assembling each marker at import time keeps the scanner scannable.
_G = "gh"
SECRET_MARKERS = (_G + "p_", "github" + "_pat_", _G + "o_", _G + "s_",
                  "-----" + "begin ", "authorization: " + "bearer",
                  "aws_secret" + "_access_key", "private" + "_key", "client" + "_secret")

# Fields that are a property of the run rather than of the data. Everything else must match exactly.
VOLATILE = {"analysed_utc"}

README = """# Replication package

*What a "Cite this repository" button certifies: an audit of citation metadata in peer-reviewed
research software*

Emil Huseynov, Baku State University. `emil.huseynov.zabil@bsu.edu.az`

Every number in the paper recomputes from the cached responses in this repository, offline.

## What is here

    analysis_plan.md            frozen before the confirmatory harvest. Amendment 1 records why the
                                corpus is the Journal of Open Source Software and what Zenodo and
                                GitHub code search failed to provide
    research/joss_published.json  the journal's own list of every accepted paper, as served
    research/harvest_stamp.json   the harvest instant and the counts it produced
    research/cff/               one file per repository: the CITATION.cff as GitHub served it, or
                                the status GitHub returned instead
    research/doi/               one file per distinct identifier: what Crossref or DataCite
                                returned, stored as published
    scripts/00_pilot.py         the pilot that made this topic worth taking
    scripts/00_pilot_badges_killed.py  the pilot that killed the previous candidate, included
                                because a negative result that changed the plan is part of the record
    scripts/01_harvest.py       re-fetches the census and the files. This will NOT reproduce the
                                paper: GitHub is live and repositories change
    scripts/02_resolve.py       re-resolves the identifiers. Also live, and resumable
    scripts/03_analyse.py       every number, from the cache, with no network access
    scripts/04_refs.py          resolves the reference list at Crossref by title, verifying the
                                title and the year, and renders it in APA 7
    scripts/05_gate.py          reads every number in the manuscript and requires each to be
                                accounted for by a measurement
    scripts/06_build.py         builds the Word files and checks the venue's stated conditions
    results/measures.json       every number the paper states
    results/references.json     the reference list as resolved

## Reproducing

    py scripts/03_analyse.py

Reads `research/`, rewrites `results/measures.json`, makes no network request. The file it produces
is the one published here.

## Two things the analysis does deliberately

**No YAML parser.** These files are hand-written and some are not valid YAML. A parser would raise on
exactly those, and they are the population most likely to contain the defects being measured, so
excluding them would bias the result through the instrument. The fields are read textually.

**The instrument is reported before the title finding.** Comparing titles with no cleaning gives 86
disagreements; one is an HTML entity and seven are records carrying a version string the file does
not. The reported number is 78, and the three counts are printed together so the correction can be
checked rather than trusted.

## Licence

The code is available for reuse. The cached files are GitHub's, Crossref's, DataCite's and the
journal's own published metadata, redistributed unmodified so the analysis can be checked.
"""


def staged():
    out = []
    for src, dst in ITEMS:
        p = os.path.join(ROOT, src.replace("/", os.sep))
        if not os.path.exists(p):
            raise SystemExit("STOP: %s is named in the package and does not exist" % src)
        if os.path.isdir(p):
            for base, _, files in os.walk(p):
                if "__pycache__" in base:
                    continue
                for f in sorted(files):
                    if f.endswith((".pyc", ".pyo", ".log")):
                        continue
                    full = os.path.join(base, f)
                    out.append((full, dst + "/" + os.path.relpath(full, p).replace(os.sep, "/")))
        else:
            out.append((p, dst))
    return out


def walk_package():
    for b, dirs, fs in os.walk(STAGE):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in fs:
            yield os.path.join(b, f)


def main():
    files = staged()
    bad = [d for _, d in files
           if os.path.basename(d).lower() in FORBIDDEN_NAMES
           or d.lower().endswith(FORBIDDEN_SUFFIX)]
    if bad:
        raise SystemExit("STOP: these would be published and must not be:\n   "
                         + "\n   ".join(bad))

    # THE CONTENT SCAN IS THE REAL GUARD. A secret that reaches the package will not announce itself
    # in the file name; it will be pasted into a script. Every staged text file is read and refused
    # if it carries a credential marker, and a file that cannot be decoded is reported rather than
    # skipped silently, because an unreadable file is not a safe one.
    leaked, unreadable = [], []
    for full, rel in files:
        if os.path.getsize(full) > 4_000_000:
            continue
        try:
            body = io.open(full, encoding="utf-8", errors="strict").read().lower()
        except (UnicodeDecodeError, OSError):
            unreadable.append(rel)
            continue
        for mark in SECRET_MARKERS:
            if mark in body:
                leaked.append("%s carries %r" % (rel, mark))
    if leaked:
        raise SystemExit("STOP: a credential marker is inside a staged file:\n   "
                         + "\n   ".join(leaked))
    print("scanned %d staged files for credential markers; %d could not be decoded and are named: %s"
          % (len(files), len(unreadable), ", ".join(unreadable[:5]) or "none"))

    tmp = tempfile.mkdtemp(prefix="p36_replication_")
    try:
        for full, rel in files:
            dest = os.path.join(tmp, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(full, dest)
        print("staged %d files into a temporary copy" % len(files))
        print("running the staged 03_analyse.py, no network needed")
        r = subprocess.run([sys.executable, os.path.join(tmp, "scripts", "03_analyse.py")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if r.returncode != 0:
            print((r.stderr or "")[-1800:])
            raise SystemExit("STOP: the staged analysis did not run")

        got = json.load(io.open(os.path.join(tmp, "results", "measures.json"), encoding="utf-8"))
        want = json.load(io.open(os.path.join(ROOT, "results", "measures.json"), encoding="utf-8"))
        differ = [k for k in sorted(set(got) | set(want))
                  if k not in VOLATILE
                  and json.dumps(got.get(k), sort_keys=True) != json.dumps(want.get(k),
                                                                          sort_keys=True)]
        if differ:
            for k in differ[:6]:
                print("   %-30s package %r vs paper %r" % (k, got.get(k), want.get(k)))
            raise SystemExit("STOP: the package does not reproduce the paper. Differs on: %s"
                             % ", ".join(differ))
        print("the staged package reproduces results/measures.json field for field")

        # THE STAGED COPY IS TAKEN AFTER THE ANALYSIS HAS RUN IN IT, and running it writes a
        # __pycache__ beside the scripts, so the filter is applied again here: the source-tree
        # filter above does not see the temporary copy, and the first package published from this
        # workspace carried a .pyc for exactly that reason.
        #
        # THE STAGED DIRECTORY BECOMES A GIT WORKING COPY once the package is published, so it is
        # emptied in place rather than deleted. Deleting it took the .git directory with it, and on
        # Windows the removal failed part way through on a read-only object file, which left a
        # half-destroyed repository.
        if os.path.exists(os.path.join(STAGE, ".git")):
            for name in os.listdir(STAGE):
                if name in (".git", ".gitattributes", ".gitignore"):
                    continue
                victim = os.path.join(STAGE, name)
                shutil.rmtree(victim) if os.path.isdir(victim) else os.remove(victim)
        elif os.path.exists(STAGE):
            shutil.rmtree(STAGE)
        os.makedirs(STAGE, exist_ok=True)
        for entry in os.listdir(tmp):
            src_p, dst_p = os.path.join(tmp, entry), os.path.join(STAGE, entry)
            if os.path.isdir(src_p):
                shutil.copytree(src_p, dst_p,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
            else:
                shutil.copy2(src_p, dst_p)
        debris = [os.path.join(b, f) for b, _, fs in os.walk(STAGE) for f in fs
                  if f.endswith((".pyc", ".pyo")) or "__pycache__" in b]
        if debris:
            raise SystemExit("STOP: build debris survived into the staged package: %s" % debris)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    io.open(os.path.join(STAGE, "README.md"), "w", encoding="utf-8", newline="\n").write(README)

    total = sum(os.path.getsize(f) for f in walk_package())
    n = sum(1 for _ in walk_package())
    print()
    print("staged at %s" % STAGE)
    print("   %d files, %.1f MB" % (n, total / 1e6))
    for size, name in sorted(((os.path.getsize(f), os.path.relpath(f, STAGE))
                              for f in walk_package()), reverse=True)[:4]:
        print("   %8.2f MB  %s" % (size / 1e6, name))
        if size > 90e6:
            raise SystemExit("STOP: %s is over GitHub's 100 MB file limit" % name)
    return 0


sys.exit(main())
