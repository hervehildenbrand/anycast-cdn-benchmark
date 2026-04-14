# Audit Report — anycast-cdn-hardmode

Generated 2026-04-08T20:32:18Z by Agent-Verify.

This report captures control-plane and data-plane evidence from each device
in the lab via direct `show` commands. Devices covered: pe-w, pe-e, spine-w,
spine-e, l1-w, l2-w, bl-w, l1-e, l2-e, bl-e, rr1, rr2.

## Junos PE: pe-w
### show isis adjacency
```
admin@pe-w> show isis adjacency 

Warning: License key missing; requires 'ISIS' license

Interface             System         L State         Hold (secs) SNPA
et-0/0/5.0            pe-e           2  Up                    23  c:61:ed:42:0:31

admin@pe-w> exit 

```

### show bgp summary
```
admin@pe-w> show bgp summary 

Warning: License key missing; requires 'BGP' license

Threading mode: BGP I/O
Default eBGP mode: advertise - accept, receive - accept
Groups: 4 Peers: 8 Down peers: 0
Table          Tot Paths  Act Paths Suppressed    History Damp State    Pending
bgp.l3vpn.0          
                      16          8          0          0          0          0
bgp.l3vpn-inet6.0    
                      16          8          0          0          0          0
Peer                     AS      InPkt     OutPkt    OutQ   Flaps Last Up/Dwn State|#Active/Received/Accepted/Damped...
10.2.0.1              65100         87         75       0       1       25:39 Establ
  CDN.inet.0: 5/7/7/0
10.2.0.3              65100         96         75       0       0       25:56 Establ
  CDN.inet.0: 5/7/7/0
10.255.0.1            65000         31         26       0       0        8:43 Establ
  bgp.l3vpn.0: 8/8/8/0
  CDN.inet.0: 7/8/8/0
10.255.0.2            65000         31         26       0       0        8:43 Establ
  bgp.l3vpn.0: 0/8/8/0
  CDN.inet.0: 0/8/8/0
fd00::1               65000        108        104       0       0       41:45 Establ
  bgp.l3vpn-inet6.0: 8/8/8/0
  CDN.inet6.0: 7/8/8/0
fd00::2               65000        108        103       0       0       41:41 Establ
  bgp.l3vpn-inet6.0: 0/8/8/0
  CDN.inet6.0: 0/8/8/0
fd00:2::1             65100         73         71       0       0       25:52 Establ
  CDN.inet6.0: 5/7/7/0
fd00:2:1::1           65100         81         66       0       0       25:48 Establ
  CDN.inet6.0: 5/7/7/0

admin@pe-w> exit 

```

### show route table CDN.inet.0
```
admin@pe-w> show route table CDN.inet.0 

CDN.inet.0: 19 destinations, 37 routes (19 active, 0 holddown, 0 hidden)
@ = Routing Use Only, # = Forwarding Use Only
+ = Active Route, - = Last Active, * = Both

10.2.0.0/31        *[Direct/0] 00:27:48
                    >  via et-0/0/2.0
                    [BGP/170] 00:25:41, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.1 via et-0/0/2.0
                    [BGP/170] 00:25:58, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
10.2.0.0/32        *[Local/0] 00:27:48
                       Local via et-0/0/2.0
10.2.0.2/31        *[Direct/0] 00:27:48
                    >  via et-0/0/3.0
                    [BGP/170] 00:25:41, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.1 via et-0/0/2.0
                    [BGP/170] 00:25:58, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
10.2.0.2/32        *[Local/0] 00:27:48
                       Local via et-0/0/3.0
10.2.0.4/31        *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
10.2.0.6/31        *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
10.100.0.0/31      *[Direct/0] 00:16:47
                    >  via et-0/0/4.0
10.100.0.0/32      *[Local/0] 00:16:47
                       Local via et-0/0/4.0
10.100.2.0/31      *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
10.255.100.11/32   *[Direct/0] 00:41:30
                    >  via lo0.100
10.255.100.13/32   *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
192.168.10.0/24    *[BGP/170] 00:25:41, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.1 via et-0/0/2.0
                       to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:25:58, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
192.168.10.10/32   *[BGP/170] 00:12:01, localpref 100, from 10.2.0.1
                      AS path: 65100 I, validation-state: unverified
                       to 10.2.0.1 via et-0/0/2.0
                    >  to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:12:01, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
192.168.11.0/24    *[BGP/170] 00:25:41, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.1 via et-0/0/2.0
                       to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:25:58, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
192.168.11.10/32   *[BGP/170] 00:05:00, localpref 100, from 10.2.0.1
                      AS path: 65100 I, validation-state: unverified
                       to 10.2.0.1 via et-0/0/2.0
                    >  to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:05:00, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
192.168.30.0/24    *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
192.168.30.10/32   *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
192.168.31.0/24    *[BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
198.51.100.1/32    *[BGP/170] 00:25:41, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.1 via et-0/0/2.0
                       to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:25:58, localpref 100
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.2.0.3 via et-0/0/3.0
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.1
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18
                    [BGP/170] 00:08:28, localpref 100, from 10.255.0.2
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.0.0.11 via et-0/0/5.0, Push 18

admin@pe-w> exit 

```

