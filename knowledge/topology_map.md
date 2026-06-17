# SD-WAN / MPLS Topology Map
The network 'gap-moe' consists of four dynamic nodes utilizing OSPF Area 0:
- Node [hub] (Core Aggregator): Management IP: 10.0.0.1. Interface eth1 connects to transit:eth1. Role: Core terminal for all branch traffic.
- Node [transit] (Core Provider Edge): Interfaces: eth1 (to hub), eth2 (to branch-1), eth3 (to branch-2). Role: Central transit traffic exchange.
- Node [branch-1] (Remote Office 1): Management IP: 10.0.1.2. Interface eth1 connects to transit:eth2. Role: Dynamic OSPF leaf node.
- Node [branch-2] (Remote Office 2): Management IP: 10.0.2.2. Interface eth1 connects to transit:eth3. Role: Dynamic OSPF leaf node.