#!/usr/bin/env python3
"""Fetch, cache and search the ratified RISC-V specifications at docs.riscv.org.

Design notes for anyone reading or extending this:

* Standard library only. The skill must run on a bare machine with no pip install.
* Versions are never hardcoded. Each spec publishes a tiny redirect stub at
  /reference/<slug>/index.html whose meta-refresh names the current version.
  Reading that stub costs ~400 bytes, so re-checking every spec is cheap and the
  cache only refills when a version actually changes.
* Pages are fetched directly. The versioned pages are static HTML, so no headless
  browser is needed. r.jina.ai stays available as a fallback (--jina) for the rare
  page that resists direct fetching.
* Heading anchors are preserved as {#anchor} markers, because a citation is only
  useful if it points at the exact subsection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "references" / "sources.json"
CACHE = Path(os.environ.get("RISCV_SPEC_CACHE", Path.home() / ".cache" / "riscv-spec"))
UA = "riscv-spec-skill/1.0 (+https://github.com/riscv/riscv-unified-db)"
TIMEOUT = 30


# --------------------------------------------------------------------------- io


def load_manifest() -> dict:
    with MANIFEST.open() as fh:
        return json.load(fh)


def http_get(url: str, use_jina: bool = False) -> str:
    """Return the body of url, or raise RuntimeError with a readable message."""
    target = url
    headers = {"User-Agent": UA}
    if use_jina:
        target = "https://r.jina.ai/" + url
        key = os.environ.get("JINA_API_KEY")
        if key:
            headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(target, headers=headers)
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8", "replace")
            # Jina answers 200 even when the upstream page failed, so check the body.
            if use_jina and body.lstrip().startswith("Title: Page not found"):
                raise RuntimeError("jina reports upstream 404 for " + url)
            if use_jina and "Warning: Target URL returned error" in body[:600]:
                raise RuntimeError("jina reports upstream error for " + url)
            return body
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} for {target}") from exc
        except Exception as exc:  # noqa: BLE001 - retry once on transport errors
            last = exc
            time.sleep(1)
    raise RuntimeError(f"cannot fetch {target}: {last}")


def fetch_page(url: str, jina: bool) -> tuple[str, str]:
    """Return (body, mode). Try a direct fetch first, then fall back to Jina."""
    if not jina:
        try:
            return http_get(url), "html"
        except RuntimeError as exc:
            print(f"  direct fetch failed ({exc}); trying r.jina.ai", file=sys.stderr)
    return http_get(url, use_jina=True), "jina"


# ----------------------------------------------------------------------- parsing


class _Text(HTMLParser):
    """Turn an Antora page into markdown-ish text, keeping heading anchors."""

    SKIP = {"script", "style", "nav", "header", "footer", "aside", "svg", "form"}
    BLOCK = {"p", "li", "td", "th", "dt", "dd", "figcaption"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.buf: list[str] = []
        self.skip = 0
        self.heading: str | None = None
        self.anchor: str | None = None
        self.pre = 0
        self.list_item = False

    # -- helpers
    def _flush(self) -> None:
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.buf)).strip()
        self.buf.clear()
        if not text:
            self.heading = None
            self.anchor = None
            self.list_item = False
            return
        if self.heading:
            level = int(self.heading[1])
            suffix = f" {{#{self.anchor}}}" if self.anchor else ""
            self.parts.append("\n" + "#" * level + " " + text + suffix + "\n")
        elif self.list_item:
            self.parts.append("- " + text)
        else:
            self.parts.append(text)
        self.heading = None
        self.anchor = None
        self.list_item = False

    # -- HTMLParser API
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        attr = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush()
            self.heading = tag
            self.anchor = attr.get("id")
        elif tag == "pre":
            self._flush()
            self.pre += 1
            self.parts.append("```")
        elif tag == "li":
            self._flush()
            self.list_item = True
        elif tag in self.BLOCK:
            self._flush()
        elif tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "pre":
            self._flush()
            self.pre = max(0, self.pre - 1)
            self.parts.append("```")
        elif tag in self.BLOCK or tag.startswith("h") and tag[1:].isdigit():
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        self.buf.append(data)

    def result(self) -> str:
        self._flush()
        out = "\n".join(p for p in self.parts if p.strip())
        return re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"


class _Links(HTMLParser):
    """Collect same-component chapter links from an Antora page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        if not href.endswith(".html"):
            return
        if "://" in href or href.startswith(("#", "..", "/")):
            return
        self.hrefs.append(href.split("#")[0])


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    return parser.result()


