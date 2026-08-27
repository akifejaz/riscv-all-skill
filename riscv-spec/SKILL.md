---
name: riscv-spec
description: Answer any RISC-V question from the authoritative sources — the ratified specifications at docs.riscv.org (ISA manual, SBI, psABI, debug, trace, IOMMU, AIA, PLIC, platform, ACPI) and the RISC-V Unified Database (UDB) for machine-readable instruction encodings, CSR field layouts, extension versions, profiles and parameters. Use this skill whenever the user asks about a RISC-V instruction, encoding, CSR, extension, profile, ISA string, SBI call, calling convention, or debug/trace interface; whenever the user says "UDB", "the spec", "is this ratified", or "is this compliant"; and whenever RISC-V development, testing, bring-up, code review or debugging needs a specification reference — even if the user names no source.
---

# riscv-spec — answer RISC-V questions from the authoritative sources

## The three layers

RISC-V has no single file that answers every question. It has three sources, and
each one is authoritative for something different. Using the wrong one produces a
confident wrong answer, so route the question before you answer it.

1. **Ratified prose — docs.riscv.org.** The "RISC-V Ratified Specifications
   Library", published by RISC-V International. It holds ratified content only.
   Authoritative for meaning, rules, and compliance.
2. **Machine-readable ISA data — UDB.** A local clone of `riscv-unified-db`.
   Authoritative for instruction encodings, CSR bit layouts, field types, and
   parameters, because those are validated against riscv-opcodes and LLVM.
3. **Non-ISA specifications — docs.riscv.org only.** SBI, psABI, debug, trace,
   IOMMU, AIA, PLIC, platform, ACPI. UDB does not model these at all.

Everything else — Spike, QEMU, GCC, LLVM, RTL, the user's code — is never a
source of truth. When one of them disagrees with layers 1 and 2, the tool is the
suspect. Report the mismatch as a finding.

## Precedence when sources disagree

Work down this ladder and stop at the first source that answers the question:

1. `docs.riscv.org` at a pinned version URL — published ratified text.
2. `https://riscv.org/specifications/ratified/` — the authoritative ratified index.
3. The Ratified Extensions wiki — ratified but not yet published in any spec.
4. The ISA manual preface status table — per-extension `Ratified`/`Frozen`/`Draft`.
5. UDB YAML — bit-level encodings, CSR layouts, parameters.
6. Tools, hardware, and user code — evidence about an implementation, never truth.

One exception runs the other way. For an encoding or a CSR bit position, prefer
UDB even over the prose, because prose tables lose fidelity when converted to
text, while UDB's encodings carry third-party validation.

## Step 1 — Locate the sources

**The ratified specs** are cached by this skill's own script. No clone needed.

```bash
python3 <skill>/scripts/riscv_docs.py list      # what exists, and what is cached
python3 <skill>/scripts/riscv_docs.py status    # cache contents and fetch dates
```

**UDB** is a local git clone. Find it in this order, and call the result `$UDB`:

1. The `UDB_ROOT` environment variable.
2. `~/riscv-unified-db`, then `~/projects/riscv-unified-db`.
3. `find ~/projects ~/work ~/src ~/dev -maxdepth 3 -type d -name riscv-unified-db 2>/dev/null | head -3`
4. No hit: tell the user, and offer to clone it (~500 MB, ask first):
   `git clone https://github.com/riscv/riscv-unified-db.git ~/riscv-unified-db`

Confirm a real clone with `test -f "$UDB/spec/std/isa/ext/I.yaml"`.

UDB questions are answerable without the ratified cache, and ratified-spec
questions are answerable without UDB. Never block one on the other.

## Step 2 — Refresh, once per day

Specifications change. Stale data is the main way this skill can be wrong.

```bash
python3 <skill>/scripts/riscv_docs.py versions          # cheap: ~400 bytes per spec
python3 <skill>/scripts/riscv_docs.py fetch sbi --all   # only when it reports STALE
```

The version check is cheap because each spec publishes a small redirect stub that
names its current version. Re-fetch only what changed.

For UDB, read the data date with `git -C "$UDB" log -1 --format=%cd --date=short`.
If it is more than a day old, and `UDB_NO_PULL` is unset, run `git -C "$UDB" fetch
origin`, then `git -C "$UDB" pull --ff-only` only when the tree is clean, the
branch is `main`, and the branch is behind. If the tree is dirty or the branch
diverged, do not pull. Report the state and continue with current data.

