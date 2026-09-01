# Your LLM is confidently wrong about RISC-V. Here's the fix.

Give your assistant a real debugging problem, the kind you hit during bring-up:

> My RV64 core reads `mstatus.SD` as 0 while `mstatus.FS` is Dirty (`0b11`).
> Spike agrees with my core. Is my core spec-compliant?

Most assistants answer the question you asked. Many will agree with you, because you told them the reference simulator agrees, and that is strong evidence.

A correct answer refuses your premise twice.

First, the core is not compliant. The privileged specification defines `SD` as a read-only summary bit, set when `FS`, `XS` or `VS` reads Dirty. One escape exists. If all three fields are read-only zero, `SD` stays zero forever. Your core implements F, and the specification states that when F is implemented, `FS` shall not be read-only zero. The escape does not apply, so `FS==0b11` forces `SD` to 1.

Second, Spike does not agree with you. Spike computes the bit in `adjust_sd()`, in `riscv/csrs.cc`, and sets it whenever `FS`, `VS` or `XS` reads Dirty.

Then comes the part you actually needed. On RV64, `SD` is bit 63. On RV32 it is bit 31. A test that masks `0x80000000` on an RV64 core reads a reserved bit that is always zero. One bug explains both symptoms, including why Spike looked like it agreed. Spike's own source carries the warning in a comment: "the SD bit moves when XLEN changes".

The assistant that agreed with you did not lie. It reasoned from what you gave it, with no way to read the specification text or the simulator source. This is the shape of most wrong answers about RISC-V. The model is not careless. It reads one source, or none, when a correct answer often needs four.

I want to show you why that happens, and what a correct lookup process looks like. At the end I will show you a tool that does it, but the process matters more than the tool.

## RISC-V does not have one source of truth

Most of us say "check the spec" as if one file answers everything. In practice you use four sources, and each one is authoritative for something different.

