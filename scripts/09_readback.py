r"""Read the built Word files back and check them against what the venue asked for.

WHY THE SOURCE IS NOT ENOUGH. 06_build.py checks the markdown it is given. This reads the .docx that
the journal will actually receive, because everything between the two is a converter, and a converter
is exactly where a paper picks up defects its source does not contain: this workspace has shipped
four manuscripts whose LaTeX source held no dash and whose PDFs held 218.

    py 09_readback.py
"""
import io
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FINAL = os.path.join(ROOT, "final")
FAILS = []


def ok(label, cond, detail=""):
    print("   %-4s %-54s %s" % ("ok" if cond else "FAIL", label, detail))
    if not cond:
        FAILS.append(label)


def text_of(path):
    """The document's visible text, with paragraph breaks preserved."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    body = re.sub(r"<[^>]+>", "", xml)
    body = body.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # PANDOC TYPESETS WHERE THE SOURCE DID NOT. Its smart extension puts a NON-BREAKING space after
    # an abbreviation, so "Mr. Emil" reaches the file as "Mr." U+00A0 "Emil", and it turns straight
    # quotes into curly ones. Both are correct in a Word document and neither is a defect, so they
    # are normalised here for comparison rather than reported as findings.
    #
    # NOTHING THAT COULD HIDE A DASH IS NORMALISED. U+2013 and U+2014 are left exactly as found, so
    # the dash check reads what the journal will receive.
    for a, b in (("\u00a0", " "), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"')):
        body = body.replace(a, b)
    return body


def main():
    man = os.path.join(FINAL, "Scientometrics_manuscript.docx")
    tp = os.path.join(FINAL, "Scientometrics_title_page.docx")
    for p in (man, tp):
        if not os.path.exists(p):
            print("STOP: %s was not built" % p)
            return 1

    body = text_of(man)
    front = text_of(tp)
    print("=" * 92)
    print("READ BACK FROM THE FILES THE JOURNAL WILL RECEIVE")
    print("=" * 92)
    print("   manuscript  %s  %d characters" % (os.path.basename(man), len(body)))
    print("   title page  %s  %d characters" % (os.path.basename(tp), len(front)))
    print()

    ok("the manuscript actually has content", len(body) > 20000, "%d characters" % len(body))
    ok("no citation marker survived the conversion", "{{" not in body and "}}" not in body)
    ok("no section says PENDING", "PENDING" not in body)
    bad = {c: body.count(c) + front.count(c) for c in ("–", "—") if
           c in body or c in front}
    ok("no en or em dash in either file", not bad, str(bad) if bad else "none")

    # APA in-text citations, both forms, rendered rather than left as markers.
    # A parenthetical may hold more than one work, separated by a semicolon, which is what APA asks
    # for and what the builder emits for {{a;b}}. The first version of this pattern required the
    # closing bracket immediately after the year and so counted only the single-work ones.
    paren = re.findall(r"\([A-Z][A-Za-zÀ-ɏ'\- ]+(?: et al\.| & [A-Z][\w'\- ]+)?, (?:19|20)\d\d"
                       r"(?:[a-z])?(?:; [A-Z][^)]*)?\)", body)
    narrative = re.findall(r"[A-Z][A-Za-zÀ-ɏ'\- ]+(?: et al\.| and [A-Z][\w'\- ]+)?"
                           r" \((?:19|20)\d\d\)", body)
    ok("parenthetical citations are rendered", len(paren) >= 8, "%d found" % len(paren))
    ok("narrative citations are rendered", len(narrative) >= 5, "%d found" % len(narrative))

    # The reference list: present, after the text, and alphabetised as the journal asks.
    ok("a References heading is present", "References" in body)
    tail = body.split("References", 1)[-1]
    # Pandoc indents body paragraphs, so a reference entry does not begin at column zero.
    entries = re.findall(r"(?m)^[ 	]*([A-Z][A-Za-zÀ-ɏ'\-]+(?:,|\s))", tail)
    ok("the reference list has entries", len(entries) >= 15, "%d first-author starts" % len(entries))
    surnames = [e.rstrip(", ").lower() for e in entries]
    ok("the reference list is alphabetised", surnames == sorted(surnames),
       "first four: %s" % ", ".join(surnames[:4]))
    ok("DOIs are written as full links", tail.count("https://doi.org/") >= 15,
       "%d links" % tail.count("https://doi.org/"))

    # The title page is where the journal wants identity, and the journal is single-blind.
    ok("the title page names the author", "Emil Huseynov" in front)
    ok("the title page carries the ORCID", "0009-0007-7142-060X" in front)
    ok("the title page carries the corresponding e-mail",
       "emil.huseynov.zabil@bsu.edu.az" in front)
    ok("the title page carries the affiliation", "Baku State University" in front)
    ok("the title page uses the title Mr.", "Mr. Emil Huseynov" in front)
    # A degree is never claimed. Only a BSc is held and the field is left empty everywhere.
    claims = [w for w in ("PhD", "Ph.D", "Dr.", "MSc", "M.Sc", "Master of", "Doctor of")
              if w in front or w in body]
    ok("no academic degree is claimed anywhere", not claims, str(claims) if claims else "none")
    ok("the declarations are on the title page", "Competing interests" in front)

    print()
    if FAILS:
        print("FAILED %d check(s): %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("the built files are what the venue asked for")
    return 0


sys.exit(main())