def chapter_links(html: str) -> list[str]:
    parser = _Links()
    parser.feed(html)
    seen: list[str] = []
    for href in parser.hrefs:
        if href not in seen:
            seen.append(href)
    return seen


# ----------------------------------------------------------------------- version


def resolve_version(base: str, slug: str, jina: bool = False) -> str:
    """Read the redirect stub and return the current version folder, e.g. 'v3.0'."""
    body, _ = fetch_page(f"{base}/{slug}/index.html", jina)
    match = re.search(r'url\s*=\s*["\']?([^"\'>\s]+)', body, re.I)
    if match:
        first = match.group(1).strip().split("/")[0]
        if first and first not in ("index.html",):
            return first
    match = re.search(r"Redirecting to .*?\s(v[\w.\-]+)", body, re.I)
    if match:
        return match.group(1)
    raise RuntimeError(f"cannot determine version for {slug}")


# ------------------------------------------------------------------------- cache


def spec_dir(slug: str, version: str) -> Path:
    return CACHE / slug / version


def write_meta(slug: str, version: str, pages: dict) -> None:
    path = CACHE / slug / "meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "version": version,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pages": pages,
    }
    path.write_text(json.dumps(meta, indent=2) + "\n")


def read_meta(slug: str) -> dict | None:
    path = CACHE / slug / "meta.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------- commands


def find_spec(manifest: dict, slug: str) -> dict:
    for spec in manifest["specs"]:
        if spec["slug"] == slug:
            return spec
    raise SystemExit(f"unknown spec '{slug}'. Run: riscv_docs.py list")


def cmd_list(args, manifest) -> int:
    category = None
    for spec in sorted(manifest["specs"], key=lambda s: (s["category"], s["slug"])):
        if spec["category"] != category:
            category = spec["category"]
            print(f"\n{category}")
        udb = {"full": "UDB models this", "partial": "UDB partial", "none": ""}[spec["udb"]]
        cached = read_meta(spec["slug"])
        state = f"cached {cached['version']}" if cached else "not cached"
        note = f" [{udb}]" if udb else ""
        print(f"  {spec['slug']:<26} {state:<16}{note}  {spec['title']}")
    return 0


def cmd_versions(args, manifest) -> int:
    base = manifest["base_url"]
    slugs = args.slugs or [s["slug"] for s in manifest["specs"]]
    stale = 0
    for slug in slugs:
        try:
            live = resolve_version(base, slug, args.jina)
        except RuntimeError as exc:
            print(f"{slug:<26} ERROR {exc}")
            continue
        meta = read_meta(slug)
        if meta is None:
            print(f"{slug:<26} {live:<14} not cached")
        elif meta["version"] != live:
            stale += 1
            print(f"{slug:<26} {live:<14} STALE (cached {meta['version']})")
        else:
            print(f"{slug:<26} {live:<14} current")
    if stale:
        print(f"\n{stale} spec(s) stale. Re-run: riscv_docs.py fetch <slug>")
    return 0


def cmd_fetch(args, manifest) -> int:
    base = manifest["base_url"]
    spec = find_spec(manifest, args.slug)
    version = args.version or resolve_version(base, args.slug, args.jina)
    root = f"{base}/{args.slug}/{version}"
    out = spec_dir(args.slug, version)
    out.mkdir(parents=True, exist_ok=True)

    queue = list(spec.get("index") or ["index.html"])
    done: dict[str, dict] = {}
    print(f"{args.slug} {version} -> {out}")

    while queue:
        page = queue.pop(0)
        if page in done:
            continue
        url = f"{root}/{page}"
        try:
            body, mode = fetch_page(url, args.jina)
        except RuntimeError as exc:
            print(f"  skip {page}: {exc}", file=sys.stderr)
            continue
        text = body if mode == "jina" else html_to_text(body)
        dest = out / (page.replace("/", "__") + ".md")
        header = f"<!-- source: {url}\n     fetched: {time.strftime('%Y-%m-%d')}\n     mode: {mode} -->\n\n"
        dest.write_text(header + text)
        done[page] = {
            "url": url,
            "bytes": len(text),
            "sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
        }
        print(f"  {page:<44} {len(text):>8} chars")
        if args.all and mode == "html":
            for href in chapter_links(body):
                if href not in done and href not in queue:
                    queue.append(href)
        if args.limit and len(done) >= args.limit:
            break
        time.sleep(args.delay)

    if not done:
        print("nothing fetched", file=sys.stderr)
        return 1
    write_meta(args.slug, version, done)
    print(f"cached {len(done)} page(s)")
    return 0


