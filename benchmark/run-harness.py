#!/usr/bin/env python3
"""
Run-to-completion harness for anycast-cdn-hardmode.

Iteratively re-invokes Claude Opus until the scorer reports COMPLETE
or until the model produces a validated platform blocker, or budget exhausted.

Each iteration is a fresh `claude` invocation with:
  - The full agent prompt (BENCHMARK-PROMPT.md PART 2)
  - The previous iteration's scorer-last.json as context bridge
  - Bypass-permissions mode so subagent dispatch works

The harness owns: lab deploy, git branch creation, iteration boundary commits,
final scoring, harness-log.json, and exit decision.

The agent owns: all design + config + per-device commits.

Usage:
    python3 benchmark/run-harness.py [--max-iterations 8] [--max-wall-clock 14400]
    python3 benchmark/run-harness.py --dry-run    # don't actually invoke claude
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow `from scorer import ...` so validate_blocker() can reuse the live
# vendor exec helpers (no duplicate subprocess plumbing here).
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
TOPOLOGY_DIR  = PROJECT_ROOT / "topology"
LAB_NAME      = "anycast-cdn-hardmode"
CLAB_FILE     = TOPOLOGY_DIR / f"{LAB_NAME}.clab.yml"

SCORER       = BENCHMARK_DIR / "scorer.py"
PROMPT       = BENCHMARK_DIR / "BENCHMARK-PROMPT.md"
INTENT       = BENCHMARK_DIR / "INTENT.md"
DESIGN       = BENCHMARK_DIR / "design.md"
BLOCKER      = BENCHMARK_DIR / "blocker.md"
SCORER_LAST  = BENCHMARK_DIR / "scorer-last.json"
HARNESS_LOG  = BENCHMARK_DIR / "harness-log.json"


# ---------------------------------------------------------------------------
# Lab management
# ---------------------------------------------------------------------------

def deploy_lab() -> None:
    print("[harness] destroying any existing hardmode lab...")
    subprocess.run(
        ["sudo", "clab", "destroy", "-t", str(CLAB_FILE), "--cleanup"],
        capture_output=True,
    )
    print("[harness] regenerating baselines from generate.py...")
    subprocess.run(["python3", "generate.py"], cwd=str(TOPOLOGY_DIR), check=True)
    print("[harness] deploying hardmode lab (this takes ~3 min for vJunos to boot)...")
    subprocess.run(
        ["sudo", "clab", "deploy", "-t", str(CLAB_FILE)],
        check=True,
    )

    # Wait for both Junos PEs
    print("[harness] waiting for both Junos PEs to be SSH-reachable...")
    for attempt in range(20):
        ready = 0
        for pe in ("pe-w", "pe-e"):
            cmd = [
                "sshpass", "-p", "admin@123",
                "ssh", "-o", "StrictHostKeyChecking=no",
                "-o", "ConnectTimeout=3",
                "-o", "LogLevel=ERROR",
                f"admin@clab-{LAB_NAME}-{pe}",
            ]
            try:
                r = subprocess.run(
                    cmd, input="show version\nexit\n",
                    capture_output=True, text=True, timeout=10,
                )
                if "Junos" in (r.stdout or ""):
                    ready += 1
            except subprocess.TimeoutExpired:
                pass
        print(f"[harness]   attempt {attempt + 1}: {ready}/2 PEs ready")
        if ready == 2:
            print("[harness] both PEs ready.")
            return
        time.sleep(20)
    print("[harness] FATAL: PEs failed to come up in time.")
    sys.exit(2)


def teardown_lab() -> None:
    print("[harness] tearing down lab...")
    subprocess.run(
        ["sudo", "clab", "destroy", "-t", str(CLAB_FILE), "--cleanup"],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Git management
# ---------------------------------------------------------------------------

def init_branch() -> str:
    """Create a fresh benchmark branch named with timestamp. Return branch name."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = f"benchmark/hardmode-opus-{ts}"
    # If we're not in a repo, init one
    rc = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                        cwd=str(PROJECT_ROOT), capture_output=True).returncode
    if rc != 0:
        subprocess.run(["git", "init", "-q", "-b", "main"],
                       cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "config", "user.email", "orchestrator@ai-agents.local"],
                       cwd=str(PROJECT_ROOT), check=True)
        subprocess.run(["git", "config", "user.name", "Orchestrator"],
                       cwd=str(PROJECT_ROOT), check=True)
    subprocess.run(["git", "checkout", "-b", branch],
                   cwd=str(PROJECT_ROOT), check=True)
    return branch


