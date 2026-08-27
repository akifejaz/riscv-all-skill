# UDB query cookbook

All commands run from the UDB clone root (`$UDB`). Commands marked **[setup]**
need the one-time `bin/setup` (see setup.md). Everything else works on a bare
clone with standard tools (`git`, `find`, `rg`).

## Freshness

```bash
git -C "$UDB" log -1 --format='%h %cd' --date=short   # data snapshot
git -C "$UDB" fetch origin && git -C "$UDB" status -sb # behind origin?
git -C "$UDB" pull --ff-only                           # only if clean + on main
```

## Instructions

Find an instruction file by mnemonic (escape dots in the mnemonic):

```bash
rg -l --glob '*.yaml' '^name: czero\.eqz$' "$UDB/spec/std/isa/inst/"
# -> spec/std/isa/inst/Zicond/czero.eqz.yaml
```

Resolved variant (self-contained, when gen/ exists):

```bash
ls "$UDB"/gen/resolved_spec/_/inst/*/czero.eqz.yaml
```

List every instruction a given extension defines:

```bash
ls "$UDB/spec/std/isa/inst/Zbb/"
```

The directory name is the defining extension for almost all files; the
`definedBy` key inside the file is authoritative — check it before you answer.

Search instruction descriptions by topic:

```bash
rg -il 'fault-only-first' "$UDB/spec/std/isa/inst/"
```

Read the answer from these keys: `encoding.match` + `encoding.variables`
(bit layout), `operation()` (behavior), `access` (legality per mode),
`definedBy` (owner), `base` (XLEN restriction, when present).

## Decode an opcode

**[setup]** The CLI decodes any encoding directly:

```bash
./bin/udb disasm 0x00558533 --config=_
# RV32: add / RV64: add
```

Without setup: take bits [6:0] as the major opcode, then match the full value
against `encoding.match` patterns (`-` = don't care) with rg over `inst/`.

## Extensions

```bash
ls "$UDB/spec/std/isa/ext/" | sed 's/\.yaml$//'        # all extension names
cat "$UDB/spec/std/isa/ext/Zicond.yaml"                # version, state, prose
```

Answer these from the extension file: `versions[].version`, `versions[].state`
(`ratified`?), `versions[].ratification_date`, `requirements` (dependencies,
for example V requires `allOf: [Zve64d, Zvl128b]`).

Which extension defines instruction X? Read `definedBy` in the instruction file.

## CSRs

CSR files sit at two depths — always locate with `find`:

```bash
find "$UDB/spec/std/isa/csr" -name 'mstatus.yaml'      # by name
rg -l '^address: 0x180' "$UDB/spec/std/isa/csr/"       # by address (satp)
```

Field questions: read `fields.<NAME>` — `location_rv32`/`location_rv64`,
`definedBy`, `type()` (RO / RO-H / RW / RW-R / RW-H / RW-RH, usually
conditional on config), `reset_value()`, `sw_write()`/`sw_read()` (WARL rules).
Quote the `type()` conditions — CSR answers are config-dependent.

## Profiles

Prefer resolved profiles — they are flattened, one line per extension:

```bash
rg -A2 '^  V:' "$UDB/gen/resolved_spec/_/profile/RVA23U64.yaml"
#   V:
#     presence: mandatory
#     version: ~> 1.0
```

Raw profile files use `$inherits` + `$remove` chains; follow the chain by hand
only when `gen/resolved_spec/` is missing or stale.

Compliance check recipe: list the profile's `presence: mandatory` extensions,
then diff against the target's ISA string / extension list, and report the gaps.

## Parameters

```bash
ls "$UDB/spec/std/isa/param/"                          # one file per parameter
cat "$UDB/spec/std/isa/param/CACHE_BLOCK_SIZE.yaml"    # schema + description
```

## The resolved-spec index

`gen/resolved_spec/_/index.json` is a flat JSON array of relative paths. Use it
as a fast existence check:

```bash
grep '"[^"]*/mstatus\.yaml"' "$UDB/gen/resolved_spec/_/index.json"
```

## CLI reference [setup]

```bash
./bin/udb list extensions --config _      # also: instructions, csrs, parameters
./bin/udb show ...                        # per-object detail
./bin/udb disasm ENCODING --config=CFG    # decode
./bin/udb tree                            # all commands
./bin/udb validate ...                    # schema-check spec or cfg files
```

`--config` accepts any name in `cfgs/` (`_`, `rv32`, `rv64`, …). The first CLI
call per session takes longer — it constructs the architecture object.

## MCP server (optional power-up)

`tools/mcp_gen_server/server.py` serves search tools (`search_instructions`,
`search_csrs`, `search_extensions`, `search_all`, IDL-function search) over the
resolved YAML. Setup and registration: see setup.md.
