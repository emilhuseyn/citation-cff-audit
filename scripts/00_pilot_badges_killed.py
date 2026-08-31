# -*- coding: utf-8 -*-
"""Pilot candidate B: does a README build badge tell the truth?

THE PREMISE TO TEST, before any of it is written up. A badge saying "build passing" is read as "this
project builds". What it actually reports is one workflow, on one branch, as of whenever the shield
was last cached. Several things can make it say something else:

  * it names a workflow file that no longer exists, or was renamed
  * it names a branch that is no longer the default
  * it points at a service that has shut down, travis-ci.org above all
  * it is a static image with the word "passing" baked in and no state behind it at all
  * the workflow it names passes while another required one fails

If none of these is common the topic is dead and this pilot has done its job in an hour, which is
what the previous five killed topics cost.

Sampled rather than censused, because this is a pilot. Popular repositories are sampled deliberately:
if the effect is absent among heavily-read READMEs it is not worth measuring in the tail.
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

TOKEN = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
if not TOKEN:
    raise SystemExit("STOP: no GitHub token; the pilot cannot read the API")
HDR = {"Authorization": "Bearer " + TOKEN,
       "Accept": "application/vnd.github+json",
       "User-Agent": "paper36-pilot"}


def api(path, tries=4):
    url = path if path.startswith("http") else "https://api.github.com" + path
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HDR),
                                        timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                time.sleep(10 * (i + 1))
                continue
            return {"__error__": e.code}
        except Exception:
            time.sleep(5 * (i + 1))
    return {"__error__": "unreachable"}


def readme(repo):
    d = api("/repos/%s/readme" % repo)
    if "__error__" in d or "content" not in d:
        return None
    import base64
    try:
        return base64.b64decode(d["content"]).decode("utf-8", "replace")
    except Exception:
        return None


# A spread of well-known repositories across ecosystems, chosen for having READMEs people read.
REPOS = [
    "psf/requests", "pallets/flask", "expressjs/express", "axios/axios",
    "pytest-dev/pytest", "numpy/numpy", "pandas-dev/pandas", "scikit-learn/scikit-learn",
    "rust-lang/regex", "serde-rs/serde", "tokio-rs/tokio", "clap-rs/clap",
    "gin-gonic/gin", "spf13/cobra", "sirupsen/logrus", "stretchr/testify",
    "square/retrofit", "google/gson", "junit-team/junit5", "apache/commons-lang",
    "chalk/chalk", "lodash/lodash", "moment/moment", "webpack/webpack",
    "psf/black", "tiangolo/fastapi", "encode/httpx", "python-attrs/attrs",
]

BADGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
SHIELD_HOSTS = ("img.shields.io", "shields.io", "badge.fury.io", "travis-ci.org",
                "travis-ci.com", "api.travis-ci.org", "api.travis-ci.com",
                "ci.appveyor.com", "circleci.com", "codecov.io", "coveralls.io",
                "github.com")

DEAD = ("travis-ci.org", "api.travis-ci.org")

print("sampling %d repositories" % len(REPOS))
print()

rows = []
service = Counter()
for repo in REPOS:
    md = readme(repo)
    if md is None:
        print("  %-30s README unreadable" % repo)
        continue
    urls = BADGE.findall(md)
    badges = [u for u in urls if any(h in u for h in SHIELD_HOSTS)]
    ga = [u for u in badges if "/actions/workflows/" in u or "workflow" in u]
    for u in badges:
        host = urllib.parse.urlparse(u).netloc
        service[host] += 1
    rows.append({"repo": repo, "badges": len(badges), "ga": len(ga), "urls": badges})
    print("  %-30s %2d badge(s), %d of them GitHub Actions" % (repo, len(badges), len(ga)))
    time.sleep(0.4)

print()
print("BADGE HOSTS ACROSS THE SAMPLE")
for h, n in service.most_common(14):
    mark = "  <- shut down" if any(d in h for d in DEAD) else ""
    print("   %-28s %3d%s" % (h, n, mark))

print()
print("DO THE GITHUB ACTIONS BADGES NAME A WORKFLOW THAT EXISTS?")
checked = missing = 0
examples = []
for r in rows:
    for u in r["urls"]:
        m = re.search(r"github\.com/([^/]+/[^/]+)/actions/workflows/([^/?]+)", u)
        if not m:
            m2 = re.search(r"github\.com/([^/]+/[^/]+)/workflows/([^/]+)/badge", u)
            if not m2:
                continue
            repo, wf = m2.group(1), urllib.parse.unquote(m2.group(2))
            kind = "legacy"
        else:
            repo, wf = m.group(1), m.group(2)
            kind = "file"
        checked += 1
        wfs = api("/repos/%s/actions/workflows" % repo)
        names = [(w.get("name"), w.get("path", "").split("/")[-1])
                 for w in (wfs.get("workflows") or [])]
        hit = any(wf == p or wf == n for n, p in names)
        if not hit:
            missing += 1
            examples.append((r["repo"], kind, wf, [p for _, p in names][:4]))
        time.sleep(0.4)

print("   GitHub Actions badges checked : %d" % checked)
print("   naming a workflow that is not in the repository's list : %d" % missing)
for e in examples[:8]:
    print("      %-24s %-7s badge names %-26s repo has %s" % e)

print()
print("VERDICT INPUTS")
print("   repositories read       : %d" % len(rows))
print("   badges found            : %d" % sum(r["badges"] for r in rows))
print("   dead-service badges     : %d"
      % sum(n for h, n in service.items() if any(d in h for d in DEAD)))
print("   median badges per README: %d"
      % sorted(r["badges"] for r in rows)[len(rows) // 2] if rows else 0)
