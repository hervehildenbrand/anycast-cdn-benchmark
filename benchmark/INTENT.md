# Anycast CDN — Architecture Intent (Hardmode)

You are configuring a multi-vendor ISP backbone + dual data center fabric to deliver an anycast CDN service. This document is the **only** specification you get. There are no per-device reference configurations. You decide the implementation.

The litmus test for this document: it should be possible for a senior network engineer at any vendor to read this and produce a working implementation. Anything that requires Junos-specific or Arista-specific knowledge is intentionally **not** here — that's the part you're being graded on.

---

## 1. Topology

```
                                        WAN  (AS 65000)
                                  ┌──────────────────────┐
                                  │   rr1   ◄──────►  rr2 │   FRR route reflectors
                                  │ 10.255.0.1   10.255.0.2│
                                  │ fd00::1      fd00::2  │
                                  └──┬──────────────────┬─┘
                                     │                  │
                                     │                  │
                       ┌─────────────┴──┐          ┌────┴─────────────┐
                       │      pe-w      │◄────────►│      pe-e        │  Juniper vJunos
                       │ 10.255.0.11    │          │ 10.255.0.13      │  PE routers
                       │ fd00::11       │          │ fd00::13         │
                       └────┬──────┬────┘          └────┬──────┬──────┘
                  client-w ─┤      │                    │      ├─ client-e
                            │      │ DCI                │ DCI  │
                            │      ├──────┐      ┌──────┤      │
                            │      │      │      │      │      │
                       ┌────▼──────▼──┐  ┌─▼──────▼──┐  ▼      ▼
                       │     bl-w     │  │   bl-e    │
                       │ 10.255.10.21 │  │10.255.30.21│   Arista cEOS
                       └──────┬───────┘  └─────┬──────┘   border-leaves
                              │                │
                       ┌──────┴────────┐  ┌────┴────────┐
                       │   spine-w     │  │   spine-e   │   Spines
                       │ 10.255.10.1   │  │ 10.255.30.1 │
                       └─┬────┬────────┘  └───┬────┬────┘
                         │    │               │    │
                      ┌──▼─┐ ┌▼───┐         ┌─▼──┐ ▼─┐
                      │l1-w│ │l2-w│         │l1-e│l2-e│  Leaves
                      └─┬──┘ └─┬──┘         └─┬──┘ └─┬─┘
                        │      │              │      │
                      h1-w   h2-w           h1-e   h2-e
                  192.168.10  .11         192.168.30  .31
                  fd00:db8:10  :11         fd00:db8:30  :31
```

**18 containers total**: 2 RRs + 2 PEs + 8 cEOS (2 spines + 4 leaves + 2 border-leaves) + 6 hosts (4 endpoints + 2 clients).

---

## 2. Addressing & ASN scheme

### Loopbacks (already configured in baselines, do NOT renumber)

| Node      | IPv4          | IPv6      | ASN   | Role           |
|-----------|---------------|-----------|-------|----------------|
| rr1       | 10.255.0.1    | fd00::1   | 65000 | WAN RR (FRR)   |
| rr2       | 10.255.0.2    | fd00::2   | 65000 | WAN RR (FRR)   |
| pe-w      | 10.255.0.11   | fd00::11  | 65000 | PE west        |
| pe-e      | 10.255.0.13   | fd00::13  | 65000 | PE east        |
| spine-w   | 10.255.10.1   | fd00:10::1  | 65100 | Spine west   |
| l1-w      | 10.255.10.11  | fd00:10::11 | 65100 | Leaf west #1 |
| l2-w      | 10.255.10.12  | fd00:10::12 | 65100 | Leaf west #2 |
| bl-w      | 10.255.10.21  | fd00:10::21 | 65100 | Border-leaf west |
| spine-e   | 10.255.30.1   | fd00:30::1  | 65300 | Spine east   |
| l1-e      | 10.255.30.11  | fd00:30::11 | 65300 | Leaf east #1 |
| l2-e      | 10.255.30.12  | fd00:30::12 | 65300 | Leaf east #2 |
| bl-e      | 10.255.30.21  | fd00:30::21 | 65300 | Border-leaf east |

