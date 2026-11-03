import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import bs4


USER_AGENT = "3t-clip-arxiv-paper-reader/0.2.0 (+https://github.com/jayn2u/3t-clip-skills)"
ID_RE = re.compile(r"(?:\d{4}\.\d{4,5}|[a-z][a-z\-]*(?:\.[a-z]{2})?/\d{7})(?:v\d+)?", re.I)
MIN_HTML_CHARS = 2000
DROP = ("refs", "appendix", "captions")


class FetchError(RuntimeError):
    pass


def parse_id(value):
    text = value.strip()
    if re.match(r"^(?:https?://)?(?:www\.|export\.)?arxiv\.org/", text, re.I):
        if not re.match(r"^https?://", text, re.I):
            text = "https://" + text
        path = urllib.parse.urlparse(text).path
        match = re.match(r"^/(?:abs|pdf|html)/(.+?)(?:\.pdf)?/?$", path)
        if not match:
            raise ValueError(f"Unsupported arXiv URL: {value}")
        text = match.group(1)
    text = re.sub(r"^arxiv:", "", text, flags=re.I)
    if not ID_RE.fullmatch(text):
        raise ValueError(f"Not an arXiv identifier: {value}")
    return text


def default_cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "arxiv-paper-reader"


class Fetcher:
    def __init__(self, cache_dir, delay, refresh):
        self.cache_dir = cache_dir
        self.delay = delay
        self.refresh = refresh
        self.last_request = None

    def wait(self):
        if self.last_request is not None:
            remaining = self.delay - (time.monotonic() - self.last_request)
            if remaining > 0:
                time.sleep(remaining)
        self.last_request = time.monotonic()

    def fetch(self, kind, ident):
        stem = ident.replace("/", "_")
        target = self.cache_dir / f"{stem}.{kind}"
        marker = self.cache_dir / f"{stem}.{kind}.url"
        missing = self.cache_dir / f"{stem}.{kind}.missing"
        if not self.refresh:
            if target.is_file() and marker.is_file():
                return target, marker.read_text(encoding="utf-8").strip()
            if missing.is_file():
                return None, None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = f"https://arxiv.org/{kind}/{ident}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        temporary = target.with_name(target.name + ".part")
        for attempt in range(4):
            self.wait()
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    final_url = response.geturl()
                    with temporary.open("wb") as output:
                        shutil.copyfileobj(response, output)
                temporary.replace(target)
                marker.write_text(final_url, encoding="utf-8")
                missing.unlink(missing_ok=True)
                return target, final_url
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    missing.write_text(url, encoding="utf-8")
                    return None, None
                if exc.code not in (429, 503) or attempt == 3:
                    raise FetchError(f"{url}: HTTP {exc.code}") from None
                time.sleep(max(self.delay, 2.0 ** (attempt + 1)))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt == 3:
                    raise FetchError(f"{url}: {exc}") from None
                time.sleep(max(self.delay, 2.0 ** (attempt + 1)))
            finally:
                temporary.unlink(missing_ok=True)
        raise FetchError(f"{url}: retries exhausted")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def sec_title(sec):
    h = sec.find(["h2"], recursive=False) or sec.find("h2")
    return h.get_text(" ", strip=True) if h else ""


def caption_norm(text):
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"^\s*Fig\.?(?=\s*\d)", "Figure", text, flags=re.I)
    return norm(text)


def h9_article(raw):
    soup = bs4.BeautifulSoup(raw, "html.parser")
    art = soup.find("article")
    if art is None:
        return None, 0
    errors = len(art.select(".ltx_ERROR"))
    for t in art.find_all(["script", "style", "nav", "button"]):
        t.decompose()
    for sel in [".ltx_page_navbar", ".ltx_page_footer", ".ltx_role_header", ".ltx_bibliography", "section.ltx_appendix", "figcaption", ".ltx_note"]:
        for t in art.select(sel):
            t.decompose()
    for m in art.find_all("math"):
        if m.get("display") == "block":
            m.replace_with("\n$$" + (m.get("alttext") or "") + "$$\n")
        else:
            for a in m.find_all("annotation"):
                a.decompose()
    for tab in art.find_all("table", class_="ltx_tabular"):
        rows = []
        for tr in tab.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"]):
                cells.append(td.get_text(" ", strip=True).replace("|", "/"))
                cells += [""] * (int(td.get("colspan", 1) or 1) - 1)
            if cells:
                rows.append(cells)
        if not rows:
            tab.decompose()
            continue
        nc = max(len(r) for r in rows)
        lines = ["|" + "|".join(r + [""] * (nc - len(r))) + "|" for r in rows]
        lines.insert(1, "|" + "|".join(["-"] * nc) + "|")
        tab.replace_with(bs4.BeautifulSoup("<pre>\n" + "\n".join(lines) + "\n</pre>", "html.parser"))
    for b in art.find_all(["p", "div", "h1", "h2", "h3", "h4", "li", "pre", "tr", "figure"]):
        b.insert_after("\n")
    return art, errors