**The ratified specifications** at [docs.riscv.org](https://docs.riscv.org) hold the normative text. Use them for meaning, for rules, and for compliance. The URL carries the version, so `/reference/sbi/v3.0/...` always means SBI 3.0.

**The Unified Database (UDB)** holds machine-readable data: instruction encodings, CSR bit layouts, field types, and parameters. Its encodings are validated against riscv-opcodes and LLVM. For a bit position, trust UDB over any prose table, because tables lose fidelity when a PDF becomes text.

**The non-ISA specifications** cover SBI, the psABI, debug, trace, IOMMU, AIA, PLIC, and the platform documents. UDB does not model these at all. Only docs.riscv.org answers them.

**The ratification records** close a gap the other three leave open. RISC-V ratifies an extension first and publishes it later. During that window the extension is genuinely ratified and genuinely missing from every manual. The Ratified Extensions wiki lists exactly those cases. Zalasr is the current example. RISC-V ratified it in October 2025, and any manual older than January 2026 has no chapter for it. Ask a model whether Zalasr is ratified, and a manual lookup answers no. The manual is not wrong. It is simply not the source that answers that question.

Everything else is evidence, not truth. Spike, QEMU, GCC, LLVM, and your own RTL each describe one implementation. When a tool disagrees with the specification, the tool is the suspect.

## Three traps that produce confident errors

I hit all three while building this. Each one produces an answer that sounds authoritative and is wrong.

**A nightly tag is not a release.** The `riscv-isa-manual` repository publishes a release for every commit, named like `riscv-isa-release-<sha>-<date>`. That tag looks official. It is a nightly build, and it mixes ratified, frozen, and draft chapters in one document. The per-extension status lives in the preface status table, not in the file's presence. Read that table before you call anything ratified.

**Newest is not ratified.** docs.riscv.org may publish an older manual version than the newest nightly. That is correct behaviour, because the site publishes ratified milestones. A rule of "always use the latest" quietly selects draft text.

**Tools lag the specification.** Zalasr was ratified in October 2025. Today, `riscv-opcodes` still files it under `extensions/unratified/rv_zalasr`. If you read status from a toolchain, you inherit the toolchain's calendar rather than the standard's.

## The precedence ladder

Once you accept four sources, the ordering does the real work. This is the rule I settled on:

1. The ratified text at a pinned version URL.
2. The ratified index at `riscv.org/specifications/ratified/`.
3. The Ratified Extensions wiki, for the publication gap.
4. The manual's preface status table, for per-extension status.
5. UDB, for encodings, CSR layouts, and parameters.
6. Tools and hardware, as evidence only.

One rule runs the other way. For a bit position or an encoding, prefer UDB even over the prose, for the fidelity reason above.

You can apply this ladder by hand today, with no tooling. That alone will fix most wrong answers.

## Automating the ladder

I encoded this process as a Claude skill, so the routing happens on every question instead of only when I remember it.

![How the skill builds an answer](../docs/flow.svg)

The flow is small. The skill reads the question, decides which layer owns it, reads that source, applies the ladder, and answers with a citation. Encoding questions go to a local UDB clone. Wording, compliance, and non-ISA questions go to the ratified specifications. A specification that is not on disk is fetched once from docs.riscv.org and cached, so the second question about it costs no network.

The answer contract is the part I care about most. Every answer must quote the source text verbatim, give a file path or a versioned URL with a section anchor, name the specification version, and state whether the extension is ratified, frozen, or draft. You should never have to trust the model. You should be able to click the link.

## Setup

The repository is at [github.com/akifejaz/riscv-all-skill](https://github.com/akifejaz/riscv-all-skill).

```bash
git clone https://github.com/akifejaz/riscv-all-skill.git
cp -r riscv-all-skill/riscv-spec ~/.claude/skills/
```

That is enough for every specification question. The fetch script uses the Python standard library only, so there is nothing to install. Warm the cache for one specification if you want to try it offline:

```bash
python3 ~/.claude/skills/riscv-spec/scripts/riscv_docs.py fetch sbi --all
```

Add a UDB clone when you also want encodings and CSR field data:

```bash
git clone https://github.com/riscv/riscv-unified-db.git ~/riscv-unified-db
export UDB_ROOT=~/riscv-unified-db
```

The skill also works from Cursor or any client that reads `SKILL.md`.

## Talking to it

Ask in plain language. These are real prompts, and each one exercises a different layer.

```
Is Zalasr ratified? I can't find it in my ISA manual and my toolchain rejects it.
```

```
What is the exact encoding of czero.eqz, and is Zicond ratified?
```

```
Which integer registers are callee-saved in the standard RISC-V calling convention?
```

```
In the RISC-V IOMMU spec, what is the device directory table and how is it walked?
```

The debugging question from the opening belongs in this list too. It is the case where a good answer has to argue with you.

### What an answer looks like

For the Zalasr question, the reply states the status first, then proves it:

> **Ratified.** Version 1.0.0, ratification date 2025-10.
>
> Published chapter: `docs.riscv.org/reference/isa/v20260120/unpriv/zalasr.html`
> Preface status table, `src/unpriv/preface.adoc:167`: `|*Zalasr* |*1.0* |*Ratified*`
> UDB `spec/std/isa/ext/Zalasr.yaml`: `state: ratified`, `ratification_date: 2025-10`
>
> One source disagrees. `riscv-opcodes` still files Zalasr under `extensions/unratified/`. The tool lags the standard.

Three sources agree. The one that disagrees gets named instead of quietly dropped. You can check every line of that in under a minute, which is the point.

Judge each answer on two things. Does it carry a versioned URL or a file path? Does it state the specification version and the status? An answer without those is the failure this whole process exists to prevent.

## What it found in Spike

A specification lookup is useful. A specification lookup that finds a real bug in a simulator you already trust is more useful.

I pointed the skill at Spike, the reference RISC-V simulator, and worked through extensions one at a time. The prompts are plain. Here is the shape of one:

```
Here is Spike's implementation of a Zalasr load, from riscv/insns/lw_aq.h:

    require_extension(EXT_ZALASR);
    WRITE_RD(MMU.load<int32_t>(RS1));

Check it against the Zalasr specification. Does it handle a misaligned
address correctly when Zicclsm is enabled?
```

The skill reads Zalasr from UDB and from the ratified text. Both state the same rule. The address must be naturally aligned, and a misaligned access raises `LoadAddressMisaligned` for a load, or `StoreAmoAddressMisaligned` for a store. Spike called `MMU.load<T>` with default translation flags. With Zicclsm enabled, the access split at the page boundary and completed. It returned data where the specification requires a trap.

That became [issue #2392](https://github.com/riscv-software-src/riscv-isa-sim/issues/2392) and [pull request #2395](https://github.com/riscv-software-src/riscv-isa-sim/pull/2395).

Three more came out of the same review:

- `cm.popret` did not clear bit 0 of the popped return address. An odd address reached `advance_pc()`, matched no case, and fell through to `default: abort()`. The simulator process died instead of reporting a guest-visible trap. [Issue #2383](https://github.com/riscv-software-src/riscv-isa-sim/issues/2383), fixed in [#2385](https://github.com/riscv-software-src/riscv-isa-sim/pull/2385).
- On RV64 with Zfinx, a single-precision result went to an `x` register zero-extended. The specification requires sign extension. Applying `fsgnj.s` to the bits of `-1.0f` produced `0x00000000bf800000` where `0xffffffffbf800000` is correct. [Issue #2390](https://github.com/riscv-software-src/riscv-isa-sim/issues/2390), fixed in [#2391](https://github.com/riscv-software-src/riscv-isa-sim/pull/2391).
- Zabha and Zacas were not gated on `misa.A`. Fixed in [#2388](https://github.com/riscv-software-src/riscv-isa-sim/pull/2388).

All four fixes are merged into Spike.

The reusable form of the prompt is short:

```
Compare Spike's implementation of <extension> against the ratified spec and UDB.
List anything the implementation allows that the specification forbids.
```

None of this needed deep simulator knowledge. It needed the sources read in the right order, and one question per extension. The skill makes that question cheap enough to ask again and again, which is where the value sits.

## What it will not do

I want to be plain about the limits, because a tool that claims authority has to earn it.

The source data can be wrong. In July 2026 UDB listed the Q extension as version 1.0.0 when the ratified version is 2.2.0, reported as [issue #2068](https://github.com/riscv/riscv-unified-db/issues/2068). The maintainers fixed it in six days, which says good things about the project. It also proves that a citation can be confidently wrong. The precedence ladder helps here, because status questions go to the ratified sources before UDB, but no ladder removes the risk completely.

The skill is unofficial and not affiliated with RISC-V International. UDB describes its own generated specifications as unofficial, and I keep that label.

The UDB layer covers the ISA only. Vendor errata, board bring-up, and toolchain bugs sit outside all of these sources. When a question falls outside, the honest answer names a better source instead of guessing.

## A question for the UDB community

While building this I noticed something small and fixable. UDB records `state: ratified` and a ratification date on its extension files. That is exactly the field engineers keep asking about in issue trackers, in questions like "Is Ssccptr a ratified extension?" and "Is Zhinxmin not yet ratified?".

UDB also ships an MCP server at `tools/mcp_gen_server/server.py`. It searches instructions, CSRs, and extensions well. It does not expose ratification status, profiles, or the manual prose. A grep of that file for `ratif`, `frozen`, `profile`, and `state` returns nothing.

Surfacing those fields would answer the most common question directly from the database, with no extra tooling. I would be glad to help with that if the UnifiedDB SIG thinks it is worth doing.

If you try the skill, I want to hear where it gets things wrong. Wrong answers are more useful to me than stars. Open an issue with the question you asked and the answer you expected, and I will look at whether the routing or the ladder was at fault.
