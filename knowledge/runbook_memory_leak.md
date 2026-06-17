# SOP-003: Core Routing Daemon Memory Exhaustion
Symptoms: Continuous linear growth in memory consumption on transit or routing nodes.

Diagnostics:
- Sort container processes by RSS memory: `docker exec clab-gap-moe-transit ps aux --sort=-rss | head -n 5`
- Show internal FRR memory allocations: `docker exec clab-gap-moe-transit vtysh -c "show memory"`

Mitigation Action (Graceful Failover & Reload):
1. Temporary route cost elevation (forces OSPF path diversion):
   `docker exec clab-gap-moe-transit vtysh -c "configure terminal" -c "interface eth1" -c "ip ospf cost 500"`
2. Restart affected daemons:
   `docker exec clab-gap-moe-transit pkill -HUP ospfd`
   `docker exec clab-gap-moe-transit pkill -HUP zebra`

Rollback Action (Restore normal routing metrics):
   `docker exec clab-gap-moe-transit vtysh -c "configure terminal" -c "interface eth1" -c "no ip ospf cost"`