# Token evidence for arxiv-paper-reader

Source: [jayn2u/arxiv-html-vs-pdf-tokens](https://github.com/jayn2u/arxiv-html-vs-pdf-tokens).
The cleaning code in `scripts/read_arxiv.py` is a port of that repository's
H9 HTML cleaner and its trimmed-PDF (`caption` rule) variant.

## What the study found

- Raw arXiv HTML costs about 580% more tokens than pdftotext output, so raw
  HTML should never be passed to a model as is.
- Among the tested representations, H9-cleaned HTML had the lowest
  cost-of-pass: 18,540 tokens versus 24,472 for trimmed PDF text (about 24%
  lower) and about 48% lower than uploading the PDF file. These differences
  were significant after Holm correction.
- H9 preserved 38 of 39 block equations and 62 of 66 tables in the audited
  sample.
- No accuracy difference between representations was statistically
  significant. The evidence supports a token-cost advantage, not an accuracy
  advantage.
- Limits: a single model, 16 papers, and rule-based grading.

## Reproduction check (o200k_base, tiktoken 0.14.0)

Counts from this skill's script on the source study's 10 papers, compared
with that repository's `results/representations.csv` (`html_h9` and
`pdf_trimmed_h9`; the PDF column was produced with `--pdf`):

| arXiv id | html path | source `html_h9` | pdf path | source `pdf_trimmed_h9` |
| --- | --- | --- | --- | --- |
| 2103.00020 | 23,268 | 23,268 | 28,243 | 28,244 |
| 2303.12501 | 8,992 | 8,992 | 9,482 | 9,483 |
| 2308.10045 | 10,708 | 10,708 | 10,435 | 10,435 |
| 2010.11929 | 7,272 | 7,272 | 7,949 | 7,949 |
| 2402.03241 | 9,102 | 9,102 | 9,328 | 9,328 |
| 2308.09911 | 12,053 | 12,053 | 12,186 | 12,186 |
| 2305.13653 | 9,253 | 9,253 | 8,846 | 8,846 |
| 2212.00794 | 9,700 | 9,700 | 10,318 | 10,318 |
| 2106.09685 | 11,612 | 11,612 | 12,022 | 12,022 |
| 2109.01134 | 9,435 | 9,435 | 11,812 | 11,812 |

The two one-token differences come from stripping the final newline in the
script's output. Counts can drift when arXiv publishes a new version of a
paper or regenerates its HTML.
