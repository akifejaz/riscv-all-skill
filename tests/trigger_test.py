#!/usr/bin/env python3
"""End-to-end test: does the riscv-spec skill trigger, route and answer correctly?

Unlike the clean-room script test, this drives a real Claude session through
`claude -p`, so the model decides for itself whether to consult the skill. That
is the only way to test triggering, over-triggering and refusal honestly.

Requires: the `claude` CLI, logged in. Each case costs a full session, so this is
deliberately a small, high-signal set rather than an exhaustive sweep.

Usage:
    python3 tests/trigger_test.py [--only ID] [--outdir DIR]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

# Ground truth below was verified independently against the sources before these
# assertions were written, so grading never depends on the reasoning under test.
CASES = [
    {
        "id": "encoding-udb",
        "category": "UDB layer",
        "prompt": "What is the exact bit encoding of the czero.eqz instruction, "
        "and is the extension that defines it ratified?",
        "skill_expected": True,
        "must_contain": ["0000111----------101-----0110011", "Zicond"],
        "must_not_contain": [],
        "note": "Encoding must be verbatim from UDB, not reconstructed.",
    },
    {
        "id": "sbi-docs",
        "category": "Non-ISA layer",
        "prompt": "In the RISC-V SBI specification, what value of hart_mask_base "
        "targets all harts?",
        "skill_expected": True,
        "must_contain": ["-1", "docs.riscv.org"],
        "must_not_contain": [],
        "note": "UDB does not model SBI; must come from the ratified cache.",
    },
    {
        "id": "hallucination-bait",
        "category": "Refusal",
        "prompt": "Is the Zfoobar extension ratified in RISC-V? I need to know "
        "before I enable it in my build.",
        "skill_expected": True,
        "must_contain": [],
        "must_not_contain": ["Zfoobar is ratified", "Zfoobar has been ratified"],
        "note": "Zfoobar does not exist. Must say so rather than invent a status.",
    },
    {
        "id": "must-not-trigger",
        "category": "Over-trigger guard",
        "prompt": "Write a C function that reverses a singly linked list in place.",
        "skill_expected": False,
        "must_contain": [],
        "must_not_contain": ["docs.riscv.org"],
        "note": "Unrelated task. The skill must stay out of the way.",
    },
    {
        "id": "out-of-scope",
        "category": "Scope guard",
        "prompt": "How much does RISC-V International membership cost per year?",
        "skill_expected": False,
        "must_contain": [],
        "must_not_contain": [],
        "note": "Mentions RISC-V but is not a specification question.",
    },
    {
        "id": "routing-psabi",
        "category": "Routing",
        "prompt": "Which integer registers are callee-saved in the standard "
        "RISC-V calling convention?",
        "skill_expected": True,
        "must_contain": ["s0", "s11"],
        "must_not_contain": [],
        "note": "Belongs to the psABI, not UDB.",
    },
]

ALLOWED = ["Bash", "Read", "Grep", "Glob", "WebFetch", "WebSearch", "Skill", "ToolSearch"]
SKILL_MARKERS = ("riscv-spec", "riscv_docs.py", "SKILL.md")


def run_case(case: dict, outdir: pathlib.Path, timeout: int) -> dict:
    cmd = [
        "claude", "-p", case["prompt"],
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", *ALLOWED,
    ]
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = proc.stdout
    except subprocess.TimeoutExpired:
        return {**case, "error": f"timed out after {timeout}s", "skill_used": None}

    answer, cost, turns, denials = "", None, None, []
    tools: list[str] = []
    skill_used = False

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in ev.get("message", {}).get("content", []) or []:
                if block.get("type") == "tool_use":
                    tools.append(block.get("name", "?"))
                    blob = json.dumps(block.get("input", {}))
                    if block.get("name") == "Skill" or any(m in blob for m in SKILL_MARKERS):
                        skill_used = True
        elif ev.get("type") == "result":
            answer = ev.get("result") or ""
            cost = ev.get("total_cost_usd")
            turns = ev.get("num_turns")
            denials = ev.get("permission_denials") or []

    if any(m in answer for m in SKILL_MARKERS):
        skill_used = True

    low = answer.lower()
    missing = [s for s in case["must_contain"] if s.lower() not in low]
    present = [s for s in case["must_not_contain"] if s.lower() in low]
    trigger_ok = skill_used == case["skill_expected"]
    passed = trigger_ok and not missing and not present

    (outdir / f"{case['id']}.txt").write_text(answer)
    return {
        **case,
        "skill_used": skill_used,
        "trigger_ok": trigger_ok,
        "missing": missing,
        "unexpected": present,
        "passed": passed,
        "tools": sorted(set(tools)),
        "cost_usd": cost,
        "turns": turns,
        "denials": denials,
        "seconds": round(time.time() - start, 1),
        "answer_chars": len(answer),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--timeout", type=int, default=420)
    ap.add_argument("--outdir", default="/tmp/riscv-spec-trigger")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cases = [c for c in CASES if not args.only or c["id"] == args.only]

    results = []
    total_cost = 0.0
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} ({case['category']}) ...", flush=True)
        res = run_case(case, outdir, args.timeout)
        results.append(res)
        total_cost += res.get("cost_usd") or 0.0
        if res.get("error"):
            print(f"    ERROR {res['error']}")
            continue
        verdict = "PASS" if res["passed"] else "FAIL"
        print(
            f"    {verdict}  skill_used={res['skill_used']} "
            f"(expected {case['skill_expected']})  {res['seconds']}s  "
            f"${res.get('cost_usd') or 0:.2f}"
        )
        if res["missing"]:
            print(f"    missing: {res['missing']}")
        if res["unexpected"]:
            print(f"    should not have said: {res['unexpected']}")
        if res["denials"]:
            print(f"    permission denials: {len(res['denials'])}")

    (outdir / "results.json").write_text(json.dumps(results, indent=2))
    passed = sum(1 for r in results if r.get("passed"))
    print(f"\nRESULT pass={passed} fail={len(results) - passed}  "
          f"total=${total_cost:.2f}  answers in {outdir}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
