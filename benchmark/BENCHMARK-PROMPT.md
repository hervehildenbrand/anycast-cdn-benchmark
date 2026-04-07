# Anycast CDN HARDMODE Benchmark — Opus, intent-driven, run-to-completion

## What this benchmark measures

Three things the legacy `anycast-cdn-final` benchmark does **not** measure:

1. **Architectural design ability.** You get an architecture intent document and 18 baseline-only devices. You design the protocol stack, addressing schemes, vendor-specific implementations, and hardening from scratch. There are no per-device reference configs anywhere on disk.
2. **Multi-agent orchestration.** You will delegate per-role implementation work to subagents (via the Agent tool). The main agent designs and integrates; subagents execute against the devices.
3. **Persistence to true completion.** A run-to-completion harness re-invokes you iteratively until the scorer reports 8/8 connectivity AND 7/7 hardening — or until you produce a validated platform-level blocker. "Good enough" is not an exit condition.

This is the only document the benchmark orchestrator hands you besides `INTENT.md`. Read both before doing anything.

---

## PART 1: SETUP SCRIPT (run by orchestrator before agent invocation)

```bash
# 1. Clean slate
sudo clab destroy -t /home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode/topology/anycast-cdn-hardmode.clab.yml --cleanup

# 2. Regenerate baselines (idempotent — should be no diff if generate.py unchanged)
cd /home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode/topology
python3 generate.py

# 3. Deploy lab from baselines
sudo clab deploy -t anycast-cdn-hardmode.clab.yml

# 4. Wait for both Juniper PEs to boot
for i in $(seq 1 20); do
  w=$(printf 'show version\nexit\n' | sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 admin@clab-anycast-cdn-hardmode-pe-w 2>/dev/null | grep -c Junos)
  e=$(printf 'show version\nexit\n' | sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 admin@clab-anycast-cdn-hardmode-pe-e 2>/dev/null | grep -c Junos)
  if [ "$w" -ge 1 ] && [ "$e" -ge 1 ]; then
    echo 'BOTH PEs READY'
    break
  fi
  sleep 20
done

# 5. Initialize benchmark git branch (if not already on one)
cd /home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode
TS=$(date -u +%Y%m%d-%H%M%S)
git checkout -b "benchmark/hardmode-opus-${TS}"

# 6. Smoke test the scorer
python3 benchmark/scorer.py --baseline-only
# Expected: connectivity 0/50, hardening 0/25.
# Confirms the lab is in clean state and the scorer can reach it.

# 7. Record start time
echo "BENCHMARK_START: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Verify before launching agent:
- 18 containers running (`sudo docker ps | grep clab-anycast-cdn-hardmode | wc -l`)
- Both Junos PEs responsive
- Scorer baseline run reports 0/0
- A clean benchmark branch exists in git

---

## PART 2: AGENT PROMPT (Opus, iteratively re-invoked by harness)

### AGENT_PROMPT START

You are Claude Opus 4.6, acting as a senior multi-vendor network engineer. The lab `anycast-cdn-hardmode` is deployed at `/home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode/`. You are running on the lab host directly — no SSH wrapping needed for device access.

## First read these (in order)

1. `benchmark/INTENT.md` — the architecture spec. This is your task.
2. `benchmark/scorer-last.json` — if it exists, you ran a previous iteration. Read it FIRST before doing anything else and identify which probes are still failing. Continue from there. If it doesn't exist, this is iteration 1 — start from scratch.
3. `topology/configs/{frr,juniper,arista}/*-baseline.conf` — the current state on each device (hostname + interfaces only).

There are **no reference configurations** anywhere on disk. Don't grep for them. They are intentionally absent. Design the implementation from `INTENT.md`.

## Persistence rule (critical)

You will be re-invoked iteratively until completion. **Stop only when one of these is true:**

(a) `python3 benchmark/scorer.py` reports `COMPLETE: True` (8/8 connectivity AND 7/7 hardening), OR
(b) You have identified a genuine platform-level blocker that no amount of additional configuration on your side can fix. Write `benchmark/blocker.md` with:
   - A clear one-paragraph description of what's broken
   - The exact `show` command output proving it (paste verbatim)
   - What would need to change at the **lab/image/kernel layer** (not your config layer) to unblock
   - An honest statement that you have explored alternative configuration approaches and none of them work

The orchestrator validates the blocker. If your blocker is actually a config issue you missed, the loop continues. Don't write blocker.md to escape work.

If neither (a) nor (b) is true at the end of your iteration, **the harness will re-invoke you with a fresh context and the latest `scorer-last.json`**. Your subagent commit history persists across iterations. The lab device state persists across iterations. Make iteration N+1 productive by leaving good breadcrumbs in iteration N (commits, design.md updates, scorer output).

## REQUIRED: USE SUBAGENTS

This task is too large and too parallel for one process. You MUST delegate per-role implementation to subagents using the Agent tool. The orchestration model is:

1. **Main agent (you)** reads `INTENT.md`, designs the architecture, writes `benchmark/design.md` with rationale, commits it as `Agent-Architect`, then delegates to subagents.
2. **Subagents** receive a focused brief, push config to their assigned devices, verify their portion works, **commit per-device per-protocol with their own author identity**, and return a status report.
3. **Main agent** reads subagent reports, runs the scorer, and either declares completion, dispatches more subagents to fix what's still failing, or writes a blocker if hard-stuck.

The required subagents (you may add more if useful):

| Subagent          | Author identity                                | Devices                            |
|-------------------|------------------------------------------------|------------------------------------|
| `Agent-WAN`       | `Agent-WAN <wan@ai-agents.local>`              | rr1, rr2, pe-w, pe-e               |
| `Agent-DC-West`   | `Agent-DC-West <dc-west@ai-agents.local>`      | spine-w, l1-w, l2-w, bl-w          |
| `Agent-DC-East`   | `Agent-DC-East <dc-east@ai-agents.local>`      | spine-e, l1-e, l2-e, bl-e          |
| `Agent-Harden`    | `Agent-Harden <harden@ai-agents.local>`        | All devices (after main config converges) |
| `Agent-Verify`    | `Agent-Verify <verify@ai-agents.local>`        | Run scorer, write results.json     |

The main agent commits `design.md` and any integration artifacts as `Agent-Architect <architect@ai-agents.local>`.

## Git workflow (mandatory — drives the Gource visualization)

The following rules are checked by the orchestrator's git-discipline scorer. Violations cost points and produce a worse Gource video.

**Author identities:** every commit MUST use one of the seven identities listed above (Architect, WAN, DC-West, DC-East, Harden, Verify, or the Orchestrator's own commits which the harness handles itself). Use `git -c user.name="..." -c user.email="..." commit ...` or `git commit --author="Name <email>" -m ...`.

**Commit cadence:**
1. **Per-device-per-protocol-stage commits.** Every time a subagent successfully pushes a chunk of config to a device, it stages and commits the corresponding `topology/configs/{vendor}/{node}.conf` file (or `frr/{node}/frr.conf` for FRR) with a message like:
   - `frr: rr1 isis + bgp rr-mesh`
   - `junos: pe-w isis-sr + mpls + ibgp vpnv4`
   - `junos: pe-w add v6 transport ibgp`
   - `arista: l1-w ospf underlay + bgp evpn (vlan-aware-bundle)`
2. **No bulk "all configs at once" commits.** Each device, each protocol stage, separate commit. Smaller is better.
3. **Each subagent commits before returning.** Don't have the main agent commit on a subagent's behalf — that loses author attribution.
4. **The Architect commits `design.md`** at the start of iteration 1 and updates it (with new commits) when design decisions change in later iterations.

**Files committed:**
- `topology/configs/frr/{rr1,rr2}/frr.conf`
- `topology/configs/juniper/pe-{w,e}.conf` — write your applied config to disk here as you push it; this file is the Gource animation surface, not the device runtime
- `topology/configs/arista/{spine,l1,l2,bl}-{w,e}.conf`
- `benchmark/design.md`
- `benchmark/results.json` (Verify subagent)
- `benchmark/blocker.md` if applicable (Architect)

**Hard rules:** no `--amend`, no `git push --force`, no commits with the default `user.name` / `user.email`, no empty commits.

## Device access (use exactly these patterns)

You are on the lab host directly. The container name prefix is `clab-anycast-cdn-hardmode-`.

**cEOS (Arista) — show & multi-line config:**
```bash
sudo docker exec clab-anycast-cdn-hardmode-l1-w Cli -p 15 -c 'show ip bgp summary'

sudo docker exec clab-anycast-cdn-hardmode-l1-w Cli -p 15 -c "configure
router bgp 65100
   router-id 10.255.10.11
   ...
end"
```

**Junos (Juniper) — show & config:**
```bash
# Show — printf piped, NO ssh -tt (it hangs on heredocs)
printf 'show isis adjacency\nexit\n' | \
  sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  admin@clab-anycast-cdn-hardmode-pe-w

# Config — printf with set commands and commit and-quit
printf 'configure
set protocols isis interface et-0/0/5.0 level 2 metric 100
commit and-quit
' | sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  admin@clab-anycast-cdn-hardmode-pe-w
```

**FRR (vtysh):**
```bash
# Suppress harmless vtysh.conf stderr warning
sudo docker exec clab-anycast-cdn-hardmode-rr1 vtysh -c 'show bgp summary' 2>/dev/null

sudo docker exec clab-anycast-cdn-hardmode-rr1 vtysh -c 'configure terminal
router bgp 65000
 neighbor 10.255.0.11 remote-as 65000
 ...
end'
```

`write memory` will fail in FRR because frr.conf is bind-mounted. That's expected — config persists in the container's running state.

**Linux hosts (h1-w, client-e, etc.):**
```bash
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -c3 192.168.30.10
sudo docker exec clab-anycast-cdn-hardmode-h1-w ip -6 route show
```

## Workflow within an iteration

### Iteration 1 (cold start)

1. Read `benchmark/INTENT.md` end-to-end.
2. Read every baseline config under `topology/configs/`. They tell you which interfaces, IPs, loopbacks, and ASNs the lab is pre-staged with.
3. Write `benchmark/design.md` with your architectural decisions: protocol choices, RT/RD scheme (constrained by INTENT.md), how you'll achieve cross-DC v6, how you'll do wECMP, how you'll structure RRs, etc. Commit as `Agent-Architect`.
4. Dispatch `Agent-WAN`, `Agent-DC-West`, `Agent-DC-East` in **parallel** (they touch disjoint device sets). Wait for all three to return.
5. Run `python3 benchmark/scorer.py`. Expect partial connectivity success. Investigate failures.
6. Dispatch fix-up subagents as needed until 8/8 connectivity passes.
7. Once connectivity is 8/8, dispatch `Agent-Harden`. Then `Agent-Verify`.
8. Run scorer one more time. If 8/8 + 7/7, you are done. Commit `results.json` via `Agent-Verify`.

### Iteration 2+ (continuation)

1. Read `benchmark/scorer-last.json` to see what's still failing.
2. Read `benchmark/design.md` to remember your previous architectural choices.
3. Identify the gap. Is it a missing config, a wrong design choice, or a platform issue?
4. Dispatch the right subagent(s) to fix the gap. Update `design.md` if your design has changed.
5. Re-run scorer. If complete, exit with success. If still gaps and you've tried alternatives, write `blocker.md`.

## Outputs (before exiting any iteration)

- `benchmark/design.md` — exists, non-trivial, reflects current state of decisions
- `topology/configs/{vendor}/{node}.conf` — updated with whatever you pushed this iteration
- Per-device commits with correct author identities — `git log --format='%an %s' -20` should show diverse authors and meaningful messages
- `benchmark/scorer-last.json` — produced by `python3 benchmark/scorer.py` at the end of the iteration
- `benchmark/results.json` — produced ONLY when complete, by `Agent-Verify`
- `benchmark/blocker.md` — produced ONLY when hard-blocked, by `Agent-Architect`

### AGENT_PROMPT END

---

## PART 3: POST-PROCESSING (run by orchestrator after agent loop exits)

```bash
cd /home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode

# 1. Final scorer run
python3 benchmark/scorer.py
# scorer-last.json now reflects the final state

# 2. Iteration efficiency calculation
# (read the harness log to count iterations)
ITERS=$(jq '.iterations' benchmark/harness-log.json)
ITER_PTS=$((10 - 2 * (ITERS - 1)))
[ $ITER_PTS -lt 0 ] && ITER_PTS=0

# 3. Git discipline scoring
git log --format='%an' "benchmark/hardmode-opus-${TS}" | sort -u
git log --oneline "benchmark/hardmode-opus-${TS}" | wc -l
# Expect: 7 distinct authors (or close), >20 commits

# 4. Render Gource movie
gource ./.git \
  --start-position $(date -d "$BENCHMARK_START" +%s) \
  --seconds-per-day 0.5 \
  --auto-skip-seconds 1 \
  --file-idle-time 0 \
  --max-files 0 \
  --hide mouse,filenames \
  --user-image-dir benchmark/avatars/ \
  --output-ppm-stream - | \
ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - \
       -vcodec libx264 -preset medium -crf 23 \
       benchmark/hardmode-opus-${TS}.mp4

# 5. Lab teardown
sudo clab destroy -t topology/anycast-cdn-hardmode.clab.yml --cleanup
```

---

## SCORING RUBRIC (100 points)

| Category               | Points | Source                             | Required for "complete" |
|------------------------|--------|------------------------------------|--------------------------|
| Connectivity gate checks | 50     | scorer.py (8 × 6.25)               | YES (must be 50/50)      |
| Hardening probes       | 25     | scorer.py (7 × ~3.6)               | YES (must be 25/25)      |
| Iteration efficiency   | 10     | `max(0, 10 - 2 * (iter - 1))`      | NO                       |
| Git discipline         | 5      | git log analysis (authors, cadence)| NO                       |
| Design quality         | 10     | manual/judge review of design.md   | NO                       |
| **Total**              | **100**| —                                  | —                        |

A run that exits via valid `blocker.md` is **not scored** — it's reported as a benchmark-blocking finding for human review.

A run that exhausts the harness budget (max iterations or wall-clock) without completing or producing a valid blocker scores partial credit on connectivity + hardening + design quality, with 0 on iteration efficiency.

---

## KNOWN-FAIR aspects vs KNOWN-HARD aspects

So you understand what you're being graded on:

**Fair help (you don't have to invent these):**
- Topology, addressing scheme, ASN map, VLAN/VNI numbers, RT scheme: in `INTENT.md`
- Vendor CLI access patterns: in this prompt
- Per-vendor verification show commands: in `INTENT.md`
- The 8 connectivity tests and 7 hardening categories: in `INTENT.md`

**Hard parts (you ARE being graded on these):**
- Vendor-specific syntax for everything
- Architectural decisions: vlan-aware-bundle vs per-vlan EVPN, 6PE vs separate v6 iBGP, static routes vs IGP for PE-RR reachability, BGP-LB vs route-map for wECMP
- Diagnosing routing failures from `show` output and fixing them
- Choosing peer group / policy / route-map names
- Subagent decomposition and parallelism
- Git workflow discipline
- Persistence — actually iterating to completion instead of stopping at "good enough"
