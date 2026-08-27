# Setup levels

Pick the smallest level that answers your questions. Each level adds to the ones
before it. Level 0 alone already answers most specification questions.

## Level 0 — the skill by itself (no clone, no build)

The ratified specifications need nothing but Python 3 and network access.

```bash
python3 <skill>/scripts/riscv_docs.py fetch sbi --all
python3 <skill>/scripts/riscv_docs.py fetch debug --all
python3 <skill>/scripts/riscv_docs.py search 'hart_mask_base'
```

This covers SBI, psABI, debug, trace, IOMMU, AIA, PLIC, platform, ACPI, the
profiles, and the ISA manual prose. The cache lands in `~/.cache/riscv-spec/`,
and a typical specification costs well under a megabyte.

Set `RISCV_SPEC_CACHE` to move the cache. Set `JINA_API_KEY` only if you want the
`--jina` fallback authenticated; the skill never requires it.

## Level 1 — a UDB clone (adds encodings and CSR field data)

```bash
git clone https://github.com/riscv/riscv-unified-db.git ~/riscv-unified-db
export UDB_ROOT=~/riscv-unified-db      # add this to your shell profile
```

The clone is roughly 500 MB. It enables every UDB lookup in
`udb-queries.md`: instruction encodings, CSR field layouts, extension versions
and dependencies, parameters, and raw profiles. Reading the database needs only
`git` and `rg`. Submodules are not required, though `ext/riscv-isa-manual` gives
you the manual sources offline if you initialize it.

## Level 2 — the UDB toolchain (adds the CLI and generators)

```bash
cd "$UDB_ROOT"
./bin/setup      # installs mise and a repo-local Ruby, Python and Node toolchain
./bin/doctor     # verify
```

Tell the user before running it: this takes roughly five to ten minutes and
installs inside the repository and mise directories, not system-wide. It is safe
to re-run. It enables `./bin/udb list`, `./bin/udb show`, and
`./bin/udb disasm ENCODING --config=_`.

## Level 3 — resolved UDB data (recommended if you have Level 2)

```bash
./do gen:resolved_arch CFG=_        # whole design space
./do gen:resolved_arch CFG=rv64     # one configuration
```

This writes self-contained YAML to `gen/resolved_spec/<cfg>/`, with `$inherits`
expanded and profiles flattened. Re-run it after any pull that touches `spec/`.

## Level 4 — optional extras

UDB ships an MCP server over its resolved YAML at
`tools/mcp_gen_server/server.py`. It adds search tools to every session:

```bash
cd "$UDB_ROOT"
python3 -m venv .venv_mcp
.venv_mcp/bin/pip install "mcp[cli]" ruamel.yaml
claude mcp add udb -- "$UDB_ROOT/.venv_mcp/bin/python3" "$UDB_ROOT/tools/mcp_gen_server/server.py"
```

UDB generators can also produce an HTML manual, a C++ simulator, C headers, and
Go code. See `udb-queries.md`. Warn the user first: they run for minutes and
write hundreds of megabytes into `gen/`.

## Keeping current

```bash
python3 <skill>/scripts/riscv_docs.py versions   # ratified specs: cheap version poll
git -C "$UDB_ROOT" fetch origin                  # UDB: check for new data
```

Re-fetch only the specifications reported `STALE`. Pull UDB only when the tree is
clean and the branch is behind.

## Troubleshooting

- `fetch` fails on one page → the script prints the error and continues. Retry
  with `--jina` to route that page through `r.jina.ai`.
- Every fetch fails → check network access; then answer from cache and UDB, and
  tell the user the data may be stale.
- `udb` CLI errors or hangs → run `./bin/doctor`, then re-run `./bin/setup`.
- `gen/resolved_spec` missing → Level 3 was never run. Use the raw `spec/` files.
- UDB pull refused → the tree is dirty or the branch diverged. Report it; never
  force it.