### show route table CDN.inet.0 198.51.100.1 extensive
```
admin@pe-w> show route table CDN.inet.0 198.51.100.1 extensive 

CDN.inet.0: 19 destinations, 37 routes (19 active, 0 holddown, 0 hidden)
198.51.100.1/32 (4 entries, 1 announced)
TSI:
Page 0 idx 0, (group IBGP-RR-V4 type Internal) Type 1 val 0x55f289fc9f98 (adv_entry)
   Advertised metrics:
     Flags: Nexthop Change
     Nexthop: Self
     Localpref: 100
     AS path: [65000] 65100 I
     Communities: target:65000:100 bandwidth-non-transitive:65100:500000
     VPN Label: 16
    Advertise: 00000003
Path 198.51.100.1
from 10.2.0.1
Vector len 4.  Val: 0
KRT in-kernel 198.51.100.1/32 -> {list:indirect(8078), indirect(8070)}
Multipath TSI
    Flags: RTargetLBWSet
    Lead Route: BGP, 10.2.0.1
    Nexthop:
      Refcnt: 5
      Template: 0x55f282ea0510(Indirect, 2 legs)
      Object: 0x55f2825c535c(Indirect, 2 legs)
    Mode: Multipath
        *BGP    Preference: 170/-101
                Next hop type: Indirect, Next hop index: 0
                Address: 0x55f2825c4f9c
                Next-hop reference count: 5
                Kernel Table Id: 0
                Source: 10.2.0.1
                Next hop type: Router, Next hop index: 8077
                Next hop: 10.2.0.1 via et-0/0/2.0, selected
                Session Id: 12
                Next hop type: Router, Next hop index: 8069
                Next hop: 10.2.0.3 via et-0/0/3.0
                Session Id: c
                Protocol next hop: 10.2.0.1 Balance: 80%
                Indirect next hop: 0x55f282112e08 8078 INH Session ID: 19
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                Protocol next hop: 10.2.0.3 Balance: 20%
                Indirect next hop: 0x55f282110d88 8070 INH Session ID: 13
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                State: <Active Ext>
                Peer AS: 65100
                Age: 25:42 	Metric2: 0 
                Validation State: unverified 
                Task: BGP_65100.10.2.0.1
                Announcement bits (4): 0-BGP_RT_Background 1-KRT 2-BGP_Multi_Path 3-Resolve tree 6 
                AS path: 65100 I 
                Communities: bandwidth-non-transitive:65100:500000
                Accepted Multipath
                Localpref: 100
                Router ID: 10.255.10.21
                Thread: junos-main 
                Indirect next hops: 2
                        Protocol next hop: 10.2.0.1 ResolvState: Resolved
                        Indirect next hop: 0x55f282112e08 8078 INH Session ID: 19
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.1 via et-0/0/2.0
                                Session Id: 12
                                10.2.0.0/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x55f28253a718 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
                                        Next hop: via et-0/0/2.0
                        Protocol next hop: 10.2.0.3 ResolvState: Resolved
                        Indirect next hop: 0x55f282110d88 8070 INH Session ID: 13
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.3 via et-0/0/3.0
                                Session Id: c
                                10.2.0.2/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x55f28253a3d8 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
                                        Next hop: via et-0/0/3.0
         BGP    Preference: 170/-101
                Next hop type: Indirect, Next hop index: 0
                Address: 0x55f28202943c
                Next-hop reference count: 8
                Kernel Table Id: 0
                Source: 10.2.0.3
                Next hop type: Router, Next hop index: 8069
                Next hop: 10.2.0.3 via et-0/0/3.0, selected
                Session Id: c
                Protocol next hop: 10.2.0.3
                Indirect next hop: 0x55f282110d88 8070 INH Session ID: 13
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                State: <NotBest Ext>
                Inactive reason: Not Best in its group - Update source
                Peer AS: 65100
                Age: 25:59 	Metric2: 0 
                Validation State: unverified 
                Task: BGP_65100.10.2.0.3
                AS path: 65100 I 
                Communities: bandwidth-non-transitive:65100:125000
                Accepted MultipathContrib
                Localpref: 100
                Router ID: 10.255.10.21
                Thread: junos-main 
                Indirect next hops: 1
                        Protocol next hop: 10.2.0.3 ResolvState: Resolved
                        Indirect next hop: 0x55f282110d88 8070 INH Session ID: 13
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.3 via et-0/0/3.0
                                Session Id: c
                                10.2.0.2/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x55f28253a3d8 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
```