def commit_orchestrator(message: str) -> None:
    """Commit any pending changes as Orchestrator. No-op if nothing staged."""
    subprocess.run(["git", "add", "-A"], cwd=str(PROJECT_ROOT), check=True)
    # If nothing to commit, skip silently
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"],
                          cwd=str(PROJECT_ROOT)).returncode
    if diff == 0:
        return
    subprocess.run([
        "git", "commit",
        "--author=Orchestrator <orchestrator@ai-agents.local>",
        "-m", message,
    ], cwd=str(PROJECT_ROOT), check=True)


# ---------------------------------------------------------------------------
# Claude invocation
# ---------------------------------------------------------------------------

def build_prompt(iteration: int) -> str:
    """Construct the prompt to feed to claude for this iteration."""
    parts = []
    parts.append(f"# anycast-cdn-hardmode benchmark — iteration {iteration}")
    parts.append("")
    parts.append("You are running on the lab host. The benchmark project is at:")
    parts.append(f"  {PROJECT_ROOT}")
    parts.append("")
    parts.append("REQUIRED READING (in order):")
    parts.append(f"  1. {PROMPT}                — full task description and rules")
    parts.append(f"  2. {INTENT}                — architecture intent (the only spec)")
    if iteration > 1 and SCORER_LAST.exists():
        parts.append(f"  3. {SCORER_LAST}           — previous iteration scorer output")
    if DESIGN.exists():
        parts.append(f"  4. {DESIGN}                — your previous design notes")
    parts.append("")
    parts.append("Begin by reading those files. Then proceed per the persistence rule.")
    parts.append("")
    if iteration == 1:
        parts.append("This is iteration 1. Cold start. Lab is at baseline.")
    else:
        parts.append(f"This is iteration {iteration}. Devices retain config from previous iterations.")
        parts.append("Read scorer-last.json BEFORE doing anything to see what's still failing.")
    parts.append("")
    parts.append("Stop when scorer reports COMPLETE: True OR when you have written a")
    parts.append("validated platform blocker.md. Otherwise continue iterating until done.")
    return "\n".join(parts)


def invoke_claude(prompt: str, dry_run: bool) -> int:
    """Invoke Claude Opus with bypass-permissions. Return rc."""
    if dry_run:
        print("[harness] (dry-run) would invoke claude with prompt:")
        print("  " + prompt.replace("\n", "\n  "))
        return 0
    cmd = [
        "claude",
        "--model", "claude-opus-4-6",
        "--permission-mode", "bypassPermissions",
        "--print",
        prompt,
    ]
    print(f"[harness] invoking claude...")
    print(f"[harness]   cmd: {' '.join(cmd[:5])} <prompt>")
    r = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return r.returncode


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def run_scorer() -> dict:
    """Run scorer.py and return parsed scorer-last.json."""
    print("[harness] running scorer...")
    subprocess.run(["python3", str(SCORER)], cwd=str(PROJECT_ROOT))
    if not SCORER_LAST.exists():
        return {"total": {"complete": False, "earned": 0, "max": 75}}
    return json.loads(SCORER_LAST.read_text())


# Compiled regexes used by the live-diff blocker validator. A line is
# dropped from BOTH the claimed output and the live output before
# comparison if it matches any of these patterns. Counter drift is
# absorbed by the 80% match threshold below, NOT by aggressive line
# stripping — IPv6 addresses, AS numbers, and prefix counts contain long
# digit runs and must be preserved.
_DYNAMIC_LINE_PATTERNS = [
    re.compile(r"\d{2}:\d{2}:\d{2}"),                          # clock timestamps
    re.compile(r"\d{4}-\d{2}-\d{2}"),                          # ISO dates
    re.compile(r"\buptime\b", re.IGNORECASE),
    re.compile(r"\blast change\b", re.IGNORECASE),
    re.compile(r"\bpid\b", re.IGNORECASE),
    re.compile(r"\bprocess id\b", re.IGNORECASE),
    re.compile(r"seq(uence)?\s*num", re.IGNORECASE),
]

