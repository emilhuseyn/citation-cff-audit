r"""Resolve every DOI the citation files declare, and cache each answer. Resumable.

WHY THIS IS A SEPARATE STEP. The harvest reads GitHub, this reads Crossref and DataCite, and the two
have different rate limits and different failure modes. Splitting them means a DOI registry having a
bad afternoon does not cost the GitHub half of a corpus that took forty minutes to collect.

WHAT IS ASKED OF EACH DOI. Crossref first, because it carries articles, then DataCite, which carries
most software records. What comes back is stored as published: the title, the type, the container.
Nothing is inferred, and a 404 from both is recorded as a DOI that does not resolve rather than as an
error.

A REGISTRY THAT CANNOT BE REACHED IS NOT A DOI THAT DOES NOT RESOLVE. Those two are recorded
separately, because a network failure counted as a finding would inflate the headline number of this
paper.

    py 02_resolve.py
"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESEARCH = os.path.join(ROOT, "research")
CFFDIR = os.path.join(RESEARCH, "cff")
DOIDIR = os.path.join(RESEARCH, "doi")
MAIL = "emil.huseynov.zabil@bsu.edu.az"
UA = {"User-Agent": "paper36-resolve (mailto:%s)" % MAIL}

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s'\"<>,)\]}]+")


def get(url, tries=4, timeout=35):
    """(payload, 'ok'|'missing'|'unreachable')"""
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                        timeout=timeout) as r:
                return json.load(r), "ok"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "missing"
            last = e
            time.sleep(4 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    return None, "unreachable"


def dois_in(text):
    """Every DOI in the file, and the one the top-level `doi:` key declares if there is one."""
    out = {"all": [], "top": None, "preferred": None}
    if not text:
        return out
    out["all"] = [d.rstrip(".,;)") for d in DOI_RE.findall(text)]
    m = re.search(r"^doi:\s*['\"]?(10\.[^\s'\"]+)", text, re.M)
    if m:
        out["top"] = m.group(1).rstrip(".,;)")
    # a doi indented under preferred-citation
    pc = re.split(r"^preferred-citation:", text, maxsplit=1, flags=re.M)
    if len(pc) == 2:
        m2 = re.search(r"^\s+doi:\s*['\"]?(10\.[^\s'\"]+)", pc[1], re.M)
        if m2:
            out["preferred"] = m2.group(1).rstrip(".,;)")
    return out


def main():
    if not os.path.isdir(CFFDIR):
        raise SystemExit("STOP: no harvest to resolve; run 01_harvest.py first")
    os.makedirs(DOIDIR, exist_ok=True)

    wanted = set()
    files = sorted(f for f in os.listdir(CFFDIR) if f.endswith(".json"))
    for f in files:
        rec = json.load(io.open(os.path.join(CFFDIR, f), encoding="utf-8"))
        d = dois_in(rec.get("cff"))
        wanted.update(d["all"])
    print("citation files cached      : %d" % len(files))
    print("distinct DOIs declared     : %d" % len(wanted))

    todo = [d for d in sorted(wanted)
            if not os.path.exists(os.path.join(DOIDIR, re.sub(r"[^A-Za-z0-9]", "_", d) + ".json"))]
    print("already resolved           : %d" % (len(wanted) - len(todo)))
    print("to resolve                 : %d" % len(todo))
    print()

    counts = {"ok": 0, "missing": 0, "unreachable": 0}
    for i, doi in enumerate(todo, 1):
        path = os.path.join(DOIDIR, re.sub(r"[^A-Za-z0-9]", "_", doi) + ".json")
        rec = {"doi": doi}
        m, st = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))
        if st == "ok":
            msg = m["message"]
            rec.update(source="crossref", state="ok",
                       title=(msg.get("title") or [""])[0],
                       type=msg.get("type", ""),
                       container=(msg.get("container-title") or [""])[0])
        else:
            time.sleep(0.5)
            m2, st2 = get("https://api.datacite.org/dois/" + urllib.parse.quote(doi))
            if st2 == "ok":
                a = m2["data"]["attributes"]
                rec.update(source="datacite", state="ok",
                           title=((a.get("titles") or [{}])[0]).get("title", ""),
                           type=(a.get("types") or {}).get("resourceTypeGeneral", ""),
                           container=((a.get("container") or {}).get("title") or ""))
            elif st == "missing" and st2 == "missing":
                rec.update(source=None, state="missing")
            else:
                rec.update(source=None, state="unreachable")
        counts[rec["state"] if rec["state"] in counts else "unreachable"] += 1
        # AN UNREACHABLE REGISTRY IS NOT CACHED. Writing it would make the next run skip it, and the
        # claim below that a re-run retries them would be false: a network failure would harden into
        # a permanent "does not resolve", which is the headline number of this paper.
        if rec["state"] != "unreachable":
            json.dump(rec, io.open(path, "w", encoding="utf-8"), indent=1)
        if i % 100 == 0 or i == len(todo):
            print("   %5d/%d  ok=%d missing=%d unreachable=%d"
                  % (i, len(todo), counts["ok"], counts["missing"], counts["unreachable"]))
        time.sleep(0.9)

    print()
    print("resolved this run: %s" % counts)
    if counts["unreachable"]:
        print("   NOTE: %d could not be reached. Those are NOT counted as unresolved DOIs;"
              % counts["unreachable"])
        print("   re-run this script and they will be retried, because the cache skips only")
        print("   the ones that got an answer.")
    return 0


sys.exit(main())