## Junos PE: pe-e
### show isis adjacency
```
admin@pe-e> show isis adjacency 

Warning: License key missing; requires 'ISIS' license

Interface             System         L State         Hold (secs) SNPA
et-0/0/5.0            pe-w           2  Up                     8  3c:f8:b3:40:0:31

admin@pe-e> exit 

```

### show bgp summary
```
admin@pe-e> show bgp summary 

Warning: License key missing; requires 'BGP' license

Threading mode: BGP I/O
Default eBGP mode: advertise - accept, receive - accept
Groups: 4 Peers: 8 Down peers: 0
Table          Tot Paths  Act Paths Suppressed    History Damp State    Pending
bgp.l3vpn.0          
                      18          9          0          0          0          0
bgp.l3vpn-inet6.0    
                      18          9          0          0          0          0
Peer                     AS      InPkt     OutPkt    OutQ   Flaps Last Up/Dwn State|#Active/Received/Accepted/Damped...
10.2.0.5              65300         79         85       0       0       26:16 Establ
  CDN.inet.0: 4/6/6/0
10.2.0.7              65300         91         84       0       0       26:16 Establ
  CDN.inet.0: 4/6/6/0
10.255.0.1            65000        125         98       0       0       39:55 Establ
  bgp.l3vpn.0: 9/9/9/0
  CDN.inet.0: 8/9/9/0
10.255.0.2            65000        125         99       0       0       39:51 Establ
  bgp.l3vpn.0: 0/9/9/0
  CDN.inet.0: 0/9/9/0
fd00::1               65000        106         98       0       0       39:47 Establ
  bgp.l3vpn-inet6.0: 9/9/9/0
  CDN.inet6.0: 8/9/9/0
fd00::2               65000        106         97       0       0       39:44 Establ
  bgp.l3vpn-inet6.0: 0/9/9/0
  CDN.inet6.0: 0/9/9/0
fd00:2:2::1           65300         77         71       0       0       26:16 Establ
  CDN.inet6.0: 4/6/6/0
fd00:2:3::1           65300         83         70       0       0       26:16 Establ
  CDN.inet6.0: 4/6/6/0

admin@pe-e> exit 

```