def cmd_search(args, manifest) -> int:
    pattern = re.compile(args.pattern, re.I)
    if not CACHE.exists():
        print("cache is empty. Run: riscv_docs.py fetch <slug> --all", file=sys.stderr)
        return 1
    hits = 0
    slugs = set(args.slug or [])
    for meta_path in sorted(CACHE.glob("*/meta.json")):
        slug = meta_path.parent.name
        if slugs and slug not in slugs:
            continue
        meta = read_meta(slug) or {}
        version = meta.get("version", "?")
        for page in sorted((meta_path.parent / version).glob("*.md")):
            url = None
            heading = None
            for line in page.read_text(errors="replace").splitlines():
                if line.startswith("<!-- source: "):
                    url = line.replace("<!-- source: ", "").strip()
                if line.startswith("#"):
                    heading = line
                if pattern.search(line) and not line.startswith("<!--"):
                    anchor = ""
                    if heading:
                        found = re.search(r"\{#([^}]+)\}", heading)
                        anchor = "#" + found.group(1) if found else ""
                    cite = f"{url}{anchor}" if url else str(page)
                    print(f"\n{slug} {version} :: {cite}")
                    if heading:
                        clean = re.sub(r"\s*\{#[^}]+\}", "", heading).strip()
                        print(f"  under: {clean}")
                    print(f"  {line.strip()[:300]}")
                    hits += 1
                    if hits >= args.max:
                        print(f"\n(stopped at {args.max} hits)")
                        return 0
    if not hits:
        print("no match in cache")
    else:
        print(f"\n{hits} hit(s)")
    return 0


def cmd_status(args, manifest) -> int:
    print(f"cache: {CACHE}")
    if not CACHE.exists():
        print("empty - run: riscv_docs.py fetch sbi --all")
        return 0
    total = 0
    for meta_path in sorted(CACHE.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        pages = len(meta.get("pages", {}))
        total += pages
        print(f"  {meta['slug']:<26} {meta['version']:<14} {pages:>3} pages  fetched {meta['fetched_at'][:10]}")
    print(f"  {'':<26} {'':<14} {total:>3} pages total")
    print("\nCheck for new versions with: riscv_docs.py versions")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jina", action="store_true", help="force r.jina.ai instead of a direct fetch")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list known specifications and cache state")
    sub.add_parser("status", help="show what is cached")

    p_ver = sub.add_parser("versions", help="compare cached versions against the live site")
    p_ver.add_argument("slugs", nargs="*")

    p_fetch = sub.add_parser("fetch", help="download and cache a specification")
    p_fetch.add_argument("slug")
    p_fetch.add_argument("--all", action="store_true", help="follow chapter links, not just the index")
    p_fetch.add_argument("--version", help="pin an explicit version folder, e.g. v3.0")
    p_fetch.add_argument("--limit", type=int, default=0, help="stop after N pages")
    p_fetch.add_argument("--delay", type=float, default=0.3, help="seconds between requests")

    p_search = sub.add_parser("search", help="regex search the local cache")
    p_search.add_argument("pattern")
    p_search.add_argument("--slug", action="append", help="restrict to a spec (repeatable)")
    p_search.add_argument("--max", type=int, default=20)

    args = parser.parse_args()
    manifest = load_manifest()
    handler = {
        "list": cmd_list,
        "versions": cmd_versions,
        "fetch": cmd_fetch,
        "search": cmd_search,
        "status": cmd_status,
    }[args.cmd]
    try:
        return handler(args, manifest)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