## Step 3 — Route the question

| Question is about | Go to |
|---|---|
| Instruction encoding, opcode, bit fields | UDB `inst/` YAML |
| Instruction behavior | UDB `operation()` IDL, then the ISA manual for intent |
| CSR address, field location, WARL, reset | UDB `csr/` YAML |
| Whether an extension is ratified | ratified index, then Ratified Extensions wiki, then preface table |
| Extension dependencies, versions | UDB `ext/` YAML |
| Profile membership (RVA23 and similar) | UDB resolved profile, then the profile doc |
| SBI, psABI, debug, trace, IOMMU, AIA, PLIC, ACPI, platform | the ratified cache only |
| Normative wording, compliance, "is this legal" | the ratified cache |

Search the ratified cache with a regex; it prints a citable URL for every hit:

```bash
python3 <skill>/scripts/riscv_docs.py search 'hart_mask_base' --slug sbi
```

For UDB queries, read [references/udb-queries.md](references/udb-queries.md).
Before interpreting a UDB file type for the first time, read
[references/udb-data-model.md](references/udb-data-model.md). For the ratified
site's URL scheme and its traps, read
[references/live-sources.md](references/live-sources.md). For installation and
optional power-ups, read [references/setup.md](references/setup.md).

## Answer contract

Every answer must let the user verify it without trusting you:

1. **Cite precisely.** For the ratified specs, give the versioned URL with the
   section anchor, such as
   `https://docs.riscv.org/reference/sbi/v3.0/binary-encoding.html#3-1-1-hart-list-parameter`.
   For UDB, give the file path.
2. **Quote verbatim.** Copy `encoding.match`, bit locations, `operation()`, and
   normative sentences exactly. Never retype or tidy them. A one-bit typo inverts
   the meaning.
3. **Name the version.** Give the spec version for ratified text, and the UDB
   commit date for UDB data.
4. **State the status.** Say whether an extension is ratified, frozen, or draft.
   Flag anything that is not ratified, and flag `spec/custom/` as vendor-specific.
5. **Say when sources disagree.** Show both, name which one is ratified, and say
   which you followed.

## Traps that produce wrong answers

Each of these has bitten a real lookup. Check them before answering.

- **A nightly is not a release.** `riscv-isa-manual` tags a release per commit,
  named `riscv-isa-release-<sha>-<date>`. UDB's `ext/riscv-isa-manual` submodule
  pins one of those nightlies, so it mixes ratified, frozen, and draft chapters.
  Read the preface status table before you call anything ratified.
- **Newest is not ratified.** docs.riscv.org may publish an older ISA manual
  version than the newest nightly, precisely because it publishes only ratified
  milestones.
- **Never cite an unversioned URL.** `/reference/<slug>/index.html` is a redirect
  stub that floats to the latest version. Cite `/reference/<slug>/<version>/...`.
- **Never fetch `/reference/search-index.js`.** It is a 28 MB client-side index
  and it will stall. Use the script's `search` over the local cache instead.
- **Never read an encoding out of a PDF.** Table extraction mangles bit fields.
  Use UDB YAML.
- **Archived and missing repositories.** `riscv/riscv-profiles` is archived and
  its content moved into the ISA manual. `riscv-non-isa/riscv-platform-specs`
  does not exist. `riscof` is archived and its documentation is stale from 2022.
  Most per-repository `github.io` sites now return 404; psABI is the exception.
- **UDB's published site carries no disclaimer.** The "UNOFFICIAL" label appears
  only in the repository README, so supply that caveat yourself.
- **RISC-V's status vocabulary is inconsistent** across its own pages, which list
  four, six, and eight states. Use one mapping: `Ratified`, `Frozen`, `Draft`.
  UDB's lowercase `development` maps to `Draft`.

## When the network is unavailable

Degrade, and say so. Answer from the local cache and from UDB, then add one line
naming the cache date and warning that a newer version may exist. Do not refuse
to answer, and do not silently present stale data as current.

## Scope limits

These sources cover the architecture and its platform interfaces. They do not
cover vendor errata, board bring-up details, or toolchain bugs. When a question
falls outside, say so plainly and name a better source rather than guessing.