### show route table CDN.inet.0
```
admin@pe-e> show route table CDN.inet.0 

CDN.inet.0: 19 destinations, 37 routes (19 active, 0 holddown, 0 hidden)
@ = Routing Use Only, # = Forwarding Use Only
+ = Active Route, - = Last Active, * = Both

10.2.0.0/31        *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
10.2.0.2/31        *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
10.2.0.4/31        *[Direct/0] 00:27:49
                    >  via et-0/0/2.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.5 via et-0/0/2.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
10.2.0.4/32        *[Local/0] 00:27:49
                       Local via et-0/0/2.0
10.2.0.6/31        *[Direct/0] 00:27:49
                    >  via et-0/0/3.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.5 via et-0/0/2.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
10.2.0.6/32        *[Local/0] 00:27:49
                       Local via et-0/0/3.0
10.100.0.0/31      *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
10.100.2.0/31      *[Direct/0] 00:16:45
                    >  via et-0/0/4.0
10.100.2.0/32      *[Local/0] 00:16:45
                       Local via et-0/0/4.0
10.255.100.11/32   *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
10.255.100.13/32   *[Direct/0] 00:39:39
                    >  via lo0.100
192.168.10.0/24    *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
192.168.10.10/32   *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
192.168.11.0/24    *[BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
192.168.11.10/32   *[BGP/170] 00:05:05, localpref 100, from 10.255.0.1
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:05:05, localpref 100, from 10.255.0.2
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
192.168.30.0/24    *[BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.5 via et-0/0/2.0
                       to 10.2.0.7 via et-0/0/3.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
192.168.30.10/32   *[BGP/170] 00:12:02, localpref 100, from 10.2.0.5
                      AS path: 65300 I, validation-state: unverified
                       to 10.2.0.5 via et-0/0/2.0
                    >  to 10.2.0.7 via et-0/0/3.0
                    [BGP/170] 00:12:02, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
192.168.31.0/24    *[BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.5 via et-0/0/2.0
                       to 10.2.0.7 via et-0/0/3.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
198.51.100.1/32    *[BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.5 via et-0/0/2.0
                       to 10.2.0.7 via et-0/0/3.0
                    [BGP/170] 00:26:16, localpref 100
                      AS path: 65300 I, validation-state: unverified
                    >  to 10.2.0.7 via et-0/0/3.0
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.1
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16
                    [BGP/170] 00:08:38, localpref 100, from 10.255.0.2
                      AS path: 65100 I, validation-state: unverified
                    >  to 10.0.0.10 via et-0/0/5.0, Push 16

admin@pe-e> exit 

```

