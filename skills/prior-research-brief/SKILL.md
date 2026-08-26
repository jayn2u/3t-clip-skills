---
name: prior-research-brief
description: Lightweight personal workflow for "what's the prior work / related research here?" requests — much lighter than a full literature-review pipeline. Use when the user asks you to look into 선행연구, related work, or prior research for something they're building or writing, wants a quick map of what's already been done on a topic before they start, or asks "has anyone already done X" / "what papers should I be citing for Y." This is deliberately a fast, personal-scale pass (a handful of papers, a short synthesis) — not the multi-agent academic-research-skills pipeline (deep-research/lit-review/3w-scan), which is the right tool instead when the user explicitly wants a formal literature review, systematic review, or a full paper section. If the user names a specific paper or bibtex/reference list rather than asking about a topic broadly, use paper-citation-lookup directly instead of this skill.
---

# Prior Research Brief

## What this is for

Sometimes you just want to know "what's already out there" before writing a
paragraph, picking a baseline, or deciding a direction is even novel — not a
formally-sectioned literature review with a synthesis_agent and a
research_architect_agent behind it. This skill is the fast, personal-scale
version: find a handful of the most relevant papers, actually read what each
one contributes (not just its title), and hand back a short brief.

If the request is really asking for a rigorous, citable literature-review
section, a systematic review, or a full research pipeline, say so and defer
to the heavier `deep-research` / `lit-review` skills instead — don't try to
stretch this lightweight pass to cover that job, and don't silently run the
heavy pipeline when the user just wanted a quick orientation.

## Workflow

1. **Clarify the topic, not the paper.** This skill is for "what's the prior
   work on X" — a topic, method, or problem — as opposed to "what does this
   specific paper say," which is `paper-citation-lookup`'s job. If the user
   already handed you a bibtex file or specific citations, use that skill
   directly instead.

2. **Find candidate papers.** Use WebSearch (arXiv, Google Scholar-style
   queries, or Semantic Scholar's search API) to find 4–8 papers that look
   genuinely relevant — prefer recent, well-cited, or clearly on-topic work
   over padding the list. If the user already has a codebase or paper draft
   with a related-work section or existing citations, check there first
   (grep for `\cite`, a `.bib` file, or an existing "Related Work" section)
   before searching cold — they may already have half the answer.

3. **Read each candidate, don't just list titles.** For each paper, hand off
   to `paper-citation-lookup`'s approach: prefer the arXiv HTML source when
   it exists, so what you report is grounded in the actual method/results
   rather than a title-shaped guess. A brief made of unread titles is not
   more useful than the search results page itself.

4. **Synthesize, don't just enumerate.** Group papers by approach or angle
   rather than a flat list, and say where they agree, where they diverge, and
   where there's an evident gap relative to what the user is doing. That gap
   is usually the actual point of asking about prior work — flag it
   explicitly rather than leaving the user to infer it from a list.

5. **Keep it short.** A prior-research brief is a few paragraphs or a short
   table, not a paper. If the user wants more depth after seeing it, that's
   the moment to reach for the heavier ARS pipeline — not before.

## Output shape

Default to something like:

```
## What's already been done on [topic]

**[Approach cluster A]** — [paper], [paper]: [what they do, one line each]
**[Approach cluster B]** — [paper]: [what it does]

**Gap / where this differs from your work:** [one or two sentences]
```

Adjust freely to the actual request — this is a starting shape, not a
template to fill in mechanically.
