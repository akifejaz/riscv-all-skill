# riscv-spec

A skill for Claude that answers RISC-V questions from the authoritative sources,
with verifiable citations instead of recall.

It routes each question to the source that is actually authoritative for it:

- **Ratified specifications** from [docs.riscv.org](https://docs.riscv.org) —
  the ISA manual, SBI, psABI, debug, trace, IOMMU, AIA, PLIC, platform, ACPI and
  the profiles. Cited by versioned URL and section anchor.
- **The [RISC-V Unified Database](https://github.com/riscv/riscv-unified-db)** —
  machine-readable instruction encodings, CSR field layouts, extension versions
  and dependencies, profiles and parameters.

Every answer cites its source, quotes encodings and normative text verbatim,
names the specification version, and flags anything that is not ratified.

## Install

1. Copy the `riscv-spec/` folder into your skills directory:

   - **Claude Code, personal:** `~/.claude/skills/`
   - **Claude Code, one project:** `<repo>/.claude/skills/`
   - **claude.ai:** upload the folder under Settings → Capabilities

2. Warm the specification cache (Python 3, no dependencies to install):

   ```bash
   python3 ~/.claude/skills/riscv-spec/scripts/riscv_docs.py fetch sbi --all
   ```

3. Optional, for instruction encodings and CSR field data, clone UDB:

   ```bash
   git clone https://github.com/riscv/riscv-unified-db.git ~/riscv-unified-db
   export UDB_ROOT=~/riscv-unified-db
   ```

See [references/setup.md](riscv-spec/references/setup.md) for the full setup
levels.

## Example questions

- "What is the exact encoding of `czero.eqz`, and is Zicond ratified?"
- "Is `mstatus.SD` writable on RV64? My core always reads 0 there."
- "What does SBI `sbi_debug_console_write` return on a bad address?"
- "Which registers are callee-saved in the RISC-V calling convention?"
- "Does RVA23 mandate the V extension? What is my rv64gc board missing?"
- "Is Zalasr ratified yet?"

## The command-line tool

The skill bundles a dependency-free script that also works on its own:

```bash
riscv_docs.py list                       # every specification and cache state
riscv_docs.py versions                   # cheap poll for new versions
riscv_docs.py fetch debug --all          # cache one specification
riscv_docs.py search 'hart_mask_base'    # regex search, prints citable URLs
riscv_docs.py status                     # what is cached and when
```

It fetches pages directly, since the published pages are static HTML. The
`--jina` flag routes a stubborn page through `r.jina.ai`, and `JINA_API_KEY` is
honored when set. Neither is required.

## Why the routing matters

RISC-V has no single file that answers everything. The ratified specifications
carry normative meaning but publish only ratified content. UDB carries exact,
third-party-validated encodings but labels its own generated specifications
UNOFFICIAL and covers only the ISA. Some extensions are ratified before they are
published anywhere. The skill encodes that structure, including the traps: a
nightly manual tag is not a release, the newest version is not always the
ratified one, and an unversioned URL silently floats.

## License and credits

This skill is MIT licensed. See [LICENSE](LICENSE).

The specification content it fetches and caches belongs to
[RISC-V International](https://riscv.org) and is licensed CC-BY-4.0. The UDB data
belongs to the [riscv-unified-db](https://github.com/riscv/riscv-unified-db)
project, licensed BSD-3-Clause-Clear with CC-BY-4.0 prose. This repository
contains no specification text; it only fetches it at runtime into a local cache.
