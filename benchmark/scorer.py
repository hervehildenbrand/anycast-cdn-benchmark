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

    total_earned = conn_earned + hard_earned
    total_max = conn_max + hard_max
    complete = (conn_earned >= conn_max - 0.01) and (hard_earned >= hard_max - 0.01)

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