### show route table CDN.inet.0 198.51.100.1 extensive
```
admin@pe-e> show route table CDN.inet.0 198.51.100.1 extensive 

CDN.inet.0: 19 destinations, 37 routes (19 active, 0 holddown, 0 hidden)
198.51.100.1/32 (4 entries, 1 announced)
TSI:
Page 0 idx 0, (group IBGP-RR-V4 type Internal) Type 1 val 0x560826fc96d8 (adv_entry)
   Advertised metrics:
     Flags: Nexthop Change
     Nexthop: Self
     Localpref: 100
     AS path: [65000] 65300 I
     Communities: target:65000:100 bandwidth-non-transitive:65300:500000
     VPN Label: 18
    Advertise: 00000003
Path 198.51.100.1
from 10.2.0.5
Vector len 4.  Val: 0
KRT in-kernel 198.51.100.1/32 -> {list:indirect(8072), indirect(8068)}
Multipath TSI
    Flags: RTargetLBWSet
    Lead Route: BGP, 10.2.0.5
    Nexthop:
      Refcnt: 4
      Template: 0x56081fea8610(Indirect, 2 legs)
      Object: 0x56081f5c4f9c(Indirect, 2 legs)
    Mode: Multipath
        *BGP    Preference: 170/-101
                Next hop type: Indirect, Next hop index: 0
                Address: 0x56081f5c4e5c
                Next-hop reference count: 4
                Kernel Table Id: 0
                Source: 10.2.0.5
                Next hop type: Router, Next hop index: 8069
                Next hop: 10.2.0.5 via et-0/0/2.0, selected
                Session Id: c
                Next hop type: Router, Next hop index: 8067
                Next hop: 10.2.0.7 via et-0/0/3.0
                Session Id: a
                Protocol next hop: 10.2.0.5 Balance: 80%
                Indirect next hop: 0x56081f112408 8072 INH Session ID: 15
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                Protocol next hop: 10.2.0.7 Balance: 20%
                Indirect next hop: 0x56081f112188 8068 INH Session ID: 11
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                State: <Active Ext>
                Peer AS: 65300
                Age: 26:17 	Metric2: 0 
                Validation State: unverified 
                Task: BGP_65300.10.2.0.5
                Announcement bits (4): 0-BGP_RT_Background 1-KRT 2-BGP_Multi_Path 3-Resolve tree 6 
                AS path: 65300 I 
                Communities: bandwidth-non-transitive:65300:500000
                Accepted Multipath
                Localpref: 100
                Router ID: 10.255.30.21
                Thread: junos-main 
                Indirect next hops: 2
                        Protocol next hop: 10.2.0.5 ResolvState: Resolved
                        Indirect next hop: 0x56081f112408 8072 INH Session ID: 15
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.5 via et-0/0/2.0
                                Session Id: c
                                10.2.0.4/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x56081f53a308 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
                                        Next hop: via et-0/0/2.0
                        Protocol next hop: 10.2.0.7 ResolvState: Resolved
                        Indirect next hop: 0x56081f112188 8068 INH Session ID: 11
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.7 via et-0/0/3.0
                                Session Id: a
                                10.2.0.6/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x56081f539cf0 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
                                        Next hop: via et-0/0/3.0
         BGP    Preference: 170/-101
                Next hop type: Indirect, Next hop index: 0
                Address: 0x56081f029f9c
                Next-hop reference count: 7
                Kernel Table Id: 0
                Source: 10.2.0.7
                Next hop type: Router, Next hop index: 8067
                Next hop: 10.2.0.7 via et-0/0/3.0, selected
                Session Id: a
                Protocol next hop: 10.2.0.7
                Indirect next hop: 0x56081f112188 8068 INH Session ID: 11
                Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                State: <NotBest Ext>
                Inactive reason: Not Best in its group - Update source
                Peer AS: 65300
                Age: 26:17 	Metric2: 0 
                Validation State: unverified 
                Task: BGP_65300.10.2.0.7
                AS path: 65300 I 
                Communities: bandwidth-non-transitive:65300:125000
                Accepted MultipathContrib
                Localpref: 100
                Router ID: 10.255.30.21
                Thread: junos-main 
                Indirect next hops: 1
                        Protocol next hop: 10.2.0.7 ResolvState: Resolved
                        Indirect next hop: 0x56081f112188 8068 INH Session ID: 11
                        Indirect next hop: INH non-key opaque: (nil) INH key opaque: (nil)
                        Indirect path forwarding next hops: 1
                                Next hop type: Router
                                Next hop: 10.2.0.7 via et-0/0/3.0
                                Session Id: a
                                10.2.0.6/31 Originating RIB: CDN.inet.0
                                  Node path count: 1
                                  Helper node: 0x56081f539cf0 
                                  Forwarding nexthops: 1
                                        Next hop type: Interface
```

## Arista spine: spine-w
### show bgp evpn summary
```
BGP summary information for VRF default
Router identifier 10.255.10.1, local AS number 65100
Neighbor Status Codes: m - Under maintenance
  Neighbor     V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc PfxAdv
  10.255.10.11 4 65100             57        82    0    0 00:36:11 Estab   9      9      31
  10.255.10.12 4 65100             60        77    0    0 00:35:39 Estab   9      9      31
  10.255.10.21 4 65100             70        72    0    0 00:35:19 Estab   22     22     18
```