def node_text(node):
    txt = re.sub(r"[ \t]+", " ", node.get_text(" "))
    return re.sub(r"\n\s*\n+", "\n\n", txt).strip()


def html_sections(art):
    sections = []
    for sec in art.find_all("section", class_="ltx_section"):
        sections.append((re.sub(r"\s+", " ", sec_title(sec)).strip(), sec))
    return sections


def select_sections(art, queries):
    picked = []
    wanted = [q.strip().lower() for q in queries if q.strip()]
    if any(q == "abstract" for q in wanted):
        abstract = art.find(class_="ltx_abstract")
        if abstract is not None:
            picked.append(node_text(abstract))
    for title, sec in html_sections(art):
        lower = title.lower()
        number = re.match(r"^(\d+|[A-Z])\b", title)
        for q in wanted:
            if q == "abstract":
                continue
            if (number and number.group(1).lower() == q) or (not q.isdigit() and q in lower):
                picked.append(node_text(sec))
                break
    return picked


def html_meta(raw):
    art = bs4.BeautifulSoup(raw, "html.parser").find("article")
    if art is None:
        return [], []
    secs = [sec_title(s) for s in art.find_all("section", class_="ltx_section")]
    apps = [sec_title(s) for s in art.find_all("section", class_="ltx_appendix")]
    return secs, apps


def pdf_captions(raw, tables_only=False):
    art = bs4.BeautifulSoup(raw, "html.parser").find("article")
    if art is None:
        return []
    captions = []
    for caption in art.find_all("figcaption"):
        if tables_only and not any(p.name == "figure" and "ltx_table" in p.get("class", []) for p in caption.parents):
            continue
        parents = [p for p in caption.parents if p.name == "section"]
        if any("ltx_bibliography" in p.get("class", []) for p in caption.parents):
            continue
        if any("ltx_appendix" in p.get("class", []) for p in parents):
            continue
        for annotation in caption.find_all("annotation"):
            annotation.decompose()
        captions.append(caption_norm(caption.get_text(" ", strip=True)))
    return captions


def find_heading(lines, title, start=0):
    t = norm(re.sub(r"^(Appendix\s+)?[A-Z0-9]+\.?\s+", "", title))
    if not t:
        return None
    for k in range(start, len(lines)):
        raw = lines[k].strip()
        if len(raw) > 90 or not raw:
            continue
        cands = {norm(raw), norm(re.sub(r"^(Appendix\s+)?([A-Z]|[0-9]{1,2})(\.|\s)\s*", "", raw))}
        if t in cands:
            return k
    return None


