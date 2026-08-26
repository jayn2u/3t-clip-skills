#!/usr/bin/env python3
"""Resolve the best source to read for one or more cited papers.

Given a .bib file, a single bibtex entry, an arXiv id/URL, a DOI, or a bare
title, this script figures out (via cheap HTTP status checks, not full
downloads) which source is worth fetching next, in priority order:

  1. arXiv HTML  (arxiv.org/html/<id>)      -- richest, section-addressable
  2. arXiv PDF   (arxiv.org/pdf/<id>)       -- fallback when HTML 404s
  3. the bib entry's own `url` field         -- publisher/anthology page
  4. Semantic Scholar Graph API              -- metadata + abstract + tldr,
                                                 and sometimes reveals an
                                                 arXiv id the bib didn't have

It does NOT read or summarize the paper -- that qualitative work belongs to
whoever calls this script (fetch the returned URL with WebFetch/Read and do
the actual reading). This script only saves round-trips spent guessing
whether a URL exists.

Usage:
  python resolve_paper.py --bib references.bib            # every entry
  python resolve_paper.py --bib references.bib --key foo2021bar
  python resolve_paper.py --arxiv 2401.12345
  python resolve_paper.py --title "Learning Transferable Visual Models..."
  python resolve_paper.py --url https://arxiv.org/abs/2401.12345

Output: JSON to stdout, one object per paper, or a JSON array for --bib.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
S2_FIELDS = "title,abstract,tldr,externalIds,url,openAccessPdf,year,citationCount"


def http_status(url, timeout=8):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "curl/8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def http_get_json(url, timeout=10, retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 + attempt * 2)
                continue
            return {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)}
    return {"error": "exhausted retries"}


def extract_arxiv_id(text):
    if not text:
        return None
    m = ARXIV_ID_RE.search(text)
    return m.group(1) if m else None


def parse_bibtex(path):
    """Minimal brace-balanced bibtex splitter. Good enough for standard
    entries; does not handle exotic nested-comment edge cases."""
    raw = open(path, encoding="utf-8").read()
    entries = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == "@":
            j = raw.find("{", i)
            if j == -1:
                break
            entry_type = raw[i + 1 : j].strip().lower()
            depth = 1
            k = j + 1
            while k < n and depth > 0:
                if raw[k] == "{":
                    depth += 1
                elif raw[k] == "}":
                    depth -= 1
                k += 1
            body = raw[j + 1 : k - 1]
            key, _, rest = body.partition(",")
            fields = {}
            for fm in re.finditer(
                r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", rest
            ):
                fields[fm.group(1).lower()] = re.sub(r"\s+", " ", fm.group(2)).strip()
            entries.append({"type": entry_type, "key": key.strip(), **fields})
            i = k
        else:
            i += 1
    return entries


def resolve_one(fields):
    """fields: dict that may contain title, eprint, archiveprefix, url, doi, key."""
    key = fields.get("key", fields.get("title", "unknown"))
    title = fields.get("title", "")
    arxiv_id = None

    # Only trust an eprint field when it's explicitly tagged as arXiv, and
    # only trust a URL's digits as an arXiv id when the URL is actually on
    # arxiv.org -- otherwise a DOI or proceedings URL containing an
    # incidental \d{4}\.\d{4,5} substring (e.g. a DOI ending in ...2026.132885)
    # gets misread as an arXiv id.
    if fields.get("archiveprefix", "").lower() == "arxiv" and fields.get("eprint"):
        arxiv_id = extract_arxiv_id(fields["eprint"])
    if not arxiv_id and "arxiv.org" in fields.get("url", ""):
        arxiv_id = extract_arxiv_id(fields["url"])

    result = {
        "key": key,
        "title": title,
        "arxiv_id": arxiv_id,
        "bib_url": fields.get("url"),
        "doi": fields.get("doi"),
        "recommended_source": None,
        "candidates": [],
    }

    if arxiv_id:
        html_url = f"https://arxiv.org/html/{arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        html_status = http_status(html_url)
        result["candidates"].append(
            {"type": "arxiv_html", "url": html_url, "status": html_status}
        )
        if html_status == 200:
            result["recommended_source"] = html_url
        else:
            pdf_status = http_status(pdf_url)
            result["candidates"].append(
                {"type": "arxiv_pdf", "url": pdf_url, "status": pdf_status}
            )
            if pdf_status == 200:
                result["recommended_source"] = pdf_url
            # else: a confirmed arXiv id with neither HTML nor PDF reachable
            # is unusual (wrong/withdrawn id) -- fall through to the next
            # tiers below rather than guessing an /abs/ URL that may 404 too.

    # Even when the bib entry has no arXiv id, many conference papers were
    # also posted to arXiv -- and arXiv HTML beats a bare proceedings
    # abstract page, so check Semantic Scholar for an arXiv id BEFORE
    # falling back to the bib's own url.
    if not result["recommended_source"] and title:
        s2 = http_get_json(
            f"{S2_SEARCH_URL}?query={urllib.parse.quote(title)}&fields={S2_FIELDS}&limit=1"
        )
        papers = s2.get("data") if isinstance(s2, dict) else None
        if papers:
            p = papers[0]
            result["semantic_scholar"] = p
            ext = p.get("externalIds") or {}
            if not arxiv_id and ext.get("ArXiv"):
                candidate_id = ext["ArXiv"]
                html_url = f"https://arxiv.org/html/{candidate_id}"
                html_status = http_status(html_url)
                result["candidates"].append(
                    {"type": "arxiv_html_via_s2", "url": html_url, "status": html_status}
                )
                if html_status == 200:
                    result["arxiv_id"] = candidate_id
                    result["recommended_source"] = html_url
        else:
            result["semantic_scholar"] = s2 if isinstance(s2, dict) else None

    if not result["recommended_source"] and fields.get("url"):
        status = http_status(fields["url"])
        result["candidates"].append(
            {"type": "bib_url", "url": fields["url"], "status": status}
        )
        if status and status < 400:
            result["recommended_source"] = fields["url"]

    if not result["recommended_source"]:
        s2 = result.get("semantic_scholar")
        if isinstance(s2, dict) and s2.get("openAccessPdf", {}).get("url"):
            result["recommended_source"] = s2["openAccessPdf"]["url"]
            result["candidates"].append(
                {"type": "s2_open_access_pdf", "url": result["recommended_source"]}
            )
        elif isinstance(s2, dict) and s2.get("abstract"):
            result["recommended_source"] = "semantic_scholar_abstract_only"

    if not result["recommended_source"]:
        result["recommended_source"] = "web_search_fallback"
        result["web_search_query"] = title or key

    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bib", help="path to a .bib file")
    ap.add_argument("--key", help="only resolve this bibtex key (used with --bib)")
    ap.add_argument("--arxiv", help="a bare arXiv id, e.g. 2401.12345")
    ap.add_argument("--title", help="a paper title to search for")
    ap.add_argument("--url", help="a URL (arxiv abs/pdf, or any paper page)")
    args = ap.parse_args()

    if args.bib:
        entries = parse_bibtex(args.bib)
        if args.key:
            entries = [e for e in entries if e["key"] == args.key]
            if not entries:
                print(json.dumps({"error": f"key {args.key} not found"}))
                sys.exit(1)
        results = [resolve_one(e) for e in entries]
        print(json.dumps(results, indent=2))
    elif args.arxiv or args.title or args.url:
        fields = {}
        if args.arxiv:
            fields = {"eprint": args.arxiv, "archiveprefix": "arxiv", "key": args.arxiv}
        elif args.url:
            fields = {"url": args.url, "key": args.url}
        if args.title:
            fields["title"] = args.title
            fields.setdefault("key", args.title)
        print(json.dumps(resolve_one(fields), indent=2))
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
