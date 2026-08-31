r"""Resolve the reference list at Crossref and render it in APA 7, which is what Scientometrics asks.

THE VENUE'S OWN RULE, read from its submission guidelines on 31.08.2026: "Cite references in the
text by name and year in parentheses", the list "alphabetized by the last names of the first author",
journal names italicised, and DOIs given "as full DOI links". That is a different instrument from the
numbered superscripts row 35 needed for JSEP, so nothing is carried over except the caution.

WHY NO DOI IS WRITTEN DOWN HERE. Row 35's first resolver pinned DOIs from memory and six of fourteen
resolved to real records that were not the intended papers: one about a drug's effect on a cell
image, one a journal's front matter, one about drawing tidy trees. Every one resolved cleanly, so
nothing failed and the file was written. A pinned DOI is only as good as the memory that pinned it.

So every entry is found by TITLE SEARCH and checked against the title asked for AND its year before
it is accepted. The year matters on its own: a chapter can carry the title of the paper it
summarises, and a preprint can carry the title of the paper it became. `posted-content` is refused
outright, which is what caught "Software citation principles" resolving to its PeerJ preprint.

A candidate that does not match stops the script. A wrong reference that resolves is worse than a
missing one, because it passes every automated check downstream.

    py 04_refs.py
"""
import difflib
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "results", "references.json")
MAIL = "emil.huseynov.zabil@bsu.edu.az"

# handle -> (expected title, expected year, tolerance in years)
WANTED = {
    # The specification this paper is about, and the principles behind it.
    "principles": ("Software citation principles", 2016, 1),
    "progress": ("Understanding progress in software citation: a study of software citation in "
                 "the CORD-19 corpus", 2022, 2),
    # "Software citation implementation challenges" was wanted here and is not in the reference
    # list: it exists only as an arXiv preprint, and this resolver refuses preprints because a
    # preprint carries the title of the paper it became. It is not cited rather than cited wrongly.
    # The venue's own tradition. The first of these is the closest published work to this paper and
    # is distinguished in the text rather than avoided.
    "r_formats": ("How do official software citation formats evolve over time? A longitudinal "
                  "analysis of R programming language packages", 2024, 2),
    "metadata_bench": ("Beyond existence checks: a cross-database benchmark of bibliographic "
                       "metadata consistency across academic domains and LLM-generated citations",
                       2026, 2),
    # Software citation measured in the bibliographic record.
    "dci": ("Research software citation in the Data Citation Index: Current practices and "
            "implications for research software sharing and reuse", 2019, 2),
    "in_code": ("In-code citation practices in open research software libraries", 2021, 2),
    "challenges": ("Challenges of measuring software impact through citations: An examination of "
                   "the lme4 R package", 2019, 2),
    "bootstrapped": ("Assessing the impact of software on science: A bootstrapped learning of "
                     "software entities in full-text papers", 2015, 2),
    "lis_software": ("How important is software to library and information science research? "
                     "A content analysis of full-text publications", 2019, 2),
    # Where the software actually lives, and whether it can be found at all.
    "where_is_it": ("Where is all the research software? An analysis of software in UK academic "
                    "repositories", 2023, 2),
    "registries": ("Nine best practices for research software registries and repositories", 2022, 2),
    # The corpus.
    # Crossref returns five peer-review records for this paper and not the paper, so the DOI says
    # where to look. It is still verified against the title and the year like every other entry.
    "joss": ("Journal of Open Source Software (JOSS): design and first-year review", 2018, 2,
             "10.7717/peerj-cs.147"),
    # Identifiers and the records behind them: what a DOI does and does not certify.
    # "Identifiers for Digital Objects: the case of software source code preservation" was wanted
    # here and is an iPRES paper Crossref does not index; it is dropped rather than approximated.
    "fair4rs": ("Introducing the FAIR Principles for research software", 2022, 2),
    # Crowded out the same way the JOSS paper is, here by "Faculty Opinions recommendation of"
    # wrappers that carry the paper's title inside their own. Hinted, and verified like the rest.
    "fair": ("The FAIR Guiding Principles for scientific data management and stewardship",
             2016, 1, "10.1038/sdata.2016.18"),
    # What authors are actually told to do, and what is known about whether they do it.
    "guide": ("Recognizing the value of software: a software citation guide", 2021, 2),
    "softcite": ("Softcite dataset: A dataset of software mentions in biomedical and economic "
                 "research publications", 2021, 2),
    # "Transitive Credit as a Means to Address Social and Technological Concerns Stemming from
    # Citation and Attribution of Digital Products" was wanted here. Its Crossref record carries no
    # author list at all, so APA cannot render it, and it is dropped rather than filled in by hand.
    # The record's own metadata being incomplete is the fact this paper is about, one level up.
    "rse_encyclopedia": ("The Research Software Encyclopedia: A Community Framework to Define "
                         "Research Software", 2022, 2),
    # Building a corpus out of GitHub is itself a threat to validity, and it has a literature.
    "perils": ("The promises and perils of mining GitHub", 2014, 2),
    "curating": ("Curating GitHub for engineered software projects", 2017, 2),
}

