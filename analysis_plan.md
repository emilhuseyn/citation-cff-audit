# Analysis plan

**Frozen 31.08.2026, before the confirmatory harvest.** Everything below was decided in advance.
Amendments are appended with their date and never edited in place.

## The question

GitHub renders a "Cite this repository" button from a `CITATION.cff` file and produces a formatted
citation from it. A reader copies what it produces. The file is machine-readable, validated against a
schema, and rendered by the platform, and all three of those things make it look finished.

None of them checks that the DOI inside resolves, that it names this software rather than a paper
about it, or that the title in the file is the title on the record.

**RQ1.** Of the DOIs declared in `CITATION.cff` files, how many resolve at all?

**RQ2.** The CFF specification defines the top-level `doi` as the DOI of the software, and reserves
`preferred-citation` for a paper the authors would rather be cited. Of the DOIs that resolve, what
kind of object do they name?

**RQ3.** Does the title in the file match the title on the record it points at?

**RQ4, the control.** If these files were almost always correct, there would be no paper. RQ4 is
reported first as a null: the counts for RQ1 to RQ3 are reported whichever way they fall, before any
interpretation.

## Corpus, and the problem with the obvious one

**GitHub's code search is an index, not a census.** It reports a total, caps enumeration at a
thousand results, and does not disclose its sampling. It is good enough to establish that an effect
exists and it cannot be the denominator of a published proportion.

The corpus is therefore built from a population that can be enumerated. **To be fixed before the
confirmatory harvest and recorded here as an amendment**, with the candidates being:

  * every software record on Zenodo created through its GitHub integration, which Zenodo's API
    enumerates completely, checking each named repository for a `CITATION.cff`;
  * the same for figshare and for the Journal of Open Source Software, whose accepted papers each
    name a repository.

Whichever is used, the denominator is stated as what it is: software that already has a DOI, which
is a favourable population for this question rather than a neutral one.

**No repository is cloned.** The study reads `CITATION.cff` through the contents API, and resolves
each DOI at Crossref and then at DataCite. Nothing else is fetched.

## What counts as what

A DOI **resolves** if Crossref or DataCite returns a record for it. A DOI that neither returns is
counted as unresolved, and the two registries are tried in that order because Crossref carries
articles and DataCite carries most software records.

A record's **kind** is Crossref's `type` or DataCite's `resourceTypeGeneral`, taken as published. No
kind is inferred from a title.

A **title match** is decided after reducing both strings to lowercase alphanumerics and asking
whether either contains the other. That is deliberately generous: it passes "NetCDF-C" against
"Unidata NetCDF", and the paper reports disagreements rather than agreements, so a generous rule
makes the reported number a lower bound.

## Exclusions, stated rather than silent

A file with no DOI anywhere is excluded from RQ1 to RQ3 **and counted**, because a citation file
without a DOI makes no claim that could be wrong.

## The pilot, and what it found

Run 31.08.2026 on 70 files reachable through the code search index, before this plan was frozen.
These numbers are the reason the topic was taken and the confirmatory harvest must be checked against
them rather than replacing them silently.

| | |
|---|---|
| files read | 70 |
| with at least one DOI | 68 |
| DOI does not resolve | **5** |
| resolves to type Software | 38 |
| resolves to a paper: journal article, preprint or proceedings | **23** |
| title disagrees with the record | **9** |

Three of the five unresolvable DOIs are `10.5281/zenodo.1234`, **the placeholder from the CFF
specification's own example**, shipped unedited in `omry/omegaconf`, `thkruz/keeptrack.space` and
`0xk1h0/ChatGPT_DAN`. `eclipse-mosquitto/mosquitto` carries the specification's placeholder title,
`My Research Software`, in a file whose DOI resolves to the real Mosquitto paper.

## Topics screened and killed before this one

1. **What a marketplace verified-publisher badge certifies.** **Killed as crowded**: VS Code
   extension security is being worked hard right now, with VSMEx (CODASPY 2026), Dissecting Malicious
   VS Code Extensions (SECRYPT 2026) and UntrustIDE (NDSS 2024).
2. **What a README build badge certifies.** **Killed by its own pilot**, and the criterion was
   written before the pilot ran: if the effect is absent among heavily-read READMEs it is not worth
   chasing into the tail. Across 28 well-known repositories and 70 badges there were zero pointing at
   a shut-down service and zero GitHub Actions badges naming a workflow the repository does not have.
   The one prior paper, "Adding sparkle to social coding" (ICSE 2018), is about badge adoption rather
   than badge truthfulness, so the question was open and the answer is that nothing is wrong.
3. **What a registry's download count counts.** **Killed as crowded and small**: the popularity-metric
   space is active, including in this paper's likely venue, and an earlier pilot in this workspace
   measured PyPI mirror inflation at 0.4 to 0.5 percent.

**The portfolio was screened first, by hand, against all 37 rows.** Licence declarations are row 20,
live at TOSEM, which rules out a licence paper in a new ecosystem however tempting Hugging Face
looks. Provenance attestation is row 9, Sigstore is row 18, self-attested claims decaying is row 14,
commit-SHA pinning is row 23. Availability of a declared dependency is row 35, written yesterday,
which rules out conda-forge source checksums and Hugging Face base-model lineage.

**Nearest published work, and why it does not close this.** "Good practice versus reality: A landscape
analysis of Research Software metadata adoption in European Open Science Clusters" (MSR 2025)
measures whether projects have the metadata. This asks whether the metadata they have points at the
right object. Adoption and correctness are different questions, and the same distinction is what made
the badge candidate worth piloting.

## Amendments

### Amendment 1, 31.08.2026: the corpus is JOSS, and why the two candidates it replaces failed

The plan left the corpus open and named two candidates. Both were tested before the confirmatory
harvest and the decision is recorded here with what each attempt showed.

**Zenodo was tried first and does not enumerate.** It holds 283,283 software records, but a
structural query for a GitHub repository in the related identifiers returns **zero**: that field is
not searchable that way. Free text for "github.com" returns 4,167, which is a text match rather than
a population and is plainly incomplete given how many records the GitHub integration mints. Deep
paging then fails outright with HTTP 400. A corpus that cannot be walked cannot be a denominator.

**The corpus is the Journal of Open Source Software.** `joss.theoj.org/papers/published.json` pages
through **every accepted paper**, and each record carries the paper's DOI, its title and its
`software_repository`. Walking it to the last page gives **3,696 accepted papers**, and that is a
census rather than an index: JOSS publishes its own list and there is nothing sampled about it.

**The population's bias is stated rather than hidden, and it points the right way.** These are
projects that submitted software to peer review and hold a DOI already, so they have done more
citation work than the average repository. If their citation files are wrong, that is a lower bound
on the wider population rather than an alarming corner of it.

**It also sharpens RQ2.** Starting from JOSS means the software's own paper DOI is known, so the
question stops being "does the DOI in the file resolve" and becomes "does it point at this software,
at this paper, or at something else". No judgement about what a title match means is needed for the
first two, because both identifiers are known in advance.

**RQ1 to RQ4 are unchanged.** They are computed over the JOSS population, and every proportion
carries that denominator explicitly.
