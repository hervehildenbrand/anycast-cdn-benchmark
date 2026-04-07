#!/usr/bin/env python3
"""
anycast-cdn-hardmode scorer.

Runs the 8 connectivity gate-checks + 7 hardening probes against the live lab
and writes a structured JSON result. No self-reporting; everything is verified
by actually executing show commands and pings against the running containers.

Usage:
    python3 scorer.py                  # full grading run
    python3 scorer.py --baseline-only  # smoke test, just confirms scorer works

Output:
    benchmark/scorer-last.json   (overwritten each run)
    stdout: short summary table
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LAB = "anycast-cdn-hardmode"
PREFIX = f"clab-{LAB}-"

# Each connectivity probe: (name, host_node, command, max_points)
CONNECTIVITY_PROBES = [
    ("intra-DC v4 inter-VLAN (h1-w → h2-w)", "h1-w", ["ping", "-c3", "-W2", "192.168.11.10"], 6.25),
    ("intra-DC v6 inter-VLAN (h1-w → h2-w)", "h1-w", ["ping", "-6", "-c3", "-W2", "2001:db8:11::10"], 6.25),
    ("cross-DC v4 (h1-w → h1-e)", "h1-w", ["ping", "-c3", "-W2", "192.168.30.10"], 6.25),
    ("cross-DC v6 (h1-w → h1-e)", "h1-w", ["ping", "-6", "-c3", "-W2", "2001:db8:30::10"], 6.25),
    ("client-w → anycast v4", "client-w", ["ping", "-c3", "-W2", "198.51.100.1"], 6.25),
    ("client-w → anycast v6", "client-w", ["ping", "-6", "-c3", "-W2", "2001:db8:cafe::1"], 6.25),
    ("client-e → anycast v4", "client-e", ["ping", "-c3", "-W2", "198.51.100.1"], 6.25),
    ("client-e → anycast v6", "client-e", ["ping", "-6", "-c3", "-W2", "2001:db8:cafe::1"], 6.25),
]

# Each hardening probe: (name, node, vendor, show_command, regex_evidence, max_points)
# Vendors: "arista", "junos", "frr"
# The probe is PASS iff the regex matches the show output.
HARDENING_PROBES = [
    ("BGP MD5 (PE iBGP)",     "pe-w",  "junos",  "show bgp neighbor 10.255.0.1",
        r"Authentication.*key.*configured|Authentication algorithm",            3.6),
    ("ISIS auth (PE)",        "pe-w",  "junos",  "show isis interface detail",
        r"hello-authentication|authentication-key-chain",                       3.6),
    ("SNMPv3 (Arista leaf)",  "l1-w",  "arista", "show running-config | section snmp-server",
        r"snmp-server\s+user\s+\S+\s+v3|snmp-server\s+group\s+.*v3",            3.6),
    ("NTP auth (Arista leaf)", "l1-w", "arista", "show running-config | section ntp",
        r"ntp\s+authenticate|ntp\s+authentication-key|ntp\s+server.*\bkey\b",   3.6),
    ("AAA (Arista leaf)",     "l1-w",  "arista", "show running-config | section aaa",
        r"aaa\s+authorization\s+exec|aaa\s+authentication\s+login",             3.6),
    ("Syslog forwarding (Arista leaf)", "l1-w", "arista", "show running-config | section logging",
        r"logging\s+host\s+10\.255\.0\.100",                                    3.6),
    ("Storm control (Arista leaf host port)", "l1-w", "arista",
        "show running-config interfaces Ethernet3",
        r"storm-control",                                                       3.4),
]


# ---------------------------------------------------------------------------
# Vendor exec wrappers
# ---------------------------------------------------------------------------

def run_host(node: str, argv: list[str], timeout: int = 15) -> tuple[int, str]:
    """Run a command inside a Linux netshoot host container."""
    cmd = ["sudo", "docker", "exec", PREFIX + node] + argv
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def run_arista(node: str, show_cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run an Arista cEOS Cli command."""
    cmd = ["sudo", "docker", "exec", PREFIX + node, "Cli", "-p", "15", "-c", show_cmd]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def run_frr(node: str, show_cmd: str, timeout: int = 15) -> tuple[int, str]:
    """Run an FRR vtysh command (suppress benign vtysh.conf stderr)."""
    cmd = ["sudo", "docker", "exec", PREFIX + node, "vtysh", "-c", show_cmd]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "")  # ignore stderr
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def run_junos(node: str, show_cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run a Junos operational command via printf | sshpass | ssh.

    Avoid ssh -tt (it hangs on heredoc). The pattern is: stdin = command + exit.
    """
    stdin = f"{show_cmd}\nexit\n"
    cmd = [
        "sshpass", "-p", "admin@123",
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        f"admin@{PREFIX}{node}",
    ]
    try:
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


VENDOR_RUNNERS = {
    "arista": run_arista,
    "junos":  run_junos,
    "frr":    run_frr,
}


# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------

def grade_connectivity() -> tuple[list[dict], float, float]:
    """Run all 8 ping probes. Return per-probe results, points earned, max points."""
    results = []
    earned = 0.0
    total = 0.0
    for name, host, argv, max_pts in CONNECTIVITY_PROBES:
        total += max_pts
        rc, out = run_host(host, argv)
        # Look for "0% packet loss" in ping output
        passed = rc == 0 and "0% packet loss" in out
        pts = max_pts if passed else 0.0
        earned += pts
        results.append({
            "category": "connectivity",
            "name": name,
            "host": host,
            "command": " ".join(argv),
            "passed": passed,
            "points": pts,
            "max_points": max_pts,
            "evidence": out.strip().splitlines()[-3:] if out else [],
        })
    return results, earned, total


def grade_hardening() -> tuple[list[dict], float, float]:
    """Run all 7 hardening probes. Return per-probe results, earned, max."""
    results = []
    earned = 0.0
    total = 0.0
    for name, node, vendor, show_cmd, regex, max_pts in HARDENING_PROBES:
        total += max_pts
        runner = VENDOR_RUNNERS[vendor]
        rc, out = runner(node, show_cmd)
        match = bool(re.search(regex, out, re.IGNORECASE | re.MULTILINE))
        passed = rc == 0 and match
        pts = max_pts if passed else 0.0
        earned += pts
        results.append({
            "category": "hardening",
            "name": name,
            "node": node,
            "vendor": vendor,
            "show_command": show_cmd,
            "regex": regex,
            "passed": passed,
            "points": pts,
            "max_points": max_pts,
            "rc": rc,
        })
    return results, earned, total


def grade_wecmp() -> tuple[list[dict], float, float]:
    """Verify weighted ECMP across DCI links produces a 4:1 ratio.

    5 sub-checks worth 1 point each (total 5):
      1. bl-w advertises link-bandwidth ext-community on its DCI sessions
         (at least two DISTINCT lbw values, indicating per-session weighting)
      2. bl-w's two lbw values form a 4:1 ratio (within 10% tolerance)
      3. bl-e advertises link-bandwidth ext-community
      4. bl-e's two lbw values form a 4:1 ratio
      5. At least one PE has the Junos `bgp-multipath link-bandwidth` knob set,
         which is what makes Junos honor the lbw ext-community for unequal ECMP.
         Without this knob, the BL advertisements are ignored on the receiving side.

    These checks are deliberately structural — they verify the *configuration*
    that produces 4:1, not the data plane distribution itself (which would
    require traffic generation).
    """
    results = []
    earned = 0.0
    total = 5.0

    def add(name: str, passed: bool, evidence: str = "") -> None:
        nonlocal earned
        pts = 1.0 if passed else 0.0
        earned += pts
        results.append({
            "category": "wecmp",
            "name": name,
            "passed": passed,
            "points": pts,
            "max_points": 1.0,
            "evidence": evidence[:200],
        })

    # bl-w running config (BGP section + any route-maps it references)
    rc, bl_w_run = run_arista("bl-w", "show running-config")
    bl_w_lbw_values = [int(v) for v in re.findall(
        r"set\s+extcommunity\s+lbw\s+(\d+)", bl_w_run, re.IGNORECASE)]
    bl_w_distinct = len(set(bl_w_lbw_values)) >= 2
    add("bl-w advertises ≥2 distinct link-bandwidth values on DCI",
        bl_w_distinct,
        f"lbw values found: {bl_w_lbw_values}")

    bl_w_ratio_ok = False
    if bl_w_distinct:
        nums = sorted(set(bl_w_lbw_values))
        ratio = nums[-1] / nums[0]
        bl_w_ratio_ok = 3.5 <= ratio <= 4.5
        add("bl-w lbw ratio is 4:1 (±10%)", bl_w_ratio_ok,
            f"min={nums[0]} max={nums[-1]} ratio={ratio:.2f}")
    else:
        add("bl-w lbw ratio is 4:1 (±10%)", False,
            "skipped: no distinct lbw values to compare")

    # bl-e running config
    rc, bl_e_run = run_arista("bl-e", "show running-config")
    bl_e_lbw_values = [int(v) for v in re.findall(
        r"set\s+extcommunity\s+lbw\s+(\d+)", bl_e_run, re.IGNORECASE)]
    bl_e_distinct = len(set(bl_e_lbw_values)) >= 2
    add("bl-e advertises ≥2 distinct link-bandwidth values on DCI",
        bl_e_distinct,
        f"lbw values found: {bl_e_lbw_values}")

    bl_e_ratio_ok = False
    if bl_e_distinct:
        nums = sorted(set(bl_e_lbw_values))
        ratio = nums[-1] / nums[0]
        bl_e_ratio_ok = 3.5 <= ratio <= 4.5
        add("bl-e lbw ratio is 4:1 (±10%)", bl_e_ratio_ok,
            f"min={nums[0]} max={nums[-1]} ratio={ratio:.2f}")
    else:
        add("bl-e lbw ratio is 4:1 (±10%)", False,
            "skipped: no distinct lbw values to compare")

    # PE side honors link-bandwidth (Junos knob)
    rc, pe_w_bgp = run_junos("pe-w", "show configuration protocols bgp")
    pe_w_honors = bool(re.search(r"link-bandwidth", pe_w_bgp, re.IGNORECASE))
    rc, pe_e_bgp = run_junos("pe-e", "show configuration protocols bgp")
    pe_e_honors = bool(re.search(r"link-bandwidth", pe_e_bgp, re.IGNORECASE))
    add("≥1 PE honors link-bandwidth (Junos `bgp-multipath link-bandwidth`)",
        pe_w_honors or pe_e_honors,
        f"pe-w={pe_w_honors} pe-e={pe_e_honors}")

    return results, earned, total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-only", action="store_true",
                        help="Smoke test only — confirms scorer can reach the lab and "
                             "expects everything to fail (lab unconfigured).")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "scorer-last.json")
    args = parser.parse_args()

    started = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()

    print(f"=" * 70)
    print(f"anycast-cdn-hardmode scorer  ({started_iso})")
    print(f"=" * 70)

    conn_results, conn_earned, conn_max = grade_connectivity()
    hard_results, hard_earned, hard_max = grade_hardening()
    wecmp_results, wecmp_earned, wecmp_max = grade_wecmp()

    elapsed = time.time() - started

    print()
    print(f"--- Connectivity ({conn_earned:.1f}/{conn_max:.1f}) ---")
    for r in conn_results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['name']}")

    print()
    print(f"--- Hardening ({hard_earned:.1f}/{hard_max:.1f}) ---")
    for r in hard_results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['name']}")

    print()
    print(f"--- wECMP ({wecmp_earned:.1f}/{wecmp_max:.1f}) ---")
    for r in wecmp_results:
        mark = "PASS" if r["passed"] else "FAIL"
        ev = r.get("evidence", "")
        suffix = f"  ({ev})" if ev else ""
        print(f"  [{mark}] {r['name']}{suffix}")

    total_earned = conn_earned + hard_earned + wecmp_earned
    total_max = conn_max + hard_max + wecmp_max
    complete = (
        conn_earned >= conn_max - 0.01
        and hard_earned >= hard_max - 0.01
        and wecmp_earned >= wecmp_max - 0.01
    )

    print()
    print(f"=" * 70)
    print(f"TOTAL: {total_earned:.1f}/{total_max:.1f}     ({elapsed:.1f}s)")
    print(f"COMPLETE: {complete}")
    print(f"=" * 70)

    payload = {
        "lab": LAB,
        "started": started_iso,
        "elapsed_seconds": round(elapsed, 1),
        "connectivity": {
            "earned": round(conn_earned, 1),
            "max":    round(conn_max, 1),
            "pass_count": sum(1 for r in conn_results if r["passed"]),
            "total":      len(conn_results),
            "results":    conn_results,
        },
        "hardening": {
            "earned": round(hard_earned, 1),
            "max":    round(hard_max, 1),
            "pass_count": sum(1 for r in hard_results if r["passed"]),
            "total":      len(hard_results),
            "results":    hard_results,
        },
        "wecmp": {
            "earned": round(wecmp_earned, 1),
            "max":    round(wecmp_max, 1),
            "pass_count": sum(1 for r in wecmp_results if r["passed"]),
            "total":      len(wecmp_results),
            "results":    wecmp_results,
        },
        "total": {
            "earned":   round(total_earned, 1),
            "max":      round(total_max, 1),
            "complete": complete,
        },
        "baseline_only": args.baseline_only,
    }
    args.output.write_text(json.dumps(payload, indent=2))
    print(f"\nWrote {args.output}")

    if args.baseline_only:
        # In baseline mode, ALL probes should fail. Exit non-zero if any pass
        # (would indicate the lab is contaminated with pre-applied config).
        if total_earned > 0.01:
            print(f"\nWARN: --baseline-only but {total_earned:.1f} pts already earned. "
                  f"Lab is not in clean state.")
            sys.exit(2)
        sys.exit(0)

    # Non-zero exit if not complete (so the run-harness loop knows)
    sys.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
