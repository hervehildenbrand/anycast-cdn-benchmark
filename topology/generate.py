#!/usr/bin/env python3
"""
Anycast CDN Final Topology Generator

Generates an 18-node simplified 2-DC anycast CDN topology:
- 2 FRR Route Reflectors: rr1, rr2 (quay.io/frrouting/frr:10.5.1)
- 2 Juniper vJunosEvolved PEs: pe-w, pe-e (vrnetlab/juniper_vjunosevolved:25.2R1.8-EVO)
- 8 Arista cEOS: DC-WEST (spine-w, l1-w, l2-w, bl-w), DC-EAST (spine-e, l1-e, l2-e, bl-e)
- 6 Linux hosts: h1-w, h2-w, h1-e, h2-e, client-w, client-e

Key Features:
- Dual-stack IPv4+IPv6 throughout
- FRR RRs with ISIS + BGP VPNv4/VPNv6
- ISIS-SR on WAN backbone
- EVPN-VXLAN DC fabrics with anycast gateway
- wECMP with link-bandwidth (40:60 west:east)
- Anycast CDN prefix 198.51.100.0/24 + 2001:db8:cafe::/48

Produces:
- ContainerLab YAML
- FRR configs (daemons + frr.conf)
- Baseline Juniper/Arista configs (hostname + interfaces only)
- Reference configs (verbose with QoS, firewall, SNMP, NTP, etc.)
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# =============================================================================
# Constants
# =============================================================================

LAB_NAME = "anycast-cdn-hardmode"
REMOTE_BASE = "/home/hhildenbrand/remote-lab/projects/anycast-cdn-hardmode/topology"

# Images
FRR_IMAGE = "quay.io/frrouting/frr:10.5.1"
JUNOS_IMAGE = "vrnetlab/juniper_vjunosevolved:25.2R1.8-EVO"
CEOS_IMAGE = "ceos:4.35.1F"
HOST_IMAGE = "nicolaka/netshoot"

# AS Numbers
WAN_ASN = 65000
DC_WEST_ASN = 65100
DC_EAST_ASN = 65300

# ISIS/SR Parameters
ISIS_AREA = "49.0001"
SRGB_START = 16000
SRGB_END = 23999
SRGB_RANGE = SRGB_END - SRGB_START + 1

# VRF/VXLAN Parameters
ANYCAST_GW_MAC = "00:1c:73:00:00:99"
ANYCAST_PREFIX_V4 = "198.51.100.0/24"
ANYCAST_PREFIX_V6 = "2001:db8:cafe::/48"

# wECMP weights (multiplied by 100 for link-bandwidth in Kbps)
WECMP_WEIGHTS = {"west": 4000, "east": 6000}

# DC VLANs
DC_WEST_VLANS = {"v10": 10, "v11": 11}  # VNI 10010, 10011
DC_EAST_VLANS = {"v30": 30, "v31": 31}  # VNI 10030, 10031

# VRF Definition
VRF_CDN = {
    "name": "CDN",
    "rd": "65000:100",
    "rt": "65000:100",
    "l3vni": 50100,
    "vlan_l3": 4001,
}

# =============================================================================
# Node Definitions
# =============================================================================

# FRR Route Reflectors
FRR_NODES = {
    "rr1": {"lo": "10.255.0.1", "lo_v6": "fd00::1", "sid": 1},
    "rr2": {"lo": "10.255.0.2", "lo_v6": "fd00::2", "sid": 2},
}

# Juniper PEs
JUNIPER_NODES = {
    "pe-w": {"lo": "10.255.0.11", "lo_v6": "fd00::11", "sid": 11, "dc": "west"},
    "pe-e": {"lo": "10.255.0.13", "lo_v6": "fd00::13", "sid": 13, "dc": "east"},
}

# Arista DC Nodes
ARISTA_NODES = {
    # DC-WEST (AS 65100)
    "spine-w": {
        "lo": "10.255.10.1",
        "lo_v6": "fd00:10::1",
        "role": "spine",
        "dc": "west",
    },
    "l1-w": {
        "lo": "10.255.10.11",
        "lo_v6": "fd00:10::11",
        "vtep": "10.255.11.11",
        "role": "leaf",
        "dc": "west",
        "vlan": 10,
        "vni": 10010,
    },
    "l2-w": {
        "lo": "10.255.10.12",
        "lo_v6": "fd00:10::12",
        "vtep": "10.255.11.12",
        "role": "leaf",
        "dc": "west",
        "vlan": 11,
        "vni": 10011,
    },
    "bl-w": {
        "lo": "10.255.10.21",
        "lo_v6": "fd00:10::21",
        "vtep": "10.255.11.21",
        "role": "border-leaf",
        "dc": "west",
    },
    # DC-EAST (AS 65300)
    "spine-e": {
        "lo": "10.255.30.1",
        "lo_v6": "fd00:30::1",
        "role": "spine",
        "dc": "east",
    },
    "l1-e": {
        "lo": "10.255.30.11",
        "lo_v6": "fd00:30::11",
        "vtep": "10.255.31.11",
        "role": "leaf",
        "dc": "east",
        "vlan": 30,
        "vni": 10030,
    },
    "l2-e": {
        "lo": "10.255.30.12",
        "lo_v6": "fd00:30::12",
        "vtep": "10.255.31.12",
        "role": "leaf",
        "dc": "east",
        "vlan": 31,
        "vni": 10031,
    },
    "bl-e": {
        "lo": "10.255.30.21",
        "lo_v6": "fd00:30::21",
        "vtep": "10.255.31.21",
        "role": "border-leaf",
        "dc": "east",
    },
}

# Host Nodes
HOST_NODES = {
    # DC-WEST hosts
    "h1-w": {
        "ip": "192.168.10.10/24",
        "ip_v6": "2001:db8:10::10/64",
        "gw": "192.168.10.1",
        "gw_v6": "2001:db8:10::1",
        "vlan": 10,
        "leaf": "l1-w",
        "dc": "west",
    },
    "h2-w": {
        "ip": "192.168.11.10/24",
        "ip_v6": "2001:db8:11::10/64",
        "gw": "192.168.11.1",
        "gw_v6": "2001:db8:11::1",
        "vlan": 11,
        "leaf": "l2-w",
        "dc": "west",
    },
    # DC-EAST hosts
    "h1-e": {
        "ip": "192.168.30.10/24",
        "ip_v6": "2001:db8:30::10/64",
        "gw": "192.168.30.1",
        "gw_v6": "2001:db8:30::1",
        "vlan": 30,
        "leaf": "l1-e",
        "dc": "east",
    },
    "h2-e": {
        "ip": "192.168.31.10/24",
        "ip_v6": "2001:db8:31::10/64",
        "gw": "192.168.31.1",
        "gw_v6": "2001:db8:31::1",
        "vlan": 31,
        "leaf": "l2-e",
        "dc": "east",
    },
    # Client hosts on PEs
    "client-w": {
        "ip": "10.100.0.1/31",
        "ip_v6": "fd00:100::1/127",
        "gw": "10.100.0.0",
        "gw_v6": "fd00:100::",
        "vlan": 0,
        "leaf": None,
        "dc": "west",
    },
    "client-e": {
        "ip": "10.100.2.1/31",
        "ip_v6": "fd00:100:2::1/127",
        "gw": "10.100.2.0",
        "gw_v6": "fd00:100:2::",
        "vlan": 0,
        "leaf": None,
        "dc": "east",
    },
}

# =============================================================================
# Link Definitions
# =============================================================================

# WAN Links: (nodeA, ethA, nodeB, ethB, ip4_a, ip4_b, ip6_a, ip6_b)
WAN_LINKS = [
    # rr1 <-> rr2
    ("rr1", "eth1", "rr2", "eth1", "10.0.0.0", "10.0.0.1", "fd00:0:0::0", "fd00:0:0::1"),
    # rr1 to PEs
    ("rr1", "eth2", "pe-w", "eth1", "10.0.0.2", "10.0.0.3", "fd00:0:1::0", "fd00:0:1::1"),
    ("rr1", "eth3", "pe-e", "eth1", "10.0.0.4", "10.0.0.5", "fd00:0:2::0", "fd00:0:2::1"),
    # rr2 to PEs
    ("rr2", "eth2", "pe-w", "eth2", "10.0.0.6", "10.0.0.7", "fd00:0:3::0", "fd00:0:3::1"),
    ("rr2", "eth3", "pe-e", "eth2", "10.0.0.8", "10.0.0.9", "fd00:0:4::0", "fd00:0:4::1"),
    # PE-PE direct link for MPLS transport
    ("pe-w", "eth6", "pe-e", "eth6", "10.0.0.10", "10.0.0.11", "fd00:0:5::0", "fd00:0:5::1"),
]

# DCI Links (PE to BL): (pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, ip6_pe, ip6_bl)
DCI_LINKS = [
    ("pe-w", "eth3", "bl-w", "Ethernet3", "10.2.0.0", "10.2.0.1", "fd00:2::0", "fd00:2::1"),
    ("pe-w", "eth4", "bl-w", "Ethernet4", "10.2.0.2", "10.2.0.3", "fd00:2:1::0", "fd00:2:1::1"),
    ("pe-e", "eth3", "bl-e", "Ethernet3", "10.2.0.4", "10.2.0.5", "fd00:2:2::0", "fd00:2:2::1"),
    ("pe-e", "eth4", "bl-e", "Ethernet4", "10.2.0.6", "10.2.0.7", "fd00:2:3::0", "fd00:2:3::1"),
]

# Client Links (PE to client hosts)
CLIENT_LINKS = [
    ("pe-w", "eth5", "client-w", "eth1", "10.100.0.0", "10.100.0.1", "fd00:100::0", "fd00:100::1"),
    ("pe-e", "eth5", "client-e", "eth1", "10.100.2.0", "10.100.2.1", "fd00:100:2::0", "fd00:100:2::1"),
]

# DC Fabric Links: (nodeA, ethA, nodeB, ethB, ip4_a, ip4_b, ip6_a, ip6_b)
FABRIC_LINKS = [
    # DC-WEST
    ("spine-w", "Ethernet1", "l1-w", "Ethernet1", "10.1.0.0", "10.1.0.1", "fd00:1:0::0", "fd00:1:0::1"),
    ("spine-w", "Ethernet2", "l2-w", "Ethernet1", "10.1.0.2", "10.1.0.3", "fd00:1:1::0", "fd00:1:1::1"),
    ("spine-w", "Ethernet3", "bl-w", "Ethernet1", "10.1.0.4", "10.1.0.5", "fd00:1:2::0", "fd00:1:2::1"),
    ("spine-w", "Ethernet4", "bl-w", "Ethernet2", "10.1.0.6", "10.1.0.7", "fd00:1:3::0", "fd00:1:3::1"),
    # DC-EAST
    ("spine-e", "Ethernet1", "l1-e", "Ethernet1", "10.1.20.0", "10.1.20.1", "fd00:1:20::0", "fd00:1:20::1"),
    ("spine-e", "Ethernet2", "l2-e", "Ethernet1", "10.1.20.2", "10.1.20.3", "fd00:1:21::0", "fd00:1:21::1"),
    ("spine-e", "Ethernet3", "bl-e", "Ethernet1", "10.1.20.4", "10.1.20.5", "fd00:1:22::0", "fd00:1:22::1"),
    ("spine-e", "Ethernet4", "bl-e", "Ethernet2", "10.1.20.6", "10.1.20.7", "fd00:1:23::0", "fd00:1:23::1"),
]

# Host Links (leaf to host)
HOST_LINKS = [
    ("l1-w", "Ethernet3", "h1-w", "eth1"),
    ("l2-w", "Ethernet3", "h2-w", "eth1"),
    ("l1-e", "Ethernet3", "h1-e", "eth1"),
    ("l2-e", "Ethernet3", "h2-e", "eth1"),
]

# =============================================================================
# Helper Functions
# =============================================================================

def isis_net(lo_ip: str) -> str:
    """Generate ISIS NET from loopback IP."""
    octets = lo_ip.split(".")
    padded = "".join(o.zfill(3) for o in octets)
    return f"{ISIS_AREA}.{padded[0:4]}.{padded[4:8]}.{padded[8:12]}.00"


def get_frr_ifaces(name: str) -> list:
    """Get interfaces for an FRR node."""
    ifaces = []
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in WAN_LINKS:
        if a == name:
            ifaces.append((ifa, b, ip4_a, ip4_b, ip6_a, ip6_b))
        elif b == name:
            ifaces.append((ifb, a, ip4_b, ip4_a, ip6_b, ip6_a))
    return ifaces


def get_juniper_ifaces(name: str) -> list:
    """Get interfaces for a Juniper node."""
    ifaces = []
    # WAN links
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in WAN_LINKS:
        if a == name:
            ifaces.append((ifa, b, ip4_a, ip4_b, ip6_a, ip6_b))
        elif b == name:
            ifaces.append((ifb, a, ip4_b, ip4_a, ip6_b, ip6_a))
    # DCI links
    for pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, ip6_pe, ip6_bl in DCI_LINKS:
        if pe == name:
            ifaces.append((pe_eth, bl, ip4_pe, ip4_bl, ip6_pe, ip6_bl))
    # Client links
    for cl in CLIENT_LINKS:
        if name == cl[0]:
            ifaces.append((cl[1], cl[2], cl[4], cl[5], cl[6], cl[7]))
    return ifaces


def eth_to_junos(eth: str) -> str:
    """Convert ethN to et-0/0/N-1 for Junos."""
    if eth.startswith("eth"):
        num = int(eth[3:]) - 1
        return f"et-0/0/{num}"
    return eth


def get_arista_ifaces(name: str) -> list:
    """Get interfaces for an Arista node."""
    ifaces = []
    # Fabric links
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in FABRIC_LINKS:
        if a == name:
            ifaces.append((ifa, b, ip4_a, ip4_b, ip6_a, ip6_b))
        elif b == name:
            ifaces.append((ifb, a, ip4_b, ip4_a, ip6_b, ip6_a))
    # DCI links (for border-leaves)
    for pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, ip6_pe, ip6_bl in DCI_LINKS:
        if bl == name:
            ifaces.append((bl_eth, pe, ip4_bl, ip4_pe, ip6_bl, ip6_pe))
    return ifaces


# =============================================================================
# FRR Config Generation
# =============================================================================

def gen_frr_daemons() -> str:
    """Generate FRR daemons file."""
    return """# FRR Daemons Configuration
