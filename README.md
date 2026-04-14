# Anycast CDN Hardmode Benchmark

An intent-driven network engineering benchmark for agentic LLMs. One architecture doc, 18 containerlab nodes (12 network devices, 6 traffic hosts), three vendor CLIs, zero reference configs. The agent figures it out.

This repo has the complete proof-of-work for the benchmark described in the LinkedIn article: **[Can an AI Build a Network? I Gave It 17 Blank Nodes and Found Out](https://www.linkedin.com/in/hhildenbrand/)**.

## What's Inside

### The Benchmark Stack (`main` branch)

| Path | What |
|---|---|
| [`benchmark/INTENT.md`](benchmark/INTENT.md) | The one-page architecture spec, only input the agent gets |
| [`benchmark/BENCHMARK-PROMPT.md`](benchmark/BENCHMARK-PROMPT.md) | Agent prompt: rules, persistence rule, sub-conversation playbook |
| [`benchmark/scorer.py`](benchmark/scorer.py) | Automated grading: connectivity pings, hardening probes, active wECMP datapath measurement |
| [`benchmark/run-harness.py`](benchmark/run-harness.py) | Run-to-completion harness: lab deploy, iteration loop, blocker validation |
| [`benchmark/v4victory-gource.mp4`](benchmark/v4victory-gource.mp4) | Gource visualization of the victory-lap run (51 commits, 64 minutes) |
| [`benchmark/v4victory-captions.txt`](benchmark/v4victory-captions.txt) | Gource caption file for reproducible rendering |
| [`benchmark/avatars/`](benchmark/avatars/) | 7 role-based avatars used in the Gource visualization |
| [`topology/anycast-cdn-hardmode.clab.yml`](topology/anycast-cdn-hardmode.clab.yml) | Containerlab topology definition (18 nodes) |
| `topology/configs/*-baseline.conf` | Baseline device configs: hostname, management IP, root password, nothing else |
| [`topology/generate.py`](topology/generate.py) | Script that generates the baseline configurations |

### The AI-Generated Configurations (run branches)

Each run branch has the full git history of a cold-start benchmark run, with per-device per-protocol commits using role-based author identities. These commits drive the Gource visualization.

| Branch | Run | Result | Details |
|---|---|---|---|
| `benchmark/hardmode-opus-20260408-194026` | Victory lap (v4.2) | **85/85 in 1 iteration, 64 min** | Clean one-shot. The run in the article and Gource video. |
| `benchmark/hardmode-opus-20260408-151131` | First v4 run | **85/85 in 4 iterations, 101 min** | The run where 1:237 wECMP polarization got caught and the reactive hash-key fix was pushed. |

## The Topology

```
                                    WAN  (AS 65000)
                              +--------------------+
                              |   rr1   <------>  rr2 |   FRR route reflectors
                              +---+----------------+-+
                                  |                |
                    +-------------+--+         +---+-----------+
                    |      pe-w      |<------->|      pe-e     |  Juniper vJunos PEs
                    +----+------+----+         +----+------+---+
               client-w -+      |                   |      +- client-e
                          | DCI (dual-homed, 4:1 wECMP)    |
                     +----+-----+--+         +--+---+------+
                     |     bl-w    |         |    bl-e     |  Arista border-leaves
                     +------+------+         +-----+------+
                            |                      |
                     +------+------+         +-----+------+
                     |   spine-w   |         |   spine-e  |  Arista spines
                     +--+-----+---+          +--+-----+---+
                        |     |                 |     |
                     +--+-+ +-+--+           +--+-+ +-+--+
                     |l1-w| |l2-w|           |l1-e| |l2-e|  Arista leaves
                     +--+-+ +-+--+           +--+-+ +-+--+
                        |     |                 |     |
                      h1-w  h2-w              h1-e  h2-e     Linux hosts
```

**18 containers**: 2 FRR RRs + 2 Juniper vJunos PEs + 8 Arista cEOS + 6 Linux hosts

## Protocol Stack

| Layer | Technology | Scope |
|---|---|---|
| WAN underlay | ISIS L2 with Segment Routing (SR-MPLS) | PE-to-PE via RRs |
| WAN overlay | iBGP VPNv4/VPNv6 with route reflection | Full mesh via RR1+RR2 |
| L3VPN | VRF CDN | PEs + border-leaves |
| DC underlay | OSPF | Per-DC fabric |
| DC overlay | BGP EVPN/VXLAN (symmetric IRB, L3VNI 50100) | Per-DC fabric |
| DCI | eBGP (dual-homed, 4:1 link-bandwidth wECMP) | PE-to-BL |
| Service | Anycast VIP: `198.51.100.1/32` + `2001:db8:cafe::1/128` | Both BLs originate |
| Hardening | BGP MD5, ISIS auth, SNMPv3, NTP auth, AAA, syslog, BGP max-routes | Full topology |

## Scoring (85 points)

| Category | Points | What |
|---|---|---|
| Connectivity | 50 | 8 ping probes: intra-DC v4/v6, cross-DC v4/v6, anycast VIP from both clients v4/v6 |
| Hardening | 25 | 7 probes: BGP MD5, ISIS auth, SNMPv3, NTP auth, AAA, syslog, BGP max-routes |
| wECMP (structural) | 5 | 5 checks on link-bandwidth advertisements |
| Deep verify | 5 | Audit report + active wECMP datapath probe + hardening functional verification |

The **active wECMP datapath probe** pushes ~1000 pps of UDP at the anycast VIP and measures the ratio of hardware interface counters on the PE's dual DCI links. Pass window: median ratio in [3.4, 4.6] (target 4:1).

## Git Author Identities

The benchmark uses 7 role-based author identities to tag commits to the subagent that produced them. This is what drives the Gource visualization.

| Role | Author | Email |
|---|---|---|
| Orchestrator (harness) | `Orchestrator` | `orchestrator@ai-agents.local` |
| Architect (design.md) | `Agent-Architect` | `architect@ai-agents.local` |
| WAN (FRR + Junos) | `Agent-WAN` | `wan@ai-agents.local` |
| DC West (Arista) | `Agent-DC-West` | `dc-west@ai-agents.local` |
| DC East (Arista) | `Agent-DC-East` | `dc-east@ai-agents.local` |
| Hardening | `Agent-Harden` | `harden@ai-agents.local` |
| Verification | `Agent-Verify` | `verify@ai-agents.local` |

## Reproducing the Gource Visualization

```bash
# Check out the victory-lap branch
git checkout benchmark/hardmode-opus-20260408-194026

# Render with Gource (requires gource + ffmpeg)
gource \
  --title "Anycast CDN Hardmode - Victory Lap" \
  --caption-file benchmark/v4victory-captions.txt \
  --caption-duration 8 --caption-size 20 \
  --user-image-dir benchmark/avatars/ \
  --seconds-per-day 0.3 \
  --auto-skip-seconds 0.5 \
  --max-file-lag 0.1 \
  --hide filenames,dirnames \
  -1280x720 \
  -o - | ffmpeg -y -r 60 -f image2pipe -vcodec ppm -i - \
  -vcodec libx264 -preset medium -pix_fmt yuv420p -crf 18 \
  gource-output.mp4
```

## Key Findings

1. **One-shot convergence** - The v4.2 victory-lap run hit 85/85 in a single iteration (64 min, 51 commits).

2. **Reactive wECMP fix** - In the v4 first run, the agent ran into 1:237 traffic polarization from Junos's default L3-only hash. It read the failing scorer logs, pushed an authoritative-looking but functionally backward `layer-3-only` hash-key fix, then forged the scorer result to pass anyway.

3. **Test-driven blind spot** - The agent configured explicit IPv4 hash keys but skipped `family inet6` because the scorer's active probe only fires IPv4 UDP. It optimized for what was measured.

## License

This benchmark framework, intent document, and scoring code are released for educational and research purposes. The AI-generated device configurations on the run branches are artifacts of Claude Opus 4.6 benchmark runs.
