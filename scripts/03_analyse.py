r"""Compute every figure from the cached JOSS census, citation files and resolved DOIs. No network.

WHAT THE JOSS CORPUS BUYS, and it is the reason Amendment 1 chose it. Every repository here belongs
to a paper whose DOI is known in advance, so the question stops being the soft one, "does the DOI in
the file resolve and does its title look right", and becomes three hard ones that need no judgement:

  * does the top-level `doi` resolve at all?
  * does it name software, or does it name a paper?
  * is it the JOSS paper's own DOI, sitting in the field the specification reserves for the software?

The last is the sharpest. The CFF specification defines the top-level `doi` as the DOI of the
software and reserves `preferred-citation` for a paper the authors would rather have cited. A JOSS
DOI in the top-level field is that distinction collapsing, and it can be detected exactly rather than
inferred, because the paper's DOI is in the census.

DENOMINATORS ARE STATED AT EVERY STEP and never quietly narrowed: papers, repositories, repositories
carrying a file, files declaring a DOI. Each is printed with what it excludes.

    py 03_analyse.py
"""
import datetime
import difflib
import html
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESEARCH = os.path.join(ROOT, "research")
CFFDIR = os.path.join(RESEARCH, "cff")
DOIDIR = os.path.join(RESEARCH, "doi")
OUT = os.path.join(ROOT, "results", "measures.json")

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s'\"<>,)\]}]+")
PAPERY = {"journal-article", "proceedings-article", "posted-content", "preprint", "Preprint",
          "Text", "book-chapter", "report", "Journal Article", "Conference Paper"}
