# UDB data model — how to read each file type

Snapshot: 2026-08 — 169 extensions, 1,377 instructions, 396 CSRs, 10 profiles.
Counts drift as upstream moves; the structure below is stable.

## Repository map

```
riscv-unified-db/
├── spec/
│   ├── std/isa/
│   │   ├── inst/<Ext>/*.yaml    # instructions, grouped by defining extension
│   │   ├── ext/<Name>.yaml      # extensions: versions, deps, prose
│   │   ├── csr/**/*.yaml        # CSRs, some in ext subdirs, some top-level
│   │   ├── param/<NAME>.yaml    # one file per architecture parameter
│   │   ├── profile*/            # profile, profile_release, profile_family
│   │   ├── isa/                 # shared IDL: globals.isa, util.idl, vec.idl…
│   │   ├── inst_type|opcode/    # format metadata (R/I/S/B/U/J)
│   │   └── exception_code/, interrupt_code/, manual/, prose/
│   ├── custom/isa/              # vendor extensions (example, Qualcomm Xqci*)
│   └── schemas/*.json           # JSON Schemas for every kind
├── cfgs/                        # configs: _ (unconfigured), rv32, rv64, …
├── gen/resolved_spec/<cfg>/     # generated: $inherits expanded + index.json
├── backends/                    # doc/PDF/ISS/Go/C/SystemVerilog generators
├── tools/ruby-gems/             # udb (API+CLI), idlc, udb-gen, udb_helpers
├── tools/mcp_gen_server/        # MCP server over resolved YAML
├── ext/                         # submodules: riscv-isa-manual, riscv-opcodes
└── bin/, do                     # setup, doctor, udb, generate, task runner
```

Every data file starts with the same three keys: `$schema`, `kind`, `name`.

## Instruction files (`kind: instruction`)

Example, `spec/std/isa/inst/I/add.yaml` (copyright header removed):

```yaml
$schema: "inst_schema.json#"
kind: instruction
name: add
long_name: Integer add
description: |
  Add the value in xs1 to xs2, and store the result in xd.
  Any overflow is thrown away.
definedBy:
  extension:
    name: I
assembly: xd, xs1, xs2
encoding:
  match: 0000000----------000-----0110011
  variables:
    - name: xs2
      location: 24-20
    - name: xs1
      location: 19-15
    - name: xd
      location: 11-7
access:
  s: always
  u: always
  vs: always
  vu: always
data_independent_timing: true
hints:
  - { $ref: inst/Zihintntl/ntl.p1.yaml# }
operation(): X[xd] = X[xs1] + X[xs2];
```

How to read each key:

- `encoding.match` — the bit pattern, MSB first. `0`/`1` are fixed bits; `-` marks
  operand bits. Length 32 or 16 (compressed). `variables` maps operands to bit
  ranges. A split range like `12|6-2` means bit 12 concatenated with bits 6..2.
  Variable entries can carry `not: 0` (illegal value) and `sign_extend: true`.
- `definedBy` — the owning extension. Accepts logic: `allOf`, `anyOf`, `oneOf`.
- `access` — legality per privilege mode (`s`, `u`, `vs`, `vu`):
  `always`, `sometimes`, or `never`.
- `operation()` — executable behavior in IDL. `X[n]` is the integer register file.
- `hints` — instructions that overlay this encoding as hints (via `$ref`).
- Some instructions add `base: 32` or `base: 64` (only valid on that XLEN) and
  `pseudoinstructions` (assembler aliases).
- RV64 instructions with an RV32 counterpart may differ per base; check for
  `base` and per-base fields before you answer an XLEN-specific question.

## Extension files (`kind: extension`)

`spec/std/isa/ext/<Name>.yaml` holds:

- `long_name`, `type` (`privileged` | `unprivileged`), `description` (AsciiDoc prose).
- `versions` — a list; each entry has `version`, `state` (for example `ratified`),
  and `ratification_date`. Always read `state` before you rely on an entry.
- `requirements` — dependency logic. Example from `V.yaml`:
  `allOf: [Zve64d, Zvl128b]`. Also `conflicts` in some files.
- Some extensions carry `params` — the parameters they introduce.

## CSR files (`kind: csr`)

Example anchor: `spec/std/isa/csr/mstatus.yaml`.

- Top level: `address` (CSR number, for example `0x300`), `priv_mode`, `length`
  (often `MXLEN`), `writable`, `definedBy`.
- `fields:` — a map of field name to:
  - `location` or `location_rv32` / `location_rv64` — bit positions per XLEN.
  - `definedBy` — the extension that makes the field exist.
  - `type()` — IDL that returns the field type: RO, RO-H, RW, RW-R, RW-H, RW-RH
    (H = hardware-updated, R = restricted values). The result often depends on
    implemented extensions and parameters.
  - `reset_value()` — IDL; often `UNDEFINED_LEGAL` (implementation choice).
  - `sw_write(csr_value)` / `sw_read()` — IDL that defines WARL behavior.

This makes UDB the most precise machine-readable CSR reference available. A field
question ("is SD writable?") is answered by `type()` plus its conditions — quote
those conditions, because the answer usually depends on the configuration.

## Profile files (`kind: profile`)

- Raw files (`spec/std/isa/profile/RVA23U64.yaml`) inherit a parent list with
  `$inherits`, prune with `$remove`, then set per-extension
  `presence: mandatory` or `presence: optional` and a `version` constraint
  (`~> 1.0` means >= 1.0.0 and < 2.0.0).
- Resolved files (`gen/resolved_spec/_/profile/RVA23U64.yaml`) are flattened:
  every extension appears inline with its presence and version. Prefer these for
  "what does RVA23 require" questions.
- Hierarchy: profile_family (RVA) → profile_release (RVA23) → profile
  (RVA23U64, RVA23S64).

## Config files (`cfgs/*.yaml`)

- `type`: `unconfigured` (`_`), `partially configured` (rv32, rv64), or
  `fully configured` (every parameter and extension pinned).
- `params`: parameter values (MXLEN, endianness, PMP count, …).
- `mandatory_extensions` / `implemented_extensions`: with version constraints.
- `arch_overlay: <name>`: merges `spec/custom/isa/<name>/` over the standard
  spec (JSON Merge Patch). This is how vendor extensions enter the database.

## Cross-reference mechanics

- `$ref: path/file.yaml#` — a link to another object. Paths are relative to the
  spec root.
- `$inherits: "file.yaml#/json/path"` — the object copies the target, then
  overrides fields. Unexpanded in `spec/`; expanded in `gen/resolved_spec/`
  (the resolved file shows `$child_of` instead).
- `.layout` files — ERB templates that generate families of YAML files (AMO
  variants, PMP registers, HPM counters). The generated `.yaml` files sit next
  to them, are read-only (mode 0444), and are the ones to read.

## IDL in one paragraph

IDL is a strongly typed C-like DSL. Types: `Bits<N>`, `XReg` (= `Bits<MXLEN>`),
`Boolean`, enums, bitfields, structs. Common builtins: `implemented?(ExtensionName::F)`,
`csr_sw_read()`, `csr_sw_write()`, `raise(...)` for exceptions. Shared code lives
in `spec/std/isa/isa/` (`globals.isa`, `util.idl`, `fp.idl`, `vec.idl`). Quote IDL
verbatim; explain it in prose next to the quote.