## Arista spine: spine-e
### show bgp evpn summary
```
BGP summary information for VRF default
Router identifier 10.255.30.1, local AS number 65300
Neighbor Status Codes: m - Under maintenance
  Neighbor     V AS           MsgRcvd   MsgSent  InQ OutQ  Up/Down State   PfxRcd PfxAcc PfxAdv
  10.255.30.11 4 65300             42        65    0    0 00:27:13 Estab   9      9      30
  10.255.30.12 4 65300             39        63    0    0 00:26:49 Estab   6      6      33
  10.255.30.21 4 65300             56        47    0    0 00:26:28 Estab   24     24     15
```

## Arista leaf: l1-w
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.10.11, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 imet 10010 10.255.11.11
                                 -                     -       -       0       i
 * >      RD: 10.255.10.12:20100 imet 10010 10.255.11.12
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 imet 10011 10.255.11.11
                                 -                     -       -       0       i
 * >      RD: 10.255.10.12:20100 imet 10011 10.255.11.12
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.10.11, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641
                                 -                     -       -       0       i
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 192.168.10.10
                                 -                     -       -       0       i
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 2001:db8:10:0:a8c1:abff:fe49:641
                                 -                     -       -       0       i
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 192.168.11.10
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 2001:db8:11::10
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP               Tunnel Type(s)
------------------ --------------
10.255.11.12       flood, unicast

Total number of remote VTEPS:  1
```

## Arista leaf: l2-w
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.10.12, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 imet 10010 10.255.11.11
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 imet 10010 10.255.11.12
                                 -                     -       -       0       i
 * >      RD: 10.255.10.11:20100 imet 10011 10.255.11.11
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 imet 10011 10.255.11.12
                                 -                     -       -       0       i
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.10.12, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 192.168.10.10
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 2001:db8:10:0:a8c1:abff:fe49:641
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115
                                 -                     -       -       0       i
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 192.168.11.10
                                 -                     -       -       0       i
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 2001:db8:11::10
                                 -                     -       -       0       i
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP               Tunnel Type(s)
------------------ --------------
10.255.11.11       flood, unicast

Total number of remote VTEPS:  1
```

## Arista leaf: bl-w
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.10.21, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 imet 10010 10.255.11.11
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 imet 10010 10.255.11.12
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 imet 10011 10.255.11.11
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 imet 10011 10.255.11.12
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.10.21, local AS number 65100
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 192.168.10.10
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.11:20100 mac-ip 10010 aac1.ab49.0641 2001:db8:10:0:a8c1:abff:fe49:641
                                 10.255.11.11          -       100     0       i Or-ID: 10.255.10.11 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 192.168.11.10
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
 * >      RD: 10.255.10.12:20100 mac-ip 10011 aac1.ab7d.f115 2001:db8:11::10
                                 10.255.11.12          -       100     0       i Or-ID: 10.255.10.12 C-LST: 10.255.10.1 
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP       Tunnel Type(s)
---------- --------------

Total number of remote VTEPS:  0
```

## Arista leaf: l1-e
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.30.11, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 imet 10030 10.255.31.11
                                 -                     -       -       0       i
 * >      RD: 10.255.30.12:20100 imet 10030 10.255.31.12
                                 10.255.31.12          -       100     0       i Or-ID: 10.255.30.12 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 imet 10031 10.255.31.11
                                 -                     -       -       0       i
 * >      RD: 10.255.30.12:20100 imet 10031 10.255.31.12
                                 10.255.31.12          -       100     0       i Or-ID: 10.255.30.12 C-LST: 10.255.30.1 
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.30.11, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2
                                 -                     -       -       0       i
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 192.168.30.10
                                 -                     -       -       0       i
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 2001:db8:30::10
                                 -                     -       -       0       i
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP               Tunnel Type(s)
------------------ --------------
10.255.31.12       flood         

Total number of remote VTEPS:  1
```

## Arista leaf: l2-e
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.30.12, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 imet 10030 10.255.31.11
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.12:20100 imet 10030 10.255.31.12
                                 -                     -       -       0       i
 * >      RD: 10.255.30.11:20100 imet 10031 10.255.31.11
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.12:20100 imet 10031 10.255.31.12
                                 -                     -       -       0       i
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.30.12, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 192.168.30.10
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 2001:db8:30::10
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP               Tunnel Type(s)
------------------ --------------
10.255.31.11       unicast, flood