**VTEP loopbacks** (Loopback1 on each Arista leaf/border-leaf, already configured):
- west leaves/BL: `10.255.11.{11,12,21}`
- east leaves/BL: `10.255.31.{11,12,21}`

### Inter-device link addressing (already in baselines)

- **WAN core** (rr↔rr, rr↔pe, pe↔pe): `10.0.0.x/31`, `fd00:0:N::/127`
- **DCI** (pe↔bl): `10.2.0.x/31`, `fd00:2:N::/127`
- **DC fabric** (spine↔leaf, spine↔bl): `10.1.0.x/31`, `fd00:1:N::/127` (west), `10.1.20.x/31`, `fd00:1:2N::/127` (east)
- **Client-facing** (pe↔client): `10.100.x.x/31`, `fd00:100:x::/127`
- **Host-facing** (leaf↔host): VLAN-tagged, see below

You don't need to invent any addressing — read the baseline configs to see what's already on each interface.

### Host VLANs and SVIs

Hosts attach to leaves on access ports. Anycast gateway SVIs live in VRF `CDN`:

| DC West VLAN | Subnet IPv4         | Subnet IPv6         | Host       |
|--------------|---------------------|---------------------|------------|
| 10           | `192.168.10.0/24`   | `2001:db8:10::/64`  | h1-w → l1-w |
| 11           | `192.168.11.0/24`   | `2001:db8:11::/64`  | h2-w → l2-w |

| DC East VLAN | Subnet IPv4         | Subnet IPv6         | Host       |
|--------------|---------------------|---------------------|------------|
| 30           | `192.168.30.0/24`   | `2001:db8:30::/64`  | h1-e → l1-e |
| 31           | `192.168.31.0/24`   | `2001:db8:31::/64`  | h2-e → l2-e |

The anycast gateway IP is `.1` in each subnet. Use a virtual MAC (`00:1c:73:00:00:99`) so all leaves present an identical L2 next hop. The L3VNI for VRF CDN is `50100`, mapped to VLAN `4001`.

### Anycast service

| Service                  | IPv4              | IPv6                  |
|--------------------------|-------------------|------------------------|
| Anycast CDN VIP          | `198.51.100.1/32` | `2001:db8:cafe::1/128` |
| Originated by            | `bl-w` and `bl-e` (Loopback100 in VRF CDN) |

Both border-leaves originate the anycast prefix. ECMP across the WAN must allow either origin to receive client traffic.

### VRF CDN

- **Name**: `CDN`
- **Route distinguisher convention**: `<loopback>:100` per device
- **Route target**: `65000:100` (single RT, both import and export, for the L3VPN)
- **L3VNI**: `50100` (Arista L3VNI for symmetric IRB across the EVPN fabric)

---

## 3. Functional requirements

You must satisfy ALL of the following. Each is independently verified by the gate-check tests (§6).