SOFTWAREY = {"Software", "software", "Workflow"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# A version inside a record title is not a different title. DataCite stores many software records as
# "NAME version 1.1.2 - what it does" while the citation file carries "NAME - what it does".
VERSION_RE = re.compile(r"\bv(?:ersion)?\.?\s*\d+(?:\.\d+)*[a-z0-9.+-]*", re.I)


def clean_title(s):
    """Undo what the transport did to the string before comparing two titles.

    TWO ARTEFACTS WERE COUNTED AS FINDINGS BY THE FIRST VERSION OF THIS COMPARISON, and both are the
    instrument rather than the data. Crossref and DataCite return some titles HTML-escaped, so
    "abstract & fast" arrives as "abstract &amp; fast"; the normaliser strips punctuation, which
    leaves the letters "amp" embedded in one string and not the other, and the containment test
    fails on a pair of identical titles. Some records also carry a literal backslash-n where the
    publisher's XML had a line break.

    A count inflated by its own instrument is the failure this workspace has already paid for once:
    a tool that scored every profile at 100 percent had never run a test.
    """
    s = html.unescape(s or "")
    s = s.replace("\n", " ").replace("\t", " ")
    return " ".join(s.split())


def title_agrees(t1, t2, drop_version=True):
    a, b = clean_title(t1), clean_title(t2)
    if drop_version:
        a, b = VERSION_RE.sub(" ", a), VERSION_RE.sub(" ", b)
    a, b = norm(a), norm(b)
    if not a or not b:
        return None
    return a in b or b in a


def parse_cff(text):
    """The fields this study reads. A YAML parser is deliberately not used.

    The files are hand-written and frequently invalid YAML; a parser would drop exactly the malformed
    ones, which is the population most likely to be wrong, so the count would be biased by the
    instrument. Regular expressions read what is there.
    """
    out = {"title": None, "top_doi": None, "preferred_doi": None, "has_preferred": False,
           "all_dois": []}
    if not text:
        return out
    m = re.search(r"^title:\s*(.+)$", text, re.M)
    if m:
        out["title"] = m.group(1).strip().strip("'\"")
    m = re.search(r"^doi:\s*['\"]?(10\.[^\s'\"]+)", text, re.M)
    if m:
        out["top_doi"] = m.group(1).rstrip(".,;)")
    out["has_preferred"] = bool(re.search(r"^preferred-citation:", text, re.M))
    if out["has_preferred"]:
        tail = re.split(r"^preferred-citation:", text, maxsplit=1, flags=re.M)[1]
        m = re.search(r"^\s+doi:\s*['\"]?(10\.[^\s'\"]+)", tail, re.M)
        if m:
            out["preferred_doi"] = m.group(1).rstrip(".,;)")
    out["all_dois"] = [d.rstrip(".,;)") for d in DOI_RE.findall(text)]
    return out


def load_dois():
    """Cached answers, keyed in lower case.

    A DOI IS CASE-INSENSITIVE BY ITS OWN SPECIFICATION and one repository declares
    10.5281/ZENODO.2545106 where every other declares the same identifier in lower case. The cache
    file names differ only in case, which on Windows is the same file, so one record was stored and
    an exact-case lookup then reported the identifier as never resolved. That would have printed as
    a DOI that does not resolve, which is this paper's headline number.
    """
    out = {}
    if not os.path.isdir(DOIDIR):
        return out
    for f in os.listdir(DOIDIR):
        if f.endswith(".json"):
            r = json.load(io.open(os.path.join(DOIDIR, f), encoding="utf-8"))
            out[r["doi"].lower()] = r
    return out


def main():
    stamp = json.load(io.open(os.path.join(RESEARCH, "harvest_stamp.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(RESEARCH, "harvest_stamp.json")) else {}
    papers = json.load(io.open(os.path.join(RESEARCH, "joss_published.json"), encoding="utf-8"))
    resolved = load_dois()
    files = sorted(f for f in os.listdir(CFFDIR) if f.endswith(".json"))
    print("reading %s" % RESEARCH)
    print("   JOSS papers          %d" % len(papers))
    print("   repositories probed  %d" % len(files))
    print("   DOIs resolved        %d" % len(resolved))
    print()

    recs = []
    for f in files:
        r = json.load(io.open(os.path.join(CFFDIR, f), encoding="utf-8"))
        r["parsed"] = parse_cff(r.get("cff"))
        recs.append(r)

    have = [r for r in recs if r.get("cff")]
    print("RQ0  DOES THE FILE EXIST AT ALL")
    print("   repositories probed                 %d" % len(recs))
    print("   carrying a CITATION.cff             %d (%.1f%%)"
          % (len(have), 100.0 * len(have) / max(len(recs), 1)))
    missing_status = Counter(r.get("status") for r in recs if not r.get("cff"))
    print("   without one, by what GitHub said    %s" % dict(missing_status))

    with_doi = [r for r in have if r["parsed"]["top_doi"]]
    no_doi = len(have) - len(with_doi)
    print()
    print("RQ1  DOES THE DECLARED DOI RESOLVE")
    print("   files with a top-level doi field    %d" % len(with_doi))
    print("   files with none (excluded, counted) %d" % no_doi)

    states = Counter()
    kinds = Counter()
    joss_in_top = []
    unresolved = []
    title_mismatch = []
    joss_prefix = []
    title_raw = 0
    title_unescaped = 0
    for r in with_doi:
        d = r["parsed"]["top_doi"]
        # RQ2b NEEDS NO REGISTRY AND IS COMPUTED FIRST, over every file that declares a top-level
        # doi. Both identifiers are already known: the census supplies the paper's DOI and the file
        # supplies what it put in the software's field, so this is a string comparison.
        #
        # It is deliberately outside the resolution branch. Computed inside it, this count would be
        # a function of how far the resolver had got, and because DOIs are resolved in sorted order
        # every 10.21105/joss identifier lands in one contiguous block near the front. A partial run
        # therefore reports a JOSS-saturated sample that looks like a finding and is an artefact of
        # the queue.
        if r.get("joss_doi") and d.lower() == str(r["joss_doi"]).lower():
            joss_in_top.append({"repo": r["repo"], "doi": d})
        if d.lower().startswith("10.21105/joss"):
            joss_prefix.append({"repo": r["repo"], "doi": d})
        res = resolved.get(d.lower())
        if res is None:
            states["not yet resolved"] += 1
            continue
        states[res["state"]] += 1
        if res["state"] != "ok":
            unresolved.append({"repo": r["repo"], "doi": d})
            continue
        kinds[res.get("type") or "unknown"] += 1
        t1, t2 = r["parsed"]["title"], res.get("title")
        if t1 and t2:
            raw_ok = norm(t1) in norm(t2) or norm(t2) in norm(t1)
            esc_ok = title_agrees(t1, t2, drop_version=False)
            ver_ok = title_agrees(t1, t2, drop_version=True)
            if not raw_ok:
                title_raw += 1
            if esc_ok is False:
                title_unescaped += 1
            if ver_ok is False:
                # A DISAGREEMENT IS NOT A UNIFORM THING and reporting one number for all of them
                # would invite the obvious objection, which is that "visualization" against
                # "visualisation" is not a citation naming the wrong object. So each is scored on
                # how far apart the two strings are and the results are reported in bands. The
                # bands are the finding; the total is only their sum.
                a = norm(VERSION_RE.sub(" ", clean_title(t1)))
                b = norm(VERSION_RE.sub(" ", clean_title(t2)))
                ratio = difflib.SequenceMatcher(None, a, b).ratio()
                title_mismatch.append({"repo": r["repo"], "cff": clean_title(t1)[:70],
                                       "record": clean_title(t2)[:70], "ratio": round(ratio, 3)})

    for k, v in states.most_common():
        print("      %-22s %d" % (k, v))

    ok = states.get("ok", 0)
    print()
    print("RQ2  WHAT KIND OF OBJECT DOES IT NAME")
    for k, v in kinds.most_common(10):
        print("      %-24s %4d  %5.1f%%" % (k, v, 100.0 * v / max(ok, 1)))
    papery = sum(v for k, v in kinds.items() if k in PAPERY)
    softwarey = sum(v for k, v in kinds.items() if k in SOFTWAREY)
    print("   names a paper                       %d (%.1f%% of resolving)"
          % (papery, 100.0 * papery / max(ok, 1)))
    print("   names software                      %d (%.1f%%)"
          % (softwarey, 100.0 * softwarey / max(ok, 1)))

    print()
    print("RQ2b THE SHARP ONE: is the top-level doi the JOSS PAPER's own DOI?")
    print("   the specification reserves that field for the SOFTWARE")
    print("   files whose top-level doi is the JOSS paper  %d (%.1f%% of files with a doi)"
          % (len(joss_in_top), 100.0 * len(joss_in_top) / max(len(with_doi), 1)))
    print("   files whose top-level doi is ANY joss DOI    %d (%.1f%%)"
          % (len(joss_prefix), 100.0 * len(joss_prefix) / max(len(with_doi), 1)))
    print("   neither of the two needs a registry: both identifiers are known in advance,")
    print("   so this count does not move as the resolver works through its queue.")
    pref = sum(1 for r in have if r["parsed"]["has_preferred"])
    print("   files that DO use preferred-citation         %d (%.1f%% of files)"
          % (pref, 100.0 * pref / max(len(have), 1)))

    print()
    print("RQ3  DOES THE TITLE MATCH THE RECORD")
    print("   THE INSTRUMENT IS REPORTED BEFORE THE FINDING, because the first two counts here")
    print("   are the tool's artefacts and only the third is about the data.")
    print("   compared with no cleaning at all         %d" % title_raw)
    print("   after undoing HTML escaping and breaks   %d  (%d were &amp; and friends)"
          % (title_unescaped, title_raw - title_unescaped))
    print("   after also ignoring a version in the record %d  (%d were 'NAME version 1.2.3')"
          % (len(title_mismatch), title_unescaped - len(title_mismatch)))
    print("   REPORTED DISAGREEMENTS              %d" % len(title_mismatch))
    near = [e for e in title_mismatch if e["ratio"] >= 0.80]
    mid = [e for e in title_mismatch if 0.50 <= e["ratio"] < 0.80]
    far = [e for e in title_mismatch if e["ratio"] < 0.50]
    print("      the same work worded differently   %3d  (similarity 0.80 and above)" % len(near))
    print("      substantially rewritten            %3d  (0.50 to 0.80)" % len(mid))
    print("      names a different thing            %3d  (below 0.50)" % len(far))
    # WHAT THE WIDEST BAND ACTUALLY CONTAINS. Reading it by eye shows one pattern doing most of the
    # work, and a pattern named mechanically is worth more than a count defended in prose. Zenodo's
    # GitHub integration titles a release "owner/repo: tag", so the record a citation file points at
    # is often not a title at all. That is a different defect from naming the wrong project and the
    # two are separated here rather than summed.
    for e in far:
        slug = e["repo"].lower()
        rec = e["record"].lower()
        e["zenodo_release_title"] = rec.startswith(slug + ":") or rec.startswith(
            slug.split("/")[-1] + ":") and re.match(r".*:\s*v?\d", rec) is not None
        e["placeholder_title"] = "my research software" in e["cff"].lower()
    zen = [e for e in far if e["zenodo_release_title"]]
    ph_t = [e for e in far if e["placeholder_title"]]
    rest = [e for e in far if not e["zenodo_release_title"] and not e["placeholder_title"]]
    print("   inside that band, by what the record actually is:")
    print("      an auto-generated release title, 'owner/repo: tag'   %3d" % len(zen))
    print("      the file carries the specification's placeholder     %3d" % len(ph_t))
    print("      a genuinely different name                           %3d" % len(rest))
    print("   the placeholder ones, in full, because they are the sharpest:")
    for e in ph_t:
        print("      %-30s cff %r" % (e["repo"][:30], e["cff"][:56]))
        print("      %-30s rec %r" % ("", e["record"][:56]))
    print("   a different name, in full:")
    for e in rest:
        print("      %-30s cff %r" % (e["repo"][:30], e["cff"][:56]))
        print("      %-30s rec %r" % ("", e["record"][:56]))

    print()
    print("RQ4  THE CONTROL, BEFORE ANY INTERPRETATION")
    print("   if these files were almost always right, there would be no paper.")
    print("   unresolvable DOIs: %d | paper-in-software-field: %d | title disagreements: %d"
          % (len(unresolved), len(joss_in_top), len(title_mismatch)))
    # A SUBSTRING TEST CANNOT COUNT THIS. "zenodo.1234" is inside "zenodo.1234567", so the loose
    # check reported four files carrying the specification's example when three carry it exactly and
    # the fourth carries a different made-up number. The three groups below are disjoint and are
    # counted, because "the example was never edited" and "a plausible identifier does not resolve"
    # are different claims about how a citation file goes wrong.
    ph = [r["repo"] for r in with_doi
          if (r["parsed"]["top_doi"] or "").lower() == "10.5281/zenodo.1234"]
    synth = [(r["repo"], r["parsed"]["top_doi"]) for r in with_doi
             if re.match(r"(?i)^10\.5281/zenodo\.(1234567|9999999|123456|0+)$",
                         r["parsed"]["top_doi"] or "")]
    other_dead = [e for e in unresolved
                  if e["repo"] not in ph and e["repo"] not in [s[0] for s in synth]]
    print("   of the %d that do not resolve:" % len(unresolved))
    print("      carry the specification's own example 10.5281/zenodo.1234 exactly   %d" % len(ph))
    for x in ph:
        print("         %s" % x)
    print("      carry another obviously invented number                             %d"
          % len(synth))
    for repo, d in synth:
        print("         %-42s %s" % (repo, d))
    print("      look like a real identifier and still do not resolve                %d"
          % len(other_dead))
    for e in other_dead:
        print("         %-42s %s" % (e["repo"], e["doi"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({
        "analysed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "harvest": stamp,
        "joss_papers": len(papers), "repos_probed": len(recs), "repos_with_cff": len(have),
        "missing_status": dict(missing_status),
        "files_with_top_doi": len(with_doi), "files_without_doi": no_doi,
        "resolution": dict(states), "kinds": dict(kinds),
        "names_paper": papery, "names_software": softwarey,
        "joss_doi_in_top_field": len(joss_in_top),
        "any_joss_doi_in_top_field": len(joss_prefix), "uses_preferred_citation": pref,
        "title_mismatches": len(title_mismatch),
        "title_mismatches_raw": title_raw,
        "title_mismatches_unescaped": title_unescaped,
        "title_same_work_reworded": len([e for e in title_mismatch if e["ratio"] >= 0.80]),
        "title_substantially_rewritten": len([e for e in title_mismatch
                                              if 0.50 <= e["ratio"] < 0.80]),
        "title_names_different_thing": len([e for e in title_mismatch if e["ratio"] < 0.50]),
        # The two band edges are written out because the manuscript quotes them, and the gate
        # refuses any number in the prose that no measurement produced. A method parameter is not
        # data, but it is not an unexplained number either, so it is recorded rather than exempted.
        "title_band_high": 0.8,
        "title_band_low": 0.5,
        "title_far_zenodo_release": len([e for e in title_mismatch
                                         if e["ratio"] < 0.50 and e.get("zenodo_release_title")]),
        "title_far_placeholder": len([e for e in title_mismatch
                                      if e["ratio"] < 0.50 and e.get("placeholder_title")]),
        "title_far_different_name": len([e for e in title_mismatch
                                         if e["ratio"] < 0.50 and not e.get("zenodo_release_title")
                                         and not e.get("placeholder_title")]),
        "placeholder_doi_exact": len(ph),
        "invented_doi_other": len(synth),
        "plausible_but_dead_doi": len(other_dead),
        "examples": {"unresolved": unresolved[:20], "joss_in_top": joss_in_top[:20],
                     "title_mismatch": title_mismatch[:20], "placeholder": ph[:20], "invented": synth[:20],
                     "plausible_dead": other_dead[:20]},
    }, io.open(OUT, "w", encoding="utf-8"), indent=1)
    print()
    print("wrote %s" % OUT)
    return 0


sys.exit(main())
