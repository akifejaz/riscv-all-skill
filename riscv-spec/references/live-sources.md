# The ratified specification sources

This file covers layer 1 and layer 3: the published ratified specifications.
For the UDB layer, read `udb-data-model.md` and `udb-queries.md`.

## docs.riscv.org in one paragraph

`docs.riscv.org` is the "RISC-V Ratified Specifications Library", published by
RISC-V International. It is an Antora site on GitHub Pages, built from about
twenty official specification repositories at pinned tags. It publishes ratified
content only, which is what makes it the top of the precedence ladder. Its
`robots.txt` explicitly allows `ClaudeBot`, `GPTBot`, and `PerplexityBot`, so
automated reading is invited rather than tolerated.

## URL scheme

Three shapes matter:

| Shape | Example | Use |
|---|---|---|
| Redirect stub | `/reference/sbi/index.html` | Discover the current version. Never cite. |
| Versioned page | `/reference/sbi/v3.0/binary-encoding.html` | Read and cite this. |
| Section anchor | `...binary-encoding.html#3-1-1-hart-list-parameter` | Cite the exact subsection. |

The stub is about 400 bytes and contains
`<meta http-equiv="refresh" content="0; url=v3.0/index.html">`. That single line
is the freshness mechanism: compare it against the cached version, and re-fetch
only on a change.

Old versions stay live. ISA manual `v20260120`, `v20250508`, and `v20240411` all
resolve, and SBI `v3.0` and `v2.0` resolve while `v1.0` is gone. Version labels
use two schemes: semantic (`v1.0`, `v3.0`) and date-stamped (`v20260120`).

Section anchors are numbered slugs, generated from the heading, for example
`id="3-1-1-hart-list-parameter"`. The cache script preserves them as `{#anchor}`
markers so that `search` can print a deep citation.

The ISA manual splits into two volumes with their own paths:
`/reference/isa/<version>/unpriv/unpriv-index.html` and
`/reference/isa/<version>/priv/priv-index.html`.

## What the script does

`scripts/riscv_docs.py` uses the standard library only, so it runs anywhere with
Python 3. It fetches pages directly, because the versioned pages are static HTML
and need no browser. `r.jina.ai` stays available through `--jina` for any page
that resists a direct fetch, and it reads `JINA_API_KEY` when that variable is
set. Jina returns markdown without heading anchors, so prefer the direct path
whenever it works.

```bash
riscv_docs.py list                       # specs, categories, cache state
riscv_docs.py versions [slug ...]        # compare cache against the live site
riscv_docs.py fetch sbi --all            # download and cache every chapter
riscv_docs.py fetch isa --version v20260120   # pin an explicit version
riscv_docs.py search 'hart_mask_base' --slug sbi
riscv_docs.py status                     # what is cached, and when it was fetched
```

The cache lives in `~/.cache/riscv-spec/<slug>/<version>/`, and
`RISCV_SPEC_CACHE` overrides that location. Every cached page starts with a
comment recording its source URL, fetch date, and retrieval mode, so a citation
never depends on memory.

`fetch --all` follows the chapter links found in the page's own navigation, so it
retrieves one complete specification rather than crawling the whole site.

## Ratified but not yet published

RISC-V ratifies extensions before it publishes them in a specification. During
that gap, the published manual does not mention an extension that is genuinely
ratified. Check this page, which is readable without a login:

`https://riscv.atlassian.net/wiki/spaces/HOME/pages/16154732/Ratified+Extensions`

It lists entries such as the Atomic Load-Acquire and Store-Release extension
(`Zalasr`, October 2025). Without it, a lookup can wrongly report a ratified
extension as unratified.

## Status vocabulary

RISC-V's own pages disagree, listing four, six, and eight lifecycle states. Use
this mapping and say which you used:

- **Ratified** — final. No changes are allowed.
- **Frozen** — changes are highly unlikely, and only for critical issues.
- **Draft** — everything is subject to change.

UDB uses a lowercase enum: `ratified`, `frozen`, `development`. Map
`development` onto `Draft`.

Inside the ISA manual, the per-extension status lives in the preface status
table, at `src/unpriv/preface.adoc`. That table, not the file's presence, decides
whether a chapter is ratified.

## Freshness signals

- `https://riscv.org/feed/` — valid RSS of RISC-V International announcements.
  This is the best general poll.
- `https://riscv.org/specifications/ratified/` — the authoritative ratified
  index. HTML only, with no feed, so detect changes by diffing.
- `https://github.com/riscv/riscv-isa-manual/releases.atom` — valid Atom, but it
  fires on every commit. It is a poor ratification signal. Do not treat a new
  release tag as a ratification event.
- `https://riscv.org/blog/feed/` returns HTML rather than RSS. Do not use it.

## Things that will waste your time

- `/reference/search-index.js` is a 28 MB client-side Lunr index. Fetching it
  stalls. There is no server-side search API. Search the local cache instead.
- There is no `sitemap.xml`. Discover specs from `references/sources.json` or
  from `/reference/home/index.html`.
- PDF attachments live at unversioned paths such as
  `/reference/abi/_attachments/riscv-abi.pdf`, so they float to the latest
  release. The HTML carries the same content with stable anchors. Prefer HTML.
- `lf-riscv.atlassian.net` redirects to `riscv.atlassian.net`.