### 3.1 WAN backbone
- IS-IS L2 with segment routing (SR-MPLS) between PEs. SRGB `16000-23999`. PE node SIDs: pe-w=11, pe-e=13.
- MPLS forwarding plane on the PE-PE link. The PEs reach each other via direct link et-0/0/5 (Junos) which is the only IS-IS adjacency.
- iBGP between PEs and RRs carrying VPNv4 (and you'll need a way to carry VPNv6 — see §3.4).
- The RRs are full route reflectors (not transit routers); they have no MPLS data plane, only BGP control plane.
- PE↔RR reachability: there is **no** IS-IS adjacency between PE and RR (FRR has no IS-IS authentication while Junos does). Use static routes on both sides over the direct link.

### 3.2 DCI (cross-DC L3VPN)
- eBGP between each PE and its border-leaf over the two parallel DCI links. Peer-AS = the DC's ASN (65100 west, 65300 east).
- Both PE↔BL eBGP sessions in each DC must be active (multipath required for wECMP — see §3.5).
- The DCI carries VRF CDN traffic between the two ASes. PEs run BGP in VRF CDN with their BL neighbors and translate to/from VPNv4 (and VPNv6) toward the RRs.

### 3.3 DC fabric (intra-DC EVPN-VXLAN)
- OSPF underlay on the spine-leaf links inside each DC.
- iBGP EVPN address-family between the spine (acting as RR-client to its own leaves) and each leaf+border-leaf in the same DC. The spine must reflect EVPN routes to its leaves.
- VRF CDN with symmetric IRB on every leaf and border-leaf — the L2 VLANs are stretched within the DC, the cross-VLAN/cross-leaf traffic uses the L3VNI.
- The EVPN address family **must** generate Type-2 (MAC/IP), Type-3 (IMET), and Type-5 (IP-Prefix) routes for the host VLANs. If your config only produces Type-5, the L2 plane will not learn remote MACs, the VTEP table will be empty, and intra-DC inter-VLAN host traffic will fail.

### 3.4 Dual-stack (IPv4 + IPv6 everywhere)
- Every functional path that works for IPv4 **must also work for IPv6**. This is non-negotiable. The 8 gate-check tests (§6) test both families and you need 8/8.
- Watch for the v6 next-hop resolution trap on Junos: VPNv6 control-plane works fine, but v4-mapped IPv6 next-hops do not resolve in `inet6.3` by default. Decide your transport strategy (dual-stack iBGP transport, 6PE, or something else) and document it.

### 3.5 Weighted ECMP across DCI

Each DC has **two parallel DCI links** between its PE and its border-leaf (e.g. pe-w↔bl-w via Ethernet3 and Ethernet4). You must produce a **4:1 traffic ratio** between those two parallel links by advertising the BGP link-bandwidth extended community with two different bandwidth values (4× on one session, 1× on the other) — and configuring the receiving PE to honor it.

The scorer's wECMP probe checks five things, all required to score full points (5/5):

1. **bl-w advertises ≥2 distinct link-bandwidth ext-community values** on its outbound DCI route announcements (one per session, so the receiving pe-w sees the asymmetry)
2. **bl-w's two values form a 4:1 ratio** (within ±10% tolerance)
3. **bl-e advertises ≥2 distinct link-bandwidth values** (same idea, mirrored on the east side)
4. **bl-e's two values form a 4:1 ratio**
5. **At least one PE has the Junos `bgp-multipath link-bandwidth` knob set** — without this, Junos receives the lbw ext-community but ignores it for unequal ECMP, and the 4:1 advertisement is silently wasted

If you only configure one BL or only configure the BL side without the PE knob, the probe will give partial credit but the run will not be COMPLETE. Both BLs and at least one PE must be set up.

`client-w` (attached to pe-w) and `client-e` (attached to pe-e) must both still reach the anycast VIP regardless — the wECMP only changes the *distribution* across links, not connectivity.

### 3.6 Anycast CDN VIP
- Both border-leaves originate `198.51.100.1/32` and `2001:db8:cafe::1/128` from a Loopback100 in VRF CDN.
- `client-w` (attached to pe-w) and `client-e` (attached to pe-e) must both be able to reach the anycast VIP. Each client should select the closer origin via shortest AS path / IGP cost / wECMP.

---

## 4. Hardening requirements

After connectivity is fully working (not before), apply security hardening across the lab. Each category is graded by an **automated probe (v2, tightened — anti-gaming)**. All seven must return PASS for the run to be COMPLETE.

The v1 probes were loose substring regexes against free-form `show` output. They have been replaced with v2 probes that anchor on specific config stanzas and require functional evidence. **Do not try to game the v2 probes** by inserting trigger words in descriptions, banners, prompts, or login announcements — the new probes only inspect specific source-of-truth show commands and use anchored regexes, and the negative-check probes (e.g., ISIS auth) will detect bypass knobs.

| # | Category | What the v2 probe verifies |
|---|---|---|
| 1 | **BGP MD5** | `set protocols bgp group <X> [neighbor <Y>] authentication-key` is configured on pe-w **AND** the iBGP session to `10.255.0.1` is `Established` (i.e. the auth actually works on the wire) |
| 2 | **ISIS auth** | `set protocols isis interface <X> hello-authentication-key` is configured on pe-w **AND** `set protocols isis no-authentication-check` is **ABSENT** (no bypass) |
| 3 | **SNMPv3** | `show snmp user` on l1-w returns a user with `Security model: v3` AND `Authentication: SHA` (or MD5) AND `Privacy: AES`/`AES-128`/`DES`. Operational view, not running-config. |
| 4 | **NTP auth** | l1-w running-config NTP section has ALL FOUR: `ntp authentication-key <N> ...`, `ntp trusted-key <N>`, `ntp authenticate`, AND `ntp server <X> ... key <N>` (a server reference using the key) |
| 5 | **AAA** | l1-w running-config AAA section has BOTH `aaa authentication login ...` AND `aaa authorization exec ...` (the v1 probe accepted either; v2 requires both) |
| 6 | **Syslog forwarding** | l1-w running-config logging section has BOTH `logging host 10.255.0.100` AND `logging source-interface Loopback0` |
| 7 | **Storm control** | l1-w running-config for `interfaces Ethernet3` has a real `storm-control <broadcast\|multicast\|unknown-unicast> level <N>` command (anchored to line start with leading whitespace, so a description containing the substring will NOT match) |

The probes inspect specific show commands and anchored config patterns. They are designed to fail if the feature is configured but not functional, or if you try to insert matching strings outside of the legitimate config location.

The exact CLI keys, algorithms, thresholds, and key names are your choice — only the structural presence and the functional state matter.

---

## 5. Constraints (do not violate)

- **Do not renumber loopbacks or interface IPs.** The baselines have the addressing the gate checks expect.
- **Do not change container images** in `topology/anycast-cdn-hardmode.clab.yml`.
- **Do not delete the baseline configs.** If you want a clean restart on a device, push minimal config — don't `clab destroy`.
- **No reference configs exist.** Don't grep for them. They are intentionally absent.
- **No hand-edited `frr.conf` on disk.** Push your FRR config via `vtysh -c` so the running config diverges from the baseline file in a way that's visible to `show running-config`.
- **All config push happens through the device CLI**, never by editing the bind-mounted files inside the container's filesystem from the host.

---

## 6. Gate-check tests (the 8 connectivity tests you must pass)

These run from the lab host. Each must succeed (`0% packet loss`) for the run to be marked complete.

```bash
# Intra-DC inter-VLAN (L3VNI symmetric IRB)
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -c3 192.168.11.10
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -6 -c3 2001:db8:11::10

# Cross-DC same-application (WAN MPLS L3VPN, both stacks)
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -c3 192.168.30.10
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -6 -c3 2001:db8:30::10

# IPv4 anycast from both clients
sudo docker exec clab-anycast-cdn-hardmode-client-w ping -c3 198.51.100.1
sudo docker exec clab-anycast-cdn-hardmode-client-e ping -c3 198.51.100.1

# IPv6 anycast from both clients
sudo docker exec clab-anycast-cdn-hardmode-client-w ping -6 -c3 2001:db8:cafe::1
sudo docker exec clab-anycast-cdn-hardmode-client-e ping -6 -c3 2001:db8:cafe::1
```

The scorer in `benchmark/scorer.py` runs these and reports PASS/FAIL per check. The run is considered "complete" only when all 8 pass AND all 7 hardening probes pass.

---

## 7. Device access (these patterns work — use them as-is)

You are running on the lab host directly. No SSH wrapping needed. The non-obvious gotchas are documented because losing iterations to CLI mechanics is wasteful.

### cEOS (Arista) — show & config
```bash
# Show command
sudo docker exec clab-anycast-cdn-hardmode-l1-w Cli -p 15 -c 'show ip bgp summary'

# Multi-line config (newlines inside the -c argument work):
sudo docker exec clab-anycast-cdn-hardmode-l1-w Cli -p 15 -c "configure
router bgp 65100
   router-id 10.255.10.11
   ...
end"
```

### Junos (Juniper vJunos-Evolved) — show & config
```bash
# Operational (show) command — printf piped to ssh, NEVER use ssh -tt
printf 'show isis adjacency\nexit\n' | \
  sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  admin@clab-anycast-cdn-hardmode-pe-w

# Config (notice 'configure', then set commands, then 'commit and-quit')
printf 'configure
set protocols isis interface et-0/0/5.0 level 2 metric 100
set ...
commit and-quit
' | sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  admin@clab-anycast-cdn-hardmode-pe-w
```

**CRITICAL**: do NOT use `ssh -tt` with heredocs or `<<EOF` — the session hangs because the pseudo-tty waits on terminal input. The `printf | ssh` pattern (no `-tt`) is the only one that works reliably.

### FRR (vtysh) — show & config
```bash
# Show command (suppress harmless vtysh.conf warning on stderr)
sudo docker exec clab-anycast-cdn-hardmode-rr1 vtysh -c 'show bgp summary' 2>/dev/null

# Multi-line config
sudo docker exec clab-anycast-cdn-hardmode-rr1 vtysh -c 'configure terminal
router bgp 65000
 ...
end'
```

`write memory` will fail because `frr.conf` is bind-mounted. That's expected and fine — the running config persists for the lifetime of the container.

### Linux hosts (h1-w, client-e, etc.) — direct exec
```bash
sudo docker exec clab-anycast-cdn-hardmode-h1-w ping -c3 192.168.30.10
sudo docker exec clab-anycast-cdn-hardmode-h1-w ip -6 route show
```

---

## 8. Verification cheat sheet (per vendor)

Use these to debug — they are NOT exhaustive but they cover the most useful queries.

### cEOS (Arista)
```
show ip bgp summary
show ip bgp neighbors <peer>
show bgp evpn summary
show bgp evpn route-type imet           # Type-3 IMET routes
show bgp evpn route-type mac-ip         # Type-2 MAC/IP routes
show vxlan vtep                         # remote VTEPs discovered via EVPN
show vxlan address-table                # learned remote MACs
show ip ospf neighbor
show ip route vrf CDN
show running-config section bgp
show running-config section vrf CDN
```

### Junos (Juniper)
```
show bgp summary
show bgp neighbor <peer>
show route table CDN.inet.0
show route table CDN.inet6.0
show route table bgp.l3vpn.0
show route table bgp.l3vpn-inet6.0
show route hidden                       # routes that won't install — start here for v6 trouble
show isis adjacency
show route protocol mpls
show configuration routing-instances CDN
show configuration protocols bgp
```

### FRR
```
show bgp summary
show bgp ipv4 vpn summary
show bgp ipv6 vpn summary
show bgp ipv4 vpn
show ip route
show isis neighbor
show running-config bgp
```

---

## 9. What you produce (deliverables)

Write each of these to `benchmark/` in the project root and commit them with the appropriate Agent identity (see BENCHMARK-PROMPT.md for git workflow):

| File | Purpose |
|------|---------|
| `benchmark/design.md` | Your architectural decisions and rationale, BEFORE you push any config. ~300-800 words. Graded for clarity and correctness, not length. |
| `topology/configs/{vendor}/{node}.conf` | The config you applied to each device, written as you go. These are the Gource animation surface — commit each one separately as you push it. |
| `benchmark/results.json` | Final scorer output (the scorer writes this; you don't have to construct it yourself). |
| `benchmark/blocker.md` | **Only** if you encounter a true platform-level blocker. Must include show command output as evidence. |

---

## 10. The persistence contract

You will be re-invoked iteratively. Each new iteration sees the previous iteration's `benchmark/scorer-last.json`. Do **not** stop at "good enough." Stop only when:

(a) the scorer reports 8/8 connectivity AND 7/7 hardening (run is complete), OR
(b) you have identified a platform-level issue you cannot work around at the configuration layer, and you have written `benchmark/blocker.md` with evidence.

If the previous iteration left things partially done, read `scorer-last.json` first, identify what's still failing, and continue from there. Devices keep state between iterations — you are fixing a partially-built network, not rebuilding from scratch.
