# -*- coding: utf-8 -*-
"""Pilot candidate C: does the DOI in a CITATION.cff resolve, and does it name that software?

THE QUESTION IS CORRECTNESS, NOT ADOPTION. The nearest published work, "Good practice versus
reality: A landscape analysis of Research Software metadata adoption in European Open Science
Clusters" (MSR 2025), measures whether projects have the metadata. This asks whether the metadata
they have points at the right thing.

WHAT COULD MAKE IT A PAPER. GitHub renders a "Cite this repository" button from CITATION.cff and a
reader copies what it produces. Nothing checks that the `doi` field resolves, that it names this
software rather than a paper about it, or that the authors in the file are the authors on the
record. A citation that resolves to the wrong object is worse than a missing one, because it looks
finished.

THIS PILOT IS ABOUT THE EFFECT AND NOT THE CORPUS. GitHub's code search is an index rather than a
census and caps at a thousand results, so it cannot be the denominator in a paper. It is good enough
to answer whether anything is wrong at all: if these files are clean, no corpus is worth building.
"""
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
HDR = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
       "User-Agent": "paper36-pilot"}
MAIL = "emil.huseynov.zabil@bsu.edu.az"


def gh(path, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request("https://api.github.com" + path, headers=HDR),
                    timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(12 * (i + 1))
                continue
            return {"__error__": e.code}
        except Exception:
            time.sleep(5 * (i + 1))
    return {"__error__": "unreachable"}


def crossref(doi, tries=4):
    u = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    for i in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers={"User-Agent": "p36 (mailto:%s)" % MAIL}),
                    timeout=35) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return "__unreachable__"


def datacite(doi, tries=3):
    u = "https://api.datacite.org/dois/" + urllib.parse.quote(doi)
    for i in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers={"User-Agent": "p36 (mailto:%s)" % MAIL}),
                    timeout=35) as r:
                return json.load(r)["data"]["attributes"]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return "__unreachable__"


# collect candidate repositories from the code search index, several pages
repos = []
for page in range(1, 6):
    r = subprocess.run(["gh", "api",
                        "/search/code?q=filename:CITATION.cff+doi&per_page=50&page=%d" % page],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        break
    for it in json.loads(r.stdout).get("items", []):
        if it["path"].lower().endswith("citation.cff"):
            repos.append((it["repository"]["full_name"], it["path"]))
    time.sleep(3)
repos = list(dict.fromkeys(repos))
print("candidate files from the code search index: %d" % len(repos))
print()

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s'\"<>,)\]]+")
stats = Counter()
rows = []

for full, path in repos[:70]:
    d = gh("/repos/%s/contents/%s" % (full, urllib.parse.quote(path)))
    if "__error__" in d or "content" not in d:
        stats["unreadable"] += 1
        continue
    import base64
    try:
        text = base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:
        stats["unreadable"] += 1
        continue

    title = None
    mt = re.search(r"^title:\s*(.+)$", text, re.M)
    if mt:
        title = mt.group(1).strip().strip("'\"")
    # the file's own doi field, and any doi inside preferred-citation
    top = re.search(r"^doi:\s*['\"]?(10\.[^\s'\"]+)", text, re.M)
    pref = "preferred-citation" in text
    dois = DOI_RE.findall(text)
    stats["files read"] += 1
    if not dois:
        stats["no DOI anywhere"] += 1
        continue
    stats["has at least one DOI"] += 1
    if top:
        stats["has a top-level doi field"] += 1
    if pref:
        stats["has preferred-citation"] += 1

    doi = (top.group(1) if top else dois[0]).rstrip(".,;")
    rec = crossref(doi)
    src = "crossref"
    if rec is None:
        rec = datacite(doi)
        src = "datacite"
    if rec == "__unreachable__":
        stats["registry unreachable"] += 1
        continue
    if rec is None:
        stats["DOI DOES NOT RESOLVE"] += 1
        rows.append((full, doi, "does not resolve", title, None))
        continue

    if src == "crossref":
        rtitle = (rec.get("title") or [""])[0]
        rtype = rec.get("type", "")
    else:
        t = rec.get("titles") or [{}]
        rtitle = t[0].get("title", "")
        rtype = (rec.get("types") or {}).get("resourceTypeGeneral", "")
    stats["resolves (%s)" % src] += 1
    stats["resolved type: %s" % (rtype or "unknown")] += 1

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())
    match = bool(title) and bool(rtitle) and (norm(title) in norm(rtitle)
                                              or norm(rtitle) in norm(title))
    if not match:
        stats["TITLE DISAGREES with the record"] += 1
    rows.append((full, doi, "%s / %s" % (src, rtype), title, rtitle))
    time.sleep(1.1)

print("PILOT RESULT")
for k, v in stats.most_common():
    print("   %-40s %4d" % (k, v))
print()
print("EXAMPLES WHERE THE FILE AND THE RECORD DISAGREE")
shown = 0
for full, doi, state, title, rtitle in rows:
    if state == "does not resolve" or (rtitle is not None and title and
                                       re.sub(r"[^a-z0-9]", "", title.lower())
                                       not in re.sub(r"[^a-z0-9]", "", rtitle.lower())
                                       and re.sub(r"[^a-z0-9]", "", rtitle.lower())
                                       not in re.sub(r"[^a-z0-9]", "", title.lower())):
        print("   %-34s %s" % (full[:34], doi[:44]))
        print("      cff says   : %s" % (title or "(no title)")[:74])
        print("      record says: %s" % (rtitle or state)[:74])
        shown += 1
        if shown >= 10:
            break