MIN_RATIO = 0.90
# A peer-review record carries the reviewed paper's title inside its own, and Crossref returns
# several of them ahead of the article. They are refused by type, and the search is widened, so
# the article is not crowded out of the result window by the reviews of itself.
BANNED_TYPES = {"posted-content", "preprint", "peer-review", "component", "grant"}


def get(url, tries=5):
    req = urllib.request.Request(url, headers={"User-Agent": "paper36-refs (mailto:%s)" % MAIL})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(5 * (i + 1))
    raise SystemExit("STOP: Crossref never answered for %s (%s). A reference list must not be "
                     "written from a search that did not run." % (url[-60:], last))


def norm(s):
    return " ".join("".join(c.lower() if (c.isalnum() or c.isspace()) else " " for c in s).split())


def apa_initials(given):
    """APA prints initials with periods and spaces: 'Jane Q. Public' -> 'J. Q.'"""
    parts = [p for p in (given or "").replace(".", " ").split() if p]
    return " ".join("%s." % p[0].upper() for p in parts)


def apa_authors(authors):
    """APA 7: all authors up to 20; for more, the first 19, an ellipsis, then the last."""
    names = []
    for a in authors:
        fam = (a.get("family") or a.get("name") or "").strip()
        if not fam:
            continue
        gi = apa_initials(a.get("given"))
        names.append(("%s, %s" % (fam, gi)).strip().rstrip(","))
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", ... " + names[-1]


def render(rec):
    """One APA 7 reference-list entry. Journal name and volume italicised, DOI as a full link."""
    out = "%s (%d). %s." % (rec["authors_apa"], rec["year"], rec["title"].rstrip("."))
    if rec.get("container"):
        out += " *%s*" % rec["container"]
        if rec.get("volume"):
            out += ", *%s*" % rec["volume"]
            if rec.get("issue"):
                out += "(%s)" % rec["issue"]
        if rec.get("pages"):
            out += ", %s" % rec["pages"]
        out += "."
    if rec.get("doi"):
        out += " https://doi.org/%s" % rec["doi"]
    return out


def clean(s):
    """Crossref stores some titles with the line breaks and indentation of the publisher's XML.

    The Research Software Encyclopedia's record holds a newline and twenty-four spaces in the middle
    of its title, which would be printed into the reference list exactly as stored.
    """
    return " ".join((s or "").split())


def check(handle, it, want_title, want_year, tol, where):
    """Accept a Crossref record only if its own title and year agree with what was asked for."""
    title = clean((it.get("title") or [""])[0])
    year = (it.get("issued", {}).get("date-parts") or [[0]])[0][0] or 0
    ratio = difflib.SequenceMatcher(None, norm(want_title), norm(title)).ratio()
    if ratio < MIN_RATIO or it.get("type") in BANNED_TYPES or abs(year - want_year) > tol:
        raise SystemExit(
            "STOP: the %s for %r does not verify.\n"
            "   asked for : %s (%s)\n"
            "   it holds  : %s (%s, %s, ratio %.2f)\n"
            "Nothing was written."
            % (where, handle, want_title, want_year, title, year, it.get("type"), ratio))
    return {"ratio": ratio, "title": title, "year": year, "type": it.get("type", ""),
            "doi": it.get("DOI", ""), "raw": it}


