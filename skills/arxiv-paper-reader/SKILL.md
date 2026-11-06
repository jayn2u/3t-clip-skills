---
name: arxiv-paper-reader
description: Reads the full text of an arXiv paper from an arXiv id or arxiv.org URL (abs, html, or pdf, versioned or not) and returns compact cleaned text, optionally only the sections you ask for. Fetches the arXiv HTML render and cleans it with the H9 rule set; when there is no HTML version or the conversion is broken it falls back to pdftotext output trimmed of references, appendix, and captions, and always reports which path it used. Use this whenever you need to read, summarize, quote, or check a claim in an arXiv paper, including when another skill such as paper-citation-lookup or prior-research-brief needs an arXiv paper's full text, instead of opening the arXiv HTML or PDF with a generic web or PDF tool.
---

# arXiv Paper Reader

## What it does

`scripts/read_arxiv.py` turns one or more arXiv papers into model-friendly
text:

1. **HTML path (default).** Downloads `https://arxiv.org/html/<id>` and
   applies H9: drops scripts, navigation, headers and footers, the
   bibliography, the appendix, figure captions, and footnotes; keeps block
   equations as `$$...$$` LaTeX; keeps inline math as its text; turns LaTeX
   tables into Markdown tables.
2. **PDF fallback.** If arXiv has no HTML version (HTTP 404), the page has
   no article body, the cleaned text is implausibly short, or the page has
   more than `--max-latex-errors` LaTeX conversion errors, it downloads
   `https://arxiv.org/pdf/<id>`, runs `pdftotext -enc UTF-8`, and trims it
   like the source study's trimmed-PDF variant: it cuts the References
   section and the appendix and removes figure/table caption paragraphs while
   keeping table bodies. When the HTML page exists, its section, appendix,
   and caption metadata guide the trim (`trim_metadata=html`); otherwise only
   text patterns are used (`trim_metadata=none`).

Every result starts with a header line such as:

```
[arxiv-paper-reader] arxiv_id=hep-th/9711200v3 path=pdf source_url=https://arxiv.org/pdf/hep-th/9711200v3 fallback_reason="no arXiv HTML version (HTTP 404)" trim_metadata=none chars=43979
```

Always tell the user which path was used (`path=html` or `path=pdf`) and,
for the PDF path, the `fallback_reason`, so they know how the text was
produced.

## Running it

Run from this skill's directory with `uv` (the only dependency is a pinned
BeautifulSoup in `scripts/requirements.txt`):

```bash
uv run --no-project --with-requirements scripts/requirements.txt python scripts/read_arxiv.py 2103.00020
uv run --no-project --with-requirements scripts/requirements.txt python scripts/read_arxiv.py https://arxiv.org/abs/2303.12501v2 --outline
uv run --no-project --with-requirements scripts/requirements.txt python scripts/read_arxiv.py 2303.12501 --section abstract --section 3
uv run --no-project --with-requirements scripts/requirements.txt python scripts/read_arxiv.py 2010.11929 --pdf
uv run --no-project --with-requirements scripts/requirements.txt python scripts/read_arxiv.py 2103.00020 2303.12501 --out-dir /tmp/arxiv-reader-out
uv run --no-project --with-requirements scripts/requirements.txt --with tiktoken==0.14.0 python scripts/read_arxiv.py 2103.00020 --count-tokens
```

Options:

- `--outline` prints only the top-level section titles. For a long paper,
  read the outline first and then pull only the sections you need with
  `--section`.
- `--section S` (repeatable, HTML path only) keeps sections whose number
  (`3`, `4.2`) or title (case-insensitive substring) matches; `abstract`
  selects the abstract. Section filtering does not apply on the PDF path, so
  the full trimmed text is returned there.
- `--pdf` forces the PDF fallback.
- `--format json` returns a list of objects with `arxiv_id`, `path`,
  `source_url`, `fallback_reason`, `sections`, `chars`, and `text`.
- `--out-dir DIR` writes each paper to `DIR/<id>.txt` and prints only the
  header lines. Use it for long papers or batches, then read the files in
  chunks.
- `--count-tokens` adds an o200k_base token count (needs the extra
  `--with tiktoken==0.14.0`).
- `--cache-dir`, `--no-cache`, `--refresh`, `--delay` control downloads.

Exit code 2 means the input was not an arXiv id; exit code 1 means the paper
could not be fetched or converted. Report that plainly instead of
summarizing from memory.

## Requirements, network, and cache

- `uv` is required. The PDF fallback also needs `pdftotext` from poppler
  (`poppler-utils` on Debian/Ubuntu, `brew install poppler` on macOS); if it
  is missing the script says so and the HTML path still works.
- The script contacts only `arxiv.org`, sends an identifying User-Agent,
  waits `--delay` seconds (default 3) between requests, and retries on
  HTTP 429/503.
- Downloads are cached under `$XDG_CACHE_HOME/arxiv-paper-reader` (default
  `~/.cache/arxiv-paper-reader`), or a temporary directory removed on exit
  with `--no-cache`. Never copy downloaded papers or extracted text into a
  repository.

## How to use the text

- Ground what you report in the text: cite section numbers, equation, or
  table content from the output, and say which path produced it.
- The HTML path drops figure captions, the appendix, and references, and the
  PDF path drops references, appendix, and captions. If the user asks about
  an appendix result, a figure caption, or the reference list, say that this
  reader removes those parts and open the arXiv page directly for that part.
- PDF-path text has no LaTeX for equations and may break tables or
  multi-column layouts; be more careful when quoting numbers from it.

## Evidence behind the defaults

The cleaning rules come from a study in
[jayn2u/arxiv-html-vs-pdf-tokens](https://github.com/jayn2u/arxiv-html-vs-pdf-tokens),
summarized in `references/token_evidence.md`. In short: H9-cleaned HTML used
fewer tokens than the trimmed PDF text (cost-of-pass about 24% lower, about
48% lower than uploading the PDF file), and raw HTML is far more expensive
than either. No accuracy advantage was shown: answer accuracy differences
between representations were not statistically significant, and the study
used one model, 16 papers, and rule-based grading. Treat the choice as a
token-cost optimization, not a quality guarantee.
