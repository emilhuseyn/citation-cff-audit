r"""Cache the JOSS census and every CITATION.cff behind it. Reads only, and resumable.

THE CORPUS IS A CENSUS, which is the whole reason it is JOSS. `published.json` pages through every
accepted paper, and each record carries the paper's DOI, its title and its `software_repository`.
Zenodo was tried first and cannot be walked: a structural query for a GitHub repository returns zero,
free text returns an incomplete 4,167, and deep paging fails with HTTP 400. Amendment 1 records it.

WHAT IS FETCHED PER REPOSITORY: one call to GitHub's contents API for `CITATION.cff`. Nothing is
cloned, no other file is read, and a 404 is a finding rather than an error, because a repository
without the file is part of the denominator.

RESUMABLE BY DESIGN. Each repository's answer is written to its own file under `research/cff/`, and a
re-run skips what is already there. GitHub allows 5,000 authenticated calls an hour and the corpus is
about 3,700, so this fits inside one window with room, but a harvest that has to start over because
it was interrupted is a harvest nobody runs twice.

    py 01_harvest.py
"""
import base64
import io
import json
import os
import subprocess
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
JOSS = os.path.join(RESEARCH, "joss_published.json")

MAIL = "emil.huseynov.zabil@bsu.edu.az"
TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stdout.strip()
if not TOKEN:
    raise SystemExit("STOP: no GitHub token; the harvest cannot read the contents API")
GH = {"Authorization": "Bearer " + TOKEN, "Accept": "application/vnd.github+json",
      "User-Agent": "paper36-harvest (mailto:%s)" % MAIL}
PLAIN = {"User-Agent": "paper36-harvest (mailto:%s)" % MAIL}


def fetch(url, headers, tries=5, timeout=45):
    """Return (status, parsed-or-None). A 404 is an answer; anything else that never lands raises."""
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                        timeout=timeout) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            if e.code in (403, 429):
                wait = 30 * (i + 1)
                print("      rate limited, waiting %ds" % wait)
                time.sleep(wait)
                last = e
                continue
            return e.code, None
        except Exception as e:
            last = e
            time.sleep(4 * (i + 1))
    raise SystemExit("STOP: %s never answered (%s)" % (url[:70], last))


def harvest_joss():
    if os.path.exists(JOSS):
        papers = json.load(io.open(JOSS, encoding="utf-8"))
        print("JOSS census already cached: %d papers" % len(papers))
        return papers
    papers, page = [], 1
    while True:
        st, d = fetch("https://joss.theoj.org/papers/published.json?page=%d" % page, PLAIN)
        if not d:
            break
        papers.extend(d)
        if page % 20 == 0:
            print("   page %3d, %d papers so far" % (page, len(papers)))
        page += 1
        time.sleep(0.8)
    os.makedirs(RESEARCH, exist_ok=True)
    json.dump(papers, io.open(JOSS, "w", encoding="utf-8"), indent=1)
    print("JOSS census: %d accepted papers over %d pages" % (len(papers), page - 1))
    return papers


def repo_of(url):
    if not url:
        return None
    u = url.strip().rstrip("/")
    if "github.com/" not in u:
        return None
    tail = u.split("github.com/", 1)[1]
    parts = [p for p in tail.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0] + "/" + parts[1].replace(".git", "")


def main():
    papers = harvest_joss()
    os.makedirs(CFFDIR, exist_ok=True)

    targets = []
    no_repo = 0
    for p in papers:
        r = repo_of(p.get("software_repository"))
        if not r:
            no_repo += 1
            continue
        targets.append((r, p))
    print()
    print("papers naming a GitHub repository : %d" % len(targets))
    print("papers naming something else      : %d (counted, not dropped)" % no_repo)

    seen = set()
    todo = []
    for r, p in targets:
        if r.lower() in seen:
            continue
        seen.add(r.lower())
        f = os.path.join(CFFDIR, r.replace("/", "__") + ".json")
        if not os.path.exists(f):
            todo.append((r, p, f))
    print("distinct repositories             : %d" % len(seen))
    print("already cached                    : %d" % (len(seen) - len(todo)))
    print("to fetch                          : %d" % len(todo))
    print()

    for i, (repo, paper, path) in enumerate(todo, 1):
        rec = {"repo": repo, "joss_doi": paper.get("doi"), "joss_title": paper.get("title"),
               "joss_published": paper.get("published_at"),
               "software_repository": paper.get("software_repository")}
        st, d = fetch("https://api.github.com/repos/%s/contents/CITATION.cff"
                      % urllib.parse.quote(repo), GH)
        rec["status"] = st
        if st == 200 and d and "content" in d:
            try:
                rec["cff"] = base64.b64decode(d["content"]).decode("utf-8", "replace")
            except Exception:
                rec["cff"] = None
                rec["status"] = "undecodable"
        else:
            rec["cff"] = None
        json.dump(rec, io.open(path, "w", encoding="utf-8"), indent=1)
        if i % 100 == 0 or i == len(todo):
            have = sum(1 for f in os.listdir(CFFDIR) if f.endswith(".json"))
            print("   %5d/%d fetched, %d cached" % (i, len(todo), have))
        time.sleep(0.55)

    files = [f for f in os.listdir(CFFDIR) if f.endswith(".json")]
    withcff = 0
    for f in files:
        if json.load(io.open(os.path.join(CFFDIR, f), encoding="utf-8")).get("cff"):
            withcff += 1
    stamp = {"harvested_utc": __import__("datetime").datetime.now(
                 __import__("datetime").timezone.utc).isoformat(),
             "joss_papers": len(papers), "papers_without_github": no_repo,
             "distinct_repos": len(seen), "cached": len(files), "with_citation_cff": withcff}
    json.dump(stamp, io.open(os.path.join(RESEARCH, "harvest_stamp.json"), "w",
                             encoding="utf-8"), indent=1)
    print()
    for k, v in stamp.items():
        print("   %-24s %s" % (k, v))
    return 0


sys.exit(main())
