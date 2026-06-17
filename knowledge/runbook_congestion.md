# SOP-001: Mitigating Core Link Congestion & Bandwidth Saturation
Symptoms: Bandwidth utilization exceeding thresholds on transit interfaces.

Diagnostics:
- Check real-time interface stats: `docker exec clab-gap-moe-transit ip -s link show dev eth1`

Mitigation Action (Egress Rate-Limiting):
- Limit transit-to-hub egress traffic to 1Mbps:
  `docker exec clab-gap-moe-transit tc qdisc add dev eth1 root handle 1: htb default 11`
  `docker exec clab-gap-moe-transit tc class add dev eth1 parent 1: classid 1:11 htb rate 1mbit`

Rollback / Reversion Action:
- Clear egress rate-limiting rules:
  `docker exec clab-gap-moe-transit tc qdisc del dev eth1 root`