def find(handle, want_title, want_year, tol, doi_hint=None):
    """Title search first. A DOI hint is a last resort and is verified exactly like a search hit.

    WHY A HINT IS NOT THE FAILURE ROW 35 HAD. There, DOIs were pinned from memory and whatever came
    back was written down; six of fourteen were the wrong paper and every one resolved cleanly. Here
    a hint only decides WHERE to look. The record still has to carry the title that was asked for and
    a year within tolerance, so a mistyped or misremembered DOI stops the script exactly as a bad
    search hit does. It is needed because Crossref indexes the JOSS paper's peer reviews and not, in
    this query, the article itself.
    """
    if doi_hint:
        m, _ = get("https://api.crossref.org/works/" + urllib.parse.quote(doi_hint)), None
        print("      title search bypassed; verifying the hinted DOI %s" % doi_hint)
        return check(handle, m["message"], want_title, want_year, tol, "hinted DOI")
    q = urllib.parse.urlencode({"query.bibliographic": want_title, "rows": 20,
                                "select": "title,author,issued,container-title,volume,issue,page,"
                                          "DOI,type"})
    items = get("https://api.crossref.org/works?" + q)["message"]["items"]
    best = None
    for it in items:
        title = clean((it.get("title") or [""])[0])
        if not title:
            continue
        ratio = difflib.SequenceMatcher(None, norm(want_title), norm(title)).ratio()
        year = (it.get("issued", {}).get("date-parts") or [[0]])[0][0] or 0
        cand = {"ratio": ratio, "title": title, "year": year, "type": it.get("type", ""),
                "doi": it.get("DOI", ""), "raw": it}
        if best is None or ratio > best["ratio"]:
            best = cand
        if ratio < MIN_RATIO:
            continue
        if it.get("type") in BANNED_TYPES:
            print("      skipping a %s with the right title: %s" % (it.get("type"), it.get("DOI")))
            continue
        if abs(year - want_year) > tol:
            print("      skipping %s: title matches but the year is %s, not %s"
                  % (it.get("DOI"), year, want_year))
            continue
        return cand
    raise SystemExit(
        "STOP: no acceptable match for %r.\n"
        "   asked for : %s (%s)\n"
        "   best found: %s (%s, %s, ratio %.2f)\n"
        "Nothing was written. A reference that cannot be verified is not softened into one that "
        "can; it is removed from the paper or the paper is wrong."
        % (handle, want_title, want_year,
           best["title"] if best else "nothing", best["year"] if best else "-",
           best["type"] if best else "-", best["ratio"] if best else 0.0))


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    refs = {}
    print("resolving %d references by title search, verifying title AND year" % len(WANTED))
    print()
    for handle, spec in WANTED.items():
        title, year, tol = spec[0], spec[1], spec[2]
        hint = spec[3] if len(spec) > 3 else None
        print("   %-18s %s" % (handle, title[:64]))
        c = find(handle, title, year, tol, hint)
        it = c["raw"]
        rec = {
            "handle": handle, "doi": c["doi"], "title": clean(c["title"]), "year": c["year"],
            "type": c["type"], "ratio": round(c["ratio"], 3),
            "container": clean((it.get("container-title") or [""])[0]),
            "volume": it.get("volume", ""), "issue": it.get("issue", ""),
            "pages": (it.get("page", "") or "").replace("–", "-").replace("—", "-"),
            "authors": [{"family": a.get("family", ""), "given": a.get("given", "")}
                        for a in (it.get("author") or [])],
        }
        rec["authors_apa"] = apa_authors(it.get("author") or [])
        if not rec["authors_apa"]:
            raise SystemExit("STOP: %s resolved with no author list; APA needs one" % handle)
        rec["apa"] = render(rec)
        # The in-text citation the manuscript will use, built from the same record rather than typed.
        fams = [a["family"] for a in rec["authors"] if a["family"]]
        if len(fams) == 1:
            rec["cite"] = "%s (%d)" % (fams[0], rec["year"])
            rec["paren"] = "%s, %d" % (fams[0], rec["year"])
        elif len(fams) == 2:
            rec["cite"] = "%s and %s (%d)" % (fams[0], fams[1], rec["year"])
            rec["paren"] = "%s & %s, %d" % (fams[0], fams[1], rec["year"])
        else:
            rec["cite"] = "%s et al. (%d)" % (fams[0], rec["year"])
            rec["paren"] = "%s et al., %d" % (fams[0], rec["year"])
        refs[handle] = rec
        print("      -> %s  %s  ratio %.2f" % (c["doi"], c["year"], c["ratio"]))
        time.sleep(1.2)

    # THE DASH RULE, applied to text this script did not write. Crossref returns page ranges with an
    # en dash and the workspace forbids one anywhere; four submitted papers carried 218 of them.
    for h, r in refs.items():
        for bad in ("–", "—"):
            if bad in r["apa"]:
                raise SystemExit("STOP: %s still carries %r after normalisation" % (h, bad))

    seen = {}
    for h, r in refs.items():
        if r["doi"] in seen:
            raise SystemExit("STOP: %s and %s resolved to the same DOI %s"
                             % (h, seen[r["doi"]], r["doi"]))
        seen[r["doi"]] = h

    json.dump(refs, io.open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print()
    print("THE LIST, alphabetised as Scientometrics asks")
    print("=" * 92)
    for r in sorted(refs.values(), key=lambda x: norm(x["authors_apa"])):
        print("   %s" % r["apa"])
    print()
    print("wrote %s" % OUT)
    return 0


sys.exit(main())