bgpd=yes
ospfd=no
ospf6d=no
ripd=no
ripngd=no
isisd=yes
pimd=no
pim6d=no
ldpd=no
nhrpd=no
eigrpd=no
babeld=no
sharpd=no
pbrd=no
bfdd=yes
fabricd=no
vrrpd=no
pathd=no
staticd=yes

vtysh_enable=yes
zebra_options="  -A 127.0.0.1 -s 90000000"
bgpd_options="   -A 127.0.0.1"
isisd_options="  -A 127.0.0.1"
staticd_options="-A 127.0.0.1"
bfdd_options="   -A 127.0.0.1"
"""


def gen_frr_baseline(name: str, node: dict) -> str:
    """Generate FRR baseline (hostname + interfaces with IPs only, no protocols).

    Used by hardmode: agent must design and apply IS-IS, BGP, statics, etc.
    from the architecture intent.
    """
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    ifaces = get_frr_ifaces(name)

    lines = []
    lines.append(f"! FRR Baseline for {name} (Route Reflector)")
    lines.append(f"! Loopback: {lo}, {lo_v6}")
    lines.append(f"! No routing protocols configured. Agent must design and apply.")
    lines.append("")
    lines.append("frr version 10.5.1")
    lines.append("frr defaults traditional")
    lines.append(f"hostname {name}")
    lines.append("log syslog informational")
    lines.append("service integrated-vtysh-config")
    lines.append("!")
    lines.append("interface lo")
    lines.append(f" ip address {lo}/32")
    lines.append(f" ipv6 address {lo_v6}/128")
    lines.append("exit")
    lines.append("!")
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces):
        lines.append(f"interface {iface}")
        lines.append(f" description to-{remote}")
        lines.append(f" ip address {ip4_local}/31")
        lines.append(f" ipv6 address {ip6_local}/127")
        lines.append("exit")
        lines.append("!")
    lines.append("end")
    return "\n".join(lines)


def gen_frr_config(name: str, node: dict) -> str:
    """Generate FRR frr.conf for route reflector."""
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    sid = node["sid"]
    ifaces = get_frr_ifaces(name)

    lines = []
    lines.append(f"! FRR Configuration for {name}")
    lines.append(f"! Role: Route Reflector (RR)")
    lines.append(f"! Loopback: {lo}, {lo_v6}")
    lines.append(f"! Node-SID: {sid}")
    lines.append("")
    lines.append(f"frr version 10.5.1")
    lines.append(f"frr defaults traditional")
    lines.append(f"hostname {name}")
    lines.append("log syslog informational")
    lines.append("service integrated-vtysh-config")
    lines.append("!")

    # Interface configurations
    lines.append("! ========================================")
    lines.append("! INTERFACE CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")

    # Loopback
    lines.append("interface lo")
    lines.append(f" ip address {lo}/32")
    lines.append(f" ipv6 address {lo_v6}/128")
    lines.append(" ip router isis WAN")
    lines.append(" ipv6 router isis WAN")
    lines.append(f" isis passive")
    lines.append("exit")
    lines.append("!")

    # P2P interfaces
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces):
        lines.append(f"interface {iface}")
        lines.append(f" description to-{remote}")
        lines.append(f" ip address {ip4_local}/31")
        lines.append(f" ipv6 address {ip6_local}/127")
        lines.append(" ip router isis WAN")
        lines.append(" ipv6 router isis WAN")
        lines.append(" isis network point-to-point")
        lines.append(" isis circuit-type level-2-only")
        lines.append("exit")
        lines.append("!")

    # Static routes to PE loopbacks (IS-IS auth mismatch with Junos prevents
    # IGP adjacency on PE-RR links, so we reach PE loopbacks via direct-link statics)
    lines.append("! ========================================")
    lines.append("! STATIC ROUTES (PE loopbacks via direct links)")
    lines.append("! ========================================")
    lines.append("!")
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in WAN_LINKS:
        if a == name and b in JUNIPER_NODES:
            lines.append(f"ip route {JUNIPER_NODES[b]['lo']}/32 {ip4_b}")
            lines.append(f"ipv6 route {JUNIPER_NODES[b]['lo_v6']}/128 {ip6_b}")
        elif b == name and a in JUNIPER_NODES:
            lines.append(f"ip route {JUNIPER_NODES[a]['lo']}/32 {ip4_a}")
            lines.append(f"ipv6 route {JUNIPER_NODES[a]['lo_v6']}/128 {ip6_a}")
    lines.append("!")

    # ISIS Configuration
    lines.append("! ========================================")
    lines.append("! ISIS CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("router isis WAN")
    lines.append(f" net {isis_net(lo)}")
    lines.append(" is-type level-2-only")
    lines.append(" log-adjacency-changes")
    lines.append(" metric-style wide")
    lines.append(" !")
    lines.append(f" segment-routing on")
    lines.append(f" segment-routing global-block {SRGB_START} {SRGB_END}")
    lines.append(f" segment-routing node-msd 8")
    lines.append(f" segment-routing prefix {lo}/32 index {sid}")
    lines.append("exit")
    lines.append("!")

    # BGP Configuration
    lines.append("! ========================================")
    lines.append("! BGP CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append(f"router bgp {WAN_ASN}")
    lines.append(f" bgp router-id {lo}")
    lines.append(" bgp log-neighbor-changes")
    lines.append(" no bgp default ipv4-unicast")
    lines.append(" bgp bestpath as-path multipath-relax")
    lines.append(" !")
    lines.append(" ! RR Mesh peer group")
    lines.append(" neighbor RR-MESH peer-group")
    lines.append(f" neighbor RR-MESH remote-as {WAN_ASN}")
    lines.append(f" neighbor RR-MESH update-source lo")
    lines.append(" !")
    lines.append(" ! RR Client peer group (PEs) - VPNv4 over v4 transport")
    lines.append(" neighbor RR-CLIENTS peer-group")
    lines.append(f" neighbor RR-CLIENTS remote-as {WAN_ASN}")
    lines.append(f" neighbor RR-CLIENTS update-source lo")
    lines.append(" neighbor RR-CLIENTS route-reflector-client")
    lines.append(" !")
    lines.append(" ! RR Client peer group (PEs) - VPNv6 over v6 transport")
    lines.append(" ! (separate group required: v4-mapped v6 next-hops can't resolve")
    lines.append(" !  in inet6.3, so we use native v6 transport with v6 next-hops)")
    lines.append(" neighbor RR-CLIENTS-V6 peer-group")
    lines.append(f" neighbor RR-CLIENTS-V6 remote-as {WAN_ASN}")
    lines.append(f" neighbor RR-CLIENTS-V6 update-source lo")
    lines.append(" neighbor RR-CLIENTS-V6 route-reflector-client")
    lines.append(" !")

    # Add neighbors
    other_rr = [n for n in FRR_NODES if n != name]
    for rr in other_rr:
        lines.append(f" neighbor {FRR_NODES[rr]['lo']} peer-group RR-MESH")

    for pe_name, pe in JUNIPER_NODES.items():
        lines.append(f" neighbor {pe['lo']} peer-group RR-CLIENTS")
        lines.append(f" neighbor {pe['lo_v6']} peer-group RR-CLIENTS-V6")

    lines.append(" !")
    lines.append(" ! VPNv4 Address Family")
    lines.append(" address-family ipv4 vpn")
    lines.append("  neighbor RR-MESH activate")
    lines.append("  neighbor RR-MESH send-community extended")
    lines.append("  neighbor RR-CLIENTS activate")
    lines.append("  neighbor RR-CLIENTS send-community extended")
    lines.append(" exit-address-family")
    lines.append(" !")
    lines.append(" ! VPNv6 Address Family - reflected to RR-CLIENTS-V6 (v6 transport)")
    lines.append(" address-family ipv6 vpn")
    lines.append("  neighbor RR-MESH activate")
    lines.append("  neighbor RR-MESH send-community extended")
    lines.append("  neighbor RR-CLIENTS-V6 activate")
    lines.append("  neighbor RR-CLIENTS-V6 send-community extended")
    lines.append(" exit-address-family")
    lines.append("exit")
    lines.append("!")
    lines.append("end")

    return "\n".join(lines)


# =============================================================================
# Juniper Config Generation (Baseline)
# =============================================================================

def gen_juniper_baseline(name: str, node: dict) -> str:
    """Generate baseline Juniper config (hostname + interfaces only)."""
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    ifaces = get_juniper_ifaces(name)

    lines = []
    lines.append(f"/* {name} - Baseline Configuration */")
    lines.append(f"/* Role: PE Router, DC: {node['dc']} */")
    lines.append("")
    lines.append("system {")
    lines.append(f"    host-name {name};")
    lines.append("    services {")
    lines.append("        ssh;")
    lines.append("        netconf {")
    lines.append("            ssh;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append("interfaces {")

    # P2P interfaces
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces, key=lambda x: x[0]):
        junos_if = eth_to_junos(iface)
        lines.append(f"    {junos_if} {{")
        lines.append(f'        description "to {remote}";')
        lines.append(f"        mtu 9200;")
        lines.append(f"        unit 0 {{")
        lines.append(f"            family inet {{")
        lines.append(f"                address {ip4_local}/31;")
        lines.append(f"            }}")
        lines.append(f"            family inet6 {{")
        lines.append(f"                address {ip6_local}/127;")
        lines.append(f"            }}")
        lines.append(f"            family iso;")
        lines.append(f"            family mpls;")
        lines.append(f"        }}")
        lines.append(f"    }}")

    # Loopback
    lines.append(f"    lo0 {{")
    lines.append(f"        unit 0 {{")
    lines.append(f"            family inet {{")
    lines.append(f"                address {lo}/32;")
    lines.append(f"            }}")
    lines.append(f"            family inet6 {{")
    lines.append(f"                address {lo_v6}/128;")
    lines.append(f"            }}")
    lines.append(f"            family iso {{")
    lines.append(f"                address {isis_net(lo)};")
    lines.append(f"            }}")
    lines.append(f"        }}")
    lines.append(f"    }}")
    lines.append("}")

    return "\n".join(lines)


# =============================================================================
# Juniper Config Generation (Reference - Full)
# =============================================================================

def gen_juniper_reference(name: str, node: dict) -> str:
    """Generate full reference Juniper config with QoS, firewall, SNMP, NTP, etc."""
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    sid = node["sid"]
    dc = node["dc"]
    ifaces = get_juniper_ifaces(name)
    weight = WECMP_WEIGHTS[dc]

    lines = []
    lines.append(f"/* ================================================================")
    lines.append(f" * {name.upper()} - REFERENCE CONFIGURATION")
    lines.append(f" * ================================================================")
    lines.append(f" * Role: Provider Edge (PE) Router")
    lines.append(f" * Data Center: {dc.upper()}")
    lines.append(f" * Loopback IPv4: {lo}")
    lines.append(f" * Loopback IPv6: {lo_v6}")
    lines.append(f" * Node-SID: {sid}")
    lines.append(f" * wECMP Weight: {weight} (link-bandwidth)")
    lines.append(f" * ================================================================ */")
    lines.append("")

    # ========================================
    # SYSTEM CONFIGURATION
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * SYSTEM CONFIGURATION")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("system {")
    lines.append(f"    host-name {name};")
    lines.append("    time-zone UTC;")
    lines.append("    root-authentication {")
    lines.append('        encrypted-password "$6$rounds=656000$encrypted$hash";')
    lines.append("    }")
    lines.append("    login {")
    lines.append('        message "\\n*** AUTHORIZED ACCESS ONLY ***\\nAll activities are logged and monitored.\\n";')
    lines.append("        retry-options {")
    lines.append("            tries-before-disconnect 3;")
    lines.append("            backoff-threshold 1;")
    lines.append("            backoff-factor 5;")
    lines.append("            minimum-time 30;")
    lines.append("        }")
    lines.append("        class super-user-local {")
    lines.append("            idle-timeout 15;")
    lines.append("            permissions all;")
    lines.append("        }")
    lines.append("        user admin {")
    lines.append("            uid 2000;")
    lines.append("            class super-user-local;")
    lines.append("            authentication {")
    lines.append('                encrypted-password "$6$rounds=656000$encrypted$hash";')
    lines.append("            }")
    lines.append("        }")
    lines.append("        user operator {")
    lines.append("            uid 2001;")
    lines.append("            class read-only;")
    lines.append("            authentication {")
    lines.append('                encrypted-password "$6$rounds=656000$encrypted$hash";')
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("    services {")
    lines.append("        ssh {")
    lines.append("            root-login deny;")
    lines.append("            protocol-version v2;")
    lines.append("            max-sessions-per-connection 5;")
    lines.append("            connection-limit 10;")
    lines.append("            rate-limit 5;")
    lines.append("        }")
    lines.append("        netconf {")
    lines.append("            ssh;")
    lines.append("            rfc-compliant;")
    lines.append("        }")
    lines.append("        web-management {")
    lines.append("            https {")
    lines.append("                system-generated-certificate;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("    syslog {")
    lines.append("        user * {")
    lines.append("            any emergency;")
    lines.append("        }")
    lines.append("        file messages {")
    lines.append("            any notice;")
    lines.append("            authorization info;")
    lines.append("        }")
    lines.append("        file interactive-commands {")
    lines.append("            interactive-commands any;")
    lines.append("        }")
    lines.append("        file security {")
    lines.append("            authorization info;")
    lines.append("            firewall any;")
    lines.append("        }")
    lines.append("        host 10.255.0.100 {")
    lines.append("            any warning;")
    lines.append("            facility-override local7;")
    lines.append("        }")
    lines.append("        source-address lo0;")
    lines.append("    }")
    lines.append("    ntp {")
    lines.append("        boot-server 10.255.0.100;")
    lines.append("        server 10.255.0.100 prefer;")
    lines.append("        server 10.255.0.101;")
    lines.append("        source-address lo0;")
    lines.append("    }")
    lines.append("    archival {")
    lines.append("        configuration {")
    lines.append("            transfer-on-commit;")
    lines.append("            archive-sites {")
    lines.append("                scp://backup@10.255.0.100:/backup/;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # CHASSIS CONFIGURATION
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * CHASSIS CONFIGURATION")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("chassis {")
    lines.append("    aggregated-devices {")
    lines.append("        ethernet {")
    lines.append("            device-count 10;")
    lines.append("        }")
    lines.append("    }")
    lines.append("    network-services enhanced-ip;")
    lines.append("}")
    lines.append("")

    # ========================================
    # INTERFACES CONFIGURATION
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * INTERFACES CONFIGURATION")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("interfaces {")

    # P2P interfaces
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces, key=lambda x: x[0]):
        junos_if = eth_to_junos(iface)
        # Determine if this is a WAN link or DCI/client link
        is_wan = any(
            (a == name and ifa == iface) or (b == name and ifb == iface)
            for a, ifa, b, ifb, *_ in WAN_LINKS
        )
        lines.append(f"    {junos_if} {{")
        lines.append(f'        description "to {remote}";')
        lines.append(f"        mtu 9200;")
        lines.append(f"        hold-time up 2000 down 0;")
        if is_wan:
            lines.append(f"        unit 0 {{")
            lines.append(f"            family inet {{")
            lines.append(f"                filter {{")
            lines.append(f"                    input PROTECT-RE;")
            lines.append(f"                }}")
            lines.append(f"                address {ip4_local}/31;")
            lines.append(f"            }}")
            lines.append(f"            family inet6 {{")
            lines.append(f"                filter {{")
            lines.append(f"                    input PROTECT-RE-V6;")
            lines.append(f"                }}")
            lines.append(f"                address {ip6_local}/127;")
            lines.append(f"            }}")
            lines.append(f"            family iso;")
            lines.append(f"            family mpls;")
            lines.append(f"        }}")
        else:
            # DCI or client link
            lines.append(f"        unit 0 {{")
            lines.append(f"            family inet {{")
            lines.append(f"                address {ip4_local}/31;")
            lines.append(f"            }}")
            lines.append(f"            family inet6 {{")
            lines.append(f"                address {ip6_local}/127;")
            lines.append(f"            }}")
            lines.append(f"        }}")
        lines.append(f"    }}")

    # Loopback
    lines.append(f"    lo0 {{")
    lines.append(f"        unit 0 {{")
    lines.append(f"            family inet {{")
    lines.append(f"                filter {{")
    lines.append(f"                    input PROTECT-RE;")
    lines.append(f"                }}")
    lines.append(f"                address {lo}/32;")
    lines.append(f"            }}")
    lines.append(f"            family inet6 {{")
    lines.append(f"                filter {{")
    lines.append(f"                    input PROTECT-RE-V6;")
    lines.append(f"                }}")
    lines.append(f"                address {lo_v6}/128;")
    lines.append(f"            }}")
    lines.append(f"            family iso {{")
    lines.append(f"                address {isis_net(lo)};")
    lines.append(f"            }}")
    lines.append(f"        }}")
    lines.append(f"    }}")
    lines.append("}")
    lines.append("")

    # ========================================
    # SNMP CONFIGURATION
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * SNMP CONFIGURATION")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("snmp {")
    lines.append(f'    description "{name} - {dc.upper()} DC PE Router";')
    lines.append(f'    location "Data Center {dc.upper()}";')
    lines.append('    contact "noc@example.com";')
    lines.append("    community public {")
    lines.append("        authorization read-only;")
    lines.append("        clients {")
    lines.append("            10.255.0.0/16;")
    lines.append("        }")
    lines.append("    }")
    lines.append("    community private {")
    lines.append("        authorization read-write;")
    lines.append("        clients {")
    lines.append("            10.255.0.100/32;")
    lines.append("            10.255.0.101/32;")
    lines.append("        }")
    lines.append("    }")
    lines.append("    trap-options {")
    lines.append(f"        source-address lo0;")
    lines.append("    }")
    lines.append("    trap-group NETWORK-MANAGEMENT {")
    lines.append("        version v2;")
    lines.append("        categories {")
    lines.append("            authentication;")
    lines.append("            chassis;")
    lines.append("            link;")
    lines.append("            remote-operations;")
    lines.append("            routing;")
    lines.append("            services;")
    lines.append("        }")
    lines.append("        targets {")
    lines.append("            10.255.0.100;")
    lines.append("            10.255.0.101;")
    lines.append("        }")
    lines.append("    }")
    lines.append("    health-monitor {")
    lines.append("        interval 300;")
    lines.append("        rising-threshold 80;")
    lines.append("        falling-threshold 70;")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # ROUTING INSTANCES (VRF)
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * ROUTING INSTANCES (VRF)")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("routing-instances {")
    lines.append(f"    {VRF_CDN['name']} {{")
    lines.append("        instance-type vrf;")
    lines.append(f"        route-distinguisher {lo}:100;")
    lines.append(f"        vrf-import VRF-CDN-IMPORT;")
    lines.append(f"        vrf-export VRF-CDN-EXPORT;")
    lines.append(f"        vrf-table-label;")
    lines.append("        routing-options {")
    lines.append("            multipath;")
    lines.append("            auto-export;")
    lines.append("        }")
    lines.append("        protocols {")
    lines.append("            bgp {")
    lines.append(f"                group DCI-{dc.upper()} {{")
    lines.append("                    type external;")
    bl_asn = DC_WEST_ASN if dc == "west" else DC_EAST_ASN
    lines.append(f"                    peer-as {bl_asn};")
    lines.append("                    multipath;")
    lines.append("                    family inet {")
    lines.append("                        unicast;")
    lines.append("                    }")
    lines.append("                    export EXPORT-CONNECTED;")
    for pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, *_ in DCI_LINKS:
        if pe == name:
            lines.append(f"                    neighbor {ip4_bl};")
    lines.append("                }")
    # Parallel v6 DCI eBGP group with v6 link neighbors
    lines.append(f"                group DCI-{dc.upper()}-V6 {{")
    lines.append("                    type external;")
    lines.append(f"                    peer-as {bl_asn};")
    lines.append("                    multipath;")
    lines.append("                    family inet6 {")
    lines.append("                        unicast;")
    lines.append("                    }")
    lines.append("                    export EXPORT-CONNECTED;")
    for pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, ip6_pe, ip6_bl in DCI_LINKS:
        if pe == name:
            lines.append(f"                    neighbor {ip6_bl};")
    lines.append("                }")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # ROUTING OPTIONS
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * ROUTING OPTIONS")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("routing-options {")
    lines.append(f"    router-id {lo};")
    lines.append(f"    autonomous-system {WAN_ASN};")
    # Static routes to RR loopbacks (IS-IS auth mismatch with FRR prevents IGP
    # adjacency on PE-RR links, so we reach RR loopbacks via direct-link statics)
    lines.append("    static {")
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in WAN_LINKS:
        if a == name and b in FRR_NODES:
            lines.append(f"        route {FRR_NODES[b]['lo']}/32 next-hop {ip4_b};")
        elif b == name and a in FRR_NODES:
            lines.append(f"        route {FRR_NODES[a]['lo']}/32 next-hop {ip4_a};")
    lines.append("    }")
    # IPv6 statics: RR v6 loopbacks via direct PE-RR links + peer PE v6 loopback via PE-PE link
    lines.append("    rib inet6.0 {")
    lines.append("        static {")
    for a, ifa, b, ifb, ip4_a, ip4_b, ip6_a, ip6_b in WAN_LINKS:
        if a == name and b in FRR_NODES:
            lines.append(f"            route {FRR_NODES[b]['lo_v6']}/128 next-hop {ip6_b};")
        elif b == name and a in FRR_NODES:
            lines.append(f"            route {FRR_NODES[a]['lo_v6']}/128 next-hop {ip6_a};")
        elif a == name and b in JUNIPER_NODES:
            lines.append(f"            route {JUNIPER_NODES[b]['lo_v6']}/128 next-hop {ip6_b};")
        elif b == name and a in JUNIPER_NODES:
            lines.append(f"            route {JUNIPER_NODES[a]['lo_v6']}/128 next-hop {ip6_a};")
    lines.append("        }")
    lines.append("    }")
    # VPNv6 next-hop resolution via inet6.0 (native v6 next-hops from RR-V6 group)
    lines.append("    resolution {")
    lines.append("        rib bgp.l3vpn-inet6.0 {")
    lines.append("            resolution-ribs inet6.0;")
    lines.append("        }")
    lines.append("    }")
    lines.append("    forwarding-table {")
    lines.append("        export PFE-LOAD-BALANCE;")
    lines.append("        ecmp-fast-reroute;")
    lines.append("        chained-composite-next-hop {")
    lines.append("            ingress {")
    lines.append("                evpn;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # PROTOCOLS - ISIS
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * PROTOCOLS - ISIS")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("protocols {")
    lines.append("    isis {")
    lines.append("        level 1 disable;")
    lines.append("        level 2 {")
    lines.append("            wide-metrics-only;")
    lines.append("            authentication-key-chain ISIS-KEY-CHAIN;")
    lines.append("            authentication-type md5;")
    lines.append("        }")
    lines.append("        traffic-engineering {")
    lines.append("            family inet {")
    lines.append("                shortcuts;")
    lines.append("            }")
    lines.append("            family inet6 {")
    lines.append("                shortcuts;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        source-packet-routing {")
    lines.append(f"            srgb start-label {SRGB_START} index-range {SRGB_RANGE};")
    lines.append(f"            node-segment ipv4-index {sid};")
    lines.append("            explicit-null;")
    lines.append("        }")
    lines.append("        export LOOPBACK-INTO-ISIS;")

    # ISIS interfaces
    for iface, remote, *_ in sorted(ifaces, key=lambda x: x[0]):
        junos_if = eth_to_junos(iface)
        is_wan = any(
            (a == name and ifa == iface) or (b == name and ifb == iface)
            for a, ifa, b, ifb, *_ in WAN_LINKS
        )
        if is_wan:
            lines.append(f"        interface {junos_if}.0 {{")
            lines.append("            point-to-point;")
            lines.append("            level 2 {")
            lines.append("                metric 100;")
            lines.append("                hello-authentication-key-chain ISIS-KEY-CHAIN;")
            lines.append("            }")
            lines.append("        }")

    lines.append("        interface lo0.0 {")
    lines.append("            passive;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # ========================================
    # PROTOCOLS - MPLS
    # ========================================
    lines.append("    /* ========================================")
    lines.append("     * PROTOCOLS - MPLS")
    lines.append("     * ======================================== */")
    lines.append("")
    lines.append("    mpls {")
    for iface, remote, *_ in sorted(ifaces, key=lambda x: x[0]):
        junos_if = eth_to_junos(iface)
        is_wan = any(
            (a == name and ifa == iface) or (b == name and ifb == iface)
            for a, ifa, b, ifb, *_ in WAN_LINKS
        )
        if is_wan:
            lines.append(f"        interface {junos_if}.0;")
    lines.append("    }")
    lines.append("")

    # ========================================
    # PROTOCOLS - BGP
    # ========================================
    lines.append("    /* ========================================")
    lines.append("     * PROTOCOLS - BGP")
    lines.append("     * ======================================== */")
    lines.append("")
    lines.append("    bgp {")
    lines.append("        group RR {")
    lines.append("            type internal;")
    lines.append(f"            local-address {lo};")
    lines.append("            family inet-vpn {")
    lines.append("                unicast;")
    lines.append("            }")
    lines.append("            authentication-algorithm hmac-sha-1-96;")
    lines.append('            authentication-key-chain "BGP-KEY-CHAIN";')
    lines.append("            export NEXT-HOP-SELF;")
    for rr_name, rr in FRR_NODES.items():
        lines.append(f"            neighbor {rr['lo']};")
    lines.append("        }")
    # Parallel iBGP group with v6 transport for VPNv6.
    # Required because v4-mapped v6 next-hops can't resolve in inet6.3
    # (family mismatch). Using native v6 transport gives v6 next-hops
    # that resolve via inet6.0 statics above.
    lines.append("        group RR-V6 {")
    lines.append("            type internal;")
    lines.append(f"            local-address {lo_v6};")
    lines.append("            family inet6-vpn {")
    lines.append("                unicast;")
    lines.append("            }")
    lines.append("            export NEXT-HOP-SELF;")
    for rr_name, rr in FRR_NODES.items():
        lines.append(f"            neighbor {rr['lo_v6']};")
    lines.append("        }")
    lines.append("    }")
    lines.append("")

    # ========================================
    # PROTOCOLS - LLDP
    # ========================================
    lines.append("    /* ========================================")
    lines.append("     * PROTOCOLS - LLDP")
    lines.append("     * ======================================== */")
    lines.append("")
    lines.append("    lldp {")
    for iface, *_ in sorted(ifaces, key=lambda x: x[0]):
        junos_if = eth_to_junos(iface)
        lines.append(f"        interface {junos_if};")
    lines.append("    }")
    lines.append("")

    # ========================================
    # PROTOCOLS - BFD
    # ========================================
    lines.append("    /* ========================================")
    lines.append("     * PROTOCOLS - BFD")
    lines.append("     * ======================================== */")
    lines.append("")
    lines.append("    bfd {")
    lines.append("        traceoptions {")
    lines.append("            file bfd-trace size 1m files 5;")
    lines.append("            flag all;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # POLICY OPTIONS
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * POLICY OPTIONS")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("policy-options {")
    lines.append("    /* Prefix lists */")
    lines.append("    prefix-list PL-LOOPBACKS {")
    lines.append("        10.255.0.0/16;")
    lines.append("    }")
    lines.append("    prefix-list PL-MANAGEMENT {")
    lines.append("        10.255.0.0/16;")
    lines.append("    }")
    lines.append("    prefix-list PL-ANYCAST {")
    lines.append(f"        {ANYCAST_PREFIX_V4};")
    lines.append("    }")
    lines.append("    prefix-list PL-RFC1918 {")
    lines.append("        10.0.0.0/8;")
    lines.append("        172.16.0.0/12;")
    lines.append("        192.168.0.0/16;")
    lines.append("    }")
    lines.append("    prefix-list PL-BOGONS {")
    lines.append("        0.0.0.0/8;")
    lines.append("        127.0.0.0/8;")
    lines.append("        169.254.0.0/16;")
    lines.append("        224.0.0.0/4;")
    lines.append("        240.0.0.0/4;")
    lines.append("    }")
    lines.append("")
    lines.append("    /* IPv6 Prefix lists */")
    lines.append("    prefix-list PL6-LOOPBACKS {")
    lines.append("        fd00::/16;")
    lines.append("    }")
    lines.append("    prefix-list PL6-ANYCAST {")
    lines.append(f"        {ANYCAST_PREFIX_V6};")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Community definitions */")
    lines.append("    community RT-CDN-IMPORT members target:65000:100;")
    lines.append("    community RT-CDN-EXPORT members target:65000:100;")
    lines.append(f"    community COLOR-{dc.upper()} members color:0:{100 if dc == 'west' else 300};")
    lines.append("    community LOW-LATENCY members 65000:1111;")
    lines.append("    community HIGH-BANDWIDTH members 65000:2222;")
    lines.append("    community CRITICAL members 65000:9999;")
    lines.append("    community BLACKHOLE members 65000:666;")
    lines.append("    community NO-EXPORT members no-export;")
    lines.append("")
    lines.append("    /* AS-path filters */")
    lines.append('    as-path AS-CUSTOMER "^65[1-3][0-9]{2}$";')
    lines.append('    as-path AS-INTERNAL "^$";')
    lines.append("")
    lines.append("    /* VRF import/export policies */")
    lines.append("    policy-statement VRF-CDN-IMPORT {")
    lines.append("        term IMPORT-CDN {")
    lines.append("            from {")
    lines.append("                community RT-CDN-IMPORT;")
    lines.append("            }")
    lines.append("            then accept;")
    lines.append("        }")
    lines.append("        term DEFAULT {")
    lines.append("            then reject;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    policy-statement VRF-CDN-EXPORT {")
    lines.append("        term EXPORT-CDN {")
    lines.append("            then {")
    lines.append("                community add RT-CDN-EXPORT;")
    lines.append(f"                community add COLOR-{dc.upper()};")
    lines.append("                accept;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Next-hop self policy */")
    lines.append("    policy-statement NEXT-HOP-SELF {")
    lines.append("        term NHS {")
    lines.append("            then {")
    lines.append("                next-hop self;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Export connected (used by DCI eBGP groups, family-agnostic) */")
    lines.append("    policy-statement EXPORT-CONNECTED {")
    lines.append("        term CONNECTED {")
    lines.append("            from protocol direct;")
    lines.append("            then accept;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Loopback into ISIS policy */")
    lines.append("    policy-statement LOOPBACK-INTO-ISIS {")
    lines.append("        term LOOPBACK {")
    lines.append("            from {")
    lines.append("                protocol direct;")
    lines.append("                route-filter 10.255.0.0/16 orlonger;")
    lines.append("            }")
    lines.append("            then accept;")
    lines.append("        }")
    lines.append("        term DEFAULT {")
    lines.append("            then reject;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Load balancing policy */")
    lines.append("    policy-statement PFE-LOAD-BALANCE {")
    lines.append("        term LB {")
    lines.append("            then {")
    lines.append("                load-balance per-packet;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* wECMP link-bandwidth export */")
    lines.append("    policy-statement LINK-BANDWIDTH-EXPORT {")
    lines.append("        term SET-BANDWIDTH {")
    lines.append("            then {")
    lines.append(f"                community add [ RT-CDN-EXPORT COLOR-{dc.upper()} ];")
    lines.append(f"                community add bandwidth:{WAN_ASN}:{weight};")
    lines.append("                accept;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Blackhole policy */")
    lines.append("    policy-statement BLACKHOLE {")
    lines.append("        term BLACKHOLE-ROUTES {")
    lines.append("            from {")
    lines.append("                community BLACKHOLE;")
    lines.append("            }")
    lines.append("            then {")
    lines.append("                next-hop discard;")
    lines.append("                accept;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /* Reject bogons policy */")
    lines.append("    policy-statement REJECT-BOGONS {")
    lines.append("        term REJECT-BOGONS {")
    lines.append("            from {")
    lines.append("                prefix-list PL-BOGONS;")
    lines.append("            }")
    lines.append("            then reject;")
    lines.append("        }")
    lines.append("        term ACCEPT-REST {")
    lines.append("            then accept;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # FIREWALL FILTERS
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * FIREWALL FILTERS")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("firewall {")
    lines.append("    family inet {")
    lines.append("        filter PROTECT-RE {")
    lines.append("            term ALLOW-SSH {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL-MANAGEMENT;")
    lines.append("                    }")
    lines.append("                    protocol tcp;")
    lines.append("                    destination-port ssh;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-NETCONF {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL-MANAGEMENT;")
    lines.append("                    }")
    lines.append("                    protocol tcp;")
    lines.append("                    destination-port 830;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-SNMP {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL-MANAGEMENT;")
    lines.append("                    }")
    lines.append("                    protocol udp;")
    lines.append("                    destination-port snmp;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-NTP {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL-MANAGEMENT;")
    lines.append("                    }")
    lines.append("                    protocol udp;")
    lines.append("                    destination-port ntp;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-ICMP {")
    lines.append("                from {")
    lines.append("                    protocol icmp;")
    lines.append("                    icmp-type [ echo-reply echo-request time-exceeded unreachable ];")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-BGP {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL-LOOPBACKS;")
    lines.append("                    }")
    lines.append("                    protocol tcp;")
    lines.append("                    destination-port bgp;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-ISIS {")
    lines.append("                from {")
    lines.append("                    protocol isis;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-BFD {")
    lines.append("                from {")
    lines.append("                    protocol udp;")
    lines.append("                    destination-port [ 3784 3785 4784 ];")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-LDP {")
    lines.append("                from {")
    lines.append("                    protocol [ tcp udp ];")
    lines.append("                    destination-port 646;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term RATE-LIMIT-ALL-ELSE {")
    lines.append("                then {")
    lines.append("                    policer POLICER-1M;")
    lines.append("                    accept;")
    lines.append("                }")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    family inet6 {")
    lines.append("        filter PROTECT-RE-V6 {")
    lines.append("            term ALLOW-SSH {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL6-LOOPBACKS;")
    lines.append("                    }")
    lines.append("                    next-header tcp;")
    lines.append("                    destination-port ssh;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-NETCONF {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL6-LOOPBACKS;")
    lines.append("                    }")
    lines.append("                    next-header tcp;")
    lines.append("                    destination-port 830;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-ICMPV6 {")
    lines.append("                from {")
    lines.append("                    next-header icmp6;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-BGP {")
    lines.append("                from {")
    lines.append("                    source-prefix-list {")
    lines.append("                        PL6-LOOPBACKS;")
    lines.append("                    }")
    lines.append("                    next-header tcp;")
    lines.append("                    destination-port bgp;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-ISIS {")
    lines.append("                from {")
    lines.append("                    next-header 124;")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term ALLOW-BFD {")
    lines.append("                from {")
    lines.append("                    next-header udp;")
    lines.append("                    destination-port [ 3784 3785 4784 ];")
    lines.append("                }")
    lines.append("                then accept;")
    lines.append("            }")
    lines.append("            term RATE-LIMIT-ALL-ELSE {")
    lines.append("                then {")
    lines.append("                    policer POLICER-1M;")
    lines.append("                    accept;")
    lines.append("                }")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    policer POLICER-1M {")
    lines.append("        if-exceeding {")
    lines.append("            bandwidth-limit 1m;")
    lines.append("            burst-size-limit 15k;")
    lines.append("        }")
    lines.append("        then discard;")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # CLASS OF SERVICE (QoS)
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * CLASS OF SERVICE (QoS)")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("class-of-service {")
    lines.append("    classifiers {")
    lines.append("        dscp CDN-DSCP-CLASSIFIER {")
    lines.append("            import default;")
    lines.append("            forwarding-class NETWORK-CONTROL {")
    lines.append("                loss-priority low code-points [ cs6 cs7 ];")
    lines.append("            }")
    lines.append("            forwarding-class VOICE {")
    lines.append("                loss-priority low code-points ef;")
    lines.append("            }")
    lines.append("            forwarding-class VIDEO {")
    lines.append("                loss-priority low code-points [ af41 af42 af43 ];")
    lines.append("            }")
    lines.append("            forwarding-class CRITICAL-DATA {")
    lines.append("                loss-priority low code-points [ af31 af32 af33 ];")
    lines.append("            }")
    lines.append("            forwarding-class BEST-EFFORT {")
    lines.append("                loss-priority low code-points [ be cs0 ];")
    lines.append("            }")
    lines.append("            forwarding-class SCAVENGER {")
    lines.append("                loss-priority high code-points cs1;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        exp CDN-MPLS-CLASSIFIER {")
    lines.append("            forwarding-class NETWORK-CONTROL {")
    lines.append("                loss-priority low code-points 6;")
    lines.append("            }")
    lines.append("            forwarding-class VOICE {")
    lines.append("                loss-priority low code-points 5;")
    lines.append("            }")
    lines.append("            forwarding-class VIDEO {")
    lines.append("                loss-priority low code-points 4;")
    lines.append("            }")
    lines.append("            forwarding-class CRITICAL-DATA {")
    lines.append("                loss-priority low code-points 3;")
    lines.append("            }")
    lines.append("            forwarding-class BEST-EFFORT {")
    lines.append("                loss-priority low code-points [ 0 1 ];")
    lines.append("            }")
    lines.append("            forwarding-class SCAVENGER {")
    lines.append("                loss-priority high code-points 2;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    drop-profiles {")
    lines.append("        LOW-DROP {")
    lines.append("            fill-level 80 drop-probability 0;")
    lines.append("            fill-level 90 drop-probability 50;")
    lines.append("            fill-level 100 drop-probability 100;")
    lines.append("        }")
    lines.append("        MEDIUM-DROP {")
    lines.append("            fill-level 60 drop-probability 0;")
    lines.append("            fill-level 80 drop-probability 50;")
    lines.append("            fill-level 100 drop-probability 100;")
    lines.append("        }")
    lines.append("        HIGH-DROP {")
    lines.append("            fill-level 40 drop-probability 0;")
    lines.append("            fill-level 70 drop-probability 50;")
    lines.append("            fill-level 100 drop-probability 100;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    forwarding-classes {")
    lines.append("        class NETWORK-CONTROL queue-num 7 priority high;")
    lines.append("        class VOICE queue-num 6 priority high;")
    lines.append("        class VIDEO queue-num 5 priority high;")
    lines.append("        class CRITICAL-DATA queue-num 4 priority medium-high;")
    lines.append("        class BEST-EFFORT queue-num 3 priority medium-low;")
    lines.append("        class SCAVENGER queue-num 0 priority low;")
    lines.append("    }")
    lines.append("")
    lines.append("    rewrite-rules {")
    lines.append("        dscp CDN-DSCP-REWRITE {")
    lines.append("            forwarding-class NETWORK-CONTROL {")
    lines.append("                loss-priority low code-point cs6;")
    lines.append("                loss-priority high code-point cs6;")
    lines.append("            }")
    lines.append("            forwarding-class VOICE {")
    lines.append("                loss-priority low code-point ef;")
    lines.append("                loss-priority high code-point ef;")
    lines.append("            }")
    lines.append("            forwarding-class VIDEO {")
    lines.append("                loss-priority low code-point af41;")
    lines.append("                loss-priority high code-point af43;")
    lines.append("            }")
    lines.append("            forwarding-class CRITICAL-DATA {")
    lines.append("                loss-priority low code-point af31;")
    lines.append("                loss-priority high code-point af33;")
    lines.append("            }")
    lines.append("            forwarding-class BEST-EFFORT {")
    lines.append("                loss-priority low code-point be;")
    lines.append("                loss-priority high code-point be;")
    lines.append("            }")
    lines.append("            forwarding-class SCAVENGER {")
    lines.append("                loss-priority low code-point cs1;")
    lines.append("                loss-priority high code-point cs1;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        exp CDN-MPLS-REWRITE {")
    lines.append("            forwarding-class NETWORK-CONTROL {")
    lines.append("                loss-priority low code-point 6;")
    lines.append("                loss-priority high code-point 6;")
    lines.append("            }")
    lines.append("            forwarding-class VOICE {")
    lines.append("                loss-priority low code-point 5;")
    lines.append("                loss-priority high code-point 5;")
    lines.append("            }")
    lines.append("            forwarding-class VIDEO {")
    lines.append("                loss-priority low code-point 4;")
    lines.append("                loss-priority high code-point 4;")
    lines.append("            }")
    lines.append("            forwarding-class CRITICAL-DATA {")
    lines.append("                loss-priority low code-point 3;")
    lines.append("                loss-priority high code-point 3;")
    lines.append("            }")
    lines.append("            forwarding-class BEST-EFFORT {")
    lines.append("                loss-priority low code-point 0;")
    lines.append("                loss-priority high code-point 1;")
    lines.append("            }")
    lines.append("            forwarding-class SCAVENGER {")
    lines.append("                loss-priority low code-point 2;")
    lines.append("                loss-priority high code-point 2;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    scheduler-maps {")
    lines.append("        CDN-SCHEDULER-MAP {")
    lines.append("            forwarding-class NETWORK-CONTROL scheduler NETWORK-CONTROL-SCHED;")
    lines.append("            forwarding-class VOICE scheduler VOICE-SCHED;")
    lines.append("            forwarding-class VIDEO scheduler VIDEO-SCHED;")
    lines.append("            forwarding-class CRITICAL-DATA scheduler CRITICAL-DATA-SCHED;")
    lines.append("            forwarding-class BEST-EFFORT scheduler BEST-EFFORT-SCHED;")
    lines.append("            forwarding-class SCAVENGER scheduler SCAVENGER-SCHED;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    schedulers {")
    lines.append("        NETWORK-CONTROL-SCHED {")
    lines.append("            transmit-rate percent 5;")
    lines.append("            priority strict-high;")
    lines.append("        }")
    lines.append("        VOICE-SCHED {")
    lines.append("            shaping-rate percent 10;")
    lines.append("            transmit-rate percent 10;")
    lines.append("            priority high;")
    lines.append("        }")
    lines.append("        VIDEO-SCHED {")
    lines.append("            shaping-rate percent 30;")
    lines.append("            transmit-rate percent 30;")
    lines.append("            priority medium-high;")
    lines.append("            drop-profile-map loss-priority low protocol any drop-profile LOW-DROP;")
    lines.append("            drop-profile-map loss-priority high protocol any drop-profile MEDIUM-DROP;")
    lines.append("        }")
    lines.append("        CRITICAL-DATA-SCHED {")
    lines.append("            shaping-rate percent 20;")
    lines.append("            transmit-rate percent 20;")
    lines.append("            priority medium-low;")
    lines.append("            drop-profile-map loss-priority low protocol any drop-profile MEDIUM-DROP;")
    lines.append("            drop-profile-map loss-priority high protocol any drop-profile HIGH-DROP;")
    lines.append("        }")
    lines.append("        BEST-EFFORT-SCHED {")
    lines.append("            shaping-rate percent 30;")
    lines.append("            transmit-rate percent 30;")
    lines.append("            priority low;")
    lines.append("            drop-profile-map loss-priority low protocol any drop-profile HIGH-DROP;")
    lines.append("            drop-profile-map loss-priority high protocol any drop-profile HIGH-DROP;")
    lines.append("        }")
    lines.append("        SCAVENGER-SCHED {")
    lines.append("            shaping-rate percent 5;")
    lines.append("            transmit-rate percent 5;")
    lines.append("            priority low;")
    lines.append("            drop-profile-map loss-priority any protocol any drop-profile HIGH-DROP;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    # ========================================
    # SECURITY (KEY CHAINS)
    # ========================================
    lines.append("/* ========================================")
    lines.append(" * SECURITY (KEY CHAINS)")
    lines.append(" * ======================================== */")
    lines.append("")
    lines.append("security {")
    lines.append("    authentication-key-chains {")
    lines.append("        key-chain ISIS-KEY-CHAIN {")
    lines.append("            key 1 {")
    lines.append("                secret $9$encrypted;")
    lines.append("                start-time 2024-01-01.00:00:00 +0000;")
    lines.append("                algorithm md5;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        key-chain BGP-KEY-CHAIN {")
    lines.append("            key 1 {")
    lines.append("                secret $9$encrypted;")
    lines.append("                start-time 2024-01-01.00:00:00 +0000;")
    lines.append("                algorithm hmac-sha-1-96;")
    lines.append("            }")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")

    return "\n".join(lines)


# =============================================================================
# Arista Config Generation (Baseline)
# =============================================================================

def gen_arista_baseline(name: str, node: dict) -> str:
    """Generate baseline Arista config (hostname + interfaces only)."""
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    role = node["role"]
    dc = node["dc"]
    ifaces = get_arista_ifaces(name)

    lines = []
    lines.append(f"! {name} - Baseline Configuration")
    lines.append(f"! Role: {role}, DC: {dc}")
    lines.append("")
    lines.append(f"hostname {name}")
    lines.append("")
    lines.append("! Management")
    lines.append("service routing protocols model multi-agent")
    lines.append("management api http-commands")
    lines.append("   no shutdown")
    lines.append("")
    lines.append("! Local user for eAPI access")
    lines.append("username admin privilege 15 role network-admin secret admin123")
    lines.append("")
    lines.append("! Global routing")
    lines.append("ip routing")
    lines.append("ipv6 unicast-routing")
    lines.append("")

    # Loopback
    lines.append("! Loopback")
    lines.append("interface Loopback0")
    lines.append(f"   ip address {lo}/32")
    lines.append(f"   ipv6 address {lo_v6}/128")
    lines.append("")

    # VTEP loopback for leaves/border-leaves
    if "vtep" in node:
        lines.append("interface Loopback1")
        lines.append(f"   description VTEP")
        lines.append(f"   ip address {node['vtep']}/32")
        lines.append("")

    # P2P interfaces
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces, key=lambda x: x[0]):
        lines.append(f"! P2P to {remote}")
        lines.append(f"interface {iface}")
        lines.append(f"   description to-{remote}")
        lines.append("   no switchport")
        lines.append("   mtu 9214")
        lines.append(f"   ip address {ip4_local}/31")
        lines.append(f"   ipv6 address {ip6_local}/127")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Arista Config Generation (Reference - Full)
# =============================================================================

def gen_arista_reference(name: str, node: dict) -> str:
    """Generate full reference Arista config."""
    lo = node["lo"]
    lo_v6 = node["lo_v6"]
    role = node["role"]
    dc = node["dc"]
    ifaces = get_arista_ifaces(name)
    dc_asn = DC_WEST_ASN if dc == "west" else DC_EAST_ASN

    lines = []
    lines.append(f"! ================================================================")
    lines.append(f"! {name.upper()} - REFERENCE CONFIGURATION")
    lines.append(f"! ================================================================")
    lines.append(f"! Role: {role.replace('-', ' ').title()}")
    lines.append(f"! Data Center: {dc.upper()} (AS {dc_asn})")
    lines.append(f"! Loopback IPv4: {lo}")
    lines.append(f"! Loopback IPv6: {lo_v6}")
    if "vtep" in node:
        lines.append(f"! VTEP IP: {node['vtep']}")
    lines.append(f"! ================================================================")
    lines.append("")

    # ========================================
    # SYSTEM CONFIGURATION
    # ========================================
    lines.append("! ========================================")
    lines.append("! SYSTEM CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append(f"hostname {name}")
    lines.append("!")
    lines.append("service routing protocols model multi-agent")
    lines.append("!")
    lines.append("management api http-commands")
    lines.append("   protocol https")
    lines.append("   no shutdown")
    lines.append("!")
    lines.append("aaa authorization exec default local")
    lines.append("!")
    lines.append("username admin privilege 15 role network-admin secret sha512 $6$encrypted$hash")
    lines.append("username operator privilege 1 role network-operator secret sha512 $6$encrypted$hash")
    lines.append("!")
    lines.append("clock timezone UTC")
    lines.append("!")
    lines.append(f"banner motd")
    lines.append(f"*** AUTHORIZED ACCESS ONLY - {name.upper()} ***")
    lines.append("All activities are logged and monitored.")
    lines.append("EOF")
    lines.append("!")

    # ========================================
    # NTP CONFIGURATION
    # ========================================
    lines.append("! ========================================")
    lines.append("! NTP CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("ntp local-interface Loopback0")
    lines.append("ntp server 10.255.0.100 prefer")
    lines.append("ntp server 10.255.0.101")
    lines.append("!")

    # ========================================
    # SNMP CONFIGURATION
    # ========================================
    lines.append("! ========================================")
    lines.append("! SNMP CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append(f"snmp-server location Data Center {dc.upper()}")
    lines.append("snmp-server contact noc@example.com")
    lines.append("snmp-server community public ro")
    lines.append("snmp-server community private rw")
    lines.append("snmp-server host 10.255.0.100 version 2c public")
    lines.append("snmp-server host 10.255.0.101 version 2c public")
    lines.append("snmp-server enable traps bgp")
    lines.append("snmp-server enable traps entity")
    lines.append("snmp-server enable traps lldp")
    lines.append("snmp-server enable traps snmp")
    lines.append("!")

    # ========================================
    # LOGGING CONFIGURATION
    # ========================================
    lines.append("! ========================================")
    lines.append("! LOGGING CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("logging buffered 100000")
    lines.append("logging console informational")
    lines.append("logging host 10.255.0.100")
    lines.append("logging source-interface Loopback0")
    lines.append("logging facility local7")
    lines.append("!")

    # ========================================
    # SPANNING-TREE
    # ========================================
    lines.append("! ========================================")
    lines.append("! SPANNING-TREE CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("spanning-tree mode mstp")
    lines.append("spanning-tree mst 0 priority 4096")
    lines.append("!")

    # ========================================
    # VLANs (for leaves and border-leaves)
    # ========================================
    if role in ("leaf", "border-leaf"):
        lines.append("! ========================================")
        lines.append("! VLAN CONFIGURATION")
        lines.append("! ========================================")
        lines.append("!")
        if dc == "west":
            lines.append("vlan 10")
            lines.append("   name VLAN10-WEST")
            lines.append("vlan 11")
            lines.append("   name VLAN11-WEST")
        else:
            lines.append("vlan 30")
            lines.append("   name VLAN30-EAST")
            lines.append("vlan 31")
            lines.append("   name VLAN31-EAST")
        lines.append(f"vlan {VRF_CDN['vlan_l3']}")
        lines.append(f"   name L3VNI-CDN")
        lines.append("!")

    # ========================================
    # VRF CONFIGURATION
    # ========================================
    if role in ("leaf", "border-leaf"):
        lines.append("! ========================================")
        lines.append("! VRF CONFIGURATION")
        lines.append("! ========================================")
        lines.append("!")
        lines.append(f"vrf instance {VRF_CDN['name']}")
        lines.append(f"   rd {lo}:100")
        lines.append("!")
        lines.append(f"ip routing vrf {VRF_CDN['name']}")
        lines.append(f"ipv6 unicast-routing vrf {VRF_CDN['name']}")
        lines.append("!")

    # ========================================
    # GLOBAL ROUTING
    # ========================================
    lines.append("! ========================================")
    lines.append("! GLOBAL ROUTING")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("ip routing")
    lines.append("ipv6 unicast-routing")
    lines.append("!")

    # ========================================
    # INTERFACES
    # ========================================
    lines.append("! ========================================")
    lines.append("! INTERFACE CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")

    # Loopback
    lines.append("interface Loopback0")
    lines.append(f"   description Router-ID")
    lines.append(f"   ip address {lo}/32")
    lines.append(f"   ipv6 address {lo_v6}/128")
    lines.append("!")

    # VTEP loopback for leaves/border-leaves
    if "vtep" in node:
        lines.append("interface Loopback1")
        lines.append("   description VTEP")
        lines.append(f"   ip address {node['vtep']}/32")
        lines.append("!")

    # P2P interfaces
    for iface, remote, ip4_local, ip4_remote, ip6_local, ip6_remote in sorted(ifaces, key=lambda x: x[0]):
        lines.append(f"interface {iface}")
        lines.append(f"   description to-{remote}")
        lines.append("   no switchport")
        lines.append("   mtu 9214")
        lines.append(f"   ip address {ip4_local}/31")
        lines.append(f"   ipv6 address {ip6_local}/127")
        lines.append("   ip ospf network point-to-point")
        lines.append("   ip ospf area 0.0.0.0")
        lines.append("!")

    # Host-facing interfaces (for leaves)
    if role == "leaf":
        vlan = node.get("vlan", 10)
        lines.append("interface Ethernet3")
        lines.append("   description to-host")
        lines.append("   switchport mode access")
        lines.append(f"   switchport access vlan {vlan}")
        lines.append("   spanning-tree portfast")
        lines.append("!")

    # VXLAN interface (for leaves and border-leaves)
    if role in ("leaf", "border-leaf"):
        lines.append("interface Vxlan1")
        lines.append(f"   vxlan source-interface Loopback1")
        lines.append("   vxlan udp-port 4789")
        if dc == "west":
            lines.append("   vxlan vlan 10 vni 10010")
            lines.append("   vxlan vlan 11 vni 10011")
        else:
            lines.append("   vxlan vlan 30 vni 10030")
            lines.append("   vxlan vlan 31 vni 10031")
        lines.append(f"   vxlan vrf {VRF_CDN['name']} vni {VRF_CDN['l3vni']}")
        lines.append("!")

    # SVI interfaces (for leaves and border-leaves)
    if role in ("leaf", "border-leaf"):
        if dc == "west":
            lines.append("interface Vlan10")
            lines.append(f"   vrf {VRF_CDN['name']}")
            lines.append("   ip address virtual 192.168.10.1/24")
            lines.append("   ipv6 address virtual 2001:db8:10::1/64")
            lines.append("!")
            lines.append("interface Vlan11")
            lines.append(f"   vrf {VRF_CDN['name']}")
            lines.append("   ip address virtual 192.168.11.1/24")
            lines.append("   ipv6 address virtual 2001:db8:11::1/64")
            lines.append("!")
        else:
            lines.append("interface Vlan30")
            lines.append(f"   vrf {VRF_CDN['name']}")
            lines.append("   ip address virtual 192.168.30.1/24")
            lines.append("   ipv6 address virtual 2001:db8:30::1/64")
            lines.append("!")
            lines.append("interface Vlan31")
            lines.append(f"   vrf {VRF_CDN['name']}")
            lines.append("   ip address virtual 192.168.31.1/24")
            lines.append("   ipv6 address virtual 2001:db8:31::1/64")
            lines.append("!")
        # L3VNI SVI
        lines.append(f"interface Vlan{VRF_CDN['vlan_l3']}")
        lines.append(f"   vrf {VRF_CDN['name']}")
        lines.append("   ip address virtual 10.254.0.1/24")
        lines.append("!")

    # ========================================
    # VIRTUAL MAC
    # ========================================
    if role in ("leaf", "border-leaf"):
        lines.append("! ========================================")
        lines.append("! VIRTUAL MAC (ANYCAST GATEWAY)")
        lines.append("! ========================================")
        lines.append("!")
        lines.append(f"ip virtual-router mac-address {ANYCAST_GW_MAC}")
        lines.append("!")

    # ========================================
    # PREFIX LISTS
    # ========================================
    lines.append("! ========================================")
    lines.append("! PREFIX LISTS")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("ip prefix-list PL-LOOPBACKS seq 10 permit 10.255.0.0/16 le 32")
    lines.append("ip prefix-list PL-ANYCAST seq 10 permit 198.51.100.0/24")
    lines.append("ip prefix-list PL-DEFAULT seq 10 permit 0.0.0.0/0")
    lines.append("!")
    lines.append("ipv6 prefix-list PL6-LOOPBACKS seq 10 permit fd00::/16 le 128")
    lines.append("ipv6 prefix-list PL6-ANYCAST seq 10 permit 2001:db8:cafe::/48")
    lines.append("!")

    # ========================================
    # ROUTE MAPS
    # ========================================
    lines.append("! ========================================")
    lines.append("! ROUTE MAPS")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("route-map RM-CONN-TO-BGP permit 10")
    lines.append("   match ip address prefix-list PL-LOOPBACKS")
    lines.append("!")
    lines.append("route-map RM-CONN-TO-BGP permit 20")
    lines.append("   match ip address prefix-list PL-ANYCAST")
    lines.append("!")

    # wECMP route-map for border-leaf
    if role == "border-leaf":
        weight = WECMP_WEIGHTS[dc]
        lines.append(f"route-map RM-LINK-BANDWIDTH permit 10")
        lines.append(f"   set extcommunity bandwidth {weight} aggregate")
        lines.append("!")

    # ========================================
    # OSPF
    # ========================================
    lines.append("! ========================================")
    lines.append("! OSPF CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("router ospf 1")
    lines.append(f"   router-id {lo}")
    lines.append("   passive-interface default")
    for iface, *_ in sorted(ifaces, key=lambda x: x[0]):
        lines.append(f"   no passive-interface {iface}")
    lines.append("   network 0.0.0.0/0 area 0.0.0.0")
    lines.append("   max-lsa 12000")
    lines.append("!")

    # ========================================
    # BGP
    # ========================================
    lines.append("! ========================================")
    lines.append("! BGP CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append(f"router bgp {dc_asn}")
    lines.append(f"   router-id {lo}")
    lines.append("   no bgp default ipv4-unicast")
    lines.append("   maximum-paths 4 ecmp 4")
    lines.append("   !")

    if role == "spine":
        # Spine peers with all leaves and border-leaves in the DC
        lines.append("   neighbor LEAF-EVPN peer group")
        lines.append(f"   neighbor LEAF-EVPN remote-as {dc_asn}")
        lines.append("   neighbor LEAF-EVPN update-source Loopback0")
        lines.append("   neighbor LEAF-EVPN route-reflector-client")
        lines.append("   neighbor LEAF-EVPN send-community extended")
        lines.append("   !")
        # Add leaf neighbors
        for arista_name, arista_node in ARISTA_NODES.items():
            if arista_node["dc"] == dc and arista_node["role"] in ("leaf", "border-leaf"):
                lines.append(f"   neighbor {arista_node['lo']} peer group LEAF-EVPN")
        lines.append("   !")
        lines.append("   address-family evpn")
        lines.append("      neighbor LEAF-EVPN activate")
        lines.append("   !")
        lines.append("   address-family ipv4")
        lines.append("      no neighbor LEAF-EVPN activate")
        lines.append("   !")
    elif role in ("leaf", "border-leaf"):
        # Leaf/BL peers with spine
        lines.append("   neighbor SPINE-EVPN peer group")
        lines.append(f"   neighbor SPINE-EVPN remote-as {dc_asn}")
        lines.append("   neighbor SPINE-EVPN update-source Loopback0")
        lines.append("   neighbor SPINE-EVPN send-community extended")
        lines.append("   !")
        spine_name = f"spine-{'w' if dc == 'west' else 'e'}"
        spine_lo = ARISTA_NODES[spine_name]["lo"]
        lines.append(f"   neighbor {spine_lo} peer group SPINE-EVPN")
        lines.append("   !")
        lines.append("   address-family evpn")
        lines.append("      neighbor SPINE-EVPN activate")
        lines.append("   !")
        lines.append("   address-family ipv4")
        lines.append("      no neighbor SPINE-EVPN activate")
        lines.append("   !")
        # EVPN VLAN service: declare L2 VLANs to BGP-EVPN so cEOS generates
        # Type-2 (MAC/IP) and Type-3 (IMET) routes. Without this block, only
        # Type-5 IP-Prefix routes are advertised and remote VTEPs never install.
        if dc == "west":
            vlan_low, vlan_high = 10, 11
        else:
            vlan_low, vlan_high = 30, 31
        lines.append("   vlan-aware-bundle CDN-VLANS")
        lines.append(f"      rd {lo}:1")
        lines.append(f"      route-target both {dc_asn}:1")
        lines.append("      redistribute learned")
        lines.append(f"      vlan {vlan_low}-{vlan_high}")
        lines.append("   !")

    # Border-leaf specific: VRF BGP for DCI
    if role == "border-leaf":
        lines.append(f"   vrf {VRF_CDN['name']}")
        lines.append(f"      rd {lo}:100")
        lines.append(f"      route-target import evpn {VRF_CDN['rt']}")
        lines.append(f"      route-target export evpn {VRF_CDN['rt']}")
        lines.append("      !")
        lines.append("      neighbor DCI peer group")
        lines.append(f"      neighbor DCI remote-as {WAN_ASN}")
        lines.append("      neighbor DCI send-community extended")
        lines.append("      !")
        # IPv6 DCI peer group (separate v6 BGP session over v6 link addresses)
        lines.append("      neighbor DCI-V6 peer group")
        lines.append(f"      neighbor DCI-V6 remote-as {WAN_ASN}")
        lines.append("      neighbor DCI-V6 send-community extended")
        lines.append("      !")
        # Add PE neighbors (v4 and v6)
        for pe, pe_eth, bl, bl_eth, ip4_pe, ip4_bl, ip6_pe, ip6_bl in DCI_LINKS:
            if bl == name:
                lines.append(f"      neighbor {ip4_pe} peer group DCI")
                lines.append(f"      neighbor {ip6_pe} peer group DCI-V6")
        lines.append("      !")
        lines.append("      redistribute connected route-map RM-CONN-TO-BGP")
        lines.append("      !")
        lines.append("      address-family ipv4")
        lines.append("         neighbor DCI activate")
        lines.append("         neighbor DCI route-map RM-LINK-BANDWIDTH out")
        lines.append("      !")
        lines.append("      address-family ipv6")
        lines.append("         neighbor DCI-V6 activate")
        lines.append("   !")

    lines.append("!")

    # ========================================
    # QoS
    # ========================================
    lines.append("! ========================================")
    lines.append("! QoS CONFIGURATION")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("qos map dscp DSCP-TO-TC")
    lines.append("   0 traffic-class 0")
    lines.append("   8 traffic-class 1")
    lines.append("   16 traffic-class 2")
    lines.append("   24 traffic-class 3")
    lines.append("   32 traffic-class 4")
    lines.append("   40 traffic-class 5")
    lines.append("   46 traffic-class 6")
    lines.append("   48 traffic-class 7")
    lines.append("!")
    lines.append("class-map type qos match-any CM-NETWORK-CONTROL")
    lines.append("   match dscp cs6 cs7")
    lines.append("!")
    lines.append("class-map type qos match-any CM-VOICE")
    lines.append("   match dscp ef")
    lines.append("!")
    lines.append("class-map type qos match-any CM-VIDEO")
    lines.append("   match dscp af41 af42 af43")
    lines.append("!")
    lines.append("class-map type qos match-any CM-CRITICAL-DATA")
    lines.append("   match dscp af31 af32 af33")
    lines.append("!")

    # ========================================
    # ACLs
    # ========================================
    lines.append("! ========================================")
    lines.append("! ACCESS CONTROL LISTS")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("ip access-list AL-MANAGEMENT")
    lines.append("   10 permit tcp 10.255.0.0/16 any eq ssh")
    lines.append("   20 permit tcp 10.255.0.0/16 any eq 443")
    lines.append("   30 permit udp 10.255.0.0/16 any eq snmp")
    lines.append("   40 permit icmp 10.255.0.0/16 any")
    lines.append("   100 deny ip any any log")
    lines.append("!")
    lines.append("ip access-list AL-BGP")
    lines.append("   10 permit tcp 10.255.0.0/16 any eq bgp")
    lines.append("   20 permit tcp any 10.255.0.0/16 eq bgp")
    lines.append("   100 deny ip any any log")
    lines.append("!")

    # ========================================
    # EVENT HANDLERS
    # ========================================
    lines.append("! ========================================")
    lines.append("! EVENT HANDLERS")
    lines.append("! ========================================")
    lines.append("!")
    lines.append("event-handler INTERFACE-DOWN")
    lines.append("   trigger on-intf Ethernet1-4 operstatus")
    lines.append("   action bash logger -p local0.warning Interface state change detected")
    lines.append("   delay 10")
    lines.append("!")

    lines.append("end")

    return "\n".join(lines)


# =============================================================================
# ContainerLab YAML Generation
# =============================================================================

def gen_clab_yaml() -> dict:
    """Generate ContainerLab topology YAML."""
    topo = {
        "name": LAB_NAME,
        "topology": {
            "kinds": {
                "linux": {"image": HOST_IMAGE},
            },
            "nodes": {},
            "links": [],
        }
    }

    nodes = topo["topology"]["nodes"]
    links = topo["topology"]["links"]

    # FRR Route Reflectors
    for name, node in FRR_NODES.items():
        nodes[name] = {
            "kind": "linux",
            "image": FRR_IMAGE,
            "binds": [
                f"configs/frr/{name}/daemons:/etc/frr/daemons",
                f"configs/frr/{name}/frr.conf:/etc/frr/frr.conf",
            ],
            "group": "wan",
            "labels": {
                "role": "rr",
                "loopback": node["lo"],
                "asn": str(WAN_ASN),
            }
        }

    # Juniper PEs
    for name, node in JUNIPER_NODES.items():
        nodes[name] = {
            "kind": "juniper_vjunosevolved",
            "image": JUNOS_IMAGE,
            "startup-config": f"configs/juniper/{name}-baseline.conf",
            "group": "wan",
            "labels": {
                "role": "pe",
                "dc": node["dc"],
                "loopback": node["lo"],
                "asn": str(WAN_ASN),
            }
        }

    # Arista cEOS
    for name, node in ARISTA_NODES.items():
        dc = node["dc"]
        group = f"dc-{dc}"
        nodes[name] = {
            "kind": "ceos",
            "image": CEOS_IMAGE,
            "startup-config": f"configs/arista/{name}-baseline.conf",
            "group": group,
            "labels": {
                "role": node["role"],
                "dc": dc,
                "loopback": node["lo"],
                "asn": str(DC_WEST_ASN if dc == "west" else DC_EAST_ASN),
            }
        }

    # Hosts
    for name, node in HOST_NODES.items():
        dc = node["dc"]
        group = f"hosts-{dc}"
        exec_cmds = [
            f"ip addr add {node['ip']} dev eth1",
            f"ip -6 addr add {node['ip_v6']} dev eth1",
            f"ip route replace default via {node['gw']}",
            f"ip -6 route replace default via {node['gw_v6']}",
        ]
        nodes[name] = {
            "kind": "linux",
            "group": group,
            "labels": {
                "role": "host",
                "dc": dc,
            },
            "exec": exec_cmds,
        }

    # WAN Links
    for a, eth_a, b, eth_b, *_ in WAN_LINKS:
        links.append({"endpoints": [f"{a}:{eth_a}", f"{b}:{eth_b}"]})

    # DCI Links
    for pe, pe_eth, bl, bl_eth, *_ in DCI_LINKS:
        eth_clab = bl_eth.replace("Ethernet", "eth")
        links.append({"endpoints": [f"{pe}:{pe_eth}", f"{bl}:{eth_clab}"]})

    # Client Links
    for pe, pe_eth, client, client_eth, *_ in CLIENT_LINKS:
        links.append({"endpoints": [f"{pe}:{pe_eth}", f"{client}:{client_eth}"]})

    # Fabric Links
    for a, eth_a, b, eth_b, *_ in FABRIC_LINKS:
        eth_a_clab = eth_a.replace("Ethernet", "eth")
        eth_b_clab = eth_b.replace("Ethernet", "eth")
        links.append({"endpoints": [f"{a}:{eth_a_clab}", f"{b}:{eth_b_clab}"]})

    # Host Links
    for leaf, leaf_eth, host, host_eth in HOST_LINKS:
        eth_clab = leaf_eth.replace("Ethernet", "eth")
        links.append({"endpoints": [f"{leaf}:{eth_clab}", f"{host}:{host_eth}"]})

    return topo


# =============================================================================
# Main
# =============================================================================

def main():
    base_dir = Path(__file__).parent
    config_dir = base_dir / "configs"

    # Create directories
    (config_dir / "frr").mkdir(parents=True, exist_ok=True)
    (config_dir / "juniper").mkdir(parents=True, exist_ok=True)
    (config_dir / "arista").mkdir(parents=True, exist_ok=True)

    print(f"Generating Anycast CDN HARDMODE topology...")
    print(f"(no reference configs - agent must design from intent)")
    print(f"=" * 60)

    stats = {
        "frr": 0,
        "juniper_baseline": 0,
        "arista_baseline": 0,
        "total_lines": 0,
    }

    # FRR — baseline only (interfaces, no protocols)
    print(f"\nFRR Route Reflectors ({len(FRR_NODES)} nodes):")
    for name, node in FRR_NODES.items():
        frr_dir = config_dir / "frr" / name
        frr_dir.mkdir(parents=True, exist_ok=True)
        (frr_dir / "daemons").write_text(gen_frr_daemons())
        frr_conf = gen_frr_baseline(name, node)
        (frr_dir / "frr.conf").write_text(frr_conf)
        lines = len(frr_conf.split("\n"))
        stats["frr"] += 1
        stats["total_lines"] += lines
        print(f"  {name}: {lines} lines (baseline)")

    # Juniper — baseline only (no -reference.conf in hardmode)
    print(f"\nJuniper PEs ({len(JUNIPER_NODES)} nodes):")
    for name, node in JUNIPER_NODES.items():
        baseline = gen_juniper_baseline(name, node)
        (config_dir / "juniper" / f"{name}-baseline.conf").write_text(baseline)
        baseline_lines = len(baseline.split("\n"))
        stats["juniper_baseline"] += 1
        stats["total_lines"] += baseline_lines
        print(f"  {name}: baseline={baseline_lines} lines")

    # Arista — baseline only (no -reference.conf in hardmode)
    print(f"\nArista cEOS ({len(ARISTA_NODES)} nodes):")
    for name, node in ARISTA_NODES.items():
        baseline = gen_arista_baseline(name, node)
        (config_dir / "arista" / f"{name}-baseline.conf").write_text(baseline)
        baseline_lines = len(baseline.split("\n"))
        stats["arista_baseline"] += 1
        stats["total_lines"] += baseline_lines
        print(f"  {name}: baseline={baseline_lines} lines")

    # Generate ContainerLab YAML
    clab = gen_clab_yaml()
    clab_path = base_dir / f"{LAB_NAME}.clab.yml"
    yaml_str = yaml.dump(clab, default_flow_style=False, sort_keys=False, width=120)
    clab_path.write_text(yaml_str)
    print(f"\nContainerLab YAML: {clab_path.name}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total nodes: {len(FRR_NODES) + len(JUNIPER_NODES) + len(ARISTA_NODES) + len(HOST_NODES)}")
    print(f"  - FRR RRs: {len(FRR_NODES)}")
    print(f"  - Juniper PEs: {len(JUNIPER_NODES)}")
    print(f"  - Arista cEOS: {len(ARISTA_NODES)}")
    print(f"  - Hosts: {len(HOST_NODES)}")
    print(f"")
    print(f"Links:")
    print(f"  - WAN: {len(WAN_LINKS)}")
    print(f"  - DCI: {len(DCI_LINKS)}")
    print(f"  - Client: {len(CLIENT_LINKS)}")
    print(f"  - Fabric: {len(FABRIC_LINKS)}")
    print(f"  - Host: {len(HOST_LINKS)}")
    print(f"  - Total: {len(WAN_LINKS) + len(DCI_LINKS) + len(CLIENT_LINKS) + len(FABRIC_LINKS) + len(HOST_LINKS)}")
    print(f"")
    print(f"Config files generated (HARDMODE - baselines only):")
    print(f"  - FRR: {stats['frr']} nodes")
    print(f"  - Juniper baseline: {stats['juniper_baseline']} files")
    print(f"  - Arista baseline: {stats['arista_baseline']} files")
    print(f"  - References: 0 (intent-only benchmark)")
    print(f"")
    print(f"Total lines of config: {stats['total_lines']}")
    print(f"{'=' * 60}")
    print(f"Done!")


if __name__ == "__main__":
    main()
