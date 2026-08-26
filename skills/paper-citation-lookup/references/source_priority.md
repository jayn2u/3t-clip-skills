# Why `resolve_paper.py` picks sources in this order

1. **arXiv HTML** (`arxiv.org/html/<id>`), if the bib entry (or a Semantic
   Scholar lookup) reveals an arXiv id and the HTML actually returns 200.
   Full text, addressable by section — the best case.

2. **arXiv PDF** (`arxiv.org/pdf/<id>`), if the id exists but HTML 404s (rare
   now, but happens for some older or malformed submissions). Still full
   text, just not section-addressable in the same way; use `Read` with a
   `pages` range for long ones instead of pulling the whole document.

3. **Semantic Scholar arXiv discovery**: if the bib entry has *no* arXiv id
   at all (common for entries that only cite the peer-reviewed venue), the
   script queries the Semantic Scholar Graph API by title before giving up on
   arXiv. Many CV/ML/NLP papers published at ACL/CVPR/NeurIPS/ICML also have
   an arXiv preprint that the bib author simply didn't bother citing — that
   preprint's HTML is still better than a bare proceedings abstract page, so
   it's checked before falling through to the bib's own `url`.

4. **The bib entry's own `url` field** (ACL Anthology, CVF Open Access, MLR
   Press, ACM DL, IEEE Xplore, ScienceDirect, etc.), if no arXiv version
   surfaced. Quality varies a lot here: some of these pages are full text,
   some are abstract-only with a PDF link, some are paywalled. Read what you
   get; don't assume it's full text just because the HTTP status was 200.

5. **Semantic Scholar metadata as a standalone fallback** (open-access PDF
   link if S2 has one, otherwise its abstract + tldr) when nothing else
   resolved. This is metadata, not the paper — treat a summary built only
   from this tier as lower-confidence and say so.

6. **Web search fallback**: if even Semantic Scholar has no record (very old
   papers, non-indexed venues, workshop papers), the script returns a
   suggested search query and expects the caller to run a manual web search
   and use judgment on what turns up.

## Rate limits

`api.semanticscholar.org`'s public search endpoint returns HTTP 429 fairly
readily without an API key. The script retries with a short backoff (up to a
few seconds per call), which is fine for a handful of lookups but adds up
across a large bibliography where most entries lack an arXiv id in the bib
itself. This is expected — let it run rather than assuming something's
broken.