Total number of remote VTEPS:  1
```

## Arista leaf: bl-e
### show bgp evpn route-type imet
```
BGP routing table information for VRF default
Router identifier 10.255.30.21, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 imet 10030 10.255.31.11
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.12:20100 imet 10030 10.255.31.12
                                 10.255.31.12          -       100     0       i Or-ID: 10.255.30.12 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 imet 10031 10.255.31.11
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.12:20100 imet 10031 10.255.31.12
                                 10.255.31.12          -       100     0       i Or-ID: 10.255.30.12 C-LST: 10.255.30.1 
```

### show bgp evpn route-type mac-ip
```
BGP routing table information for VRF default
Router identifier 10.255.30.21, local AS number 65300
Route status codes: * - valid, > - active, S - Stale, E - ECMP head, e - ECMP
                    c - Contributing to ECMP, % - Pending best path selection
Origin codes: i - IGP, e - EGP, ? - incomplete
AS Path Attributes: Or-ID - Originator ID, C-LST - Cluster List, LL Nexthop - Link Local Nexthop

          Network                Next Hop              Metric  LocPref Weight  Path
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 192.168.30.10
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
 * >      RD: 10.255.30.11:20100 mac-ip 10030 aac1.ab2e.92a2 2001:db8:30::10
                                 10.255.31.11          -       100     0       i Or-ID: 10.255.30.11 C-LST: 10.255.30.1 
```

### show vxlan vtep
```
Remote VTEPS for Vxlan1:

VTEP       Tunnel Type(s)
---------- --------------

Total number of remote VTEPS:  0
```

## FRR RR: rr1
### show bgp ipv4 vpn summary
```
BGP router identifier 10.255.0.1, local AS number 65000 VRF default vrf-id 0
BGP table version 0
RIB entries 3, using 384 bytes of memory
Peers 3, using 50 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.255.0.11     4      65000       127       135       47    0    0 00:08:57            9       17 N/A
10.255.0.13     4      65000       101       126       47    0    0 00:40:03            8       17 N/A
10.255.0.2      4      65000         0         0        0    0    0    never      Connect        0 N/A

Total number of neighbors 3
```

### show bgp ipv6 vpn summary
```
BGP router identifier 10.255.0.1, local AS number 65000 VRF default vrf-id 0
BGP table version 0
RIB entries 3, using 384 bytes of memory
Peers 3, using 50 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.255.0.2      4      65000         0         0        0    0    0    never      Connect        0 N/A
fd00::11        4      65000       106       108       15    0    0 00:41:59            9       17 N/A
fd00::13        4      65000       100       106       15    0    0 00:39:55            8       17 N/A

Total number of neighbors 3
```

## FRR RR: rr2
### show bgp ipv4 vpn summary
```
BGP router identifier 10.255.0.2, local AS number 65000 VRF default vrf-id 0
BGP table version 0
RIB entries 3, using 384 bytes of memory
Peers 3, using 50 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.255.0.11     4      65000       125       133       47    0    0 00:08:57            9       17 N/A
10.255.0.13     4      65000       101       125       47    0    0 00:39:59            8       17 N/A
10.255.0.1      4      65000         0         0        0    0    0    never      Connect        0 N/A

Total number of neighbors 3
```

### show bgp ipv6 vpn summary
```
BGP router identifier 10.255.0.2, local AS number 65000 VRF default vrf-id 0
BGP table version 0
RIB entries 3, using 384 bytes of memory
Peers 3, using 50 KiB of memory
Peer groups 1, using 64 bytes of memory

Neighbor        V         AS   MsgRcvd   MsgSent   TblVer  InQ OutQ  Up/Down State/PfxRcd   PfxSnt Desc
10.255.0.1      4      65000         0         0        0    0    0    never      Connect        0 N/A
fd00::11        4      65000       105       108       15    0    0 00:41:55            9       17 N/A
fd00::13        4      65000        99       106       15    0    0 00:39:52            8       17 N/A

Total number of neighbors 3
```