# Allow only safe characters in the blocker `Command:` field; the orchestrator
# will exec this string against a containerlab node so shell metacharacters
# must be rejected before any subprocess call.
_SAFE_NODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_UNSAFE_CMD_RE = re.compile(r"[;|&`$()<>]")


def _filter_dynamic(text: str) -> list[str]:
    """Normalize and drop dynamic lines from `text`. Returns the surviving
    non-empty lines, with internal whitespace runs collapsed and trimmed."""
    out: list[str] = []
    for raw in text.splitlines():
        if any(p.search(raw) for p in _DYNAMIC_LINE_PATTERNS):
            continue
        norm = re.sub(r"\s+", " ", raw).strip()
        if norm:
            out.append(norm)
    return out


def _parse_blocker(body: str) -> tuple[str, str, str] | None:
    """Parse the structured blocker.md format into (node, command, claimed_output).
    Return None if the file does not match the required structure."""
    # Node: <name>
    node_m = re.search(r"^\s*Node:\s*(\S+)\s*$", body, re.MULTILINE)
    cmd_m = re.search(r"^\s*Command:\s*(.+?)\s*$", body, re.MULTILINE)
    if not node_m or not cmd_m:
        return None
    node = node_m.group(1)
    command = cmd_m.group(1)
    # Output: followed by a fenced code block. The fence may be on the
    # same line as `Output:` or the next non-empty line.
    out_m = re.search(
        r"^\s*Output:\s*\n+\s*```[^\n]*\n(.*?)\n\s*```",
        body, re.MULTILINE | re.DOTALL,
    )
    if not out_m:
        return None
    return node, command, out_m.group(1)


def _vendor_for_node(node: str) -> str | None:
    """Map a node name prefix to the vendor runner to use. Returns None for
    nodes the harness will not exec a 'show' against (hosts/clients)."""
    if node.startswith("pe-"):
        return "junos"
    if node.startswith("rr"):
        return "frr"
    if node in ("h1-w", "h1-e", "h2-w", "h2-e", "client-w", "client-e"):
        return "host"
    # everything else (spine-*, l[12]-*, bl-*) is Arista cEOS
    return "arista"


