# SOP-002: Dynamic Routing and Interface Flapping Precursor
Symptoms: Progressive packet drop rates or hello timeout warnings on OSPF links.

Diagnostics:
- Check OSPF neighbor status: `docker exec clab-gap-moe-transit vtysh -c "show ip ospf neighbor"`

Mitigation Action (OSPF Timer Relaxing):
- Increase OSPF dead interval to 60 seconds on target interface to prevent flap drops:
  `docker exec clab-gap-moe-<NODE> vtysh -c "configure terminal" -c "interface <INTERFACE>" -c "ip ospf dead-interval 60"`

Verification Action:
- Check OSPF convergence: `docker exec clab-gap-moe-transit vtysh -c "show ip ospf neighbor <NEIGHBOR_ID>"`

Rollback Action:
- Revert dead-interval to default (40s):
  `docker exec clab-gap-moe-<NODE> vtysh -c "configure terminal" -c "interface <INTERFACE>" -c "no ip ospf dead-interval"`