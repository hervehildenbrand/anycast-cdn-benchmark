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
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


def validate_blocker() -> bool:
    """Check if benchmark/blocker.md exists and looks legitimate.

    Acceptance criteria (kept loose for v1):
      - file exists, > 200 chars
      - contains the words 'show' and 'output' or 'evidence' (suggesting copy-pasted show output)
      - contains the words 'kernel', 'image', or 'platform' (suggesting platform-level cause)
    """
    if not BLOCKER.exists():
        return False
    body = BLOCKER.read_text()
    if len(body) < 200:
        return False
    if not any(k in body.lower() for k in ("show", "evidence", "output")):
        return False
    if not any(k in body.lower() for k in ("kernel", "image", "platform", "container")):
        return False
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
        log["iterations"].append({
            "n":         iteration,
            "claude_rc": rc,
            "score":     score.get("total", {}),
            "elapsed":   round(time.time() - started, 1),
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
