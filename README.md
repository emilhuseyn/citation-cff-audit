# Replication package

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