def trim_pdf(ptxt, secs, apps, table_captions=(), captions=()):
    L = ptxt.split("\n")
    sec_idx = []
    pos = 0
    for s in secs:
        k = find_heading(L, s, pos)
        sec_idx.append(k)
        if k is not None:
            pos = k + 1
    last = max([k for k in sec_idx if k is not None], default=0)
    ref = next((k for k in range(last, len(L)) if re.fullmatch(r"\s*(References|REFERENCES|Bibliography|R EFERENCES)\s*", L[k])), None)
    app_idx = [i for i in (find_heading(L, a, last + 1) for a in apps) if i is not None]
    app0 = min(app_idx) if app_idx else None
    keep = [True] * len(L)

    def cut(a, b):
        for k in range(a, min(b, len(L))):
            keep[k] = False

    if ref is not None:
        end = app0 if app0 and app0 > ref else len(L)
        cut(ref, end)
    if app0 is not None:
        end = ref if ref and ref > app0 else len(L)
        cut(app0, end)
    if table_captions:
        boundaries = {i for i in sec_idx + app_idx + [ref, app0, len(L)] if i is not None}
        boundaries.update(i for i, line in enumerate(L) if "\f" in line or re.match(r"\s*(?:Table|Figure|Fig\.)\s*\d+\b", line))
        for i, line in enumerate(L):
            if re.match(r"\s*Table\s*\d+\b", line) and any(title.startswith(caption_norm(line)) for title in table_captions):
                end = min(b for b in boundaries if b > i)
                for k in range(i, end):
                    keep[k] = True
    txt = "\n".join(l for l, kp in zip(L, keep) if kp)
    paras = re.split(r"\n\s*\n", txt)
    titles = tuple(caption_norm(title) for title in (*captions, *table_captions))
    kept = []
    for paragraph in paras:
        lines = paragraph.split("\n")
        start = 0
        while start < len(lines):
            if re.match(r"\s*(Figure|Fig\.|Table)\s*\d+\b", lines[start]):
                beginning = caption_norm(lines[start])
                matches = [title for title in titles if beginning and title.startswith(beginning)]
                if not matches and not re.match(r"\s*(Figure|Fig\.|Table)\s*\d+[.:]", lines[start]):
                    start += 1
                    continue
                end = start
                accumulated = ""
                while end < len(lines):
                    line = lines[end]
                    if end > start and ("\f" in line or re.match(r"\s*(Figure|Fig\.|Table)\s*\d+\b", line)):
                        break
                    candidate = caption_norm(accumulated + line)
                    if matches:
                        remaining = [title for title in matches if candidate and candidate in title]
                        if not remaining:
                            break
                        matches = remaining
                    elif end >= start + 8 or re.fullmatch(r"\s*[+−-]?\d[\d,.]*%?\s*", line) or re.fullmatch(r"\s*(?:\S+\s+){0,3}[+−-]?\d[\d,.]*%?(?:\s+[+−-]?\d[\d,.]*%?)+\s*", line):
                        break
                    accumulated += line
                    end += 1
                if end == start:
                    start += 1
                    continue
                del lines[start:end]
            else:
                start += 1
        if lines:
            kept.append("\n".join(lines))
    stats = dict(pdf_sections_found=sum(i is not None for i in sec_idx), pdf_sections_total=len(secs), pdf_references_found=ref is not None)
    return "\n\n".join(kept), stats