def validate_blocker() -> bool:
    """Live-diff validation of benchmark/blocker.md.

    The agent must produce a structured blocker:

        Node: <name>
        Command: <single-line show command>
        Output:
        ```
        <verbatim platform output>
        ```

    The harness re-executes the same command live against the named
    container, strips dynamic fields (timestamps, uptimes, sequence
    numbers) from both sides, and accepts the blocker iff at least 80% of
    the claimed non-dynamic lines appear verbatim in the live output AND
    at least three claimed lines remain after filtering.
    """
    if not BLOCKER.exists():
        return False
    body = BLOCKER.read_text()
    parsed = _parse_blocker(body)
    if parsed is None:
        print("[harness] blocker rejected: missing Node/Command/Output structure")
        return False
    node, command, claimed = parsed

    if not _SAFE_NODE_RE.match(node):
        print(f"[harness] blocker rejected: unsafe Node value: {node!r}")
        return False
    if _UNSAFE_CMD_RE.search(command):
        print(f"[harness] blocker rejected: shell metacharacters in Command: {command!r}")
        return False

    vendor = _vendor_for_node(node)
    if vendor in (None, "host"):
        print(f"[harness] blocker rejected: cannot live-validate vendor for node {node}")
        return False

    # Re-import here so a stale module state from earlier in the run does
    # not block the import path.
    try:
        import scorer  # noqa: WPS433
    except Exception as e:
        print(f"[harness] blocker rejected: cannot import scorer helpers: {e}")
        return False

    try:
        if vendor == "junos":
            rc, live = scorer.run_junos(node, command)
        elif vendor == "arista":
            rc, live = scorer.run_arista(node, command)
        elif vendor == "frr":
            rc, live = scorer.run_frr(node, command)
        else:
            print(f"[harness] blocker rejected: unknown vendor {vendor}")
            return False
    except Exception as e:
        print(f"[harness] blocker rejected: live exec failed: {e}")
        return False

    claimed_lines = _filter_dynamic(claimed)
    live_lines = _filter_dynamic(live)

    if len(claimed_lines) < 3:
        print(f"[harness] blocker rejected: only {len(claimed_lines)} non-dynamic claimed lines (need ≥3)")
        return False

    live_set = set(live_lines)
    matched = sum(1 for l in claimed_lines if l in live_set)
    ratio = matched / len(claimed_lines)
    if ratio < 0.80:
        print(f"[harness] blocker rejected: live-diff match {matched}/{len(claimed_lines)} = {ratio:.0%} (<80%)")
        return False

    print(f"[harness] blocker accepted: live-diff match {matched}/{len(claimed_lines)} = {ratio:.0%}")
    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-iterations", type=int, default=8,
                        help="Max iterations before failure (default 8)")
    parser.add_argument("--max-wall-clock", type=int, default=4 * 60 * 60,
                        help="Max wall-clock seconds before failure (default 4h)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually invoke claude or deploy lab")
    parser.add_argument("--skip-deploy", action="store_true",
                        help="Skip lab deploy (assume lab already running)")
    args = parser.parse_args()

    started = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()

    log = {
        "started":         started_iso,
        "lab":             LAB_NAME,
        "max_iterations":  args.max_iterations,
        "max_wall_clock":  args.max_wall_clock,
        "iterations":      [],
        "exit_reason":     None,
        "final_score":     None,
    }

    if not args.skip_deploy and not args.dry_run:
        deploy_lab()

    branch = init_branch()
    print(f"[harness] benchmark branch: {branch}")
    log["branch"] = branch

    commit_orchestrator(f"harness: start hardmode-opus benchmark on branch {branch}")

    iteration = 0
    while True:
        iteration += 1
        elapsed = time.time() - started
        print(f"\n[harness] === iteration {iteration} (elapsed {int(elapsed)}s) ===")

        # Iteration boundary commit (only iter 2+)
        if iteration > 1:
            commit_orchestrator(
                f"iter {iteration}: continuing — previous scorer reports incomplete"
            )

        prompt = build_prompt(iteration)
        rc = invoke_claude(prompt, args.dry_run)
        print(f"[harness] claude returned rc={rc}")

        # After claude returns, run the scorer
        score = run_scorer()
        # Capture per-probe failure detail so the harness log can later
        # distinguish "agent fixed a real bug" iterations from "scorer noise"
        # iterations. We snapshot only failing probes (name + evidence) to
        # keep the log compact.
        failures: list[dict] = []
        for cat_name in ("connectivity", "hardening", "wecmp", "deep_verify"):
            cat = score.get(cat_name) or {}
            for r in cat.get("results", []):
                if not r.get("passed"):
                    failures.append({
                        "category": cat_name,
                        "name":     r.get("name"),
                        "evidence": r.get("evidence"),
                    })
        # Tally git commits authored on this branch since the previous
        # iteration boundary. A retry that contains only Verify/Architect
        # commits is probably scorer noise; one with WAN/DC/Harden commits
        # is a real config-change retry.
        config_change_authors = {
            "Agent-WAN", "Agent-DC-West", "Agent-DC-East", "Agent-Harden",
        }
        try:
            git_log = subprocess.run(
                ["git", "log", "--format=%an", f"-{50}"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True,
            )
            recent_authors = set(git_log.stdout.split())
        except Exception:
            recent_authors = set()
        had_config_change = bool(recent_authors & config_change_authors)
        log["iterations"].append({
            "n":               iteration,
            "claude_rc":       rc,
            "score":           score.get("total", {}),
            "elapsed":         round(time.time() - started, 1),
            "failures":        failures,
            "had_config_change": had_config_change,
        })

        if score.get("total", {}).get("complete"):
            log["exit_reason"] = "complete"
            log["final_score"] = score
            commit_orchestrator(
                f"complete: {score['total']['earned']}/{score['total']['max']} "
                f"in {iteration} iter, {int(time.time() - started)}s"
            )
            break

        if validate_blocker():
            log["exit_reason"] = "blocker"
            log["final_score"] = score
            commit_orchestrator(
                f"blocker: agent reported platform issue at iter {iteration}"
            )
            break

        # Iteration finished without success/blocker. Decide if we have budget
        # for ANOTHER iteration before looping back.
        elapsed = time.time() - started
        if iteration >= args.max_iterations:
            log["exit_reason"] = "max_iterations_exceeded"
            break
        if elapsed >= args.max_wall_clock:
            log["exit_reason"] = "max_wall_clock_exceeded"
            break

        # Otherwise continue to next iteration

    # Compute iteration efficiency points
    if log["exit_reason"] == "complete":
        iter_pts = max(0, 10 - 2 * (iteration - 1))
    else:
        iter_pts = 0
    log["iteration_efficiency_points"] = iter_pts

    # v4.1 — classify each retry as 'real_fix' (the iteration committed
    # config changes via WAN/DC/Harden authors) vs 'noise' (only Verify
    # or Architect commits, suggesting the agent didn't change anything
    # functional and the retry was caused by transient probe noise).
    # The first iteration is never a "retry" — it's the initial build.
    breakdown = []
    for it in log["iterations"]:
        if it["n"] == 1:
            breakdown.append({"iter": 1, "kind": "initial_build"})
            continue
        kind = "real_fix" if it.get("had_config_change") else "noise"
        breakdown.append({
            "iter": it["n"],
            "kind": kind,
            "complete_at_end": bool(it.get("score", {}).get("complete")),
        })
    log["iteration_efficiency_breakdown"] = breakdown

    # Run the OUT-OF-TREE hidden holdout scorer exactly once at end-of-run.
    # Output is appended to the harness log only — never to scorer-last.json
    # and never fed back into any agent prompt. The absolute path is
    # hard-coded so the agent cannot shadow it with a same-named file in
    # the repo.
    HIDDEN_SCORER = Path("/tmp/anycast-cdn-hidden/hidden_scorer.py")
    if HIDDEN_SCORER.exists():
        try:
            hp = subprocess.run(
                ["python3", str(HIDDEN_SCORER)],
                capture_output=True, text=True, timeout=180,
            )
            try:
                log["hidden_scorer"] = json.loads(hp.stdout)
            except Exception as e:
                log["hidden_scorer"] = {
                    "error":  f"json parse failed: {e}",
                    "stdout": hp.stdout[:1000],
                    "stderr": hp.stderr[:500],
                }
        except Exception as e:
            log["hidden_scorer"] = {"error": f"exec failed: {e}"}
    else:
        log["hidden_scorer"] = {"error": f"not found at {HIDDEN_SCORER}"}

    # Persist harness log
    HARNESS_LOG.write_text(json.dumps(log, indent=2))

    # Print summary
    print("\n" + "=" * 70)
    print("HARNESS SUMMARY")
    print("=" * 70)
    print(f"Branch:           {branch}")
    print(f"Iterations run:   {iteration}")
    print(f"Exit reason:      {log['exit_reason']}")
    print(f"Wall clock:       {int(time.time() - started)}s")
    if log["final_score"]:
        t = log["final_score"]["total"]
        print(f"Scorer total:     {t['earned']}/{t['max']}")
    print(f"Iter eff points:  {iter_pts}/10")
    print("=" * 70)

    # Final commit
    commit_orchestrator(
        f"harness: end {log['exit_reason']} after {iteration} iter, "
        f"{int(time.time() - started)}s"
    )

    sys.exit(0 if log["exit_reason"] == "complete" else 1)


if __name__ == "__main__":
    main()
