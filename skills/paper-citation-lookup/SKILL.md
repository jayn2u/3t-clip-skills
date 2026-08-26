---
name: paper-citation-lookup
description: Looks up what a specific cited paper actually says — its method, contribution, or a claim you attributed to it — starting from an arXiv ID/URL, a paper title, a DOI, or a whole .bib/reference list. Prefers the arXiv HTML render (arxiv.org/html/<id>) over the PDF or abstract page whenever it exists, because it is the only format Claude can read section-by-section instead of guessing from an abstract. Falls back through arXiv PDF, the publisher/proceedings page, and Semantic Scholar metadata when no arXiv HTML exists. Use this whenever the user asks "what does [paper] actually claim/do", wants you to verify a citation before they write it into a paper, pastes a bibtex entry or arXiv link and asks for a summary, or hands you a whole bibliography file and wants each entry's contribution captured (e.g. for filling in AGENTS.md/CLAUDE.md project notes, a related-work section, or a citation list) — even if they don't say the word "arXiv" out loud.
---

# Paper Citation Lookup

## Why arXiv HTML first

An abstract tells you what a paper claims to have done, not how, and a PDF
forces you to either read the whole thing or guess which page has the part
you need. arXiv's HTML render (`arxiv.org/html/<id>`) is full text with real
section boundaries, so you can quote "Section 3.2" or "Table 4" instead of
paraphrasing an abstract and hoping it's accurate. Since ~2023 arXiv
auto-generates HTML for nearly all new submissions and has backfilled a large
share of older ones, so checking for it first is usually a quick win, not a
special case.

## Workflow

**1. Get an identifier for each paper.** From what the user gave you:
- arXiv ID/URL → use directly.
- Bibtex entry → the id is often in `eprint` + `archiveprefix = {arXiv}`, or
  embedded in the `url` field.
- Title only, or a proceedings URL (ACL Anthology, CVF, MLR Press, NeurIPS
  proceedings, ACM/IEEE DL, ScienceDirect) → these often *also* have an arXiv
  preprint even though the bib entry doesn't say so — don't assume "no arXiv
  id in the bib" means "no arXiv version."

**2. Resolve the best source before fetching anything.** Run
`scripts/resolve_paper.py` rather than hand-checking URLs one at a time — it
does the HTTP status probing and the arXiv-vs-proceedings-page tradeoff for
you and returns a `recommended_source` plus the reasoning trail:

```bash
python3 scripts/resolve_paper.py --arxiv 2401.12345
python3 scripts/resolve_paper.py --title "Learning Transferable Visual Models From Natural Language Supervision"
python3 scripts/resolve_paper.py --url https://arxiv.org/abs/2401.12345
python3 scripts/resolve_paper.py --bib references.bib                  # every entry
python3 scripts/resolve_paper.py --bib references.bib --key smith2024foo  # one entry
```

The priority it applies, and why, is in `references/source_priority.md` —
skim it once if a result surprises you (e.g. it picked a Semantic Scholar
abstract over a paywalled proceedings page).

**3. Fetch and actually read `recommended_source`.**
- An `arxiv_html` or `arxiv_pdf` URL → WebFetch it (or Read, for the PDF —
  Read handles PDFs natively; pass `pages` for long papers rather than
  pulling the whole thing at once).
- A `bib_url` or `s2_open_access_pdf` → WebFetch it. If it turns out to be
  paywalled or JS-gated, fall back to the `semantic_scholar` block already in
  the result (abstract + tldr) plus a WebSearch for anything the abstract
  doesn't cover.
- `semantic_scholar_abstract_only` or `web_search_fallback` → you don't have
  full text; say so plainly rather than inventing method details from the
  title alone. The abstract/tldr is enough for a one-line summary but not for
  claims about specific numbers, ablations, or section content.

**4. Ground the answer in where it came from.** When you report what a paper
says, note which source it came from (e.g. "per Section 4.1 of the arXiv
HTML" vs. "per the abstract only — full text wasn't available") so the user
knows how much to trust the specificity of the claim. This matters most when
they're about to cite the paper themselves.

## Batch mode (a whole bibliography)

When handed a `.bib` file or a list of several references, don't process them
one at a time with separate tool round-trips for the resolution step — run
`resolve_paper.py --bib <file>` once to get every entry's recommended source
up front, *then* fetch/read them (this can be sequential or, if you have
subagents available and the list is long, split across a few in parallel).
Semantic Scholar's public API is rate-limited without a key; the script
already retries with backoff, but on a large bibliography (20+ entries
without arXiv ids in the bib itself) expect it to take a couple of minutes —
that's normal, not a hang.

Produce one short entry per paper: title, a sentence or two on what it
actually contributes (not just the title reworded), and the source it came
from. If the user's end goal is something like populating a project's
AGENTS.md/CLAUDE.md with what the codebase's cited work does, match whatever
structure already exists in that file rather than inventing a new one.

## When there's truly nothing to fetch

Some entries won't have arXiv HTML, a working bib URL, or Semantic Scholar
coverage (older papers, non-CS venues, dead links). At that point the honest
answer is "I could only confirm the title/venue/year — full text wasn't
reachable" rather than filling in a plausible-sounding summary. A wrong
citation description is worse than an admittedly thin one.