def pdf_to_text(path):
    if shutil.which("pdftotext") is None:
        raise FetchError("pdftotext is required for the PDF fallback; install poppler-utils (poppler) and retry")
    result = subprocess.run(["pdftotext", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True)
    if result.returncode:
        raise FetchError(f"pdftotext failed for {path.name} (exit {result.returncode})")
    return result.stdout


def count_tokens(text):
    try:
        import tiktoken
    except ImportError:
        raise FetchError("--count-tokens needs tiktoken; add --with tiktoken==0.14.0 to the uv run command") from None
    return len(tiktoken.get_encoding("o200k_base").encode(text, disallowed_special=()))


def read_paper(ident, fetcher, force_pdf=False, sections=(), max_latex_errors=100):
    info = dict(arxiv_id=ident, path=None, source_url=None, fallback_reason=None)
    html_path, html_url = fetcher.fetch("html", ident)
    raw = None
    art = None
    if html_path is None:
        info["fallback_reason"] = "no arXiv HTML version (HTTP 404)"
    else:
        raw = html_path.read_text(encoding="utf-8", errors="replace")
        art, errors = h9_article(raw)
        info["latex_errors"] = errors
        if art is None:
            info["fallback_reason"] = "arXiv HTML has no article element (conversion broken)"
        else:
            body = node_text(art)
            if len(body) < MIN_HTML_CHARS:
                info["fallback_reason"] = f"cleaned HTML is only {len(body)} characters (conversion broken)"
            elif errors > max_latex_errors:
                info["fallback_reason"] = f"arXiv HTML has {errors} LaTeX conversion errors (more than {max_latex_errors})"
    if force_pdf and info["fallback_reason"] is None:
        info["fallback_reason"] = "PDF path forced with --pdf"
    if info["fallback_reason"] is None:
        info["path"] = "html"
        info["source_url"] = html_url
        info["sections"] = [title for title, _ in html_sections(art)]
        if sections:
            picked = select_sections(art, sections)
            if not picked:
                raise FetchError(f"no section matched {list(sections)}; available: {info['sections']}")
            text = "\n\n".join(picked)
        else:
            text = node_text(art)
        return text, info
    pdf_path, pdf_url = fetcher.fetch("pdf", ident)
    if pdf_path is None:
        raise FetchError(f"{ident}: neither usable arXiv HTML nor a PDF is available")
    ptxt = pdf_to_text(pdf_path)
    if raw is not None:
        secs, apps = html_meta(raw)
        text, stats = trim_pdf(ptxt, secs, apps, table_captions=pdf_captions(raw, tables_only=True), captions=pdf_captions(raw))
        info["trim_metadata"] = "html"
    else:
        text, stats = trim_pdf(ptxt, [], [])
        info["trim_metadata"] = "none"
    info.update(stats)
    info["path"] = "pdf"
    info["source_url"] = pdf_url
    if sections:
        info["section_filter"] = "ignored on the PDF path; full trimmed text returned"
    return text.strip(), info


def header(info):
    keys = ["arxiv_id", "path", "source_url", "fallback_reason", "trim_metadata", "chars", "tokens_o200k", "section_filter"]
    parts = [f"{k}={json.dumps(info[k], ensure_ascii=False) if isinstance(info[k], str) and ' ' in info[k] else info[k]}" for k in keys if info.get(k) is not None]
    return "[arxiv-paper-reader] " + " ".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read arXiv papers as H9-cleaned HTML text, falling back to trimmed pdftotext output")
    parser.add_argument("papers", nargs="+", help="arXiv ids or arxiv.org abs/html/pdf URLs, optionally versioned")
    parser.add_argument("--pdf", action="store_true", help="force the trimmed-PDF fallback path")
    parser.add_argument("--section", action="append", default=[], help="HTML path only: keep sections whose number or title matches; repeatable; 'abstract' selects the abstract")
    parser.add_argument("--outline", action="store_true", help="print only the section titles")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--out-dir", type=Path, help="write each paper to <out-dir>/<id>.txt and print only headers")
    parser.add_argument("--count-tokens", action="store_true", help="report o200k_base token counts (needs tiktoken)")
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--no-cache", action="store_true", help="download into a temporary directory that is removed on exit")
    parser.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between arXiv requests")
    parser.add_argument("--max-latex-errors", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        idents = [parse_id(p) for p in args.papers]
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    temporary = tempfile.TemporaryDirectory(prefix="arxiv-paper-reader-") if args.no_cache else None
    cache_dir = Path(temporary.name) if temporary else (args.cache_dir or default_cache_dir())
    fetcher = Fetcher(cache_dir, args.delay, args.refresh)
    status = 0
    results = []
    try:
        for ident in idents:
            try:
                text, info = read_paper(ident, fetcher, args.pdf, args.section, args.max_latex_errors)
            except FetchError as exc:
                print(f"Error: {ident}: {exc}", file=sys.stderr)
                status = 1
                continue
            if args.outline:
                text = "\n".join(info.get("sections") or ["(no section outline on the PDF path)"])
            info["chars"] = len(text)
            if args.count_tokens:
                try:
                    info["tokens_o200k"] = count_tokens(text)
                except FetchError as exc:
                    print(f"Error: {exc}", file=sys.stderr)
                    return 1
            if args.out_dir:
                args.out_dir.mkdir(parents=True, exist_ok=True)
                target = args.out_dir / (ident.replace("/", "_") + (".json" if args.format == "json" else ".txt"))
                info["output_file"] = str(target)
                if args.format == "json":
                    target.write_text(json.dumps(dict(info, text=text), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                else:
                    target.write_text(text + "\n", encoding="utf-8")
            if args.format == "json":
                results.append(info if args.out_dir else dict(info, text=text))
            else:
                print(header(info) + (f" output_file={info['output_file']}" if args.out_dir else ""))
                if not args.out_dir:
                    print()
                    print(text)
                    print()
        if args.format == "json":
            print(json.dumps(results, ensure_ascii=False, indent=2))
    finally:
        if temporary:
            temporary.cleanup()
    return status


if __name__ == "__main__":
    sys.exit(main())
